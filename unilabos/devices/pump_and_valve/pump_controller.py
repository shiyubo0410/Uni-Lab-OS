# -*- coding: utf-8 -*-
"""
蠕动泵控制器驱动 (Modbus RTU over RS485)

协议来源:
    郑州科威莱电子技术有限公司《RS485 串口步进电机使用手册 V2.3》

协议:
    - 通讯方式: RS-485, Modbus RTU
    - 默认波特率: 9600, 8N1
    - 默认站号: 1
    - 功能码: 0x03 读保持寄存器, 0x06 写单个保持寄存器

寄存器表 (节选, 按手册 2.2):
    0x01 RW  运行方向 (1=正方向仅设, 0=反方向仅设, 3=正转运动, 4=反转运动)
    0x02 RW  运行/暂停 (1=运行, 0=暂停, 不清零行程)
    0x03 W   停止 (写 1 清零已运行圈数/角度/脉冲)
    0x04 RW  速度 (1-800 圈/min)
    0x05 RW  脉冲数 (0-65535, 0=一直转)
    0x06 RW  圈数 (0-65535, 0=一直转)
    0x07 RW  角度 (0-65535, 0=一直转)
    0x08 RW  设备地址 (1-247)
    0x09 RW  脱机使能 (1=使能/释放电机, 0=不使能/锁紧)
    0x0A W   一键回原点
    0x16 R   读取已运行角度 (正=正转方向, 负=反转方向)
    0x17 R   读取限位开关状态 (0=均无, 1=正转触发, 2=反转触发, 3=均触发)
    0x18-0x19 R  读取已运行的 32 位脉冲数
    0x20 W   恢复出厂设置 (写 1)

按手册 3.1 节, 正确的启动顺序:
    1. 设置速度 (写 0x04)
    2. 设置行程 (写 0x05/0x06/0x07 任意一个, 0 = 一直转)
    3. 设置运行方向 (写 0x01 = 1/0 仅设方向)
    4. 发送运行 (写 0x02 = 1)
    步骤 1.2.3 不分先后, 运行结束后参数不变可只发送步骤 4 复用.

注意事项:
    - 任何寄存器写入后 5 秒会自动保存到 EEPROM, 高频反复写会损耗 flash.
    - 故心跳采用 0x03 读功能码 (无副作用), 不能用 0x06 写命令做心跳.
"""

import logging
import struct
import sys
import time
from enum import IntEnum
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import serial
from serial import Serial
from serial.serialutil import SerialException

from unilabos.registry.decorators import action, device, not_action, topic_config


class PeristalticPumpError(Exception):
    """蠕动泵驱动异常基类"""


class PeristalticPumpConnectionError(PeristalticPumpError):
    """连接异常"""


class DirectionValue(IntEnum):
    """寄存器 0x01 的取值 (按手册 2.2)"""

    SET_FORWARD = 0x0001   # 仅设方向 (正), 不启动
    SET_REVERSE = 0x0000   # 仅设方向 (反), 不启动
    RUN_FORWARD = 0x0003   # 设方向并立即正转
    RUN_REVERSE = 0x0004   # 设方向并立即反转


# ---------------------------------------------------------------------------
# 共享 RS485 总线管理: 同一 port 上的多个泵共用一个 Serial 对象 + 一把锁
# ---------------------------------------------------------------------------
_BUS_CACHE: Dict[str, Tuple[Serial, Lock]] = {}
_BUS_CACHE_LOCK = Lock()


def _get_or_open_bus(port: str, baudrate: int, timeout: float) -> Tuple[Serial, Lock]:
    """获取或新建一条 RS485 总线 (Serial + Lock), 同 port 复用"""
    with _BUS_CACHE_LOCK:
        cached = _BUS_CACHE.get(port)
        if cached is not None:
            ser, lock = cached
            if ser.is_open:
                return ser, lock
            try:
                ser.open()
                return ser, lock
            except Exception:
                _BUS_CACHE.pop(port, None)

        ser = Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )
        lock = Lock()
        _BUS_CACHE[port] = (ser, lock)
        return ser, lock


def _close_bus(port: str) -> None:
    with _BUS_CACHE_LOCK:
        cached = _BUS_CACHE.pop(port, None)
    if cached is not None:
        ser, _ = cached
        try:
            if ser.is_open:
                ser.close()
        except Exception:
            pass


def _crc16_modbus(data: bytes) -> bytes:
    """Modbus RTU CRC16 (小端序)"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


# ---------------------------------------------------------------------------
# 驱动主体
# ---------------------------------------------------------------------------
@device(
    id="pump.peristaltic",
    category=["pump"],
    description=(
        "蠕动泵控制器 (RS-485 Modbus RTU, 9600bps 8N1). "
        "支持速度/方向/圈数/脉冲/角度/体积运行, 定时运行通过圈数换算."
    ),
    display_name="蠕动泵",
)
class PeristalticPumpController:
    """
    蠕动泵控制器驱动

    用法 1: 直接打开串口
        p = PeristalticPumpController(port="/dev/ttyUSB0", device_id=1)
        p.start(rpm=120, duration_seconds=60)         # 120rpm 跑 60 秒

    用法 2: 同 port 挂多个泵 (自动共享 Serial + Lock)
        p1 = PeristalticPumpController(port="/dev/ttyUSB0", device_id=1)
        p2 = PeristalticPumpController(port="/dev/ttyUSB0", device_id=2)

    用法 3: 工作站托管模式 (外部注入 Serial)
        p = PeristalticPumpController(port="serial_bus", device_id=1, auto_connect=False)
        p.hardware_interface = shared_serial   # 由工作站注入
    """

    # 寄存器地址常量 (按手册 2.2)
    REG_DIRECTION = 0x0001
    REG_RUN_PAUSE = 0x0002
    REG_STOP = 0x0003
    REG_SPEED = 0x0004
    REG_PULSE_COUNT = 0x0005
    REG_ROTATION_COUNT = 0x0006
    REG_ANGLE = 0x0007
    REG_DEVICE_ADDRESS = 0x0008
    REG_OFFLINE_ENABLE = 0x0009
    REG_HOME = 0x000A
    REG_ACCEL_COEF = 0x000E
    REG_RUN_ANGLE = 0x0016         # 已运行角度 (只读)
    REG_LIMIT_STATUS = 0x0017      # 限位开关状态 (只读)
    REG_RUN_PULSE_HIGH = 0x0018    # 已运行脉冲数高 16 位 (只读)
    REG_RUN_PULSE_LOW = 0x0019     # 已运行脉冲数低 16 位 (只读)
    REG_HOME_SPEED = 0x001A
    REG_FACTORY_RESET = 0x0020

    # 功能码
    FUNC_READ = 0x03
    FUNC_WRITE_SINGLE = 0x06

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        device_id: int = 1,
        timeout: float = 0.5,
        ml_per_rotation: float = 1.0,
        response_delay: float = 0.1,
        auto_connect: bool = True,
    ):
        """
        :param port: 串口号 (Windows: COMx, Linux: /dev/ttyUSBx)
        :param baudrate: 波特率, 默认 9600
        :param device_id: Modbus 站号 (1-247)
        :param timeout: 串口读超时 (秒)
        :param ml_per_rotation: 每圈泵送体积 (mL/圈), 用于 run_with_volume 换算, 与泵管型号有关
        :param response_delay: 发送后等待响应的延迟 (秒), 默认 0.1s
        :param auto_connect: 是否在 __init__ 时自动打开串口
        """
        self.port = port
        self.baudrate = int(baudrate)
        self.device_id = int(device_id)
        self.timeout = float(timeout)
        self.ml_per_rotation = float(ml_per_rotation)
        self.response_delay = float(response_delay)

        self.logger = logging.getLogger(f"PeristalticPump[{device_id}@{port}]")

        # 串口对象 + 锁 (默认在 _do_connect 中通过总线缓存获取)
        self._serial: Optional[Serial] = None
        self._lock: Lock = Lock()
        self._is_connected = False

        # 软件缓存
        self._status: str = "Idle"       # Idle / Running / Paused / Error
        self._direction_set: int = 0x0001  # 上次设置的方向 (0x01=正, 0x00=反)
        self._current_speed: int = 0
        self._last_error: str = ""

        # hardware_interface 健康检查约定 (与 xkc_y28 / youling_motor 一致)
        self.hardware_interface: Any = port

        if auto_connect:
            try:
                self._do_connect()
            except Exception as exc:
                self.logger.warning(f"自动连接失败: {exc}")

    # ============================================================
    # 连接管理
    # ============================================================
    @not_action
    def _do_connect(self) -> bool:
        if self._is_connected and self._serial and self._serial.is_open:
            return True
        try:
            ser, lock = _get_or_open_bus(self.port, self.baudrate, self.timeout)
            self._serial = ser
            self._lock = lock
            self._is_connected = ser.is_open
            if self._is_connected:
                self.hardware_interface = ser
                self.logger.info(
                    f"已连接 {self.port} @ {self.baudrate}bps (站号 {self.device_id})"
                )
            return self._is_connected
        except (OSError, SerialException) as exc:
            self._last_error = f"connect: {exc}"
            self.logger.error(self._last_error)
            self._is_connected = False
            self.hardware_interface = self.port
            return False

    @not_action
    def _disconnect(self) -> None:
        self._is_connected = False
        self.hardware_interface = self.port

    # ============================================================
    # Modbus RTU 帧构建 / 收发
    # ============================================================
    @not_action
    def _build_write_single(self, reg_addr: int, value: int) -> bytes:
        """构建 0x06 写单个寄存器命令"""
        payload = struct.pack(
            ">BBHH",
            self.device_id,
            self.FUNC_WRITE_SINGLE,
            reg_addr,
            value & 0xFFFF,
        )
        return payload + _crc16_modbus(payload)

    @not_action
    def _build_read(self, reg_addr: int, count: int = 1) -> bytes:
        """构建 0x03 读保持寄存器命令"""
        payload = struct.pack(
            ">BBHH",
            self.device_id,
            self.FUNC_READ,
            reg_addr,
            count & 0xFFFF,
        )
        return payload + _crc16_modbus(payload)

    @not_action
    def _send_recv(self, frame: bytes, expected_len: int) -> Optional[bytes]:
        """
        发送 Modbus 命令并读取指定长度的响应.

        - 0x06 写命令响应 = 整条 echo (8 字节)
        - 0x03 读命令响应 = addr(1) + 0x03(1) + 字节数(1) + 数据(2*n) + CRC(2)
        - 异常码响应 = addr(1) + (功能码|0x80)(1) + 错误码(1) + CRC(2) = 5 字节

        I/O 异常会抛出, 让 DeviceWorker 感知错误并触发重连/掉线逻辑.
        """
        ser: Optional[Serial] = (
            self.hardware_interface
            if hasattr(self.hardware_interface, "write")
            else self._serial
        )
        if ser is None or not getattr(ser, "is_open", False):
            if not self._do_connect():
                return None
            ser = self._serial

        with self._lock:
            try:
                if hasattr(ser, "reset_input_buffer"):
                    ser.reset_input_buffer()
                ser.write(frame)
                if self.response_delay > 0:
                    time.sleep(self.response_delay)
                response = ser.read(expected_len)
                # 兼容设备先回异常码 (5 字节) 后断流的情况: 若实际读到的比期望短,
                # 先看是不是合法的异常码响应
                if len(response) < expected_len and len(response) >= 5:
                    pass  # 走下面的异常码分支
            except (OSError, SerialException) as exc:
                self._last_error = f"io: {exc}"
                self.logger.error(self._last_error)
                self._is_connected = False
                self.hardware_interface = self.port
                raise

        if not response:
            self._last_error = (
                f"no_response addr={self.device_id} reg=0x{frame[2]:02X}{frame[3]:02X}"
            )
            self.logger.warning(self._last_error)
            return None

        # 异常码响应
        if len(response) >= 2 and (response[1] & 0x80):
            if len(response) >= 5 and response[-2:] == _crc16_modbus(response[:-2]):
                err = response[2]
                self._last_error = f"modbus_error: 0x{err:02X}"
                self.logger.warning(f"设备返回 Modbus 错误码 0x{err:02X}")
            else:
                self._last_error = f"bad_exception_frame: {response.hex()}"
            return None

        if len(response) < expected_len:
            self._last_error = (
                f"short_response: got {len(response)}/{expected_len} bytes"
            )
            self.logger.warning(self._last_error)
            return None

        if response[-2:] != _crc16_modbus(response[:-2]):
            self._last_error = f"crc_error: {response.hex()}"
            self.logger.warning(self._last_error)
            return None

        return response

    @not_action
    def write_single_register(self, reg_addr: int, value: int) -> bool:
        """写单个寄存器 (0x06), 验证 echo, 返回是否成功"""
        frame = self._build_write_single(reg_addr, value & 0xFFFF)
        response = self._send_recv(frame, expected_len=8)
        if response is None:
            return False
        if response != frame:
            self._last_error = (
                f"echo_mismatch: sent={frame.hex()}, recv={response.hex()}"
            )
            self.logger.warning(self._last_error)
            return False
        self.logger.debug(
            f"WRITE reg=0x{reg_addr:04X} value=0x{value & 0xFFFF:04X} OK"
        )
        return True

    @not_action
    def read_registers(self, reg_addr: int, count: int = 1) -> Optional[List[int]]:
        """读 N 个连续寄存器 (0x03), 返回无符号 16 位整数列表"""
        # 响应长度: addr(1) + func(1) + byte_count(1) + 2*count + crc(2)
        frame = self._build_read(reg_addr, count)
        resp = self._send_recv(frame, expected_len=5 + 2 * count)
        if resp is None:
            return None
        # resp[2] = byte_count, 应该 == 2 * count
        regs: List[int] = []
        for i in range(count):
            regs.append(struct.unpack(">H", resp[3 + 2 * i : 5 + 2 * i])[0])
        self.logger.debug(f"READ reg=0x{reg_addr:04X} count={count} -> {regs}")
        return regs

    # ============================================================
    # 1. 方向控制 (仅设方向, 不启动)
    # ============================================================
    @action(description="设置电机转向 (仅设方向, 不启动). FORWARD=正向出液, REVERSE=反向吸液")
    def set_direction(self, direction: str = "FORWARD") -> Dict[str, Any]:
        """
        手册 0x01 寄存器: 写 1=正方向, 写 0=反方向, **不启动运行**
        """
        d = str(direction).upper().strip()
        if d in ("REVERSE", "反转", "反向", "BACKWARD"):
            val = DirectionValue.SET_REVERSE.value
            name = "反向(吸液)"
        else:
            val = DirectionValue.SET_FORWARD.value
            name = "正向(出液)"

        ok = self.write_single_register(self.REG_DIRECTION, val)
        if ok:
            self._direction_set = val
        return {
            "success": ok,
            "direction": "REVERSE" if val == 0 else "FORWARD",
            "message": f"方向设置为 {name} (不启动)" if ok else f"方向设置失败: {self._last_error}",
        }

    # ============================================================
    # 2. 参数设置
    # ============================================================
    @action(description="设置电机运行速度 (1-800 圈/min)")
    def set_speed(self, rpm: int = 60) -> Dict[str, Any]:
        speed = max(1, min(800, int(rpm)))
        ok = self.write_single_register(self.REG_SPEED, speed)
        if ok:
            self._current_speed = speed
        return {
            "success": ok,
            "speed_rpm": speed,
            "message": f"速度设置为 {speed} rpm" if ok else f"速度设置失败: {self._last_error}",
        }

    @action(description="设置脉冲数行程 (0-65535, 0=一直转直到 stop)")
    def set_pulse_count(self, pulse_count: int = 1600) -> Dict[str, Any]:
        pulses = max(0, min(65535, int(pulse_count)))
        ok = self.write_single_register(self.REG_PULSE_COUNT, pulses)
        return {
            "success": ok,
            "pulse_count": pulses,
            "message": (
                f"脉冲数设置为 {pulses}" + (" (一直转)" if pulses == 0 else "")
            ) if ok else f"失败: {self._last_error}",
        }

    @action(description="设置运行圈数 (0-65535, 0=一直转直到 stop)")
    def set_rotation_count(self, rounds: int = 1) -> Dict[str, Any]:
        rounds = max(0, min(65535, int(rounds)))
        ok = self.write_single_register(self.REG_ROTATION_COUNT, rounds)
        return {
            "success": ok,
            "rounds": rounds,
            "message": (
                f"圈数设置为 {rounds}" + (" (一直转)" if rounds == 0 else "")
            ) if ok else f"失败: {self._last_error}",
        }

    @action(description="设置旋转角度 (度, 0-65535, 0=一直转)")
    def set_angle(self, degrees: float = 360) -> Dict[str, Any]:
        deg = max(0, min(65535, int(round(float(degrees)))))
        ok = self.write_single_register(self.REG_ANGLE, deg)
        return {
            "success": ok,
            "angle_deg": deg,
            "message": (
                f"角度设置为 {deg}°" + (" (一直转)" if deg == 0 else "")
            ) if ok else f"失败: {self._last_error}",
        }

    @action(description="设置加减速系数 (0-10, 0=不开启加减速, 越大加速越快)")
    def set_accel_coefficient(self, coef: int = 0) -> Dict[str, Any]:
        c = max(0, min(10, int(coef)))
        ok = self.write_single_register(self.REG_ACCEL_COEF, c)
        return {
            "success": ok,
            "coef": c,
            "message": f"加减速系数={c}" if ok else f"失败: {self._last_error}",
        }

    # ============================================================
    # 3. 运行控制 (按手册 3.1: 速度 -> 行程 -> 方向 -> 运行)
    # ============================================================
    @action(description=(
        "启动蠕动泵. 按手册顺序设速度/行程/方向, 再发运行. "
        "duration_seconds>0 时按时长换算圈数 (rounds = rpm/60 * duration_s); "
        "duration_seconds=0 时持续运行直到 stop()."
    ))
    def start(
        self,
        rpm: int = 60,
        duration_seconds: float = 0.0,
        direction: str = "FORWARD",
    ) -> Dict[str, Any]:
        """
        :param rpm: 运行速度 rpm (1-800)
        :param duration_seconds: 运行时长秒 (>0 自动换算圈数, =0 持续运行)
        :param direction: "FORWARD" / "REVERSE"
        """
        rpm = int(rpm)
        duration_seconds = float(duration_seconds)

        if rpm <= 0:
            return {"success": False, "message": f"rpm 必须 > 0, 当前 {rpm}"}

        # 1. 速度
        spd_res = self.set_speed(rpm)
        if not spd_res["success"]:
            return {"success": False, "message": f"速度设置失败: {self._last_error}"}

        # 2. 行程 (圈数)
        if duration_seconds > 0:
            rounds = (rpm / 60.0) * duration_seconds
            rounds_int = max(1, round(rounds))
        else:
            rounds_int = 0    # 0 = 一直转
        r_res = self.set_rotation_count(rounds_int)
        if not r_res["success"]:
            return {"success": False, "message": f"圈数设置失败: {self._last_error}"}

        # 3. 方向 (仅设方向, 不启动)
        dir_res = self.set_direction(direction)
        if not dir_res["success"]:
            return {"success": False, "message": f"方向设置失败: {self._last_error}"}

        # 4. 启动 (写 0x02 = 1)
        ok = self.write_single_register(self.REG_RUN_PAUSE, 0x0001)
        if ok:
            self._status = "Running"
        return {
            "success": ok,
            "speed_rpm": self._current_speed,
            "direction": dir_res["direction"],
            "duration_seconds": duration_seconds,
            "rounds": rounds_int,
            "message": (
                f"已启动: {dir_res['direction']}, {self._current_speed} rpm, "
                + (f"{duration_seconds}s≈{rounds_int}圈" if duration_seconds > 0 else "持续运行")
            ) if ok else f"启动失败: {self._last_error}",
        }

    @action(description="正转启动 (持续运行, 按上次速度/直接 rpm 参数)")
    def forward(self, rpm: int = 0, duration_seconds: float = 0.0) -> Dict[str, Any]:
        """
        :param rpm: 速度 rpm (0 = 沿用上次设置的速度)
        :param duration_seconds: 时长 (0 = 持续运行)
        """
        if rpm > 0:
            return self.start(rpm=rpm, duration_seconds=duration_seconds, direction="FORWARD")
        elif self._current_speed > 0:
            return self.start(
                rpm=self._current_speed,
                duration_seconds=duration_seconds,
                direction="FORWARD",
            )
        else:
            return {
                "success": False,
                "message": "未指定 rpm 且当前速度为 0, 请提供 rpm 参数或先 set_speed",
            }

    @action(description="反转启动 (持续运行, 按上次速度/直接 rpm 参数)")
    def reverse(self, rpm: int = 0, duration_seconds: float = 0.0) -> Dict[str, Any]:
        """
        :param rpm: 速度 rpm (0 = 沿用上次设置的速度)
        :param duration_seconds: 时长 (0 = 持续运行)
        """
        if rpm > 0:
            return self.start(rpm=rpm, duration_seconds=duration_seconds, direction="REVERSE")
        elif self._current_speed > 0:
            return self.start(
                rpm=self._current_speed,
                duration_seconds=duration_seconds,
                direction="REVERSE",
            )
        else:
            return {
                "success": False,
                "message": "未指定 rpm 且当前速度为 0, 请提供 rpm 参数或先 set_speed",
            }

    @action(description="停止运行并清零已运行行程 (写 0x03=1, 手册推荐的停止方式)")
    def stop(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_STOP, 0x0001)
        if ok:
            self._status = "Idle"
        return {
            "success": ok,
            "message": "已停止 (行程清零)" if ok else f"停止失败: {self._last_error}",
        }

    @action(description="暂停 (写 0x02=0, 保留行程, 再次 start 从中断处继续)")
    def pause(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_RUN_PAUSE, 0x0000)
        if ok:
            self._status = "Paused"
        return {
            "success": ok,
            "message": "已暂停 (行程保留)" if ok else f"暂停失败: {self._last_error}",
        }

    @action(description="恢复运行 (从 pause 暂停状态恢复, 写 0x02=1)")
    def resume(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_RUN_PAUSE, 0x0001)
        if ok:
            self._status = "Running"
        return {
            "success": ok,
            "message": "已恢复运行" if ok else f"恢复失败: {self._last_error}",
        }

    # ============================================================
    # 4. 脱机使能
    # ============================================================
    @action(description="打开脱机使能 (释放电机, 不保持力矩, 可手动转动, 写 0x09=1)")
    def enable_offline_mode(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_OFFLINE_ENABLE, 0x0001)
        return {
            "success": ok,
            "message": "脱机使能已打开 (电机释放)" if ok else f"失败: {self._last_error}",
        }

    @action(description="关闭脱机使能 (电机保持力矩, 锁紧位置, 写 0x09=0)")
    def disable_offline_mode(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_OFFLINE_ENABLE, 0x0000)
        return {
            "success": ok,
            "message": "脱机使能已关闭 (电机锁紧)" if ok else f"失败: {self._last_error}",
        }

    # ============================================================
    # 5. 回原点 / 设备参数
    # ============================================================
    @action(description="一键回原点 (写 0x0A, 根据正反行程差距自动计算回原方向)")
    def home(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_HOME, 0x0001)
        return {
            "success": ok,
            "message": "已发送回原点指令" if ok else f"失败: {self._last_error}",
        }

    @action(description="设置当前位置为原点 (写 0x15=1)")
    def set_current_as_home(self) -> Dict[str, Any]:
        ok = self.write_single_register(0x0015, 0x0001)
        return {
            "success": ok,
            "message": "已设置当前位置为原点" if ok else f"失败: {self._last_error}",
        }

    @action(description="修改 Modbus 站号 (1-247, 写 0x08). 设置后通信地址自动切换")
    def set_address(self, new_address: int = 1) -> Dict[str, Any]:
        addr = int(new_address)
        if not 1 <= addr <= 247:
            return {"success": False, "message": f"站号超出范围: {addr} (1-247)"}
        ok = self.write_single_register(self.REG_DEVICE_ADDRESS, addr)
        if ok:
            self.device_id = addr
            self.logger.info(f"站号已修改为 {addr}")
        return {
            "success": ok,
            "new_address": addr,
            "message": f"站号修改{'成功' if ok else '失败'}",
        }

    # ============================================================
    # 6. 高级功能
    # ============================================================
    @action(description=(
        "按体积运行 (mL). 根据 ml_per_rotation 自动换算圈数, "
        "需提前确认每圈泵送体积与泵管匹配."
    ))
    def run_with_volume(
        self,
        volume_ml: float = 10.0,
        rpm: int = 60,
        direction: str = "FORWARD",
        ml_per_rotation: float = 0.0,
    ) -> Dict[str, Any]:
        """
        :param volume_ml: 目标泵送体积 (mL)
        :param rpm: 运行速度 rpm
        :param direction: "FORWARD" / "REVERSE"
        :param ml_per_rotation: 每圈体积 (mL/圈), 0 表示沿用 self.ml_per_rotation
        """
        volume_ml = float(volume_ml)
        rpm = int(rpm)
        ml_per_rot = float(ml_per_rotation) if ml_per_rotation > 0 else self.ml_per_rotation

        if volume_ml <= 0 or rpm <= 0 or ml_per_rot <= 0:
            return {
                "success": False,
                "message": (
                    f"参数非法: volume_ml={volume_ml}, rpm={rpm}, "
                    f"ml_per_rotation={ml_per_rot}"
                ),
            }

        rounds = max(1, round(volume_ml / ml_per_rot))
        # 按手册顺序: 速度 -> 圈数 -> 方向 -> 运行
        spd = self.set_speed(rpm)
        if not spd["success"]:
            return {"success": False, "message": f"速度设置失败: {self._last_error}"}
        r = self.set_rotation_count(rounds)
        if not r["success"]:
            return {"success": False, "message": f"圈数设置失败: {self._last_error}"}
        d = self.set_direction(direction)
        if not d["success"]:
            return {"success": False, "message": f"方向设置失败: {self._last_error}"}
        ok = self.write_single_register(self.REG_RUN_PAUSE, 0x0001)
        if ok:
            self._status = "Running"
        return {
            "success": ok,
            "volume_ml": volume_ml,
            "rpm": rpm,
            "direction": d["direction"],
            "ml_per_rotation": ml_per_rot,
            "rounds": rounds,
            "message": (
                f"按体积运行: 目标 {volume_ml}mL, {rpm}rpm, "
                f"{rounds} 圈 ({ml_per_rot}mL/圈)"
            ) if ok else f"启动失败: {self._last_error}",
        }

    @action(description="读取一次综合状态 (运行状态 + 速度 + 圈数 + 方向, 用 0x03 读功能码)")
    def read_status(self) -> Dict[str, Any]:
        # 一次读 0x01-0x07 共 7 个寄存器
        regs = self.read_registers(self.REG_DIRECTION, 7)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        direction_val = regs[0]
        run_pause = regs[1]
        # regs[2] 是 0x03 寄存器 (停止), 一般是 0
        speed = regs[3]
        pulse = regs[4]
        rounds = regs[5]
        angle = regs[6]

        running = run_pause == 0x0001
        if direction_val == 0x0001:
            dir_name = "FORWARD"
        elif direction_val == 0x0000:
            dir_name = "REVERSE"
        elif direction_val == 0x0003:
            dir_name = "FORWARD_RUN"
        elif direction_val == 0x0004:
            dir_name = "REVERSE_RUN"
        else:
            dir_name = f"UNKNOWN(0x{direction_val:04X})"

        # 用真实状态更新缓存
        self._status = "Running" if running else self._status
        self._current_speed = speed

        return {
            "success": True,
            "running": running,
            "status": self._status,
            "direction_raw": direction_val,
            "direction": dir_name,
            "speed_rpm": speed,
            "pulse_count": pulse,
            "rounds": rounds,
            "angle_deg": angle,
            "message": (
                f"running={running}, dir={dir_name}, speed={speed}rpm, "
                f"pulse={pulse}, rounds={rounds}, angle={angle}°"
            ),
        }

    @action(description="读取已运行的角度 (正=正转, 负=反转, 相对原点位置)")
    def read_run_angle(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_RUN_ANGLE, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        raw = regs[0]
        signed = raw - 0x10000 if raw >= 0x8000 else raw
        return {"success": True, "angle_deg": signed}

    @action(description="读取限位开关状态 (0=均无, 1=正转触发, 2=反转触发, 3=均触发)")
    def read_limit_status(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_LIMIT_STATUS, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        names = {0: "均无触发", 1: "正转限位触发", 2: "反转限位触发", 3: "正反限位均触发"}
        v = regs[0]
        return {"success": True, "code": v, "message": names.get(v, f"unknown({v})")}

    # ============================================================
    # 7. 连接 / 断开
    # ============================================================
    @action(description="打开串口连接")
    def connect(self) -> Dict[str, Any]:
        ok = self._do_connect()
        return {
            "success": ok,
            "port": self.port,
            "baudrate": self.baudrate,
            "device_id": self.device_id,
            "message": "连接成功" if ok else f"连接失败: {self._last_error}",
        }

    @action(description="关闭串口连接 (同 port 的其他泵会一起断开)")
    def disconnect(self) -> Dict[str, Any]:
        _close_bus(self.port)
        self._disconnect()
        return {"success": True, "message": "串口已关闭"}

    # ============================================================
    # 8. 心跳 (用 0x03 读功能码, 无副作用; 同时拿到真实运行状态)
    # ============================================================
    @not_action
    def _heartbeat_and_refresh(self) -> bool:
        """
        发送 0x03 读 0x02 (运行/暂停状态) 寄存器.
        - 完全无副作用 (不写 EEPROM)
        - 同时拿到真实运行状态, 更新 _status 缓存
        - 读失败时抛异常, 让 DeviceWorker 计数错误并触发掉线
        """
        regs = self.read_registers(self.REG_RUN_PAUSE, 1)
        if regs is None:
            raise RuntimeError(f"心跳失败: {self._last_error or 'no_response'}")
        # 0x02 寄存器: 1=运行, 0=暂停 (但停止后也是 0)
        # 这里只在 "Paused" 时不动状态; Running/Idle 由 start/stop 设置
        run_pause = regs[0]
        if run_pause == 0x0001:
            self._status = "Running"
        elif self._status == "Running":
            # 之前是 Running, 现在 0x02=0 说明行程走完自动停了
            self._status = "Idle"
        return True

    # ============================================================
    # 状态属性 (telemetry 定时广播)
    # ============================================================
    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=3.0)
    def status(self) -> str:
        """
        运行状态 (Idle / Running / Paused / Error).
        通过 0x03 读 0x02 寄存器验证设备在线并刷新真实状态.
        """
        try:
            self._heartbeat_and_refresh()
        except Exception:
            self._status = "Error"
            raise
        return self._status

    @property
    @topic_config(period=5.0)
    def current_speed_rpm(self) -> int:
        """当前设置的转速 (软件缓存, rpm)"""
        return int(self._current_speed)

    @property
    @topic_config(period=10.0)
    def direction(self) -> str:
        """当前方向 (软件缓存)"""
        return "REVERSE" if self._direction_set == 0x0000 else "FORWARD"

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


# ---------------------------------------------------------------------------
# 独立运行: 命令行测试 + probe 命令字节串打印
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="蠕动泵控制器驱动测试")
    parser.add_argument("--port", default="COM7", help="串口号")
    parser.add_argument("--baudrate", type=int, default=9600, help="波特率")
    parser.add_argument("--address", type=int, default=1, help="Modbus 站号, 默认 1")
    parser.add_argument("--rpm", type=int, default=60, help="测试转速 rpm")
    parser.add_argument("--duration", type=float, default=5.0, help="运行时长(秒)")
    parser.add_argument("--smoke", action="store_true", help="冒烟测试: 只发心跳读, 不让泵动")
    parser.add_argument(
        "--probe-bytes",
        action="store_true",
        help="打印 fingerprints.yaml 用的 probe 命令字节串 (含 CRC)",
    )
    args = parser.parse_args()

    if args.probe_bytes:
        cases = [
            ("write 0x0009=0 (脱机使能=0 echo)", struct.pack(">BBHH", 1, 0x06, 0x0009, 0x0000)),
            ("read 0x0007 (角度寄存器)", struct.pack(">BBHH", 1, 0x03, 0x0007, 0x0001)),
            ("read 0x0002 (运行状态, 心跳用)", struct.pack(">BBHH", 1, 0x03, 0x0002, 0x0001)),
        ]
        for name, frame in cases:
            full = frame + _crc16_modbus(frame)
            esc = "".join(f"\\x{b:02x}" for b in full)
            print(f"# {name}:")
            print(f'  send: "{esc}"')
            print(f"  hex: {full.hex(' ').upper()}")
            print()
        sys.exit(0)

    try:
        pump = PeristalticPumpController(
            port=args.port,
            baudrate=args.baudrate,
            device_id=args.address,
            auto_connect=True,
        )
        if not pump._is_connected:
            print(f"✗ 连接失败: {pump._last_error}")
            sys.exit(1)

        print(f"✓ 已连接到 {args.port} 站号 {args.address}")

        # 1. 心跳读取
        print("\n[1/4] 心跳读取 (0x03 读 0x02)")
        try:
            pump._heartbeat_and_refresh()
            print(f"  ✓ 心跳成功, 当前状态: {pump._status}")
        except Exception as exc:
            print(f"  ✗ 心跳失败: {exc}")
            sys.exit(1)

        # 2. 综合状态读取
        print("\n[2/4] 综合状态读取 (read_status)")
        res = pump.read_status()
        print(f"  {res}")

        if args.smoke:
            print("\n[smoke] 冒烟测试完成 (--smoke 不运行电机)")
            sys.exit(0)

        # 3. 启动测试
        print(f"\n[3/4] 启动测试 ({args.rpm} rpm, {args.duration}s, 正转)")
        res = pump.start(rpm=args.rpm, duration_seconds=args.duration, direction="FORWARD")
        print(f"  {res}")

        # 边运行边读状态
        for i in range(int(args.duration) + 2):
            time.sleep(1)
            s = pump.read_status()
            print(f"  t={i+1}s status={s.get('running')} speed={s.get('speed_rpm')} rounds_left={s.get('rounds')}")

        # 4. 停止
        print("\n[4/4] stop (清零)")
        res = pump.stop()
        print(f"  {res}")

        pump.disconnect()

    except KeyboardInterrupt:
        print("\n用户中断")
    except PeristalticPumpError as exc:
        print(f"驱动错误: {exc}")

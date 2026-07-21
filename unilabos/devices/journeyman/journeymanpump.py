# -*- coding: utf-8 -*-
"""
简美 JourneyMan 蠕动泵驱动 (M 型 / L 型基本型系列, RS-485 Modbus RTU)

协议来源:
    《JourneyMan 简美 外控模块 (M型/L型 基本型系列蠕动泵) 产品手册》第 6 节「通讯」

协议:
    - 通讯方式: RS-485, 标准 Modbus RTU
    - 默认参数: 9600 bps, 8 数据位, **偶校验 (E)**, 1 停止位  → 8E1
      (注意: 与常见的 8N1 不同, 必须用偶校验, 否则收发全乱码)
    - 默认站号: 1, 广播地址 0xFF
    - 功能码: 0x03 读保持寄存器, 0x06 写单个保持寄存器

寄存器点表 (手册 6.3, 地址为十六进制):
    0x0000 RW 转速        取值 0~最高转速, 系数 0.1RPM (寄存器值 = RPM × 10)
    0x0001 RW 转向        0=顺时针 (CW), 1=逆时针 (CCW)
    0x0002 RW 运行状态    0=停止, 1=运行
    0x0003 RW 通讯地址    1-254, 255=广播
    0x000C    通讯速率    保留
    0x000D RW 脚踏控制方式 0=脉冲式, 1=电平式

通讯示例 (手册 6.4, 已验证 CRC):
    停止:          01 06 00 02 00 00 28 0A
    启动:          01 06 00 02 00 01 E9 CA
    设转速 120RPM: 01 06 00 00 04 B0 8A BE   (1200 = 0x04B0, ×0.1 = 120 RPM)

对外单位约定:
    - 速度对外用 RPM (与寄存器 0.1RPM 系数的换算在驱动内部完成)。
    - 方向对外用 FORWARD / REVERSE (FORWARD=顺时针出液, REVERSE=逆时针吸液),
      同时兼容 CW / CCW 写法, 与同类蠕动泵驱动参数名保持一致。
"""

import logging
import struct
import sys
import time
from threading import Lock, Timer
from typing import Any, Dict, List, Optional, Tuple

import serial
from serial import Serial
from serial.serialutil import SerialException

from unilabos.registry.decorators import action, device, not_action, topic_config


class JourneymanPumpError(Exception):
    """简美蠕动泵驱动异常基类"""


# ---------------------------------------------------------------------------
# 共享 RS-485 总线管理: 同一 port 上的多个泵共用一个 Serial 对象 + 一把锁,
# 避免多 worker 抢占串口造成总线串扰 (与项目内其它 RS-485 驱动一致)。
# ---------------------------------------------------------------------------
_BUS_CACHE: Dict[str, Tuple[Serial, Lock]] = {}
_BUS_CACHE_LOCK = Lock()


def _get_or_open_bus(port: str, baudrate: int, timeout: float) -> Tuple[Serial, Lock]:
    """获取或新建一条 RS-485 总线 (Serial + Lock), 同 port 复用。8E1 偶校验。"""
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
            parity=serial.PARITY_EVEN,   # 简美手册: 偶校验
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
    """Modbus RTU CRC16 (小端序追加)。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


@device(
    id="journeyman_peristaltic_pump",
    category=["pump"],
    description=(
        "简美 JourneyMan 蠕动泵 (M/L 型基本型系列, RS-485 Modbus RTU, 9600 8E1). "
        "支持转速/转向/启停控制, 转速系数 0.1RPM。"
    ),
    displayname="简美蠕动泵 (JourneyMan)",
)
class JourneymanPump:
    """
    简美 JourneyMan 蠕动泵驱动。

    用法 1: 直接打开串口
        p = JourneymanPump(port="/dev/ttyUSB0", device_id=1)
        p.start(rpm=120, direction="FORWARD")   # 120rpm 正转
        p.stop()

    用法 2: 同 port 挂多个泵 (自动共享 Serial + Lock)
        p1 = JourneymanPump(port="/dev/ttyUSB0", device_id=1)
        p2 = JourneymanPump(port="/dev/ttyUSB0", device_id=2)
    """

    # 寄存器地址常量 (手册 6.3)
    REG_SPEED = 0x0000          # 转速, 系数 0.1RPM (寄存器值 = RPM × 10)
    REG_DIRECTION = 0x0001      # 转向: 0=顺时针(CW), 1=逆时针(CCW)
    REG_RUN = 0x0002            # 运行状态: 0=停止, 1=运行
    REG_ADDRESS = 0x0003        # 通讯地址: 1-254
    REG_BAUD = 0x000C           # 通讯速率 (保留)
    REG_PEDAL_MODE = 0x000D     # 脚踏控制方式: 0=脉冲式, 1=电平式

    # 转速系数: 寄存器值 = RPM / SPEED_SCALE
    SPEED_SCALE = 0.1

    # 功能码
    FUNC_READ = 0x03
    FUNC_WRITE_SINGLE = 0x06

    # 方向取值
    DIR_CW = 0x0000   # 顺时针 (正转/出液)
    DIR_CCW = 0x0001  # 逆时针 (反转/吸液)

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        device_id: int = 1,
        timeout: float = 0.5,
        max_rpm: int = 600,
        response_delay: float = 0.1,
        auto_connect: bool = True,
    ):
        """
        初始化简美蠕动泵。

        Args:
            port[串口]: 串口号 (Windows: COMx, Linux: /dev/ttyUSBx)。
            baudrate[波特率]: 串口波特率, 手册默认 9600。
            device_id[站号]: Modbus 站号 (1-254), 默认 1。
            timeout[超时(s)]: 串口读超时, 单位秒。
            max_rpm[最高转速(RPM)]: 转速上限, 用于 set_speed 限幅, L600 默认 600。
            response_delay[响应延迟(s)]: 发送后等待响应的延迟, 单位秒。
            auto_connect[自动连接]: 是否在初始化时自动打开串口。
        """
        self.port = port
        self.baudrate = int(baudrate)
        self.device_id = int(device_id)
        self.timeout = float(timeout)
        self.max_rpm = int(max_rpm)
        self.response_delay = float(response_delay)

        self.logger = logging.getLogger(f"JourneymanPump[{device_id}@{port}]")

        self._serial: Optional[Serial] = None
        self._lock: Lock = Lock()
        self._is_connected = False

        # 软件缓存
        self._status: str = "Idle"        # Idle / Running / Error
        self._current_speed: int = 0       # RPM
        self._direction: int = self.DIR_CW
        self._last_error: str = ""

        # 定时运行: 本泵硬件无圈数/定时寄存器, 只能软件定时——start(duration_seconds>0)
        # 时起一个后台 Timer, 到点自动 stop(); stop()/新的 start() 会取消未触发的旧定时器。
        self._stop_timer: Optional[Timer] = None

        # hardware_interface 健康检查约定 (与项目内其它 RS-485 驱动一致)
        self.hardware_interface: Any = port

        if auto_connect:
            try:
                self._do_connect()
            except Exception as exc:  # noqa: BLE001
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
                    f"已连接 {self.port} @ {self.baudrate}bps 8E1 (站号 {self.device_id})"
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
        payload = struct.pack(
            ">BBHH", self.device_id, self.FUNC_WRITE_SINGLE, reg_addr, value & 0xFFFF
        )
        return payload + _crc16_modbus(payload)

    @not_action
    def _build_read(self, reg_addr: int, count: int = 1) -> bytes:
        payload = struct.pack(
            ">BBHH", self.device_id, self.FUNC_READ, reg_addr, count & 0xFFFF
        )
        return payload + _crc16_modbus(payload)

    @not_action
    def _send_recv(self, frame: bytes, expected_len: int) -> Optional[bytes]:
        """
        发送 Modbus 命令并读取定长响应, 校验 CRC。

        - 0x06 写命令响应 = 整条 echo (8 字节)
        - 0x03 读命令响应 = addr(1)+0x03(1)+字节数(1)+数据(2*n)+CRC(2)
        - 异常码响应 = addr(1)+(功能码|0x80)(1)+错误码(1)+CRC(2) = 5 字节

        I/O 异常会抛出, 让 DeviceWorker 感知错误并触发重连/掉线。
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
            self._last_error = f"short_response: got {len(response)}/{expected_len} bytes"
            self.logger.warning(self._last_error)
            return None

        if response[-2:] != _crc16_modbus(response[:-2]):
            self._last_error = f"crc_error: {response.hex()}"
            self.logger.warning(self._last_error)
            return None

        return response

    @not_action
    def write_single_register(self, reg_addr: int, value: int) -> bool:
        """写单个寄存器 (0x06), 验证 echo。"""
        frame = self._build_write_single(reg_addr, value & 0xFFFF)
        response = self._send_recv(frame, expected_len=8)
        if response is None:
            return False
        if response != frame:
            self._last_error = f"echo_mismatch: sent={frame.hex()}, recv={response.hex()}"
            self.logger.warning(self._last_error)
            return False
        self.logger.debug(f"WRITE reg=0x{reg_addr:04X} value=0x{value & 0xFFFF:04X} OK")
        return True

    @not_action
    def read_registers(self, reg_addr: int, count: int = 1) -> Optional[List[int]]:
        """读 N 个连续寄存器 (0x03), 返回无符号 16 位整数列表。"""
        frame = self._build_read(reg_addr, count)
        resp = self._send_recv(frame, expected_len=5 + 2 * count)
        if resp is None:
            return None
        regs: List[int] = []
        for i in range(count):
            regs.append(struct.unpack(">H", resp[3 + 2 * i : 5 + 2 * i])[0])
        self.logger.debug(f"READ reg=0x{reg_addr:04X} count={count} -> {regs}")
        return regs

    @not_action
    def _cancel_stop_timer(self) -> None:
        """取消未触发的定时停止 Timer（若有）。"""
        timer = self._stop_timer
        self._stop_timer = None
        if timer is not None:
            try:
                timer.cancel()
            except Exception:  # noqa: BLE001
                pass

    @not_action
    def _resolve_direction(self, direction: str) -> Tuple[int, str]:
        """把对外的方向字符串解析成寄存器值与显示名。"""
        d = str(direction).upper().strip()
        if d in ("REVERSE", "CCW", "反转", "反向", "BACKWARD", "逆时针"):
            return self.DIR_CCW, "REVERSE"
        return self.DIR_CW, "FORWARD"

    # ============================================================
    # 动作: 参数设置
    # ============================================================
    @action(description="设置转速 (RPM, 内部按 0.1RPM 系数换算成寄存器值)")
    def set_speed(self, rpm: float = 60) -> Dict[str, Any]:
        """
        Args:
            rpm[转速(RPM)]: 目标转速, 0~max_rpm。
        """
        rpm_clamped = max(0.0, min(float(self.max_rpm), float(rpm)))
        reg_val = int(round(rpm_clamped / self.SPEED_SCALE))  # RPM × 10
        reg_val = max(0, min(0xFFFF, reg_val))
        ok = self.write_single_register(self.REG_SPEED, reg_val)
        if ok:
            self._current_speed = rpm_clamped
        return {
            "success": ok,
            "speed_rpm": rpm_clamped,
            "register_value": reg_val,
            "message": (
                f"转速设置为 {rpm_clamped} RPM (寄存器={reg_val})"
                if ok else f"转速设置失败: {self._last_error}"
            ),
        }

    @action(description="设置转向 (仅设方向, 不启停). FORWARD=顺时针出液, REVERSE=逆时针吸液")
    def set_direction(self, direction: str = "FORWARD") -> Dict[str, Any]:
        """
        Args:
            direction[转向]: FORWARD/CW 顺时针, REVERSE/CCW 逆时针。
        """
        val, name = self._resolve_direction(direction)
        ok = self.write_single_register(self.REG_DIRECTION, val)
        if ok:
            self._direction = val
        return {
            "success": ok,
            "direction": name,
            "message": f"转向设置为 {name}" if ok else f"转向设置失败: {self._last_error}",
        }

    # ============================================================
    # 动作: 运行控制
    # ============================================================
    @action(description=(
        "启动蠕动泵 (可选先设转速/转向, 再写运行=1). "
        "duration_seconds>0 时由软件定时, 到点自动停止 (立即返回, 不阻塞); "
        "=0 时持续运行直到 stop()."
    ))
    def start(
        self, rpm: float = 0, direction: str = "FORWARD", duration_seconds: float = 0.0
    ) -> Dict[str, Any]:
        """
        Args:
            rpm[转速(RPM)]: 启动转速, >0 时先下发转速; =0 沿用当前转速。
            direction[转向]: FORWARD/REVERSE。
            duration_seconds[运行时间(s)]: 运行时长(秒), >0 时到点自动停止, =0 持续运行直到 stop()。
        """
        duration_seconds = float(duration_seconds)

        if float(rpm) > 0:
            spd = self.set_speed(rpm)
            if not spd["success"]:
                return {"success": False, "message": f"转速设置失败: {self._last_error}"}

        dir_res = self.set_direction(direction)
        if not dir_res["success"]:
            return {"success": False, "message": f"转向设置失败: {self._last_error}"}

        # 起新一轮运行前, 先取消上一轮可能还挂着的定时停止
        self._cancel_stop_timer()

        ok = self.write_single_register(self.REG_RUN, 0x0001)
        if not ok:
            return {"success": False, "message": f"启动失败: {self._last_error}"}

        self._status = "Running"

        # 软件定时: 到点后台线程自动调 stop()
        if duration_seconds > 0:
            timer = Timer(duration_seconds, self._timed_stop)
            timer.daemon = True
            self._stop_timer = timer
            timer.start()

        return {
            "success": True,
            "speed_rpm": self._current_speed,
            "direction": dir_res["direction"],
            "duration_seconds": duration_seconds,
            "message": (
                f"已启动: {dir_res['direction']}, {self._current_speed} RPM, "
                + (f"将在 {duration_seconds}s 后自动停止" if duration_seconds > 0 else "持续运行")
            ),
        }

    @not_action
    def _timed_stop(self) -> None:
        """定时器到点回调: 自动停止 (异常只记录, 不抛出, 避免后台线程崩溃)。"""
        self._stop_timer = None
        try:
            self.stop()
            self.logger.info("定时运行到点, 已自动停止")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"定时自动停止失败: {exc}")

    @action(description="停止蠕动泵 (写运行=0, 同时取消未触发的定时停止)")
    def stop(self) -> Dict[str, Any]:
        self._cancel_stop_timer()
        ok = self.write_single_register(self.REG_RUN, 0x0000)
        if ok:
            self._status = "Idle"
        return {
            "success": ok,
            "message": "已停止" if ok else f"停止失败: {self._last_error}",
        }

    @action(description="正转启动 (顺时针出液). rpm=0 沿用当前转速, duration_seconds>0 时定时停止")
    def forward(self, rpm: float = 0, duration_seconds: float = 0.0) -> Dict[str, Any]:
        return self.start(rpm=rpm, direction="FORWARD", duration_seconds=duration_seconds)

    @action(description="反转启动 (逆时针吸液). rpm=0 沿用当前转速, duration_seconds>0 时定时停止")
    def reverse(self, rpm: float = 0, duration_seconds: float = 0.0) -> Dict[str, Any]:
        return self.start(rpm=rpm, direction="REVERSE", duration_seconds=duration_seconds)

    @action(description="读取一次综合状态 (转速 + 转向 + 运行状态, 用 0x03 读功能码)")
    def read_status(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_SPEED, 3)  # 0x00,0x01,0x02
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        speed_rpm = regs[0] * self.SPEED_SCALE
        direction = "REVERSE" if regs[1] == self.DIR_CCW else "FORWARD"
        running = regs[2] == 0x0001

        self._current_speed = speed_rpm
        self._direction = regs[1]
        self._status = "Running" if running else ("Idle" if self._status != "Error" else self._status)

        return {
            "success": True,
            "running": running,
            "status": self._status,
            "speed_rpm": speed_rpm,
            "direction": direction,
            "message": f"running={running}, speed={speed_rpm}RPM, dir={direction}",
        }

    @action(description="修改 Modbus 站号 (1-254, 写 0x0003). 设置后通信地址自动切换")
    def set_address(self, new_address: int = 1) -> Dict[str, Any]:
        """
        Args:
            new_address[新站号]: 目标 Modbus 站号 (1-254)。
        """
        addr = int(new_address)
        if not 1 <= addr <= 254:
            return {"success": False, "message": f"站号超出范围: {addr} (1-254)"}
        ok = self.write_single_register(self.REG_ADDRESS, addr)
        if ok:
            self.device_id = addr
            self.logger.info(f"站号已修改为 {addr}")
        return {
            "success": ok,
            "new_address": addr,
            "message": f"站号修改{'成功' if ok else '失败'}",
        }

    # ============================================================
    # 连接 / 断开
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
    # 心跳 (用 0x03 读运行状态寄存器, 无副作用)
    # ============================================================
    @not_action
    def _heartbeat_and_refresh(self) -> bool:
        """读 0x0002 运行状态, 刷新缓存; 失败抛异常让 DeviceWorker 计数掉线。"""
        regs = self.read_registers(self.REG_RUN, 1)
        if regs is None:
            raise RuntimeError(f"心跳失败: {self._last_error or 'no_response'}")
        if regs[0] == 0x0001:
            self._status = "Running"
        elif self._status == "Running":
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
        """运行状态 (Idle / Running / Error). 通过 0x03 读 0x02 验证在线并刷新。"""
        try:
            self._heartbeat_and_refresh()
        except Exception:
            self._status = "Error"
            raise
        return self._status

    @property
    @topic_config(period=5.0)
    def speed_rpm(self) -> float:
        """当前转速 (RPM, 软件缓存)。"""
        return float(self._current_speed)

    @property
    @topic_config(period=10.0)
    def direction(self) -> str:
        """当前转向 (软件缓存)。"""
        return "REVERSE" if self._direction == self.DIR_CCW else "FORWARD"

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


# ---------------------------------------------------------------------------
# 独立运行: 命令行测试 + probe 命令字节串打印 (供 fingerprints.yaml 用)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="简美 JourneyMan 蠕动泵驱动测试")
    parser.add_argument("--port", default="COM5", help="串口号")
    parser.add_argument("--baudrate", type=int, default=9600)
    parser.add_argument("--address", type=int, default=1, help="Modbus 站号")
    parser.add_argument("--rpm", type=float, default=120, help="测试转速 RPM")
    parser.add_argument("--duration", type=float, default=5.0, help="运行时长(秒)")
    parser.add_argument("--smoke", action="store_true", help="冒烟测试: 只读状态, 不让泵动")
    parser.add_argument("--probe-bytes", action="store_true", help="打印 probe 命令字节串")
    args = parser.parse_args()

    if args.probe_bytes:
        cases = [
            ("read 0x0002 (运行状态, 心跳/探测用)", struct.pack(">BBHH", args.address, 0x03, 0x0002, 0x0001)),
            ("read 0x0000 (转速)", struct.pack(">BBHH", args.address, 0x03, 0x0000, 0x0001)),
        ]
        for name, frame in cases:
            full = frame + _crc16_modbus(frame)
            esc = "".join(f"\\x{b:02x}" for b in full)
            print(f"# {name}:")
            print(f'  send: "{esc}"')
            print(f"  hex:  {full.hex(' ').upper()}")
            print()
        sys.exit(0)

    pump = JourneymanPump(
        port=args.port, baudrate=args.baudrate, device_id=args.address, auto_connect=True
    )
    if not pump._is_connected:
        print(f"✗ 连接失败: {pump._last_error}")
        sys.exit(1)
    print(f"✓ 已连接 {args.port} 站号 {args.address}")

    print("\n[1/3] 读取状态")
    print(f"  {pump.read_status()}")

    if args.smoke:
        print("\n[smoke] 冒烟测试完成 (不运行电机)")
        sys.exit(0)

    print(f"\n[2/3] 启动 {args.rpm}RPM 正转, 运行 {args.duration}s")
    print(f"  {pump.start(rpm=args.rpm, direction='FORWARD')}")
    for i in range(int(args.duration)):
        time.sleep(1)
        s = pump.read_status()
        print(f"  t={i+1}s running={s.get('running')} speed={s.get('speed_rpm')}")

    print("\n[3/3] 停止")
    print(f"  {pump.stop()}")
    pump.disconnect()

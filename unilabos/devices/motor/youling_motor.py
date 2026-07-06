# -*- coding: utf-8 -*-
"""
深圳俏优灵 (Youling / 优灵) 步进电机 B 系列驱动 (YL42B / YL57B)

参考: 《步进电机 B 系列产品手册》
- 通讯方式: RS485 (Modbus RTU)
- 默认波特率: 115200, 8N1, 无奇偶校验
- 默认站号: 1, 可设 1~254
- 供电: DC 24V, 工作电流 5A 自适应
- 功能码: 0x03 读寄存器, 0x06 写单个, 0x10 写多个

寄存器表 (节选):
    0x00 R    电机状态 (0=待机/到达, 1=运行中, 2=碰撞停, 3=正光电停, 4=反光电停)
    0x01 RW   实际步数高位
    0x02 RW   实际步数低位 (steps = (high<<16) | low, 32 位有符号)
    0x03 R    实际速度 (rpm)
    0x04 RW   急停指令
    0x05 R    电流 (mA)
    0x06 RW   使能 (1=使能 / 0=失能, 默认 1)
    0x07 RW   K 引脚 PWM 输出占空比 (0-1000 -> 0%-100%)
    0x0E RW   单圈绝对值归零
    0x0F RW   归零指令 (写入值即归零速度, 正数=正向, 负数=反向)

    位置模式 (一次写 0x10~0x15):
    0x10 目标步数高位
    0x11 目标步数低位
    0x12 保留
    0x13 速度 (rpm)
    0x14 加速度 (0-60000 rpm/s)
    0x15 精度 (步数)

    速度模式 (一次写 0x60~0x63):
    0x60 保留
    0x61 速度 (有符号, 负数=反转)
    0x62 加速度
    0x63 保留

    力矩速度模式:
    0x70 电流 (mA)

    设备参数:
    0xE0 设备地址 (1-254)
    0xE1 堵转电流 (mA)
    0xE3 每圈步数 (默认 0x0640=1600)
    0xE4 限位开关使能
    0xE5 堵转逻辑 (0=断电, 1=人机对抗)
    0xE6 堵转时间 (ms)
    0xE7 默认速度
    0xE8 默认加速度
    0xE9 默认精度
    0xEA 通讯波特率高 16 位
    0xEB 通讯波特率低 16 位 (0x0001 0xC200 -> 115200)
    0xF0 R   版本号 (例 0x001F = v3.1)
"""

import logging
import struct
import sys
import time
from dataclasses import dataclass
from enum import IntEnum
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import serial
from serial import Serial
from serial.serialutil import SerialException

from unilabos.registry.decorators import action, device, not_action, topic_config


class YoulingMotorError(Exception):
    """优灵电机异常基类"""


class YoulingMotorConnectionError(YoulingMotorError):
    """连接异常"""


class YoulingMotorTimeoutError(YoulingMotorError):
    """超时异常"""


class MotorStatus(IntEnum):
    """电机状态 (寄存器 0x00 的值)"""

    STANDBY = 0x0000             # 待机中或到达位置
    RUNNING = 0x0001             # 正在运行
    COLLISION_STOP = 0x0002      # 碰撞停
    FORWARD_PHOTO_STOP = 0x0003  # 正光电停
    REVERSE_PHOTO_STOP = 0x0004  # 反光电停


# ---------------------------------------------------------------------------
# 共享 RS485 总线管理: 同一 port 上的多个电机共用一个 Serial 对象 + 一把锁
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
            # 串口已关闭, 重新打开同一对象
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


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _crc16_modbus(data: bytes) -> bytes:
    """Modbus RTU CRC16 (小端), 与手册中 ModBusCRC 一致"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


def _to_u16(value: int) -> int:
    """有符号 16 位 -> 无符号 16 位 (Modbus 寄存器值)"""
    if value < 0:
        value = (value + 0x10000) & 0xFFFF
    return value & 0xFFFF


def _from_u16_signed(value: int) -> int:
    """无符号 16 位 -> 有符号 16 位"""
    return value - 0x10000 if value >= 0x8000 else value


def _to_u32(value: int) -> int:
    """有符号 32 位 -> 无符号 32 位"""
    if value < 0:
        value = (value + 0x100000000) & 0xFFFFFFFF
    return value & 0xFFFFFFFF


def _from_u32_signed(value: int) -> int:
    """无符号 32 位 -> 有符号 32 位"""
    return value - 0x100000000 if value >= 0x80000000 else value


# ---------------------------------------------------------------------------
# 驱动主体
# ---------------------------------------------------------------------------
@device(
    id="motor.youling.yl42b",
    category=["motor"],
    description="深圳俏优灵 YL42B/YL57B 步进电机 (RS-485 Modbus RTU, 默认 115200bps, 24V 供电). YL42B 与 YL57B 协议完全一致, 共用此驱动.",
    display_name="Youling YL B 系列步进电机",
)
class YoulingStepperMotor:
    """
    俏优灵 YL B 系列步进电机驱动 (Modbus RTU over RS485)

    用法 1: 直接打开串口 (适合单电机或同步骤序使用)
        m = YoulingStepperMotor(port="COM3", device_id=1)
        m.enable()
        m.move_to_position(steps=16384, speed=1000)

    用法 2: RS485 总线挂多个电机 (同 port 自动共享 Serial 与 Lock)
        m1 = YoulingStepperMotor(port="COM3", device_id=1)
        m2 = YoulingStepperMotor(port="COM3", device_id=2)
        # m1, m2 共用同一个串口和写锁, 不会互相串话

    用法 3: 工作站托管模式 (外部注入 Serial)
        m = YoulingStepperMotor(port="serial_bus", device_id=1, auto_connect=False)
        m.hardware_interface = shared_serial   # 由工作站注入
    """

    # 寄存器地址常量
    REG_STATUS = 0x00
    REG_ACTUAL_STEP_HIGH = 0x01
    REG_ACTUAL_STEP_LOW = 0x02
    REG_ACTUAL_SPEED = 0x03
    REG_EMERGENCY_STOP = 0x04
    REG_CURRENT = 0x05
    REG_ENABLE = 0x06
    REG_PWM_OUTPUT = 0x07
    REG_ZERO_SINGLE_CIRCLE = 0x0E
    REG_HOME = 0x0F

    # 位置模式
    REG_TARGET_STEP_HIGH = 0x10
    REG_TARGET_STEP_LOW = 0x11
    REG_POS_RESERVED = 0x12
    REG_POS_SPEED = 0x13
    REG_POS_ACCEL = 0x14
    REG_POS_PRECISION = 0x15

    # 速度模式
    REG_SPEED_RESERVED = 0x60
    REG_SPEED_VALUE = 0x61
    REG_SPEED_ACCEL = 0x62

    # 力矩速度模式
    REG_TORQUE_CURRENT = 0x70

    # 设备参数
    REG_DEVICE_ADDRESS = 0xE0
    REG_STALL_CURRENT = 0xE1
    REG_STEPS_PER_REV = 0xE3
    REG_LIMIT_SWITCH_ENABLE = 0xE4
    REG_STALL_LOGIC = 0xE5
    REG_STALL_TIME = 0xE6
    REG_DEFAULT_SPEED = 0xE7
    REG_DEFAULT_ACCEL = 0xE8
    REG_DEFAULT_PRECISION = 0xE9
    REG_BAUDRATE_HIGH = 0xEA
    REG_BAUDRATE_LOW = 0xEB
    REG_VERSION = 0xF0

    # 功能码
    FUNC_READ = 0x03
    FUNC_WRITE_SINGLE = 0x06
    FUNC_WRITE_MULTIPLE = 0x10

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        device_id: int = 1,
        timeout: float = 0.5,
        steps_per_rev: int = 1600,
        lead_mm: float = 4.0,
        response_delay: float = 0.02,
        auto_connect: bool = True,
    ):
        """
        :param port: 串口号 (Windows: COMx, Linux: /dev/ttyUSBx)
        :param baudrate: 波特率, 默认 115200
        :param device_id: Modbus 站号 (1-254)
        :param timeout: 串口读超时(秒)
        :param steps_per_rev: 每圈步数 (默认 1600, 与 0xE3 寄存器一致)
        :param lead_mm: 丝杠导程 (mm/圈), 用于 move_distance 计算
        :param response_delay: 发送后等待响应的延迟(秒)
        :param auto_connect: 是否在 __init__ 时自动打开串口
        """
        self.port = port
        self.baudrate = int(baudrate)
        self.device_id = int(device_id)
        self.timeout = float(timeout)
        self.steps_per_rev = int(steps_per_rev)
        self.lead_mm = float(lead_mm)
        self.response_delay = float(response_delay)

        self.logger = logging.getLogger(f"YoulingMotor[{device_id}@{port}]")

        # 串口对象 + 锁 (默认在 _do_connect 中通过总线缓存获取)
        self._serial: Optional[Serial] = None
        self._lock: Lock = Lock()
        self._is_connected = False

        # 缓存状态 (供 topic_config 读取, 避免每次属性访问都发命令)
        self._status: MotorStatus = MotorStatus.STANDBY
        self._actual_steps: int = 0
        self._actual_speed: int = 0
        self._current_ma: int = 0
        self._last_error: str = ""

        # hardware_interface: 健康检查约定 (与 xkc_y28 等设备保持一致)
        # 连接成功时指向 Serial 对象, 失败时退化为 port 字符串
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
        """打开串口 (同 port 复用)"""
        if self._is_connected and self._serial and self._serial.is_open:
            return True
        try:
            ser, lock = _get_or_open_bus(self.port, self.baudrate, self.timeout)
            self._serial = ser
            self._lock = lock
            self._is_connected = ser.is_open
            if self._is_connected:
                self.hardware_interface = ser
                self.logger.info(f"已连接 {self.port} @ {self.baudrate}bps (站号 {self.device_id})")
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
        # 不主动关闭共享串口 (其他电机可能还在用); 由 _close_bus 显式关闭
        self.hardware_interface = self.port

    # ============================================================
    # Modbus RTU 帧构建 / 收发
    # ============================================================
    @not_action
    def _build_read(self, reg_addr: int, count: int = 1) -> bytes:
        payload = struct.pack(">BBHH", self.device_id, self.FUNC_READ, reg_addr, count)
        return payload + _crc16_modbus(payload)

    @not_action
    def _build_write_single(self, reg_addr: int, value: int) -> bytes:
        payload = struct.pack(
            ">BBHH",
            self.device_id,
            self.FUNC_WRITE_SINGLE,
            reg_addr,
            _to_u16(value),
        )
        return payload + _crc16_modbus(payload)

    @not_action
    def _build_write_multiple(self, reg_addr: int, values: List[int]) -> bytes:
        count = len(values)
        payload = struct.pack(
            ">BBHHB",
            self.device_id,
            self.FUNC_WRITE_MULTIPLE,
            reg_addr,
            count,
            count * 2,
        )
        for v in values:
            payload += struct.pack(">H", _to_u16(v))
        return payload + _crc16_modbus(payload)

    @not_action
    def _send_recv(self, frame: bytes, response_len: int) -> Optional[bytes]:
        """加锁发送并读取期望长度的响应, 校验 CRC"""
        # 优先使用外部注入的 hardware_interface (Serial 对象)
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
                response = ser.read(response_len)
            except (OSError, SerialException) as exc:
                self._last_error = f"io: {exc}"
                self.logger.error(self._last_error)
                self._is_connected = False
                self.hardware_interface = self.port
                return None

        if not response:
            self._last_error = f"no_response addr={self.device_id} reg=0x{frame[2]:02X}{frame[3]:02X}"
            return None

        # 异常码响应: [addr][func|0x80][error_code][CRC_L][CRC_H], 长度 5
        if len(response) >= 2 and (response[1] & 0x80):
            if len(response) >= 5 and response[-2:] == _crc16_modbus(response[:-2]):
                err = response[2]
                self._last_error = f"modbus_error: 0x{err:02X}"
                self.logger.warning(f"设备返回 Modbus 错误码 0x{err:02X}")
            else:
                self._last_error = f"bad_exception_frame: {response.hex()}"
            return None

        if len(response) < response_len:
            self._last_error = f"short_response: got {len(response)}/{response_len} bytes"
            return None

        if response[-2:] != _crc16_modbus(response[:-2]):
            self._last_error = f"crc_error: {response.hex()}"
            self.logger.warning(self._last_error)
            return None

        return response

    # ============================================================
    # 底层读写 API
    # ============================================================
    @not_action
    def read_registers(self, reg_addr: int, count: int = 1) -> Optional[List[int]]:
        """读取 N 个连续寄存器, 返回无符号 16 位整数列表"""
        # 响应长度: addr(1) + func(1) + byte_count(1) + 2*count + crc(2)
        resp = self._send_recv(self._build_read(reg_addr, count), 5 + 2 * count)
        if resp is None:
            return None
        regs: List[int] = []
        for i in range(count):
            regs.append(struct.unpack(">H", resp[3 + 2 * i : 5 + 2 * i])[0])
        return regs

    @not_action
    def write_single_register(self, reg_addr: int, value: int) -> bool:
        """写单个寄存器 (功能码 0x06)"""
        frame = self._build_write_single(reg_addr, value)
        # 06 功能码响应与请求格式相同, 长度 8
        return self._send_recv(frame, 8) is not None

    @not_action
    def write_multiple_registers(self, reg_addr: int, values: List[int]) -> bool:
        """写多个寄存器 (功能码 0x10)"""
        frame = self._build_write_multiple(reg_addr, values)
        # 10 功能码响应: [addr][func][reg_h][reg_l][count_h][count_l][crc_l][crc_h], 长度 8
        return self._send_recv(frame, 8) is not None

    # ============================================================
    # 状态读取
    # ============================================================
    @action(description="读取电机运行状态 (待机/运行/碰撞停/光电停)")
    def read_status(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_STATUS, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        try:
            self._status = MotorStatus(regs[0])
            return {"success": True, "status": self._status.name, "code": int(regs[0])}
        except ValueError:
            self._last_error = f"unknown_status: 0x{regs[0]:04X}"
            return {"success": False, "code": int(regs[0]), "message": self._last_error}

    @action(description="读取当前实际步数 (32 位有符号)")
    def read_actual_steps(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_ACTUAL_STEP_HIGH, 2)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        steps = _from_u32_signed((regs[0] << 16) | regs[1])
        self._actual_steps = steps
        return {"success": True, "steps": steps}

    @action(description="读取当前实际速度 (rpm)")
    def read_actual_speed(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_ACTUAL_SPEED, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        speed = _from_u16_signed(regs[0])
        self._actual_speed = speed
        return {"success": True, "speed_rpm": speed}

    @action(description="读取当前电流 (mA)")
    def read_current(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_CURRENT, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        self._current_ma = _from_u16_signed(regs[0])
        return {"success": True, "current_ma": self._current_ma}

    @action(description="读取版本号, 例 0x001F -> v3.1")
    def read_version(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_VERSION, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        raw = regs[0]
        return {
            "success": True,
            "raw": int(raw),
            "version": f"{raw >> 4}.{raw & 0x0F}",
        }

    @action(description="读取设备地址寄存器 0xE0")
    def read_device_address(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_DEVICE_ADDRESS, 1)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        return {"success": True, "device_address": int(regs[0])}

    @action(description="一次读取电机状态 + 步数 + 速度 + 电流 (前 6 个寄存器)")
    def get_status_info(self) -> Dict[str, Any]:
        regs = self.read_registers(self.REG_STATUS, 6)
        if regs is None:
            return {"success": False, "message": f"读取失败: {self._last_error}"}
        try:
            status = MotorStatus(regs[0])
            self._status = status
        except ValueError:
            status = None
        steps = _from_u32_signed((regs[1] << 16) | regs[2])
        speed = _from_u16_signed(regs[3])
        current = _from_u16_signed(regs[5])
        self._actual_steps = steps
        self._actual_speed = speed
        self._current_ma = current
        return {
            "success": True,
            "status": status.name if status else f"UNKNOWN(0x{regs[0]:04X})",
            "actual_steps": steps,
            "actual_speed_rpm": speed,
            "current_ma": current,
        }

    # ============================================================
    # 基础控制
    # ============================================================
    @action(description="使能电机 (写 0x06=1)")
    def enable(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_ENABLE, 1)
        return {"success": ok, "message": "使能成功" if ok else f"使能失败: {self._last_error}"}

    @action(description="失能电机 (写 0x06=0, 释放力矩)")
    def disable(self) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_ENABLE, 0)
        return {"success": ok, "message": "失能成功" if ok else f"失能失败: {self._last_error}"}

    @action(description="急停 (写 0x04=0, 手册示例 11)")
    def emergency_stop(self) -> Dict[str, Any]:
        # 手册示例: 01 10 00 04 00 01 02 00 00 ...  即写多寄存器, 单个值 0
        ok = self.write_multiple_registers(self.REG_EMERGENCY_STOP, [0])
        return {"success": ok, "message": "已发送急停" if ok else f"急停失败: {self._last_error}"}

    @action(description="设置 K 引脚 PWM 输出占空比 (0-1000, 对应 0%-100%, 频率 1kHz)")
    def set_pwm(self, duty: int = 0) -> Dict[str, Any]:
        duty = max(0, min(1000, int(duty)))
        ok = self.write_single_register(self.REG_PWM_OUTPUT, duty)
        return {"success": ok, "duty": duty, "message": f"PWM={duty/10.0:.1f}%" if ok else self._last_error}

    # ============================================================
    # 归零
    # ============================================================
    @action(description="归零指令, 写入值为归零速度 (rpm), 正数=正向, 负数=反向")
    def home(self, speed_rpm: int = -200) -> Dict[str, Any]:
        # 先确保使能, 等驱动器进入使能态再下发归零指令 (经验值 300ms)
        self.write_single_register(self.REG_ENABLE, 1)
        time.sleep(0.3)
        ok = self.write_multiple_registers(self.REG_HOME, [_to_u16(int(speed_rpm))])
        return {
            "success": ok,
            "speed_rpm": int(speed_rpm),
            "message": "归零指令已发送" if ok else f"归零失败: {self._last_error}",
        }

    @action(description="单圈绝对值归零 (写 0x0E=1)")
    def single_turn_zero(self) -> Dict[str, Any]:
        ok = self.write_multiple_registers(self.REG_ZERO_SINGLE_CIRCLE, [1])
        return {"success": ok, "message": "单圈归零已发送" if ok else f"失败: {self._last_error}"}

    # ============================================================
    # 位置模式
    # ============================================================
    @action(description="位置模式: 移动到目标步数, 一次写入目标位置/速度/加速度/精度")
    def move_to_position(
        self,
        steps: int = 0,
        speed: int = 1000,
        acceleration: int = 5000,
        precision: int = 100,
    ) -> Dict[str, Any]:
        """
        :param steps: 目标步数 (32 位有符号)
        :param speed: 速度 rpm
        :param acceleration: 加速度 rpm/s (0-60000)
        :param precision: 精度 (步数), 实际位置与目标相差小于此值视为到位

        手册示例 (页 13): 写完 0x10-0x15 六个寄存器电机就会按参数自动运动,
        无需额外触发信号。但使能后必须等约 300ms 让驱动器内部状态机切到使能态,
        否则位置指令会被丢弃。
        """
        # 仅当未在 RUNNING 时才使能, 避免打断正在执行的运动
        try:
            cur = self.read_registers(self.REG_STATUS, 1)
            running = bool(cur and cur[0] == MotorStatus.RUNNING.value)
        except Exception:
            running = False
        if not running:
            self.write_single_register(self.REG_ENABLE, 1)
            time.sleep(0.3)  # 关键: 等待驱动器进入使能态, 经验值 300ms

        target_u32 = _to_u32(int(steps))
        high = (target_u32 >> 16) & 0xFFFF
        low = target_u32 & 0xFFFF

        values = [
            high,
            low,
            0x0000,                       # 0x12 保留
            _to_u16(int(speed)),
            max(0, min(60000, int(acceleration))),
            max(0, int(precision)),
        ]
        ok = self.write_multiple_registers(self.REG_TARGET_STEP_HIGH, values)
        return {
            "success": ok,
            "target_steps": int(steps),
            "speed_rpm": int(speed),
            "acceleration": int(acceleration),
            "precision": int(precision),
            "message": "运动指令已发送" if ok else f"失败: {self._last_error}",
        }

    @action(description="位置模式: 按距离(mm)移动, 自动换算步数/转速 (依赖 steps_per_rev 与 lead_mm)")
    def move_distance(
        self,
        distance_mm: float = 0.0,
        speed_mm_s: float = 5.0,
        acceleration: int = 5000,
        precision: int = 100,
    ) -> Dict[str, Any]:
        if self.lead_mm <= 0:
            return {"success": False, "message": f"lead_mm 必须>0, 当前 {self.lead_mm}"}
        steps = int(round(distance_mm / self.lead_mm * self.steps_per_rev))
        rpm = max(1, int(round(abs(speed_mm_s) / self.lead_mm * 60)))
        res = self.move_to_position(
            steps=steps, speed=rpm, acceleration=acceleration, precision=precision
        )
        res.update({
            "distance_mm": float(distance_mm),
            "speed_mm_s": float(speed_mm_s),
            "computed_steps": steps,
            "computed_rpm": rpm,
        })
        return res

    # ============================================================
    # 速度模式
    # ============================================================
    @action(description="速度模式: 以指定速度持续运行 (负数=反转)")
    def set_speed_mode(
        self,
        speed_rpm: int = 1000,
        acceleration: int = 250,
    ) -> Dict[str, Any]:
        try:
            cur = self.read_registers(self.REG_STATUS, 1)
            running = bool(cur and cur[0] == MotorStatus.RUNNING.value)
        except Exception:
            running = False
        if not running:
            self.write_single_register(self.REG_ENABLE, 1)
            time.sleep(0.3)
        # 一次写 4 个寄存器: 0x60(保留=0), 0x61(速度), 0x62(加速度), 0x63(保留=0)
        values = [
            0x0000,
            _to_u16(int(speed_rpm)),
            max(0, min(60000, int(acceleration))),
            0x0000,
        ]
        ok = self.write_multiple_registers(self.REG_SPEED_RESERVED, values)
        return {
            "success": ok,
            "speed_rpm": int(speed_rpm),
            "acceleration": int(acceleration),
            "message": "速度模式已启动" if ok else f"失败: {self._last_error}",
        }

    @action(description="速度模式停止 (设速度=0)")
    def stop_speed_mode(self) -> Dict[str, Any]:
        return self.set_speed_mode(speed_rpm=0, acceleration=5000)

    # ============================================================
    # 力矩速度模式
    # ============================================================
    @action(description="力矩速度模式: 设定输出电流 (mA), 0x70 寄存器")
    def set_torque_current(self, current_ma: int = 500) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_TORQUE_CURRENT, max(0, int(current_ma)))
        return {"success": ok, "current_ma": int(current_ma)}

    # ============================================================
    # 等待 / 阻塞辅助
    # ============================================================
    @action(description="等待电机停止 (轮询状态寄存器)")
    def wait_until_stopped(
        self,
        timeout: float = 60.0,
        poll_interval: float = 0.1,
    ) -> Dict[str, Any]:
        deadline = time.time() + timeout
        last_status = None
        while time.time() < deadline:
            res = self.read_status()
            if not res.get("success"):
                time.sleep(poll_interval)
                continue
            last_status = res["status"]
            if last_status == MotorStatus.STANDBY.name:
                steps_res = self.read_actual_steps()
                return {
                    "success": True,
                    "status": last_status,
                    "actual_steps": steps_res.get("steps"),
                    "message": "电机已到达/停止",
                }
            if last_status in (
                MotorStatus.COLLISION_STOP.name,
                MotorStatus.FORWARD_PHOTO_STOP.name,
                MotorStatus.REVERSE_PHOTO_STOP.name,
            ):
                return {
                    "success": False,
                    "status": last_status,
                    "message": f"电机异常停止: {last_status}",
                }
            time.sleep(poll_interval)
        return {"success": False, "status": last_status, "message": f"等待超时 {timeout}s"}

    # ============================================================
    # 设备参数配置
    # ============================================================
    @action(description="修改 Modbus 站号 (1-254). 修改后将自动切换到新地址通信")
    def set_address(self, new_address: int = 1) -> Dict[str, Any]:
        addr = int(new_address)
        if not 1 <= addr <= 254:
            return {"success": False, "message": f"站号超出范围: {addr} (1-254)"}
        ok = self.write_single_register(self.REG_DEVICE_ADDRESS, addr)
        if ok:
            self.device_id = addr
            self.logger.info(f"站号已修改为 {addr}")
        return {
            "success": ok,
            "new_address": addr,
            "message": f"站号修改{'成功' if ok else '失败'}",
        }

    @action(description="修改每圈步数 (脉冲细分), 例如 1600 / 3200 / 6400 / 12800 / 16384")
    def set_steps_per_rev(self, steps_per_rev: int = 1600) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_STEPS_PER_REV, int(steps_per_rev))
        if ok:
            self.steps_per_rev = int(steps_per_rev)
        return {"success": ok, "steps_per_rev": int(steps_per_rev)}

    @action(description="修改默认速度 (上电时赋给 0x13/0x61, rpm)")
    def set_default_speed(self, speed_rpm: int = 5000) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_DEFAULT_SPEED, _to_u16(int(speed_rpm)))
        return {"success": ok, "speed_rpm": int(speed_rpm)}

    @action(description="修改默认加速度 (上电时赋给 0x14/0x62, rpm/s, 0-60000)")
    def set_default_acceleration(self, acceleration: int = 60000) -> Dict[str, Any]:
        ok = self.write_single_register(
            self.REG_DEFAULT_ACCEL, max(0, min(60000, int(acceleration)))
        )
        return {"success": ok, "acceleration": int(acceleration)}

    @action(description="修改默认精度 (上电时赋给 0x15)")
    def set_default_precision(self, precision: int = 100) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_DEFAULT_PRECISION, max(0, int(precision)))
        return {"success": ok, "precision": int(precision)}

    @action(description="启用/禁用限位开关 (0xE4)")
    def set_limit_switch_enabled(self, enabled: bool = True) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_LIMIT_SWITCH_ENABLE, 1 if enabled else 0)
        return {"success": ok, "enabled": bool(enabled)}

    @action(description="设置堵转电流阈值 (mA), 超过此电流一段时间认为堵转")
    def set_stall_current(self, current_ma: int = 3000) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_STALL_CURRENT, max(0, int(current_ma)))
        return {"success": ok, "current_ma": int(current_ma)}

    @action(description="设置堵转时间 (ms), 超过此时间进入人机对抗并报错")
    def set_stall_time(self, time_ms: int = 1000) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_STALL_TIME, max(0, int(time_ms)))
        return {"success": ok, "time_ms": int(time_ms)}

    @action(description="设置堵转逻辑 (0=断电需重新上电, 1=人机对抗)")
    def set_stall_logic(self, logic: int = 0) -> Dict[str, Any]:
        ok = self.write_single_register(self.REG_STALL_LOGIC, 1 if logic else 0)
        return {"success": ok, "logic": int(bool(logic))}

    @action(description="修改通讯波特率 (写 0xEA/0xEB), 改完需断电重启或按新波特率重连")
    def set_baudrate(self, baudrate: int = 115200) -> Dict[str, Any]:
        high = (int(baudrate) >> 16) & 0xFFFF
        low = int(baudrate) & 0xFFFF
        ok = self.write_multiple_registers(self.REG_BAUDRATE_HIGH, [high, low])
        return {
            "success": ok,
            "baudrate": int(baudrate),
            "message": "波特率已写入, 请按新波特率重连" if ok else f"失败: {self._last_error}",
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

    @action(description="关闭串口连接 (同 port 的其他电机会一起断开)")
    def disconnect(self) -> Dict[str, Any]:
        _close_bus(self.port)
        self._disconnect()
        return {"success": True, "message": "串口已关闭"}

    # ============================================================
    # 状态属性 (定时广播)
    # ============================================================
    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def status(self) -> str:
        """电机状态 (枚举名). 每 2s 主动查询一次"""
        res = self.read_status()
        if not res.get("success"):
            raise RuntimeError(f"读取 status 失败: {self._last_error or 'unknown'}")
        return res["status"]

    @property
    @topic_config(period=2.0)
    def actual_steps(self) -> int:
        res = self.read_actual_steps()
        if not res.get("success"):
            raise RuntimeError(f"读取 actual_steps 失败: {self._last_error or 'unknown'}")
        return int(res.get("steps", 0))

    @property
    @topic_config(period=2.0)
    def actual_speed(self) -> int:
        res = self.read_actual_speed()
        if not res.get("success"):
            raise RuntimeError(f"读取 actual_speed 失败: {self._last_error or 'unknown'}")
        return int(res.get("speed_rpm", 0))

    @property
    @topic_config(period=5.0)
    def current_ma(self) -> int:
        res = self.read_current()
        if not res.get("success"):
            raise RuntimeError(f"读取 current_ma 失败: {self._last_error or 'unknown'}")
        return int(res.get("current_ma", 0))

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


# ---------------------------------------------------------------------------
# 独立运行: 命令行测试
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Youling YL B 系列步进电机驱动测试")
    parser.add_argument("--port", default="COM3", help="串口号")
    parser.add_argument("--baudrate", type=int, default=115200, help="波特率, 默认 115200")
    parser.add_argument("--address", type=int, default=1, help="Modbus 站号, 默认 1")
    parser.add_argument("--timeout", type=float, default=0.5, help="串口超时(秒)")
    parser.add_argument("--smoke", action="store_true", help="冒烟测试: 只读, 不让电机动")
    parser.add_argument("--scan", action="store_true", help="扫描 1~16 站号")
    parser.add_argument("--list-ports", action="store_true", help="列出可用串口")
    args = parser.parse_args()

    if args.list_ports:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            print(f"  {p.device:10s} - {p.description}")
        sys.exit(0)

    if args.scan:
        print(f"=== 扫描 {args.port} @ {args.baudrate}bps 上 1~16 号站点 ===")
        found = []
        for addr in range(1, 17):
            m = YoulingStepperMotor(
                port=args.port,
                baudrate=args.baudrate,
                device_id=addr,
                timeout=args.timeout,
            )
            res = m.read_status()
            if res.get("success"):
                print(f"  站号 {addr:2d}: ✓ {res['status']}")
                found.append(addr)
            else:
                print(f"  站号 {addr:2d}: ✗ 无响应")
        print(f"\n共找到 {len(found)} 个电机: {found}")
        sys.exit(0)

    motor = YoulingStepperMotor(
        port=args.port,
        baudrate=args.baudrate,
        device_id=args.address,
        timeout=args.timeout,
    )

    # 连接测试
    print(f"\n>>> 连接测试 (站号 {args.address})")
    res = motor.read_status()
    if not res.get("success"):
        print(f"✗ 无响应: {res.get('message')}")
        sys.exit(2)
    print(f"✓ 状态: {res['status']} (code={res['code']})")

    # 完整状态
    info = motor.get_status_info()
    print(f"\n>>> 完整状态: {info}")

    # 版本号
    ver = motor.read_version()
    if ver.get("success"):
        print(f">>> 版本号: v{ver['version']} (raw=0x{ver['raw']:04X})")

    if args.smoke:
        print("\n✓ 冒烟测试通过 (未驱动电机)")
        sys.exit(0)

    # 交互菜单
    while True:
        print("\n--- Youling YL B 系列电机菜单 ---")
        print("  1) 读完整状态")
        print("  2) 使能")
        print("  3) 失能")
        print("  4) 归零 (-200 rpm)")
        print("  5) 位置模式: +16384 步 @ 1000 rpm")
        print("  6) 距离模式: 输入 mm 和 mm/s")
        print("  7) 速度模式: 输入 rpm")
        print("  8) 速度模式停止")
        print("  9) 急停")
        print(" 10) 设置 PWM 占空比 (0-1000)")
        print("  q) 退出")
        choice = input("选择: ").strip().lower()
        try:
            if choice == "1":
                print(motor.get_status_info())
            elif choice == "2":
                print(motor.enable())
            elif choice == "3":
                print(motor.disable())
            elif choice == "4":
                print(motor.home(-200))
                print(motor.wait_until_stopped(timeout=60))
            elif choice == "5":
                print(motor.move_to_position(steps=16384, speed=1000))
                print(motor.wait_until_stopped(timeout=60))
            elif choice == "6":
                d = float(input("距离mm [默认10]: ") or "10")
                v = float(input("速度mm/s [默认5]: ") or "5")
                print(motor.move_distance(distance_mm=d, speed_mm_s=v))
                print(motor.wait_until_stopped(timeout=60))
            elif choice == "7":
                v = int(input("速度rpm (负数=反转): "))
                print(motor.set_speed_mode(speed_rpm=v, acceleration=250))
            elif choice == "8":
                print(motor.stop_speed_mode())
            elif choice == "9":
                print(motor.emergency_stop())
            elif choice == "10":
                d = int(input("占空比 (0-1000): "))
                print(motor.set_pwm(d))
            elif choice == "q":
                break
            else:
                print("无效输入")
        except KeyboardInterrupt:
            print("\n⚠ 用户中断, 急停")
            motor.emergency_stop()
        except Exception as e:
            print(f"✗ 异常: {e}")

    motor.disconnect()

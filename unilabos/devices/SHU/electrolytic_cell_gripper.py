"""
Electrolytic Cell Gripper Workstation Driver (电解池夹爪工作站)

Combines 2x QYL stepper motors + 1x DH PGE gripper into a single device
with two high-level actions: pick_sample and place_sample.

All three physical devices share COM via RS-485 Modbus RTU.
Motor 1 (slave_id=1), Motor 2 (slave_id=2), Gripper (slave_id=5).

Communication: 9600, 8N1

v8:
    - More robust Modbus RTU send/receive for CH340 + USB hub environments.
    - Use flush + polling read instead of fixed sleep + single read.
    - Add retries for Modbus operations.
    - Check motor command return values.
    - Fail fast when motor status cannot be read repeatedly.
"""

import logging
import struct
import time as time_module
from typing import Dict, Any, Optional

from unilabos.registry.decorators import device, topic_config, not_action, action

try:
    from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode
except ImportError:
    BaseROS2DeviceNode = None

try:
    import serial
    from serial import Serial
except ImportError:
    serial = None
    Serial = None


# ══════════════════════════════════════════════════════════════════════════════
# CRC16 Modbus
# ══════════════════════════════════════════════════════════════════════════════

def _crc16_modbus(data: bytes) -> bytes:
    """Calculate Modbus RTU CRC16, returns 2 bytes: low byte first."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


# ══════════════════════════════════════════════════════════════════════════════
# Internal Modbus helpers
# ══════════════════════════════════════════════════════════════════════════════

class _ModbusRTU:
    """Low-level Modbus RTU helper bound to a Serial port."""

    def __init__(self, ser: Serial, logger: logging.Logger):
        self._ser = ser
        self.logger = logger

        # CH340 + USB hub 环境下建议稍长一点
        self.default_timeout = 1.0
        self.frame_gap = 0.008       # 9600bps 下 3.5 字符约 4ms，这里留 8ms
        self.poll_interval = 0.005
        self.retry_delay = 0.05

    # ── Frame builders ──────────────────────────────────────────────────────

    @staticmethod
    def _build_read_frame(slave_id: int, register: int, count: int = 1) -> bytes:
        frame = struct.pack(">B B H H", slave_id, 0x03, register, count)
        return frame + _crc16_modbus(frame)

    @staticmethod
    def _build_write_single_frame(slave_id: int, register: int, value: int) -> bytes:
        frame = struct.pack(">B B H H", slave_id, 0x06, register, value & 0xFFFF)
        return frame + _crc16_modbus(frame)

    @staticmethod
    def _build_write_multiple_frame(
        slave_id: int, start_register: int, values: list
    ) -> bytes:
        count = len(values)
        byte_count = count * 2
        frame = struct.pack(
            ">B B H H B", slave_id, 0x10, start_register, count, byte_count
        )
        for v in values:
            frame += struct.pack(">H", v & 0xFFFF)
        return frame + _crc16_modbus(frame)

    # ── Send / Receive ──────────────────────────────────────────────────────

    def send_and_receive(
        self,
        frame: bytes,
        expect_len: int,
        timeout: Optional[float] = None,
    ) -> Optional[bytes]:
        """
        Robust Modbus RTU transaction.

        Important changes from old version:
        - Adds inter-frame silent gap.
        - Resets input/output buffer before sending.
        - Uses write + flush.
        - Polls in_waiting until expected length is collected or timeout.
        - Searches response frame inside raw stream.
        """
        if self._ser is None or not self._ser.is_open:
            self.logger.error("Serial not open")
            return None

        timeout = timeout if timeout is not None else self.default_timeout

        slave_id = frame[0]
        fc_sent = frame[1]

        try:
            # Modbus RTU frame gap
            time_module.sleep(self.frame_gap)

            # 清掉上一帧残留
            try:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
            except Exception:
                pass

            self.logger.debug(f"TX: {frame.hex(' ')}")

            self._ser.write(frame)
            self._ser.flush()

            deadline = time_module.monotonic() + timeout
            raw = bytearray()

            while time_module.monotonic() < deadline:
                n = self._ser.in_waiting
                if n:
                    raw.extend(self._ser.read(n))

                    # 正常响应收齐
                    if len(raw) >= expect_len:
                        # 再等一个很短的时间，吃掉可能晚到的尾字节
                        time_module.sleep(0.01)
                        n2 = self._ser.in_waiting
                        if n2:
                            raw.extend(self._ser.read(n2))
                        break

                    # 异常响应长度通常 5 字节：slave, fc|0x80, err, crc_lo, crc_hi
                    if len(raw) >= 5:
                        for i in range(len(raw) - 1):
                            if raw[i] == slave_id and raw[i + 1] == (fc_sent | 0x80):
                                break
                else:
                    time_module.sleep(self.poll_interval)

            raw = bytes(raw)
            self.logger.debug(f"RX: {raw.hex(' ') if raw else '(empty)'}")

            if len(raw) == 0:
                self.logger.warning(
                    f"No response from slave={slave_id}, fc=0x{fc_sent:02X}"
                )
                return None

            if len(raw) < expect_len:
                self.logger.warning(
                    f"Short response: expected >={expect_len}, got {len(raw)}"
                )

            # Locate normal or exception response in raw stream
            for i in range(max(0, len(raw) - 1)):
                # Normal response
                if raw[i] == slave_id and raw[i + 1] == fc_sent:
                    resp = raw[i:]

                    if len(resp) < expect_len:
                        self.logger.warning(
                            f"Located response but too short: expected {expect_len}, got {len(resp)}"
                        )
                        return None

                    resp = resp[:expect_len]
                    payload = resp[:-2]
                    crc_recv = resp[-2:]

                    if _crc16_modbus(payload) != crc_recv:
                        self.logger.warning(
                            f"CRC mismatch: resp={resp.hex(' ')}, "
                            f"calc={_crc16_modbus(payload).hex(' ')}, recv={crc_recv.hex(' ')}"
                        )
                        return None

                    return resp

                # Modbus exception response
                if raw[i] == slave_id and raw[i + 1] == (fc_sent | 0x80):
                    if i + 4 < len(raw):
                        error_code = raw[i + 2]
                        self.logger.error(
                            f"Modbus exception: slave={slave_id}, "
                            f"FC=0x{raw[i + 1]:02X}, err=0x{error_code:02X}"
                        )
                    else:
                        self.logger.error(
                            f"Modbus exception response too short: {raw.hex(' ')}"
                        )
                    return None

            self.logger.warning(
                f"Could not locate valid response frame for slave={slave_id}, "
                f"fc=0x{fc_sent:02X}, raw={raw.hex(' ')}"
            )
            return None

        except Exception as e:
            self.logger.error(f"send_and_receive failed: {e}")
            return None

    # ── High-level register operations ──────────────────────────────────────

    def read_registers(
        self,
        slave_id: int,
        start: int,
        count: int = 1,
        retries: int = 2,
    ) -> Optional[list]:
        frame = self._build_read_frame(slave_id, start, count)
        expect = 3 + count * 2 + 2

        for attempt in range(retries + 1):
            resp = self.send_and_receive(frame, expect, timeout=self.default_timeout)
            if resp is not None and len(resp) >= expect:
                values = []
                for i in range(count):
                    offset = 3 + i * 2
                    values.append(struct.unpack(">H", resp[offset: offset + 2])[0])
                return values

            if attempt < retries:
                self.logger.warning(
                    f"read_registers retry {attempt + 1}/{retries}: "
                    f"slave={slave_id}, start=0x{start:04X}, count={count}"
                )
                time_module.sleep(self.retry_delay)

        return None

    def write_single(
        self,
        slave_id: int,
        register: int,
        value: int,
        retries: int = 2,
    ) -> bool:
        frame = self._build_write_single_frame(slave_id, register, value)

        for attempt in range(retries + 1):
            resp = self.send_and_receive(frame, 8, timeout=self.default_timeout)
            if resp is not None and len(resp) >= 8:
                return True

            if attempt < retries:
                self.logger.warning(
                    f"write_single retry {attempt + 1}/{retries}: "
                    f"slave={slave_id}, reg=0x{register:04X}, value={value}"
                )
                time_module.sleep(self.retry_delay)

        return False

    def write_multiple(
        self,
        slave_id: int,
        start: int,
        values: list,
        retries: int = 2,
    ) -> bool:
        frame = self._build_write_multiple_frame(slave_id, start, values)

        # FC10 长帧给更长超时
        for attempt in range(retries + 1):
            resp = self.send_and_receive(frame, 8, timeout=1.2)
            if resp is not None and len(resp) >= 8:
                return True

            if attempt < retries:
                self.logger.warning(
                    f"write_multiple retry {attempt + 1}/{retries}: "
                    f"slave={slave_id}, start=0x{start:04X}, values={values}"
                )
                time_module.sleep(self.retry_delay)

        return False


# ══════════════════════════════════════════════════════════════════════════════
# Helper: signed 32-bit conversion
# ══════════════════════════════════════════════════════════════════════════════

def _from_signed32(val: int) -> tuple:
    if val < 0:
        val += 0x100000000
    return ((val >> 16) & 0xFFFF, val & 0xFFFF)


def _to_signed32(high: int, low: int) -> int:
    val = (high << 16) | low
    if val >= 0x80000000:
        val -= 0x100000000
    return val


# ══════════════════════════════════════════════════════════════════════════════
# Motor register addresses
# ══════════════════════════════════════════════════════════════════════════════

# Zeta 一体式步进电机寄存器 (与 xyz_guangdian.YL_REG 一致, 依据 Zeta 手册)
_M_STATUS = 0x0000     # 只读 0=待机/到位 1=运行 2=碰撞停 3=正光电停 4=反光电停
_M_POS_H = 0x0001      # 只读 实际步数高位 (不可写!)
_M_POS_L = 0x0002      # 只读 实际步数低位 (不可写!)
_M_SPEED = 0x0003      # 只读 实际速度 rpm
_M_ESTOP = 0x0004      # 急停指令
_M_ENABLE = 0x0006     # 1=使能 0=失能, 默认1
_M_ZERO = 0x000E       # 单圈绝对值归零 (写1=把当前位置置零)
_M_HOME = 0x000F       # 归零指令 (定点模式写入值=归零速度 rpm)
_M_PP_TARGET_H = 0x0010  # 目标步数高位 (一帧连写0x10~0x15触发绝对定位)
_M_PP_TARGET_L = 0x0011  # 目标步数低位
_M_PP_RESERVED = 0x0012  # 保留位, 必须写0
_M_PP_RUN_SPD = 0x0013   # 速度 rpm
_M_PP_ACCEL = 0x0014     # 加速度 rpm/s
_M_PP_TOL = 0x0015       # 到位精度(步)
_M_FW_STEPS_H = 0x0040
_M_FW_STEPS_L = 0x0041
_M_FW_INIT_SPD = 0x0042
_M_FW_RUN_SPD = 0x0043
_M_FW_ACCEL = 0x0044
_M_FW_TOL = 0x0045

# Gripper register addresses
_G_INIT = 0x0100
_G_FORCE = 0x0101
_G_TARGET_POS = 0x0103
_G_SPEED = 0x0104
_G_INIT_STATE = 0x0200
_G_GRIP_STATE = 0x0201
_G_ACTUAL_POS = 0x0202

# Motor status map
_MOTOR_STATUS = {
    0: "Idle",
    1: "Busy",
    2: "Stopped",
    3: "LimitPos",
    4: "LimitNeg",
}


# ══════════════════════════════════════════════════════════════════════════════
# Main workstation class
# ══════════════════════════════════════════════════════════════════════════════

@device(
    id="electrolytic_cell_gripper",
    category=["workstation"],
    description="电解池夹爪工作站: 2个Zeta步进电机(X/Z轴) + 1个PGE平行夹爪, 提供取样/放样组合动作",
    displayname="电解池夹爪工作站",
    device_type="python",
    version="1.0.0",
)
class ElectrolyticCellGripper:
    """
    Electrolytic Cell Gripper Workstation (电解池夹爪).

    Combines:
      - Motor 1 (slave_id=1): Horizontal slide
      - Motor 2 (slave_id=2): Vertical slide
      - Gripper  (slave_id=5): DH PGE parallel gripper

    Exposes:
      - pick_sample()
      - place_sample()
    """

    _ros_node: "BaseROS2DeviceNode"

    MOTOR_SPEED = 5000   # 运行速度 rpm
    MOTOR_ACCEL = 5000   # 加速度 rpm/s
    MOTOR_TOL = 100      # 到位精度(步)

    def __init__(
        self,
        device_id: str = None,
        port: str = "COM4",
        baudrate: int = 9600,
        timeout: float = 0.5,
        motor1_slave_id: int = 1,
        motor2_slave_id: int = 2,
        gripper_slave_id: int = 5,
        **kwargs,
    ):
        """
        初始化电解池夹爪工作站 (三设备共用一条 RS-485 Modbus RTU 总线)。

        Args:
            device_id[设备ID]: 设备实例 ID，默认使用 electrolytic_cell_gripper。
            port[串口]: RS-485 串口号，例如 COM4 或 /dev/ttyUSB0。
            baudrate[波特率]: 串口波特率，三个从站需统一为 9600。
            timeout[超时时间(s)]: 串口读超时时间，单位秒。
            motor1_slave_id[电机1从站号]: X 轴电机 Modbus 从站地址。
            motor2_slave_id[电机2从站号]: Z 轴电机 Modbus 从站地址。
            gripper_slave_id[夹爪从站号]: 夹爪 Modbus 从站地址。
        """
        if device_id is None and "id" in kwargs:
            device_id = kwargs.pop("id")

        self.device_id = device_id or "electrolytic_cell_gripper"
        self.logger = logging.getLogger(f"ECG.{self.device_id}")

        self._port_name: str = port
        self._baudrate: int = int(baudrate)
        self._timeout: float = float(timeout)

        self._motor1_id: int = int(motor1_slave_id)
        self._motor2_id: int = int(motor2_slave_id)
        self._gripper_id: int = int(gripper_slave_id)

        self._ser: Optional[Serial] = None
        self._bus: Optional[_ModbusRTU] = None

        self.data: Dict[str, Any] = {
            "status": "Idle",
        }

    # ── Framework hooks ─────────────────────────────────────────────────────

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode"):
        self._ros_node = ros_node

    def _ensure_serial(self) -> bool:
        if self._bus is not None and self._ser is not None and self._ser.is_open:
            return True

        self.logger.info(f"Opening serial port {self._port_name} @ {self._baudrate}...")
        try:
            if Serial is None:
                self.logger.error("pyserial not installed")
                return False

            self._ser = Serial(
                port=self._port_name,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self._timeout,
                write_timeout=1.0,
            )

            if not self._ser.is_open:
                self.logger.error(f"Failed to open {self._port_name}")
                return False

            try:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
            except Exception:
                pass

            self._bus = _ModbusRTU(self._ser, self.logger)
            self.logger.info(f"Serial {self._port_name} opened successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to open serial: {e}")
            return False

    @action(description="初始化并打开串口")
    async def initialize(self) -> bool:
        self.logger.info("initialize() called")
        ok = self._ensure_serial()
        if ok:
            self.data["status"] = "Idle"
            self.logger.info("initialize() SUCCESS — serial is open")
        else:
            self.data["status"] = "Error"
            self.logger.error("initialize() FAILED — could not open serial")
        return ok

    @action(description="关闭串口并清理")
    async def cleanup(self) -> bool:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None
        self._bus = None
        self.data["status"] = "Offline"
        return True

    @property
    @topic_config()
    def status(self) -> str:
        return self.data.get("status", "Idle")

    # ── Internal motor helpers ──────────────────────────────────────────────

    def _motor_set_position_zero(self, slave_id: int) -> bool:
        # 0x0001/0x0002 是只读实际步数寄存器, 不能写。
        # Zeta 协议用 FC06 往 0x000E(单圈绝对值归零)写1 把当前位置置零。
        return self._bus.write_single(slave_id, _M_ZERO, 0x0001)

    def _motor_move_absolute(
        self,
        slave_id: int,
        position: int,
        speed: int = None,
        accel: int = None,
    ) -> bool:
        spd = speed if speed is not None else self.MOTOR_SPEED
        acc = accel if accel is not None else self.MOTOR_ACCEL
        pos_h, pos_l = _from_signed32(int(position))
        # 0x10目标H, 0x11目标L, 0x12保留=0, 0x13速度rpm, 0x14加速度rpm/s, 0x15到位精度; 连写即触发
        values = [pos_h, pos_l, 0, spd, acc, self.MOTOR_TOL]
        return self._bus.write_multiple(slave_id, _M_PP_TARGET_H, values)

    def _motor_read_status(self, slave_id: int) -> Optional[Dict]:
        regs = self._bus.read_registers(slave_id, _M_STATUS, 4)
        if regs is None or len(regs) < 4:
            return None
        return {
            "status_code": regs[0],
            "status": _MOTOR_STATUS.get(regs[0], f"Unknown({regs[0]})"),
            "position": _to_signed32(regs[1], regs[2]),
            "speed_reg": regs[3],
        }

    def _motor_emergency_stop(self, slave_id: int) -> bool:
        return self._bus.write_single(slave_id, _M_ESTOP, 0x0001)

    def _preflight_motors(self):
        """电机动作前探活: 读一次状态寄存器(FC03 0x0000)。
        若无应答, 给出可读报错(通常是 波特率/供电/地址/接线 问题, 而非协议帧问题)。
        """
        for slave_id in (self._motor1_id, self._motor2_id):
            info = self._motor_read_status(slave_id)
            if info is None:
                raise RuntimeError(
                    f"Motor{slave_id} 无应答: 请检查电机波特率(应=9600)、动力供电、"
                    f"从站地址(应={slave_id})、A/B接线是否接入本总线"
                )
            self.logger.info(
                f"Motor{slave_id} online: pos={info['position']}, status={info['status']}"
            )

    def _require(self, ok: bool, message: str):
        if not ok:
            raise RuntimeError(message)

    async def _motor_wait_idle(
        self,
        slave_id: int,
        timeout: float = 120.0,
        poll_interval: float = 0.3,
        max_consecutive_failures: int = 5,
    ) -> bool:
        elapsed = 0.0
        consecutive_failures = 0
        motor_name = f"Motor{slave_id}"

        while elapsed < timeout:
            info = self._motor_read_status(slave_id)

            if info is None:
                consecutive_failures += 1
                self.logger.warning(
                    f"{motor_name} status read failed "
                    f"({consecutive_failures}/{max_consecutive_failures})"
                )

                if consecutive_failures >= max_consecutive_failures:
                    raise RuntimeError(
                        f"{motor_name} communication lost while waiting idle"
                    )
            else:
                consecutive_failures = 0
                code = info["status_code"]

                if code != 1:
                    self.logger.info(
                        f"{motor_name} idle: pos={info['position']}, status={info['status']}"
                    )
                    return True

            await self._ros_node.sleep(poll_interval)
            elapsed += poll_interval

        raise RuntimeError(f"{motor_name} wait_idle timed out after {timeout}s")

    # ── Internal gripper helpers ────────────────────────────────────────────

    def _gripper_init(self) -> bool:
        return self._bus.write_single(self._gripper_id, _G_INIT, 0x01)

    async def _gripper_wait_init(self, timeout: float = 30.0) -> bool:
        elapsed = 0.0
        while elapsed < timeout:
            regs = self._bus.read_registers(self._gripper_id, _G_INIT_STATE, 1)
            if regs is not None and regs[0] == 1:
                self.logger.info("Gripper init complete")
                return True
            await self._ros_node.sleep(0.5)
            elapsed += 0.5

        raise RuntimeError("Gripper init timed out")

    def _gripper_set_force(self, force: int) -> bool:
        force = max(20, min(100, force))
        return self._bus.write_single(self._gripper_id, _G_FORCE, force)

    def _gripper_set_speed(self, speed: int) -> bool:
        speed = max(1, min(100, speed))
        return self._bus.write_single(self._gripper_id, _G_SPEED, speed)

    def _gripper_set_position(self, position: int) -> bool:
        position = max(0, min(1000, position))
        return self._bus.write_single(self._gripper_id, _G_TARGET_POS, position)

    async def _gripper_wait_done(self, timeout: float = 15.0) -> bool:
        elapsed = 0.0
        while elapsed < timeout:
            regs = self._bus.read_registers(self._gripper_id, _G_GRIP_STATE, 1)
            if regs is not None and regs[0] in (1, 2, 3):
                state_names = {1: "Reached", 2: "Gripped", 3: "Dropped"}
                self.logger.info(f"Gripper done: {state_names.get(regs[0], regs[0])}")
                return True
            await self._ros_node.sleep(0.2)
            elapsed += 0.2

        raise RuntimeError("Gripper wait timed out")

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION 1: 夹取样品
    # ══════════════════════════════════════════════════════════════════════════

    @action(description="取样: 归零并夹取样品")
    async def pick_sample(self):
        if not self._ensure_serial():
            self.logger.error("pick_sample ABORTED: cannot open serial port")
            self.data["status"] = "Error"
            return

        self.data["status"] = "Busy"
        self.logger.info("=" * 60)
        self.logger.info("pick_sample START")
        self.logger.info("=" * 60)

        try:
            self.logger.info("[0/11] Preflight: probe motors...")
            self._preflight_motors()

            self.logger.info("[1/11] Gripper init (homing)...")
            self._require(self._gripper_init(), "Gripper init command failed")
            await self._gripper_wait_init(timeout=30.0)

            self.logger.info("[2/11] Set gripper force = 50%")
            self._require(self._gripper_set_force(50), "Set gripper force failed")
            time_module.sleep(0.05)

            self.logger.info("[3/11] Set gripper speed = 100%")
            self._require(self._gripper_set_speed(100), "Set gripper speed failed")
            time_module.sleep(0.05)

            self.logger.info("[4/11] Motor1 + Motor2 set position zero")
            self._require(
                self._motor_set_position_zero(self._motor1_id),
                "Motor1 set zero failed",
            )
            time_module.sleep(0.05)
            self._require(
                self._motor_set_position_zero(self._motor2_id),
                "Motor2 set zero failed",
            )
            time_module.sleep(0.05)

            self.logger.info("[5/11] Motor1 move to 838000 steps")
            self._require(
                self._motor_move_absolute(self._motor1_id, 838000, speed=5000, accel=5000),
                "Motor1 move command failed",
            )
            await self._motor_wait_idle(self._motor1_id, timeout=120.0)

            self.logger.info("[6/11] Motor2 move to -600000 steps")
            self._require(
                self._motor_move_absolute(self._motor2_id, -600000, speed=5000, accel=5000),
                "Motor2 move command failed",
            )
            await self._motor_wait_idle(self._motor2_id, timeout=120.0)

            self.logger.info("[7/11] Gripper close")
            self._require(self._gripper_set_position(0), "Gripper close command failed")
            await self._gripper_wait_done(timeout=15.0)

            self.logger.info("[8/11] Motor2 move to 0 steps")
            self._require(
                self._motor_move_absolute(self._motor2_id, 0, speed=5000, accel=5000),
                "Motor2 move to 0 command failed",
            )
            await self._motor_wait_idle(self._motor2_id, timeout=120.0)

            self.logger.info("[9/11] Motor1 move to 0 steps")
            self._require(
                self._motor_move_absolute(self._motor1_id, 0, speed=5000, accel=5000),
                "Motor1 move to 0 command failed",
            )
            await self._motor_wait_idle(self._motor1_id, timeout=120.0)

            self.logger.info("[10/11] Motor2 move to -630000 steps")
            self._require(
                self._motor_move_absolute(self._motor2_id, -630000, speed=5000, accel=5000),
                "Motor2 move to -630000 command failed",
            )
            await self._motor_wait_idle(self._motor2_id, timeout=120.0)

            self.data["status"] = "Idle"
            self.logger.info("=" * 60)
            self.logger.info("pick_sample COMPLETE")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"pick_sample failed: {e}")
            self.data["status"] = "Error"

    # ══════════════════════════════════════════════════════════════════════════
    # ACTION 2: 放下样品
    # ══════════════════════════════════════════════════════════════════════════

    @action(description="放样: 沿零点放回样品并回位")
    async def place_sample(self):
        if not self._ensure_serial():
            self.logger.error("place_sample ABORTED: cannot open serial port")
            self.data["status"] = "Error"
            return

        self.data["status"] = "Busy"
        self.logger.info("=" * 60)
        self.logger.info("place_sample START")
        self.logger.info("=" * 60)

        try:
            self.logger.info("[0/6] Preflight: probe motors...")
            self._preflight_motors()

            self.logger.info("[1/6] Motor2 move to 0 steps")
            self._require(
                self._motor_move_absolute(self._motor2_id, 0, speed=5000, accel=5000),
                "Motor2 move to 0 command failed",
            )
            await self._motor_wait_idle(self._motor2_id, timeout=120.0)

            self.logger.info("[2/6] Motor1 move to 838000 steps")
            self._require(
                self._motor_move_absolute(self._motor1_id, 838000, speed=5000, accel=5000),
                "Motor1 move to 838000 command failed",
            )
            await self._motor_wait_idle(self._motor1_id, timeout=120.0)

            self.logger.info("[3/6] Motor2 move to -590000 steps")
            self._require(
                self._motor_move_absolute(self._motor2_id, -590000, speed=5000, accel=5000),
                "Motor2 move to -590000 command failed",
            )
            await self._motor_wait_idle(self._motor2_id, timeout=120.0)

            self.logger.info("[4/6] Gripper open")
            self._require(self._gripper_set_position(1000), "Gripper open command failed")
            await self._gripper_wait_done(timeout=15.0)

            self.logger.info("[5/6] Motor2 move to 0 steps")
            self._require(
                self._motor_move_absolute(self._motor2_id, 0, speed=5000, accel=5000),
                "Motor2 move to 0 command failed",
            )
            await self._motor_wait_idle(self._motor2_id, timeout=120.0)

            self.logger.info("[6/6] Motor1 move to 0 steps")
            self._require(
                self._motor_move_absolute(self._motor1_id, 0, speed=5000, accel=5000),
                "Motor1 move to 0 command failed",
            )
            await self._motor_wait_idle(self._motor1_id, timeout=120.0)

            self.data["status"] = "Idle"
            self.logger.info("=" * 60)
            self.logger.info("place_sample COMPLETE")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"place_sample failed: {e}")
            self.data["status"] = "Error"

    # ══════════════════════════════════════════════════════════════════════════
    # Emergency stop
    # ══════════════════════════════════════════════════════════════════════════

    @action(description="急停两个电机")
    async def emergency_stop(self):
        self.logger.warning("EMERGENCY STOP")
        if self._bus is not None:
            self._motor_emergency_stop(self._motor1_id)
            time_module.sleep(0.05)
            self._motor_emergency_stop(self._motor2_id)
        self.data["status"] = "Stopped"


# ══════════════════════════════════════════════════════════════════════════════
# 独立运行示例: 先「取样」pick_sample, 再「放样」place_sample (一个完整取放循环)
#
# 用法(不经过 unilab 框架, 直接连硬件跑一次取放):
#   python -m unilabos.devices.SHU.electrolytic_cell_gripper
# 或:
#   python unilabos/devices/SHU/electrolytic_cell_gripper.py
#
# 运行会发生什么:
#   1) 打开串口 @ 9600 (按需改 _DEMO_CONFIG["port"])
#   2) 探活两个电机(FC03 读 0x0000), 没上线会直接报错并退出
#   3) 取样 pick_sample:
#        归零(把当前位置设为零点) -> Motor1 838000 -> Motor2 -600000 -> 夹爪夹取
#        -> Motor2 0 -> Motor1 0 -> Motor2 -630000
#   4) 放样 place_sample (沿同一零点, 不再归零):
#        Motor2 0 -> Motor1 838000 -> Motor2 -590000 -> 夹爪张开放样
#        -> Motor2 0 -> Motor1 0 (两轴回零点)
#   ⚠️ 会真实驱动电机运动! 先确认零点位置合适、行程范围安全、可随时急停。
#      取样中途失败会跳过放样, 避免带着错误零点乱跑。
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s [%(funcName)s]",
    )

    _DEMO_CONFIG = {
        "port": "COM6",           # 按实际串口修改
        "baudrate": 9600,
        "timeout": 0.5,
        "motor1_slave_id": 1,     # X 轴电机
        "motor2_slave_id": 2,     # Z 轴电机
        "gripper_slave_id": 5,    # 夹爪
    }

    class _FakeRosNode:
        """独立运行时替代 ROS 节点, 只提供动作里用到的 async sleep。"""

        async def sleep(self, seconds: float):
            await asyncio.sleep(seconds)

    async def _run_pick_then_place():
        dev = ElectrolyticCellGripper(device_id="ecg_demo", **_DEMO_CONFIG)
        dev.post_init(_FakeRosNode())

        print("=" * 60)
        print("初始化并打开串口...")
        if not await dev.initialize():
            print("初始化失败: 串口打不开, 检查 COM 口占用/线缆")
            return

        print("开始执行「取样」pick_sample ...")
        await dev.pick_sample()
        print(f"取样结束, 设备状态 = {dev.status}")

        if dev.status == "Error":
            print("取样失败, 跳过放样 (避免带着错误零点乱跑)")
            await dev.cleanup()
            return

        print("开始执行「放样」place_sample (沿取样的零点回位) ...")
        await dev.place_sample()
        print(f"放样结束, 设备状态 = {dev.status}")

        await dev.cleanup()

    asyncio.run(_run_pick_then_place())
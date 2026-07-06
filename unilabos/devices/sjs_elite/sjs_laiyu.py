# -*- coding: utf-8 -*-
"""广州铼羽 APD-SV 单通道固体加样仪驱动

通信方式：Modbus RTU over RS485
默认波特率 115200，8N1，默认站号 1
功能码：0x03（读）、0x06（写单寄存器）、0x10（写多寄存器）
"""

import logging
import struct
import time
from threading import Lock
from typing import Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode

logger = logging.getLogger(__name__)

# ────────────────────── 寄存器地址 ──────────────────────
# 读取类
REG_RUNNING_STATUS = 0x0000      # 运行状态：0=加样中，1=空闲
REG_BALANCE_WEIGHT_HI = 0x0001   # 天平实时质量高位
REG_BALANCE_WEIGHT_LO = 0x0002   # 天平实时质量低位
REG_LAST_WEIGHT_HI = 0x0003      # 最近一次完成加样质量高位
REG_LAST_WEIGHT_LO = 0x0004      # 最近一次完成加样质量低位
REG_DOOR_STATUS = 0x0005         # 天平门状态
REG_Z_STATUS = 0x0006            # Z 轴状态
REG_MOTOR_STATUS = 0x0007        # 加样电机状态

# 设置类
REG_TARGET_WEIGHT_HI = 0x0010    # 设定加样质量高位
REG_TARGET_WEIGHT_LO = 0x0011    # 设定加样质量低位
REG_DISPENSE_MODE = 0x0012       # 加样模式：1=精细，2=标准
REG_DEVICE_ADDR = 0x001F         # 设备地址

# 控制类
REG_RESET_ALL = 0x0020           # 写 0xAAAA 复位所有结构
REG_Z_POS_HI = 0x0021            # Z 轴位置步数高位
REG_Z_POS_LO = 0x0022            # Z 轴位置步数低位
REG_TARE = 0x0023                # 写 0xAAAA 天平去皮置零
REG_START = 0x0024               # 写 1 开始加样
REG_ABORT = 0x0025               # 写 1 中止加样
REG_HEAD_RESET = 0x0026          # 写 1 加样头复位
REG_Z_RESET = 0x0027             # 写 1 Z 轴复位至最高
REG_DOOR_RESET = 0x0028          # 写 1 天平门复位（关闭）
REG_ESTOP = 0x0029               # 0=全部急停，2=天平门急停，3=Z轴急停
REG_DOOR_CTRL = 0x0037           # 天平门控制：1=复位，2=对齐，3=最大

# ────────────────────── 常量 ──────────────────────
STEPS_PER_MM = 64000 / 30        # 64000步 ≈ 30mm
WEIGHT_SCALE = 10                # 寄存器值 3000 → 300.0mg

AXIS_STATUS_MAP = {
    0: "就绪", 1: "运行中", 2: "异常/碰撞停",
    3: "正限位停", 4: "反限位停", 5: "未连接",
}


def _crc16(data: bytes) -> bytes:
    """Modbus RTU CRC16 校验"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return struct.pack("<H", crc)


@device(
    id="sample_dispenser.laiyu.apd_sv",
    category=["sample_dispenser"],
    description="铼羽 APD-SV 单通道固体加样仪 (Modbus RTU / RS485)",
    display_name="铼羽 APD-SV 加样仪",
)
class ApdSvDispenser:
    """铼羽 APD-SV 单通道固体加样仪驱动

    通过 RS485 串口使用 Modbus RTU 协议控制。
    """

    _ros_node: BaseROS2DeviceNode

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self.device_id = device_id or "apd_sv"
        self.config = config or {}
        self.config.update({k: v for k, v in kwargs.items() if k in ("port", "baudrate", "slave_addr", "poll_interval", "timeout")})
        self.port: str = self.config.get("port", "COM3")
        self.baudrate: int = self.config.get("baudrate", 115200)
        self.slave_addr: int = self.config.get("slave_addr", 1)
        self.poll_interval: float = self.config.get("poll_interval", 0.3)
        self.timeout: float = self.config.get("timeout", 300.0)
        logger.info("初始化配置: port=%s, baudrate=%d, slave_addr=%d", self.port, self.baudrate, self.slave_addr)

        self._serial: Optional[serial.Serial] = None
        self._lock = Lock()
        self.data: Dict[str, Any] = {
            "status": "Idle",
            "balance_weight_mg": 0.0,
            "last_dispensed_mg": 0.0,
            "door_status": "未知",
            "z_status": "未知",
            "motor_status": "未知",
        }

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node
        try:
            self._open_serial()
            self.data["status"] = "Connected"
            ros_node.lab_logger().info(f"加样仪串口已连接: {self.port} @ {self.baudrate}")
        except Exception as e:
            self.data["status"] = "Error"
            ros_node.lab_logger().error(f"加样仪串口连接失败: {e}")

    # ═══════════════════ Modbus RTU 底层 ═══════════════════

    @not_action
    def _open_serial(self) -> None:
        if self._serial and self._serial.is_open:
            return
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
        )
        logger.info("串口已打开: %s @ %d", self.port, self.baudrate)

    @not_action
    def _send_and_recv(self, frame: bytes, expected_min: int = 5) -> Optional[bytes]:
        """发送帧并接收响应，帧间间隔 ≥ 3.5 字符时间"""
        with self._lock:
            if not self._serial or not self._serial.is_open:
                self._open_serial()
            self._serial.reset_input_buffer()
            self._serial.write(frame)
            logger.debug("TX: %s", frame.hex())
            time.sleep(0.05)
            resp = self._serial.read(256)
            if resp:
                logger.debug("RX: %s", resp.hex())
            else:
                logger.warning("无响应")
            return resp if len(resp) >= expected_min else None

    @not_action
    def _read_registers(self, start: int, count: int) -> Optional[list[int]]:
        """FC 0x03 读取保持寄存器，返回 16 位无符号整数列表"""
        pdu = struct.pack(">BBHH", self.slave_addr, 0x03, start, count)
        frame = pdu + _crc16(pdu)
        resp = self._send_and_recv(frame, expected_min=5 + count * 2)
        if resp is None:
            return None
        if resp[1] & 0x80:
            logger.error("读寄存器 0x%04X 错误码: 0x%02X", start, resp[2])
            return None
        if resp[1] != 0x03:
            return None
        n = resp[2]
        data = resp[3: 3 + n]
        return [int.from_bytes(data[i: i + 2], "big") for i in range(0, len(data), 2)]

    @not_action
    def _write_single_register(self, address: int, value: int) -> bool:
        """FC 0x06 写单个保持寄存器"""
        pdu = struct.pack(">BBHH", self.slave_addr, 0x06, address, value & 0xFFFF)
        frame = pdu + _crc16(pdu)
        resp = self._send_and_recv(frame, expected_min=8)
        if resp is None:
            return False
        if resp[1] & 0x80:
            logger.error("写寄存器 0x%04X 错误码: 0x%02X", address, resp[2])
            return False
        return resp[1] == 0x06

    @not_action
    def _write_multiple_registers(self, start: int, values: list[int]) -> bool:
        """FC 0x10 写多个保持寄存器"""
        count = len(values)
        byte_count = count * 2
        pdu = struct.pack(">BBHHB", self.slave_addr, 0x10, start, count, byte_count)
        for v in values:
            pdu += struct.pack(">H", v & 0xFFFF)
        frame = pdu + _crc16(pdu)
        resp = self._send_and_recv(frame, expected_min=8)
        if resp is None:
            return False
        if resp[1] & 0x80:
            logger.error("写多寄存器 0x%04X 错误码: 0x%02X", start, resp[2])
            return False
        return resp[1] == 0x10

    @not_action
    def _read_u32(self, reg_hi: int) -> Optional[int]:
        """读取两个连续寄存器，组合为 32 位无符号整数"""
        regs = self._read_registers(reg_hi, 2)
        if regs is None or len(regs) < 2:
            return None
        return (regs[0] << 16) | regs[1]

    @not_action
    def _write_u32(self, reg_hi: int, value: int) -> bool:
        """将 32 位无符号整数写入两个连续寄存器"""
        hi = (value >> 16) & 0xFFFF
        lo = value & 0xFFFF
        return self._write_multiple_registers(reg_hi, [hi, lo])

    @not_action
    def _wait_idle(self, timeout: Optional[float] = None) -> bool:
        """轮询运行状态寄存器直到空闲或超时"""
        t = timeout or self.timeout
        start = time.time()
        time.sleep(0.3)
        while time.time() - start < t:
            regs = self._read_registers(REG_RUNNING_STATUS, 1)
            if regs and regs[0] == 1:
                return True
            time.sleep(self.poll_interval)
        logger.error("等待空闲超时 (%.0fs)", t)
        return False

    @not_action
    def _wait_dispense_done(
        self,
        target_weight_raw: int,
        timeout: Optional[float] = None,
        max_retries: int = 3,
        idle_debounce: float = 1.5,
    ) -> tuple[bool, str]:
        """等待加样完成。

        成功条件（严格大于，避免天平噪声导致过早判定完成）：
            天平实时质量 > 目标质量 → 发送中止指令并返回成功。

        自停重试：
            若设备中途自行停止（运行状态寄存器回到"空闲"）而质量仍未达目标，
            自动重发 REG_START 继续加样，最多 max_retries 次。
            超出重试次数或超时仍未达目标 → 返回失败原因。

        Returns:
            (success, reason)：success 为 True 时 reason 为空字符串。
        """
        t = timeout or self.timeout
        start = time.time()
        time.sleep(0.3)
        retries_used = 0
        idle_since: Optional[float] = None

        while time.time() - start < t:
            weight = self._read_u32(REG_BALANCE_WEIGHT_HI)
            if weight is not None and weight > target_weight_raw:
                logger.info("天平质量 %.1fmg 已超过目标 %.1fmg，发送中止指令",
                            weight / WEIGHT_SCALE, target_weight_raw / WEIGHT_SCALE)
                self._write_single_register(REG_ABORT, 1)
                return True, ""

            regs = self._read_registers(REG_RUNNING_STATUS, 1)
            if regs and regs[0] == 1:  # 设备已空闲
                if idle_since is None:
                    idle_since = time.time()
                elif time.time() - idle_since >= idle_debounce:
                    cur_mg = (weight or 0) / WEIGHT_SCALE
                    tgt_mg = target_weight_raw / WEIGHT_SCALE
                    if retries_used < max_retries:
                        retries_used += 1
                        logger.warning(
                            "设备已空闲但质量 %.1fmg 未达目标 %.1fmg，"
                            "第 %d/%d 次重发开始指令",
                            cur_mg, tgt_mg, retries_used, max_retries,
                        )
                        if not self._write_single_register(REG_START, 1):
                            reason = "重发开始指令失败，串口可能异常"
                            logger.error(reason)
                            return False, reason
                        idle_since = None
                        time.sleep(0.5)
                    else:
                        reason = (
                            f"设备提前停止且重试 {max_retries} 次后仍未达目标"
                            f"（当前 {cur_mg:.1f}mg < 目标 {tgt_mg:.1f}mg），"
                            f"请检查加样头是否有料/是否堵塞"
                        )
                        logger.error(reason)
                        return False, reason
            else:
                idle_since = None

            time.sleep(self.poll_interval)

        reason = f"加样超时 ({t:.0f}s)"
        logger.error(reason)
        return False, reason

    @not_action
    def _wait_axis_idle(self, status_reg: int, timeout: float = 60.0) -> bool:
        """等待指定轴/门状态变为就绪 (0)"""
        start = time.time()
        time.sleep(0.3)
        while time.time() - start < timeout:
            regs = self._read_registers(status_reg, 1)
            if regs and regs[0] == 0:
                return True
            if regs and regs[0] >= 2:
                logger.error("轴/门异常停止，状态码: %d", regs[0])
                return False
            time.sleep(self.poll_interval)
        return False

    # ═══════════════════ 连接管理 ═══════════════════

    @action(description="连接加样仪串口")
    def connect(self) -> Dict[str, Any]:
        try:
            self._open_serial()
            self.data["status"] = "Connected"
            return {"success": True, "message": f"已连接 {self.port}"}
        except Exception as e:
            logger.error("连接失败: %s", e)
            self.data["status"] = "Error"
            return {"success": False, "message": str(e)}

    @action(description="断开加样仪连接")
    def disconnect(self) -> Dict[str, Any]:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
        self.data["status"] = "Idle"
        return {"success": True}

    # ═══════════════════ 复位操作 ═══════════════════

    @action(description="复位所有结构（Z轴最高、天平门关闭、加样头复位）")
    def reset_all(self) -> Dict[str, Any]:
        """初次通电必须执行，Z轴回最高点，天平门关闭"""
        self.data["status"] = "Resetting"
        ok = self._write_single_register(REG_RESET_ALL, 0xAAAA)
        if not ok:
            self.data["status"] = "Error"
            return {"success": False, "message": "复位指令发送失败"}
        idle = self._wait_idle(timeout=60.0)
        self.data["status"] = "Ready" if idle else "Error"
        return {"success": idle, "message": "复位完成" if idle else "复位超时"}

    @action(description="Z轴复位至最高点")
    def reset_z_axis(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_Z_RESET, 1)
        if not ok:
            return {"success": False, "message": "Z轴复位指令失败"}
        idle = self._wait_axis_idle(REG_Z_STATUS, timeout=30.0)
        return {"success": idle}

    @action(description="加样头复位")
    def reset_dispenser_head(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_HEAD_RESET, 1)
        if not ok:
            return {"success": False, "message": "加样头复位指令失败"}
        idle = self._wait_axis_idle(REG_MOTOR_STATUS, timeout=30.0)
        return {"success": idle}

    @action(description="天平门复位（关闭）")
    def reset_balance_door(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_DOOR_RESET, 1)
        if not ok:
            return {"success": False, "message": "天平门复位指令失败"}
        idle = self._wait_axis_idle(REG_DOOR_STATUS, timeout=30.0)
        return {"success": idle}

    # ═══════════════════ 天平操作 ═══════════════════

    @action(description="天平去皮置零")
    def tare_balance(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_TARE, 0xAAAA)
        return {"success": ok}

    @action(description="读取天平实时质量(mg)")
    def read_balance_weight(self) -> Dict[str, Any]:
        val = self._read_u32(REG_BALANCE_WEIGHT_HI)
        if val is None:
            return {"success": False, "weight_mg": None}
        weight_mg = val / WEIGHT_SCALE
        self.data["balance_weight_mg"] = weight_mg
        return {"success": True, "weight_mg": weight_mg}

    @action(description="读取最近一次加样完成质量(mg)")
    def read_last_dispensed_weight(self) -> Dict[str, Any]:
        val = self._read_u32(REG_LAST_WEIGHT_HI)
        if val is None:
            return {"success": False, "weight_mg": None}
        weight_mg = val / WEIGHT_SCALE
        self.data["last_dispensed_mg"] = weight_mg
        return {"success": True, "weight_mg": weight_mg}

    # ═══════════════════ Z 轴控制 ═══════════════════

    @action(description="移动Z轴到指定高度(mm)")
    def move_z_axis(self, height_mm: float = 30.0) -> Dict[str, Any]:
        """移动 Z 轴到离最高点指定距离处

        Args:
            height_mm: 下降高度（毫米），数值越大越靠下，注意行程过长会碰撞
        """
        steps = int(height_mm * STEPS_PER_MM)
        ok = self._write_u32(REG_Z_POS_HI, steps)
        if not ok:
            return {"success": False, "message": "Z轴位置写入失败"}
        idle = self._wait_axis_idle(REG_Z_STATUS, timeout=30.0)
        return {"success": idle, "height_mm": height_mm, "steps": steps}

    @action(description="读取Z轴当前位置(mm)")
    def read_z_position(self) -> Dict[str, Any]:
        val = self._read_u32(REG_Z_POS_HI)
        if val is None:
            return {"success": False, "height_mm": None}
        height_mm = round(val / STEPS_PER_MM, 2)
        return {"success": True, "height_mm": height_mm, "steps": val}

    # ═══════════════════ 天平门控制 ═══════════════════

    @action(description="打开天平门至最大")
    def open_door(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_DOOR_CTRL, 3)
        if not ok:
            return {"success": False, "message": "天平门打开指令失败"}
        idle = self._wait_axis_idle(REG_DOOR_STATUS, timeout=30.0)
        return {"success": idle}

    @action(description="关闭天平门")
    def close_door(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_DOOR_CTRL, 1)
        if not ok:
            return {"success": False, "message": "天平门关闭指令失败"}
        idle = self._wait_axis_idle(REG_DOOR_STATUS, timeout=30.0)
        return {"success": idle}

    # ═══════════════════ 加样模式 ═══════════════════

    @action(description="设置加样模式")
    def set_dispense_mode(self, mode: int = 2) -> Dict[str, Any]:
        """设置加样模式

        Args:
            mode: 1=精细模式，2=标准模式
        """
        if mode not in (1, 2):
            return {"success": False, "message": "mode 必须为 1(精细) 或 2(标准)"}
        ok = self._write_single_register(REG_DISPENSE_MODE, mode)
        return {"success": ok, "mode": "精细" if mode == 1 else "标准"}

    @action(description="读取当前加样模式")
    def read_dispense_mode(self) -> Dict[str, Any]:
        regs = self._read_registers(REG_DISPENSE_MODE, 1)
        if regs is None:
            return {"success": False, "mode": None}
        m = regs[0]
        return {"success": True, "mode_code": m, "mode": {1: "精细", 2: "标准"}.get(m, "未知")}

    # ═══════════════════ 加样控制 ═══════════════════

    @action(description="执行加样（阻塞直到完成）")
    def dispense(
        self,
        weight_mg: float = 100.0,
        z_height_mm: float = 30.0,
        mode: int = 2,
        read_actual_weight: bool = False,
        tare_before: bool = True,
        tare_settle_time: float = 1.5,
        reset_head_before_start: bool = True,
        max_dispense_retries: int = 3,
    ) -> Dict[str, Any]:
        """完整加样流程：天平去皮 → 加样头复位 → 设置参数 → 开始加样 → 等待完成

        Args:
            weight_mg: 目标加样质量（毫克），例如 300.0 表示加 300mg
            z_height_mm: Z轴下降高度（毫米），距最高点的距离
            mode: 加样模式，1=精细模式，2=标准模式（默认标准）
            read_actual_weight: 加样完成后是否读取天平回传的实际质量
            tare_before: 加样前是否先给天平去皮（瓶子已放入时必须去皮，否则
                天平读数可能已大于目标值，导致立即判定完成而未实际加样）
            tare_settle_time: 去皮后等待天平稳定的秒数
            reset_head_before_start: 开始加样前是否先复位加样头。解决"第一次调用
                不加样、只动 Z 轴"的问题——设备需要加样电机处于就绪(0)状态，
                REG_START 才会被固件接受。
            max_dispense_retries: 设备中途自停（空闲但质量未达目标）时自动重发
                "开始加样"的最大次数，0 表示不重试
        """
        self.data["status"] = "Dispensing"

        # 0. 天平去皮：瓶子已在天平上，必须先清零，避免瓶重被当成加样质量
        if tare_before:
            if not self._write_single_register(REG_TARE, 0xAAAA):
                self.data["status"] = "Error"
                return {"success": False, "message": "天平去皮指令失败"}
            time.sleep(max(0.0, tare_settle_time))
            # 校验：去皮后实时质量应接近 0，否则说明去皮未生效，拒绝继续
            cur = self._read_u32(REG_BALANCE_WEIGHT_HI)
            if cur is not None and cur >= int(weight_mg * WEIGHT_SCALE):
                self.data["status"] = "Error"
                return {
                    "success": False,
                    "message": f"去皮后天平读数 {cur / WEIGHT_SCALE:.1f}mg 仍 ≥ 目标 {weight_mg:.1f}mg，"
                               f"请检查天平是否稳定或目标质量是否过小",
                }
            logger.info("天平去皮完成，当前读数: %.1fmg",
                        (cur or 0) / WEIGHT_SCALE)

        # 1. 加样头强制复位：让加样电机回到就绪状态(0)，否则 REG_START 会被固件忽略
        #    （这是"第一次调用只下降 Z 轴、不加样"的根因——上电/上次异常后加样头
        #     状态机未处于就绪态，直到下一次调用时才恰好到位）
        if reset_head_before_start:
            motor_regs = self._read_registers(REG_MOTOR_STATUS, 1)
            motor_code = motor_regs[0] if motor_regs else None
            if motor_code != 0:
                logger.info("加样头当前状态=%s，执行强制复位",
                            AXIS_STATUS_MAP.get(motor_code, motor_code))
            if not self._write_single_register(REG_HEAD_RESET, 1):
                self.data["status"] = "Error"
                return {"success": False, "message": "加样头复位指令发送失败"}
            if not self._wait_axis_idle(REG_MOTOR_STATUS, timeout=30.0):
                self.data["status"] = "Error"
                return {
                    "success": False,
                    "message": "加样头复位超时或异常，请检查加样仪机械结构",
                }
            logger.info("加样头已复位就绪")

        # 2. 设定加样质量
        weight_raw = int(weight_mg * WEIGHT_SCALE)
        if not self._write_u32(REG_TARGET_WEIGHT_HI, weight_raw):
            self.data["status"] = "Error"
            return {"success": False, "message": "设定加样质量失败"}

        # 3. 设定加样模式
        if mode in (1, 2):
            self._write_single_register(REG_DISPENSE_MODE, mode)

        # 4. 移动 Z 轴到指定高度
        steps = int(z_height_mm * STEPS_PER_MM)
        if not self._write_u32(REG_Z_POS_HI, steps):
            self.data["status"] = "Error"
            return {"success": False, "message": "设定Z轴位置失败"}
        if not self._wait_axis_idle(REG_Z_STATUS, timeout=30.0):
            self.data["status"] = "Error"
            return {"success": False, "message": "Z轴移动超时或异常"}

        # 5. 再次确认加样电机就绪，否则 START 指令仍会被固件忽略
        motor_regs = self._read_registers(REG_MOTOR_STATUS, 1)
        if motor_regs and motor_regs[0] != 0:
            self.data["status"] = "Error"
            return {
                "success": False,
                "message": f"开始加样前加样电机状态异常(code={motor_regs[0]}, "
                           f"{AXIS_STATUS_MAP.get(motor_regs[0], '未知')})，"
                           f"请手动复位加样头后重试",
            }

        # 6. 开始加样
        if not self._write_single_register(REG_START, 1):
            self.data["status"] = "Error"
            return {"success": False, "message": "开始加样指令失败"}

        logger.info("加样开始: 目标 %.1fmg, Z轴 %.1fmm, 模式 %s",
                     weight_mg, z_height_mm, "精细" if mode == 1 else "标准")

        # 7. 阻塞等待加样完成：仅当天平实时质量严格大于目标质量时才成功退出；
        #    若设备中途自停（空闲但未达目标），自动重发开始指令最多 N 次。
        ok, reason = self._wait_dispense_done(
            weight_raw,
            timeout=self.timeout,
            max_retries=max_dispense_retries,
        )
        if not ok:
            self.data["status"] = "Timeout" if "超时" in reason else "Error"
            return {"success": False, "message": reason}

        # 6. 天平门复位（关闭）+ Z轴复位至最高，等待完成
        self._write_single_register(REG_DOOR_RESET, 1)
        self._wait_axis_idle(REG_DOOR_STATUS, timeout=30.0)
        self._write_single_register(REG_Z_RESET, 1)
        self._wait_axis_idle(REG_Z_STATUS, timeout=30.0)

        self.data["status"] = "Ready"

        # 7. 可选：读取天平回传的实际质量
        actual_mg = None
        if read_actual_weight:
            actual = self._read_u32(REG_LAST_WEIGHT_HI)
            actual_mg = actual / WEIGHT_SCALE if actual is not None else None
            self.data["last_dispensed_mg"] = actual_mg or 0.0
            logger.info("加样完成: 实际 %.1fmg", actual_mg or 0.0)
        else:
            logger.info("加样完成")

        return {
            "success": True,
            "target_mg": weight_mg,
            "actual_mg": actual_mg,
        }

    @action(description="仅开始加样（不等待完成）")
    def start_dispensing(self) -> Dict[str, Any]:
        """需先通过其他指令设定好质量和Z轴位置"""
        ok = self._write_single_register(REG_START, 1)
        if ok:
            self.data["status"] = "Dispensing"
        return {"success": ok}

    @action(description="中止当前加样")
    def abort_dispensing(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_ABORT, 1)
        self.data["status"] = "Aborted" if ok else "Error"
        return {"success": ok}

    # ═══════════════════ 急停 ═══════════════════

    @action(description="急停所有运动")
    def emergency_stop_all(self) -> Dict[str, Any]:
        ok = self._write_single_register(REG_ESTOP, 0)
        self.data["status"] = "E-Stop"
        return {"success": ok}

    @action(description="急停天平门")
    def emergency_stop_door(self) -> Dict[str, Any]:
        return {"success": self._write_single_register(REG_ESTOP, 2)}

    @action(description="急停Z轴")
    def emergency_stop_z(self) -> Dict[str, Any]:
        return {"success": self._write_single_register(REG_ESTOP, 3)}

    # ═══════════════════ 状态查询 ═══════════════════

    @action(description="读取设备完整状态")
    def read_all_status(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        regs = self._read_registers(REG_RUNNING_STATUS, 1)
        result["running"] = regs[0] == 0 if regs else None

        w = self._read_u32(REG_BALANCE_WEIGHT_HI)
        result["balance_weight_mg"] = w / WEIGHT_SCALE if w is not None else None

        for name, reg in [("door", REG_DOOR_STATUS), ("z_axis", REG_Z_STATUS), ("motor", REG_MOTOR_STATUS)]:
            r = self._read_registers(reg, 1)
            code = r[0] if r else None
            result[f"{name}_status"] = AXIS_STATUS_MAP.get(code, "未知") if code is not None else "未知"

        mode = self._read_registers(REG_DISPENSE_MODE, 1)
        result["mode"] = {1: "精细", 2: "标准"}.get(mode[0], "未知") if mode else "未知"

        self.data["balance_weight_mg"] = result.get("balance_weight_mg", 0.0) or 0.0
        self.data["door_status"] = result.get("door_status", "未知")
        self.data["z_status"] = result.get("z_axis_status", "未知")
        self.data["motor_status"] = result.get("motor_status", "未知")

        return {"success": True, **result}

    # ═══════════════════ 状态属性（前端 Topic） ═══════════════════

    @property
    @topic_config(period=3.0)
    def status(self) -> str:
        return self.data.get("status", "Idle")

    @property
    @topic_config(period=3.0)
    def balance_weight_mg(self) -> float:
        return self.data.get("balance_weight_mg", 0.0)

    @property
    @topic_config(period=5.0)
    def last_dispensed_mg(self) -> float:
        return self.data.get("last_dispensed_mg", 0.0)

    @property
    @topic_config(period=5.0)
    def door_status(self) -> str:
        return self.data.get("door_status", "未知")

    @property
    @topic_config(period=5.0)
    def z_status(self) -> str:
        return self.data.get("z_status", "未知")


# ═══════════════════ 本地调试 ═══════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

    dev = ApdSvDispenser(config={"port": "COM6", "baudrate": 115200, "slave_addr": 1})
    print(dev.connect())
    print(dev.reset_all())
    print(dev.tare_balance())
    print(dev.dispense(weight_mg=1, z_height_mm=30.0, mode=2))
    print(dev.disconnect())

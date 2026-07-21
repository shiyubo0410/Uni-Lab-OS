"""
JYHSM 一体化温度变送器驱动
厂家：安徽久跃仪表有限公司
通信协议：Modbus RTU (RS485)
默认参数：9600, 8N1, 从站地址 1

寄存器映射：
  - 0x0000: 实时值*100，有符号整型
  - 0x0001: 实时值*10，有符号整型
  - 0x0002-0x0003: 实时浮点值，ABCD 格式，32-bit IEEE754
  - 0x0108-0x0109: 偏移值，浮点，ABCD 格式
  - 0x012C: 从站地址，1~247
  - 0x012D: 波特率，0~7 对应 1200~115200
  - 0x012E: 校验位，0=None, 1=Odd, 2=Even
  - 0x012F: 小数位数，0~3
  - 0x0130: 单位，11=℃, 12=℉
  - 0x0131: ADC 速率，10 或 40 Hz

说明：
  - 兼容 UniLab sensor 物模型：value/read_value。
  - temperature 和 value 同步更新。
  - 后台温度监控使用 threading.Thread，避免 UniLab 动作线程中 no running event loop。
"""

import asyncio
import logging
import struct
import threading
import time as time_module
from typing import Any, Dict, List, Tuple

try:
    import serial
except ImportError:  # pragma: no cover
    serial = None

try:
    from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode
except ImportError:  # pragma: no cover
    BaseROS2DeviceNode = None

try:
    from unilabos.registry.decorators import device, action, topic_config, not_action
except ImportError:  # pragma: no cover
    def device(**kwargs):
        def wrapper(cls):
            return cls
        return wrapper
    def action(**kwargs):
        def wrapper(func):
            return func
        return wrapper
    def topic_config(**kwargs):
        def wrapper(func):
            return func
        return wrapper
    def not_action(func):
        return func


# ==================== Modbus RTU 工具函数 ====================

def _crc16_modbus(data: bytes) -> int:
    """计算 Modbus RTU CRC16 校验码。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _build_read_request(slave_addr: int, func_code: int, start_reg: int, reg_count: int) -> bytes:
    """构建 Modbus RTU 读请求帧。"""
    frame = struct.pack(">BBHH", int(slave_addr), int(func_code), int(start_reg), int(reg_count))
    crc = _crc16_modbus(frame)
    return frame + struct.pack("<H", crc)


def _build_write_single_request(slave_addr: int, reg_addr: int, value: int) -> bytes:
    """构建 Modbus RTU 写单寄存器请求帧，功能码 06H。"""
    frame = struct.pack(">BBHH", int(slave_addr), 0x06, int(reg_addr), int(value) & 0xFFFF)
    crc = _crc16_modbus(frame)
    return frame + struct.pack("<H", crc)


def _build_write_multiple_request(slave_addr: int, start_reg: int, values: List[int]) -> bytes:
    """构建 Modbus RTU 写多寄存器请求帧，功能码 10H。"""
    reg_count = len(values)
    byte_count = reg_count * 2
    frame = struct.pack(">BBHHB", int(slave_addr), 0x10, int(start_reg), reg_count, byte_count)
    for value in values:
        frame += struct.pack(">H", int(value) & 0xFFFF)
    crc = _crc16_modbus(frame)
    return frame + struct.pack("<H", crc)


def _validate_response(resp: bytes, slave_addr: int, func_code: int) -> bytes:
    """
    验证 Modbus RTU 响应帧，并返回数据区 payload。
    先定位帧头，避免 RS485 总线前导噪声或回声导致解析偏移。
    """
    if not resp or len(resp) < 5:
        raise ValueError(f"响应帧过短或为空: {resp}")

    header = bytes([int(slave_addr), int(func_code)])
    start = resp.find(header)

    if start < 0:
        err_header = bytes([int(slave_addr), int(func_code) | 0x80])
        err_start = resp.find(err_header)
        if err_start >= 0 and len(resp) >= err_start + 5:
            err_code = resp[err_start + 2]
            raise ValueError(f"Modbus 异常响应: 功能码={hex(func_code)}, 异常码={hex(err_code)}")
        raise ValueError(f"响应中未找到帧头 [{hex(slave_addr)}, {hex(func_code)}]: {resp.hex()}")

    frame = resp[start:]

    if func_code in (0x03, 0x04):
        if len(frame) < 5:
            raise ValueError(f"读响应帧过短: {frame.hex()}")
        byte_count = frame[2]
        expected_len = 3 + byte_count + 2
        if len(frame) < expected_len:
            raise ValueError(f"读响应帧长度不足: 期望 {expected_len}, 实际 {len(frame)}")
        payload = frame[:expected_len]
        crc_received = struct.unpack("<H", payload[-2:])[0]
        crc_calculated = _crc16_modbus(payload[:-2])
        if crc_received != crc_calculated:
            raise ValueError(f"CRC 校验失败: 接收={hex(crc_received)}, 计算={hex(crc_calculated)}")
        return payload[3:-2]

    if func_code in (0x06, 0x10):
        expected_len = 8
        if len(frame) < expected_len:
            raise ValueError(f"写响应帧长度不足: 期望 {expected_len}, 实际 {len(frame)}")
        payload = frame[:expected_len]
        crc_received = struct.unpack("<H", payload[-2:])[0]
        crc_calculated = _crc16_modbus(payload[:-2])
        if crc_received != crc_calculated:
            raise ValueError(f"CRC 校验失败: 接收={hex(crc_received)}, 计算={hex(crc_calculated)}")
        return payload[2:-2]

    raise ValueError(f"不支持的功能码: {hex(func_code)}")


def _decode_float_abcd(high_word: int, low_word: int) -> float:
    """两个 16-bit 寄存器值解码为 IEEE754 浮点数，ABCD 大端格式。"""
    raw = struct.pack(">HH", int(high_word) & 0xFFFF, int(low_word) & 0xFFFF)
    return float(struct.unpack(">f", raw)[0])


def _encode_float_abcd(value: float) -> Tuple[int, int]:
    """浮点数编码为两个 16-bit 寄存器值，ABCD 大端格式。"""
    raw = struct.pack(">f", float(value))
    return struct.unpack(">HH", raw)


# ==================== 常量映射 ====================

BAUDRATE_MAP = {
    0: 1200.0,
    1: 2400.0,
    2: 4800.0,
    3: 9600.0,
    4: 19200.0,
    5: 38400.0,
    6: 57600.0,
    7: 115200.0,
}
BAUDRATE_REVERSE_MAP = {v: k for k, v in BAUDRATE_MAP.items()}
UNIT_MAP = {11.0: "℃", 12.0: "℉"}


@device(
    id="jyhsm_temperature_transmitter",
    category=["sensor"],
    description="JYHSM 一体化温度变送器 (Modbus RTU, RS485)",
    display_name="JYHSM温度变送器",
)
class JyhsmTemperatureTransmitter:
    """JYHSM 一体化温度变送器 Modbus RTU 驱动。"""

    _ros_node: "BaseROS2DeviceNode"

    def __init__(
        self,
        device_id: str = None,
        port: str = "COM4",
        baudrate: int = 9600,
        slave_address: int = 7,
        timeout: float = 1.0,
        monitor_interval: float = 1.0,
        **kwargs,
    ):
        """JYHSM 一体化温度变送器驱动 (Modbus RTU)。

        Args:
            device_id: 设备唯一标识。
            port: RS-485 串口号，例如 COM4 或 /dev/ttyUSB0。
            baudrate: 串口波特率，默认 9600。
            slave_address: Modbus 从站地址，默认 7。
            timeout: 串口读超时时间，单位秒。
            monitor_interval: 后台温度轮询周期，单位秒。
        """
        if device_id is None and "id" in kwargs:
            device_id = kwargs.pop("id")
        # 兼容旧的 config 字典传参：平铺参数优先，config 兜底。
        config = kwargs.pop("config", None) or {}

        self.device_id = device_id or "jyhsm_temp_1"
        self.config = config
        self.logger = logging.getLogger(f"JyhsmTemp.{self.device_id}.jyhsm_temperature_transmitter")
        self._ros_node = None

        self._port = str(config.get("port", port))
        self._baudrate = float(config.get("baudrate", baudrate))
        self._slave_address = int(config.get("slave_address", config.get("slave_id", slave_address)))
        self._timeout = float(config.get("timeout", timeout))
        self._serial = None
        self._serial_lock = threading.Lock()

        self._monitoring_thread = None
        self._monitoring_internal = False
        self._monitor_interval = float(config.get("monitor_interval", monitor_interval))

        # self.data 必须预填充所有属性字段。
        # value 是 sensor 通用字段；temperature 是温度计语义字段，二者同步更新。
        self.data: Dict[str, Any] = {
            "status": "Idle",
            "value": 0.0,
            "temperature": 0.0,
            "target_temperature": -999.0,
            "tolerance": 0.5,
            "monitoring": False,
            "alarm_triggered": False,
            "alarm_status": "Idle",
            "offset": 0.0,
            "unit": "℃",
            "slave_address": float(self._slave_address),
            "baudrate": float(self._baudrate),
        }

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode"):
        self._ros_node = ros_node

    # ==================== 属性 ====================

    @property
    def status(self) -> str:
        return str(self.data.get("status", "Idle"))

    @property
    def value(self) -> float:
        return float(self.data.get("value", 0.0))

    @property
    def temperature(self) -> float:
        return float(self.data.get("temperature", 0.0))

    @property
    def target_temperature(self) -> float:
        return float(self.data.get("target_temperature", -999.0))

    @property
    def tolerance(self) -> float:
        return float(self.data.get("tolerance", 0.5))

    @property
    def monitoring(self) -> bool:
        return bool(self.data.get("monitoring", False))

    @property
    def alarm_triggered(self) -> bool:
        return bool(self.data.get("alarm_triggered", False))

    @property
    def alarm_status(self) -> str:
        return str(self.data.get("alarm_status", "Idle"))

    @property
    def offset(self) -> float:
        return float(self.data.get("offset", 0.0))

    @property
    def unit(self) -> str:
        return str(self.data.get("unit", "℃"))

    @property
    def slave_address(self) -> float:
        return float(self.data.get("slave_address", 1.0))

    @property
    def baudrate(self) -> float:
        return float(self.data.get("baudrate", 9600.0))

    # ==================== 串口通信 ====================

    def _open_serial(self):
        if serial is None:
            raise ImportError("pyserial 未安装，请先安装 pyserial")
        if self._serial is not None and self._serial.is_open:
            return
        self._serial = serial.Serial(
            port=self._port,
            baudrate=int(self._baudrate),
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self._timeout,
        )

    def _close_serial(self):
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def _send_and_receive(self, request: bytes, expected_resp_len: int = 64) -> bytes:
        self._open_serial()
        with self._serial_lock:
            self._serial.reset_input_buffer()
            self.logger.info(f"[TX] {request.hex(' ')}")
            self._serial.write(request)
            self._serial.flush()
            time_module.sleep(0.05)
            resp = self._serial.read(expected_resp_len)
            self.logger.info(f"[RX] {resp.hex(' ')}")
            return resp

    def _read_registers(self, start_reg: int, reg_count: int, func_code: int = 0x03) -> bytes:
        request = _build_read_request(self._slave_address, func_code, start_reg, reg_count)
        resp = self._send_and_receive(request, expected_resp_len=5 + reg_count * 2 + 10)
        return _validate_response(resp, self._slave_address, func_code)

    def _write_single_register(self, reg_addr: int, value: int):
        request = _build_write_single_request(self._slave_address, reg_addr, value)
        resp = self._send_and_receive(request, expected_resp_len=20)
        _validate_response(resp, self._slave_address, 0x06)

    def _write_multiple_registers(self, start_reg: int, values: List[int]):
        request = _build_write_multiple_request(self._slave_address, start_reg, values)
        resp = self._send_and_receive(request, expected_resp_len=20)
        _validate_response(resp, self._slave_address, 0x10)

    async def _sleep(self, seconds: float):
        if self._ros_node is not None:
            await self._ros_node.sleep(float(seconds))
        else:
            await asyncio.sleep(float(seconds))

    # ==================== 温度读取核心 ====================

    def _read_temperature_once(self) -> float:
        """同步读取一次温度，并更新 self.data。供 async 动作和后台线程共用。"""
        data = self._read_registers(0x0002, 2, func_code=0x03)
        high_word = struct.unpack(">H", data[0:2])[0]
        low_word = struct.unpack(">H", data[2:4])[0]
        temp = _decode_float_abcd(high_word, low_word)

        self.data["temperature"] = float(temp)
        self.data["value"] = float(temp)

        self.logger.info(f"[TEMP] {temp:.3f} {self.data.get('unit', '℃')}")
        return float(temp)

    # ==================== UniLab 动作 ====================

    @action()
    async def initialize(self) -> bool:
        try:
            self.data["status"] = "Busy"
            self._open_serial()
            result = await self.read_temperature()
            if not result.get("success", False):
                self.data["status"] = "Error"
                return False
            self.data["status"] = "Idle"
            return True
        except Exception as exc:
            self.data["status"] = "Error"
            self.logger.error(f"初始化失败: {exc}")
            return False

    @action()
    async def cleanup(self) -> bool:
        await self.stop_temperature_monitoring()
        self._close_serial()
        self.data["status"] = "Offline"
        return True

    @action()
    async def read_temperature(self) -> Dict[str, Any]:
        """读取当前温度，返回包含 success/value/temperature/unit 的字典。"""
        try:
            self.data["status"] = "Busy"
            temp = self._read_temperature_once()
            self.data["status"] = "Idle"
            return {
                "success": True,
                "temperature": float(temp),
                "value": float(temp),
                "unit": self.data.get("unit", "℃"),
            }
        except Exception as exc:
            self.data["status"] = "Error"
            self.logger.error(f"读取温度失败: {exc}")
            return {
                "success": False,
                "message": str(exc),
                "temperature": float(self.data.get("temperature", 0.0)),
                "value": float(self.data.get("value", 0.0)),
                "unit": self.data.get("unit", "℃"),
            }

    @action()
    async def read_value(self) -> Dict[str, Any]:
        """sensor 物模型通用读取接口。"""
        return await self.read_temperature()

    @action()
    async def set_target_temperature(self, target: float) -> bool:
        try:
            self.data["target_temperature"] = float(target)
            return True
        except Exception as exc:
            self.logger.error(f"设置目标温度失败: {exc}")
            return False

    @action()
    async def set_tolerance(self, tolerance: float) -> bool:
        try:
            self.data["tolerance"] = abs(float(tolerance))
            return True
        except Exception as exc:
            self.logger.error(f"设置误差范围失败: {exc}")
            return False

    def _monitor_temperature_thread_loop(self, target: float, tolerance: float, timeout: float):
        """后台线程循环读取温度。"""
        start_time = time_module.time()
        self.data["alarm_status"] = "Monitoring"
        self.data["monitoring"] = True

        try:
            while self._monitoring_internal:
                try:
                    current_temp = self._read_temperature_once()
                    self.data["status"] = "Idle"

                    if abs(current_temp - float(target)) <= float(tolerance):
                        self.data["alarm_triggered"] = True
                        self.data["alarm_status"] = "Reached"
                        self._monitoring_internal = False
                        break

                    if float(timeout) > 0.0 and (time_module.time() - start_time) > float(timeout):
                        self.data["alarm_status"] = "Timeout"
                        self._monitoring_internal = False
                        break

                    time_module.sleep(self._monitor_interval)

                except Exception as exc:
                    self.data["status"] = "Error"
                    self.data["alarm_status"] = "Error"
                    self.logger.error(f"温度监控读取失败: {exc}")
                    self._monitoring_internal = False
                    break
        finally:
            self.data["monitoring"] = False
            if self.data.get("status") == "Busy":
                self.data["status"] = "Idle"

    @action()
    async def start_temperature_monitoring(self, target: float, tolerance: float = 0.5, timeout: float = 0.0) -> bool:
        """开始后台监控温度，后台线程持续更新 temperature/value。"""
        try:
            await self.stop_temperature_monitoring()

            self.data["target_temperature"] = float(target)
            self.data["tolerance"] = abs(float(tolerance))
            self.data["monitoring"] = True
            self.data["alarm_triggered"] = False
            self.data["alarm_status"] = "Monitoring"
            self.data["status"] = "Idle"
            self._monitoring_internal = True

            self._monitoring_thread = threading.Thread(
                target=self._monitor_temperature_thread_loop,
                args=(float(target), abs(float(tolerance)), float(timeout)),
                daemon=True,
            )
            self._monitoring_thread.start()
            return True
        except Exception as exc:
            self.data["monitoring"] = False
            self.data["alarm_status"] = "Error"
            self.data["status"] = "Error"
            self.logger.error(f"启动温度监控失败: {exc}")
            return False

    @action()
    async def stop_temperature_monitoring(self) -> bool:
        """停止温度监控。"""
        try:
            self._monitoring_internal = False
            if self._monitoring_thread is not None and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=2.0)
            self._monitoring_thread = None
            self.data["monitoring"] = False
            if self.data.get("alarm_status") == "Monitoring":
                self.data["alarm_status"] = "Cancelled"
            self.data["status"] = "Idle"
            return True
        except Exception as exc:
            self.logger.error(f"停止温度监控失败: {exc}")
            return False

    @action()
    async def wait_for_temperature(self, target: float, tolerance: float = 0.5, timeout: float = 300.0) -> bool:
        """阻塞等待温度达到目标值，用于工作流串联。"""
        try:
            self.data["status"] = "Busy"
            self.data["target_temperature"] = float(target)
            self.data["tolerance"] = abs(float(tolerance))
            self.data["monitoring"] = True
            self.data["alarm_triggered"] = False
            self.data["alarm_status"] = "Monitoring"
            self._monitoring_internal = True

            start_time = time_module.time()
            while self._monitoring_internal:
                result = await self.read_temperature()
                if not result.get("success", False):
                    self.data["alarm_status"] = "Error"
                    self.data["monitoring"] = False
                    self.data["status"] = "Error"
                    return False

                current_temp = float(result["temperature"])
                if abs(current_temp - float(target)) <= abs(float(tolerance)):
                    self.data["alarm_triggered"] = True
                    self.data["alarm_status"] = "Reached"
                    self.data["monitoring"] = False
                    self.data["status"] = "Idle"
                    self._monitoring_internal = False
                    return True

                if float(timeout) > 0.0 and (time_module.time() - start_time) > float(timeout):
                    self.data["alarm_status"] = "Timeout"
                    self.data["monitoring"] = False
                    self.data["status"] = "Idle"
                    self._monitoring_internal = False
                    return False

                await self._sleep(self._monitor_interval)

            self.data["monitoring"] = False
            self.data["status"] = "Idle"
            return False
        except asyncio.CancelledError:
            self.data["alarm_status"] = "Cancelled"
            self.data["monitoring"] = False
            self.data["status"] = "Idle"
            raise
        except Exception as exc:
            self.data["alarm_status"] = "Error"
            self.data["monitoring"] = False
            self.data["status"] = "Error"
            self.logger.error(f"等待温度失败: {exc}")
            return False

    @action()
    async def set_offset(self, offset: float) -> bool:
        """设置温度偏移值。"""
        try:
            self.data["status"] = "Busy"
            high_word, low_word = _encode_float_abcd(float(offset))
            self._write_multiple_registers(0x0108, [high_word, low_word])
            self.data["offset"] = float(offset)
            self.data["status"] = "Idle"
            return True
        except Exception as exc:
            self.data["status"] = "Error"
            self.logger.error(f"设置偏移失败: {exc}")
            return False

    @action()
    async def set_unit(self, unit: float) -> bool:
        """设置单位：11=℃，12=℉。"""
        try:
            unit_code = int(float(unit))
            if float(unit_code) not in UNIT_MAP:
                self.data["status"] = "Error"
                self.logger.error(f"不支持的单位代码: {unit}")
                return False
            self.data["status"] = "Busy"
            self._write_single_register(0x0130, unit_code)
            self.data["unit"] = UNIT_MAP.get(float(unit_code), "℃")
            self.data["status"] = "Idle"
            return True
        except Exception as exc:
            self.data["status"] = "Error"
            self.logger.error(f"设置单位失败: {exc}")
            return False

    @action()
    async def set_slave_address(self, address: float) -> bool:
        """设置从站地址，范围 1~247。写入后新地址立即生效。"""
        try:
            address_int = int(float(address))
            if address_int < 1 or address_int > 247:
                self.data["status"] = "Error"
                self.logger.error(f"地址超出范围: {address}")
                return False
            self.data["status"] = "Busy"
            self._write_single_register(0x012C, address_int)
            self._slave_address = address_int
            self.data["slave_address"] = float(address_int)
            self.data["status"] = "Idle"
            return True
        except Exception as exc:
            self.data["status"] = "Error"
            self.logger.error(f"设置从站地址失败: {exc}")
            return False

    @action()
    async def set_baudrate(self, baudrate: float) -> bool:
        """设置波特率。支持 1200~115200 的说明书列举值。"""
        try:
            baudrate_float = float(baudrate)
            code = BAUDRATE_REVERSE_MAP.get(baudrate_float)
            if code is None:
                self.data["status"] = "Error"
                self.logger.error(f"不支持的波特率: {baudrate}")
                return False

            self.data["status"] = "Busy"
            self._write_single_register(0x012D, int(code))
            self._close_serial()
            self._baudrate = baudrate_float
            self.data["baudrate"] = baudrate_float
            self.data["status"] = "Idle"
            return True
        except Exception as exc:
            self.data["status"] = "Error"
            self.logger.error(f"设置波特率失败: {exc}")
            return False

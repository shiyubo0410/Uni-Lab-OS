# -*- coding: utf-8 -*-
"""
FG100M 智能气体变送器驱动 (Modbus RTU)

厂商：福州锐思可智能科技有限公司 (www.ruisc.com)
功能：连续在线监测可燃气体 / 氧气 / 有毒气体浓度，同时支持温度、湿度测量
通信：RS485 ModBus RTU，默认 9600 8N1，默认从机地址 1（1~0x7F）

寄存器列表（功能码 0x03 读取）：
    0x0200 R 气体浓度值      (uint16)
    0x0201 R 温度值          (int16，带符号)
    0x0202 R 湿度值          (uint16，0~10000)
    0x0203 R 报警状态        (0-正常 / 1-高报警 / 2-低报警 / 3-故障)
    0x0204 R 浓度单位        (0-VOL% / 1-%LEL / 2-PPM / 3-mg/m3)
    0x0205 R 浓度小数点位数  (0-3)
    0x0206 R 温度小数点位数  (默认 1)
    0x0207 R 湿度小数点位数  (默认 1)
    0x0208 R 模块 SN 号      (字符型 4 字节，占 2 寄存器)
    0x020C R 气体物质名称
    0x020D R 高报警设置值
    0x020E R 低报警设置值
    0x020F R 满量程

写寄存器（功能码 0x06）：
    0x800F W 写入 0x5566 后才允许修改下面的寄存器
    0x0010 W RS485 地址 (1~0x7F，默认 1)
    0x0011 W 通讯波特率   (1=2400 / 2=4800 / 3=9600 / 4=115200)

注意：上电后约 20s 自检 + 热机；部分传感器在断电后需 2 小时热机时间。
"""

import logging
import struct
import threading
import time
from typing import Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config


UNIT_MAP = {
    0: "VOL%",
    1: "%LEL",
    2: "PPM",
    3: "mg/m3",
}

ALARM_MAP = {
    0: "Normal",
    1: "HighAlarm",
    2: "LowAlarm",
    3: "Fault",
}

BAUDRATE_CODE_MAP = {
    2400: 0x0001,
    4800: 0x0002,
    9600: 0x0003,
    115200: 0x0004,
}

WRITE_ENABLE_REG = 0x800F
WRITE_ENABLE_KEY = 0x5566


def _calc_crc16(data: bytes) -> bytes:
    """计算 Modbus CRC16，返回小端序 2 字节"""
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
    id="sensor.ruisc.fg100m",
    category=["sensor"],
    description="FG100M 智能气体变送器 (RS485 ModBus RTU，可测气体浓度/温度/湿度)",
    display_name="锐思可 FG100M 气体变送器",
)
class FG100M:
    """
    锐思可 FG100M 智能气体变送器驱动

    通过 Modbus RTU 协议读取气体浓度、温湿度、报警状态等信息。
    支持同一 RS485 总线上挂接多个变送器（不同从机地址）。
    """

    def __init__(
        self,
        port: str = "COM6",
        baudrate: int = 9600,
        device_id: int = 1,
        timeout: float = 1.0,
        auto_connect: bool = True,
    ):
        """
        初始化 FG100M 变送器。

        Args:
            port[串口路径]: RS485 串口设备名，例如 COM6 或 /dev/ttyUSB0。
            baudrate[波特率]: 通讯波特率，默认 9600。
            device_id[从机地址]: Modbus 从机地址，范围 1~127，默认 1。
            timeout[超时(秒)]: 读取超时时间，默认 1.0 秒。
            auto_connect[自动连接]: 实例化时是否立即打开串口。
        """
        self.port = port
        self.baudrate = int(baudrate)
        self.device_id = int(device_id)
        self.timeout = float(timeout)

        self.logger = logging.getLogger(f"FG100M[{self.device_id}@{self.port}]")

        self._lock = threading.Lock()
        self._serial: Optional[serial.Serial] = None
        self._is_connected = False
        # hardware_interface: 健康检查约定 — 成功打开串口时为 Serial 对象，失败时为 port 字符串
        # DeviceWorker 的 _driver_is_healthy 据此判断重连是否成功
        self.hardware_interface: Any = port

        # 缓存的实时值
        self._gas_concentration: float = 0.0
        self._gas_unit: str = "PPM"
        self._gas_unit_code: int = 2
        self._temperature: float = 0.0
        self._humidity: float = 0.0
        self._alarm_status: str = "Normal"
        self._alarm_code: int = 0
        self._gas_decimals: int = 0
        self._temp_decimals: int = 1
        self._humi_decimals: int = 1
        self._last_error: str = ""

        if auto_connect and self.port:
            try:
                self._do_connect()
            except Exception as exc:
                self.logger.warning(f"自动连接 FG100M 失败: {exc}")

    # ---------- 内部方法 ----------

    @not_action
    def _do_connect(self) -> bool:
        """建立串口连接"""
        if self._is_connected and self._serial and self._serial.is_open:
            return True
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            self._is_connected = self._serial.is_open
            if self._is_connected:
                self.hardware_interface = self._serial
                self.logger.info(f"已连接到 {self.port} @ {self.baudrate} baud")
            return self._is_connected
        except Exception as exc:
            self._last_error = f"connect: {exc}"
            self.logger.error(self._last_error)
            self._is_connected = False
            self.hardware_interface = self.port
            return False

    @not_action
    def _send_recv(self, request: bytes, expected_len: int) -> Optional[bytes]:
        """发送 Modbus 请求并读取响应"""
        if not self._is_connected or self._serial is None or not self._serial.is_open:
            if not self._do_connect():
                return None
        with self._lock:
            try:
                self._serial.reset_input_buffer()
                self._serial.write(request)
                response = self._serial.read(expected_len)
                if len(response) != expected_len:
                    # 可能是异常响应（功能码 MSB 置 1，长度为 5）
                    if len(response) == 5 and (response[1] & 0x80):
                        err_code = response[2]
                        self._last_error = f"modbus exception 0x{err_code:02X}"
                        self.logger.debug(f"Modbus 异常响应: {response.hex()}")
                    return None
                return response
            except Exception as exc:
                self._last_error = f"send: {exc}"
                self.logger.error(self._last_error)
                self._is_connected = False
                # 抛出异常让 DeviceWorker 感知 IO 错误并触发重连逻辑
                raise

    @not_action
    def _read_registers(self, start_addr: int, count: int) -> Optional[bytes]:
        """
        读取连续保持寄存器，返回原始数据部分（去掉地址/功能码/字节数/CRC）。

        :return: 长度为 count*2 的原始字节，失败返回 None
        """
        payload = struct.pack(">BBHH", self.device_id, 0x03, start_addr, count)
        request = payload + _calc_crc16(payload)
        # 响应：addr(1) + func(1) + byte_count(1) + data(count*2) + crc(2)
        expected_len = 5 + count * 2
        response = self._send_recv(request, expected_len=expected_len)
        if response is None:
            return None

        if response[0] != self.device_id or response[1] != 0x03 or response[2] != count * 2:
            self.logger.debug(f"响应头异常: {response.hex()}")
            self._last_error = "响应头异常"
            return None

        if response[-2:] != _calc_crc16(response[:-2]):
            self.logger.debug(f"CRC 校验失败: {response.hex()}")
            self._last_error = "CRC 校验失败"
            return None

        return bytes(response[3 : 3 + count * 2])

    @not_action
    def _write_register(self, addr: int, value: int) -> bool:
        """通过功能码 0x06 写入单个寄存器"""
        payload = struct.pack(">BBHH", self.device_id, 0x06, addr & 0xFFFF, value & 0xFFFF)
        request = payload + _calc_crc16(payload)
        response = self._send_recv(request, expected_len=8)
        if response is None:
            return False
        if response[-2:] != _calc_crc16(response[:-2]):
            self._last_error = "写寄存器 CRC 校验失败"
            return False
        # 正常响应是回显请求
        echo_addr = (response[2] << 8) | response[3]
        echo_value = (response[4] << 8) | response[5]
        return echo_addr == (addr & 0xFFFF) and echo_value == (value & 0xFFFF)

    @not_action
    def _enable_write(self) -> bool:
        """写保护使能：写入 0x5566 到 0x800F"""
        return self._write_register(WRITE_ENABLE_REG, WRITE_ENABLE_KEY)

    @not_action
    def _read_realtime(self) -> Optional[Dict[str, Any]]:
        """
        一次性读取 0x0200~0x0207 共 8 个寄存器，得到当前气体浓度、温湿度、报警、单位、小数点位数。
        并刷新缓存的状态值。
        """
        data = self._read_registers(0x0200, 8)
        if data is None or len(data) != 16:
            return None

        # 解析：8 个寄存器，前 1 个是 uint16 气体浓度，第 2 个是 int16 温度，其余 uint16
        raw_gas = struct.unpack(">H", data[0:2])[0]
        raw_temp = struct.unpack(">h", data[2:4])[0]
        raw_humi = struct.unpack(">H", data[4:6])[0]
        alarm_code = struct.unpack(">H", data[6:8])[0]
        unit_code = struct.unpack(">H", data[8:10])[0]
        gas_dp = struct.unpack(">H", data[10:12])[0]
        temp_dp = struct.unpack(">H", data[12:14])[0]
        humi_dp = struct.unpack(">H", data[14:16])[0]

        # 限定小数点位数在合理范围（说明书定义 0-3）
        gas_dp = max(0, min(gas_dp, 6))
        temp_dp = max(0, min(temp_dp, 6))
        humi_dp = max(0, min(humi_dp, 6))

        gas_value = raw_gas / (10 ** gas_dp)
        temp_value = raw_temp / (10 ** temp_dp)
        humi_value = raw_humi / (10 ** humi_dp)

        self._gas_concentration = gas_value
        self._gas_unit_code = unit_code
        self._gas_unit = UNIT_MAP.get(unit_code, f"Unit{unit_code}")
        self._temperature = temp_value
        self._humidity = humi_value
        self._alarm_code = alarm_code
        self._alarm_status = ALARM_MAP.get(alarm_code, f"Unknown({alarm_code})")
        self._gas_decimals = gas_dp
        self._temp_decimals = temp_dp
        self._humi_decimals = humi_dp

        return {
            "gas_concentration": gas_value,
            "gas_unit": self._gas_unit,
            "temperature": temp_value,
            "humidity": humi_value,
            "alarm_status": self._alarm_status,
            "alarm_code": alarm_code,
            "raw_gas": raw_gas,
            "raw_temperature": raw_temp,
            "raw_humidity": raw_humi,
            "gas_decimals": gas_dp,
            "temp_decimals": temp_dp,
            "humi_decimals": humi_dp,
        }

    # ---------- 连接管理 ----------

    @action(description="打开串口，连接 FG100M 变送器")
    def connect(self) -> Dict[str, Any]:
        ok = self._do_connect()
        return {
            "success": ok,
            "port": self.port,
            "baudrate": self.baudrate,
            "device_id": self.device_id,
            "message": "FG100M 已连接" if ok else f"连接失败: {self._last_error}",
        }

    @action(description="关闭串口，断开 FG100M 变送器")
    def disconnect(self) -> Dict[str, Any]:
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._is_connected = False
        self.hardware_interface = self.port
        return {"success": True, "message": "FG100M 已断开"}

    # ---------- 读取操作 ----------

    @action(description="读取气体浓度、温度、湿度与报警状态")
    def read(self) -> Dict[str, Any]:
        """
        读取并返回所有实时测量数据。
        """
        data = self._read_realtime()
        if data is None:
            return {
                "success": False,
                "message": f"读取失败: {self._last_error or '无响应或 CRC 错误'}",
            }
        return {
            "success": True,
            "gas_concentration": data["gas_concentration"],
            "gas_unit": data["gas_unit"],
            "temperature": data["temperature"],
            "humidity": data["humidity"],
            "alarm_status": data["alarm_status"],
            "alarm_code": data["alarm_code"],
            "message": (
                f"气体={data['gas_concentration']:.{self._gas_decimals}f}{data['gas_unit']}, "
                f"温度={data['temperature']:.{self._temp_decimals}f}℃, "
                f"湿度={data['humidity']:.{self._humi_decimals}f}%RH, "
                f"报警={data['alarm_status']}"
            ),
        }

    @action(description="读取气体浓度（含单位）")
    def read_gas_concentration(self) -> Dict[str, Any]:
        data = self._read_realtime()
        if data is None:
            return {"success": False, "message": f"读取失败: {self._last_error or '无响应'}"}
        return {
            "success": True,
            "value": data["gas_concentration"],
            "unit": data["gas_unit"],
            "message": f"{data['gas_concentration']:.{self._gas_decimals}f}{data['gas_unit']}",
        }

    @action(description="读取环境温度 (℃)")
    def read_temperature(self) -> Dict[str, Any]:
        data = self._read_realtime()
        if data is None:
            return {"success": False, "message": f"读取失败: {self._last_error or '无响应'}"}
        return {
            "success": True,
            "value": data["temperature"],
            "unit": "degC",
            "message": f"{data['temperature']:.{self._temp_decimals}f}℃",
        }

    @action(description="读取环境湿度 (%RH)")
    def read_humidity(self) -> Dict[str, Any]:
        data = self._read_realtime()
        if data is None:
            return {"success": False, "message": f"读取失败: {self._last_error or '无响应'}"}
        return {
            "success": True,
            "value": data["humidity"],
            "unit": "%RH",
            "message": f"{data['humidity']:.{self._humi_decimals}f}%RH",
        }

    @action(description="读取报警状态")
    def read_alarm(self) -> Dict[str, Any]:
        data = self._read_realtime()
        if data is None:
            return {"success": False, "message": f"读取失败: {self._last_error or '无响应'}"}
        return {
            "success": True,
            "alarm_status": data["alarm_status"],
            "alarm_code": data["alarm_code"],
            "message": data["alarm_status"],
        }

    @action(description="读取设备 SN、气体名称、报警阈值、满量程等信息")
    def read_device_info(self) -> Dict[str, Any]:
        """
        组合读取 0x0208~0x020F 的元信息：
            - 0x0208~0x0209: 4 字节 SN
            - 0x020C: 气体物质名称
            - 0x020D: 高报警阈值
            - 0x020E: 低报警阈值
            - 0x020F: 满量程
        """
        sn_bytes = self._read_registers(0x0208, 2)
        meta = self._read_registers(0x020C, 4)
        if sn_bytes is None or meta is None:
            return {"success": False, "message": f"读取失败: {self._last_error or '无响应'}"}

        sn = sn_bytes.rstrip(b"\x00").decode("ascii", errors="replace")
        gas_name_code = struct.unpack(">H", meta[0:2])[0]
        high_alarm_raw = struct.unpack(">H", meta[2:4])[0]
        low_alarm_raw = struct.unpack(">H", meta[4:6])[0]
        full_scale_raw = struct.unpack(">H", meta[6:8])[0]

        scale = 10 ** self._gas_decimals if self._gas_decimals else 1
        return {
            "success": True,
            "sn": sn,
            "gas_name_code": gas_name_code,
            "high_alarm": high_alarm_raw / scale,
            "low_alarm": low_alarm_raw / scale,
            "full_scale": full_scale_raw / scale,
            "gas_unit": self._gas_unit,
            "message": (
                f"SN={sn}, 气体码={gas_name_code}, 量程={full_scale_raw/scale}{self._gas_unit}, "
                f"高报={high_alarm_raw/scale}{self._gas_unit}, 低报={low_alarm_raw/scale}{self._gas_unit}"
            ),
        }

    # ---------- 配置操作 ----------

    @action(description="修改 RS485 从机地址 (1~127)，写入后需要复位电源")
    def set_address(self, new_address: int = 1) -> Dict[str, Any]:
        """
        Args:
            new_address[新从机地址]: 新的 Modbus 从机地址，范围 1~127。
        """
        addr = int(new_address)
        if not 1 <= addr <= 0x7F:
            return {"success": False, "message": f"地址超出范围: {addr} (1~127)"}

        if not self._enable_write():
            return {"success": False, "message": f"写使能失败: {self._last_error}"}

        ok = self._write_register(0x0010, addr)
        if ok:
            self.device_id = addr
            self.logger.info(f"从机地址已修改为 {addr}")
        return {
            "success": ok,
            "new_address": addr,
            "message": f"从机地址修改{'成功' if ok else '失败'}",
        }

    @action(description="修改通讯波特率 (2400/4800/9600/115200)，写入后需要复位电源")
    def set_baudrate(self, baudrate: int = 9600) -> Dict[str, Any]:
        """
        Args:
            baudrate[波特率]: 通讯波特率，支持 2400/4800/9600/115200。
        """
        baud = int(baudrate)
        if baud not in BAUDRATE_CODE_MAP:
            return {
                "success": False,
                "message": f"不支持的波特率: {baud}, 可选: {list(BAUDRATE_CODE_MAP.keys())}",
            }

        if not self._enable_write():
            return {"success": False, "message": f"写使能失败: {self._last_error}"}

        ok = self._write_register(0x0011, BAUDRATE_CODE_MAP[baud])
        if ok:
            self.logger.info(f"波特率已修改为 {baud}（设备复位后生效）")
        return {
            "success": ok,
            "new_baudrate": baud,
            "message": f"波特率修改{'成功' if ok else '失败'}，设备复位后生效",
        }

    # ---------- 状态属性（自动周期发布） ----------

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def gas_concentration(self) -> float:
        """气体浓度实际值 - 每 2 秒发布"""
        data = self._read_realtime()
        if data is None:
            raise RuntimeError(f"读取失败: {self._last_error or '无响应'}")
        return float(self._gas_concentration)

    @property
    @topic_config(period=5.0)
    def gas_unit(self) -> str:
        """气体浓度单位 - 每 5 秒发布"""
        if not self._is_connected:
            raise RuntimeError("设备未连接")
        return self._gas_unit

    @property
    @topic_config(period=2.0)
    def temperature(self) -> float:
        """环境温度 (℃) - 每 2 秒发布"""
        if not self._is_connected:
            raise RuntimeError("设备未连接")
        return float(self._temperature)

    @property
    @topic_config(period=2.0)
    def humidity(self) -> float:
        """环境湿度 (%RH) - 每 2 秒发布"""
        if not self._is_connected:
            raise RuntimeError("设备未连接")
        return float(self._humidity)

    @property
    @topic_config(period=2.0)
    def alarm_status(self) -> str:
        """报警状态 - 每 2 秒发布"""
        if not self._is_connected:
            raise RuntimeError("设备未连接")
        return self._alarm_status

    @property
    @topic_config(period=2.0)
    def status(self) -> str:
        """统一 status 字符串：Idle / Running / Error / 报警态"""
        if not self._is_connected:
            return "Error"
        # 优先暴露报警态，便于上层快速识别
        if self._alarm_code in (1, 2):
            return self._alarm_status
        if self._alarm_code == 3:
            return "Error"
        return "Idle"

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sensor = FG100M(port="COM6", device_id=1)

    try:
        info = sensor.read_device_info()
        print(f"[info] {info}")
        for i in range(10):
            result = sensor.read()
            print(f"[{i+1}] {result}")
            time.sleep(2)
    finally:
        sensor.disconnect()

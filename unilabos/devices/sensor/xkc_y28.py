# -*- coding: utf-8 -*-
"""
XKC-Y28 电导率/液位传感器驱动 (Modbus RTU)
简化版，无需 shared_bus 依赖，适用于网关独立部署

通信协议:
  读取数据:  TX [addr] 03 00 01 00 02 [CRC_L] [CRC_H]
             RX [addr] 03 04 [level_H] [level_L] [rssi_H] [rssi_L] [CRC_L] [CRC_H]

  level: 0x0000=无液, 0x0001=有液
  rssi:  信号强度 (0-1023)
"""

import logging
import struct
import threading
import time
from typing import Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config


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
    return struct.pack('<H', crc)


@device(
    id="sensor_xkc_y28",
    category=["sensor"],
    description="XKC-Y28 非接触式电导率/液位传感器 (Modbus RTU)",
    display_name="XKC-Y28 液位传感器",
)
class XKC_Y28:
    """
    XKC-Y28 非接触式液位传感器驱动

    通过 Modbus RTU 协议读取液位状态和信号强度 (RSSI)。
    支持同一 RS485 总线上挂接多个传感器（不同站号）。
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        device_id: int = 1,
        timeout: float = 1.0,
        auto_connect: bool = True,
    ):
        """
        :param port: 串口路径
        :param baudrate: 波特率 (默认 9600)
        :param device_id: Modbus 站号 (1-255)
        :param timeout: 读取超时 (秒)
        :param auto_connect: 是否自动连接
        """
        self.port = port
        self.baudrate = int(baudrate)
        self.device_id = int(device_id)
        self.timeout = float(timeout)

        self.logger = logging.getLogger(f"XKC_Y28[{device_id}@{port}]")

        self._lock = threading.Lock()
        self._serial: Optional[serial.Serial] = None
        self._is_connected = False
        # hardware_interface: 健康检查约定 — 成功打开串口时为 Serial 对象，失败时为 port 字符串
        # DeviceWorker 的 _driver_is_healthy 据此判断重连是否成功
        self.hardware_interface: Any = port

        self._liquid_detected: bool = False
        self._rssi: int = 0
        self._last_error: str = ""

        if auto_connect and self.port:
            try:
                self._do_connect()
            except Exception as exc:
                self.logger.warning(f"自动连接传感器失败: {exc}")

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
                # 健康检查标志：连接成功时 hardware_interface 指向 Serial 对象
                self.hardware_interface = self._serial
                self.logger.info(f"已连接到 {self.port} @ {self.baudrate} baud")
            return self._is_connected
        except Exception as exc:
            self._last_error = f"connect: {exc}"
            self.logger.error(self._last_error)
            self._is_connected = False
            # 连接失败时 hardware_interface 退化为 port 字符串，标记驱动不健康
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
                return response if len(response) == expected_len else None
            except Exception as exc:
                self._last_error = f"send: {exc}"
                self.logger.error(self._last_error)
                self._is_connected = False
                # 抛出异常让 DeviceWorker 感知 IO 错误并触发重连逻辑
                raise

    @not_action
    def _read_raw(self) -> Optional[Dict[str, Any]]:
        """执行一次 Modbus 读取并解析"""
        payload = struct.pack('>BBHH', self.device_id, 0x03, 0x0001, 0x0002)
        request = payload + _calc_crc16(payload)
        response = self._send_recv(request, expected_len=9)
        if response is None:
            return None

        addr, func, byte_count = response[0], response[1], response[2]
        if addr != self.device_id or func != 0x03 or byte_count != 0x04:
            self.logger.debug(f"响应头异常: {response.hex()}")
            return None

        if response[7:9] != _calc_crc16(response[:7]):
            self.logger.debug(f"CRC 校验失败: {response.hex()}")
            return None

        raw_level = (response[3] << 8) | response[4]
        rssi = (response[5] << 8) | response[6]

        self._liquid_detected = (raw_level == 0x0001)
        self._rssi = rssi
        return {"liquid_detected": self._liquid_detected, "rssi": rssi}

    # ---------- 动作 ----------

    @action(description="打开串口，连接传感器")
    def connect(self) -> Dict[str, Any]:
        ok = self._do_connect()
        return {
            "success": ok,
            "port": self.port,
            "baudrate": self.baudrate,
            "message": "传感器已连接" if ok else f"传感器连接失败: {self._last_error}",
        }

    @action(description="关闭串口，断开传感器")
    def disconnect(self) -> Dict[str, Any]:
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._is_connected = False
        return {"success": True, "message": "传感器已断开"}

    @action(description="读取液位和 RSSI 信号强度")
    def read(self) -> Dict[str, Any]:
        data = self._read_raw()
        if data is None:
            return {
                "success": False,
                "liquid_detected": False,
                "rssi": 0,
                "message": f"读取失败: {self._last_error or '无响应或 CRC 错误'}",
            }
        return {
            "success": True,
            "liquid_detected": data["liquid_detected"],
            "rssi": data["rssi"],
            "message": f"液位={'有液' if data['liquid_detected'] else '无液'}, RSSI={data['rssi']}",
        }

    @action(description="修改传感器 Modbus 站号 (1-255)，成功时 LED 会闪烁")
    def set_address(self, new_address: int = 1) -> Dict[str, Any]:
        addr = int(new_address)
        if not 1 <= addr <= 255:
            return {"success": False, "message": f"站号超出范围: {addr} (1-255)"}

        payload = struct.pack('>BBHH', self.device_id, 0x06, 0x0004, addr)
        request = payload + _calc_crc16(payload)
        response = self._send_recv(request, expected_len=7)
        if response is None:
            return {"success": False, "message": "无响应"}

        success = response[4] == (addr & 0xFF)
        if success:
            self.device_id = addr
            self.logger.info(f"站号已修改为 {addr}")
        return {
            "success": success,
            "new_address": addr,
            "message": f"站号修改{'成功' if success else '失败'}",
        }

    # ---------- 状态属性 ----------

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def liquid_detected(self) -> bool:
        """液位状态 - 每 2 秒发布"""
        data = self._read_raw()
        if data is None:
            raise RuntimeError(f"读取失败: {self._last_error or '无响应'}")
        return self._liquid_detected

    @property
    @topic_config(period=2.0)
    def rssi(self) -> int:
        """信号强度 - 每 2 秒发布"""
        # 确保设备已连接，否则抛出异常让 DeviceWorker 计数错误
        if not self._is_connected:
            raise RuntimeError("设备未连接")
        return self._rssi

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    sensor = XKC_Y28(port="/dev/ttyUSB0", device_id=1)

    try:
        for i in range(10):
            result = sensor.read()
            print(f"[{i+1}] {result}")
            time.sleep(1)
    finally:
        sensor.disconnect()

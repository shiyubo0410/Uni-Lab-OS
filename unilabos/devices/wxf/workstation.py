# -*- coding: utf-8 -*-
"""
WXF 工作站驱动
管理同一 RS485 总线上的 2 台润泽注射泵 + 2 个 XKC 液位传感器。

所有设备共享一个串口、一把线程锁，协议混合使用：
  - 注射泵: ASCII 协议 (/{addr}command\r\n)
  - 液位传感器: Modbus RTU 二进制协议
"""

import serial
import struct
import time
import threading
import logging
import re
from typing import Optional, Dict, Any, List

try:
    from unilabos.device_comms.universal_driver import UniversalDriver
except ImportError:
    class UniversalDriver:
        def __init__(self):
            self.logger = logging.getLogger(self.__class__.__name__)

        def execute_command_from_outer(self, command: str):
            pass


# ==============================================================================
# 共享串口总线
# ==============================================================================

class SharedBus:
    """
    RS485 共享总线。
    支持两种协议:
      - send_ascii(): ASCII 命令 (泵)
      - send_modbus(): 二进制帧 (传感器)
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 3.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.lock = threading.RLock()
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        )

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def close(self):
        if self._serial and self._serial.is_open:
            self._serial.close()

    def send_ascii(self, command: str) -> str:
        """发送 ASCII 命令，读取直到 \\n，返回原始响应字符串"""
        with self.lock:
            self._serial.reset_input_buffer()
            self._serial.write(command.encode("ascii"))
            time.sleep(0.05)
            raw = self._serial.read_until(b"\n")
            return "".join(chr(b) for b in raw)

    def send_modbus(self, request: bytes, expected_len: int) -> Optional[bytes]:
        """发送 Modbus RTU 二进制帧，返回响应；失败返回 None"""
        with self.lock:
            self._serial.reset_input_buffer()
            self._serial.write(request)
            response = self._serial.read(expected_len)
            return response if len(response) == expected_len else None


# ==============================================================================
# Modbus CRC16
# ==============================================================================

def _crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)


# ==============================================================================
# XKC 液位传感器节点
# ==============================================================================

class XKCSensor:
    """单个 XKC 液位传感器，绑定到 SharedBus"""

    def __init__(self, device_id: int, bus: SharedBus):
        self.device_id = device_id
        self.bus = bus

    def read(self) -> Optional[Dict[str, Any]]:
        payload = struct.pack('>BBHH', self.device_id, 0x03, 0x0001, 0x0002)
        request = payload + _crc16(payload)
        response = self.bus.send_modbus(request, expected_len=9)
        if response is None:
            return None
        if response[0] != self.device_id or response[1] != 0x03 or response[2] != 0x04:
            return None
        if response[7:9] != _crc16(response[:7]):
            return None
        raw_level = (response[3] << 8) | response[4]
        rssi = (response[5] << 8) | response[6]
        return {"liquid_detected": raw_level == 0x0001, "rssi": rssi}


# ==============================================================================
# 润泽注射泵节点
# ==============================================================================

class SyringePump:
    """单个润泽注射泵，绑定到 SharedBus"""

    LIQUID_SOURCE_MAP = {"液体1": 1, "液体2": 2, "液体3": 3}
    COLUMN_TARGET_MAP = {"柱1": 4, "柱2": 5, "柱3": 6}
    FIXED_VELOCITY = 5.0

    def __init__(self, address: str, bus: SharedBus, max_volume: float = 25.0):
        self.address = address
        self.bus = bus
        self.max_volume = max_volume
        self.total_steps = 6000
        self.total_steps_vel = 6000
        self._status = "Idle"

    def _query(self, command: str) -> str:
        run = "R" if "?" not in command else ""
        full = f"/{self.address}{command}{run}\r\n"
        raw = self.bus.send_ascii(full)
        return raw[3:-3] if len(raw) > 6 else raw

    def _standardize_status(self, s: str) -> str:
        return "Idle" if s == "`" else "Busy"

    def _run(self, command: str) -> str:
        response = self._query(command)
        while True:
            time.sleep(0.5)
            if self.get_status() == "Idle":
                break
        return response

    def get_status(self) -> str:
        raw = self._query("Q")
        self._status = self._standardize_status(raw)
        return self._status

    def initialize(self) -> str:
        return self._run("Z")

    def set_max_velocity(self, velocity: float):
        pulse_freq = min(6000, int(velocity / self.max_volume * self.total_steps_vel))
        return self._run(f"V{pulse_freq}")

    def set_valve_position(self, position) -> str:
        if isinstance(position, float):
            position = round(position / 120)
        cmd = f"I{position}" if isinstance(position, int) or (isinstance(position, str) and ord(position) <= 57) else str(position).upper()
        return self._run(cmd)

    def get_valve_position(self) -> str:
        raw = self._query("?6")
        return raw[1].upper() if len(raw) > 1 else raw

    def get_position(self) -> float:
        raw = self._query("?0")
        m = re.search(r'\d+', raw)
        pos_step = int(m.group()) if m else 0
        return pos_step / self.total_steps * self.max_volume

    def pull_plunger(self, volume: float) -> str:
        pos_step = int(volume / self.max_volume * self.total_steps)
        return self._run(f"P{pos_step}")

    def push_plunger(self, volume: float) -> str:
        pos_step = int(volume / self.max_volume * self.total_steps)
        return self._run(f"D{pos_step}")

    def set_position(self, position: float, max_velocity: float = None) -> str:
        vcmd = ""
        if max_velocity is not None:
            pulse_freq = min(6000, int(max_velocity / self.max_volume * self.total_steps_vel))
            vcmd = f"V{pulse_freq}"
        pos_step = int(position / self.max_volume * self.total_steps)
        return self._run(f"{vcmd}A{pos_step}")

    def stop(self) -> str:
        return self._run("T")


# ==============================================================================
# WXF 工作站
# ==============================================================================

class WxfWorkstation(UniversalDriver):
    """
    WXF 工作站：2 台润泽注射泵 + 2 个 XKC 液位传感器，共享一条 RS485 总线。
    """

    def __init__(
        self,
        port: str = "COM9",
        baudrate: int = 9600,
        pump_addresses: List[str] = None,
        pump_max_volume: float = 25.0,
        sensor_ids: List[int] = None,
        threshold: int = 0,
        timeout: float = 3.0,
        poll_interval: float = 0.5,
    ):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.pump_addresses = pump_addresses if pump_addresses else ["1", "2"]
        self.pump_max_volume = pump_max_volume
        self.sensor_ids = sensor_ids if sensor_ids else [1, 2]
        self.threshold = threshold
        self.timeout = timeout
        self.poll_interval = poll_interval

        self._bus: Optional[SharedBus] = None
        self._is_connected = False

        self.pumps: Dict[str, SyringePump] = {}
        self.sensors: Dict[int, XKCSensor] = {}
        self._sensor_cache: Dict[int, Dict[str, Any]] = {}

        self._stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

        if self.port:
            self.connect()

    # ------------------------------------------------------------------
    # 连接
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        if self._is_connected:
            return True
        try:
            self._bus = SharedBus(self.port, self.baudrate, self.timeout)
            for addr in self.pump_addresses:
                self.pumps[addr] = SyringePump(addr, self._bus, self.pump_max_volume)
            for sid in self.sensor_ids:
                self.sensors[sid] = XKCSensor(sid, self._bus)
                self._sensor_cache[sid] = {"liquid_detected": False, "rssi": 0}
            self._is_connected = True
            self.logger.info(
                f"WXF Workstation connected: {self.port} @ {self.baudrate}, "
                f"pumps={self.pump_addresses}, sensors={self.sensor_ids}"
            )
            self._start_polling()
            return True
        except Exception as e:
            self.logger.error(f"Connect failed: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)
        if self._bus:
            self._bus.close()
        self._is_connected = False
        self.logger.info("WXF Workstation disconnected.")

    # ------------------------------------------------------------------
    # 传感器轮询
    # ------------------------------------------------------------------

    def _start_polling(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._polling_loop, daemon=True, name="WxfPoll"
        )
        self._poll_thread.start()

    def _apply_threshold(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.threshold > 0:
            data = dict(data)
            data["liquid_detected"] = data["rssi"] > self.threshold
        return data

    def _polling_loop(self):
        while not self._stop_event.is_set():
            if not self._is_connected:
                time.sleep(1.0)
                continue
            for sid, sensor in self.sensors.items():
                data = sensor.read()
                if data:
                    self._sensor_cache[sid] = self._apply_threshold(data)
            time.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # 状态属性
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def liquid_detected(self) -> bool:
        if self.sensor_ids:
            return self._sensor_cache[self.sensor_ids[0]]["liquid_detected"]
        return False

    @property
    def rssi(self) -> int:
        if self.sensor_ids:
            return self._sensor_cache[self.sensor_ids[0]]["rssi"]
        return 0

    # ------------------------------------------------------------------
    # 泵操作
    # ------------------------------------------------------------------

    def pump_initialize(self, pump_address: str = "1") -> bool:
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            self.logger.error(f"Pump {pump_address} not found, available: {list(self.pumps.keys())}")
            return False
        self.pumps[pump_address].initialize()
        self.logger.info(f"Pump {pump_address} initialized.")
        return True

    def pump_set_valve(self, pump_address: str = "1", position: int = 1) -> bool:
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            return False
        self.pumps[pump_address].set_valve_position(int(position))
        self.logger.info(f"Pump {pump_address} valve -> {position}")
        return True

    def pump_pull(self, pump_address: str = "1", volume: float = 1.0) -> bool:
        """吸液"""
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            return False
        self.pumps[pump_address].pull_plunger(float(volume))
        self.logger.info(f"Pump {pump_address} pull {volume} mL")
        return True

    def pump_push(self, pump_address: str = "1", volume: float = 1.0) -> bool:
        """排液"""
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            return False
        self.pumps[pump_address].push_plunger(float(volume))
        self.logger.info(f"Pump {pump_address} push {volume} mL")
        return True

    def pump_set_velocity(self, pump_address: str = "1", velocity: float = 5.0) -> bool:
        """设置泵速 (mL/s)"""
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            return False
        self.pumps[pump_address].set_max_velocity(float(velocity))
        self.logger.info(f"Pump {pump_address} velocity -> {velocity} mL/s")
        return True

    def pump_stop(self, pump_address: str = "1") -> bool:
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            return False
        self.pumps[pump_address].stop()
        self.logger.info(f"Pump {pump_address} stopped.")
        return True

    def add_liquid(self, pump_address: str = "1", liquid_source: str = "液体1",
                   column_target: str = "柱1", volume: float = 1.0) -> bool:
        """
        加液操作：从指定液体口吸取 → 注入指定柱子。
        """
        pump_address = str(pump_address)
        if pump_address not in self.pumps:
            return False
        pump = self.pumps[pump_address]

        inlet = SyringePump.LIQUID_SOURCE_MAP.get(liquid_source)
        outlet = SyringePump.COLUMN_TARGET_MAP.get(column_target)
        if inlet is None or outlet is None:
            self.logger.error(f"Invalid source/target: {liquid_source}/{column_target}")
            return False

        pump.set_max_velocity(SyringePump.FIXED_VELOCITY)
        pump.set_valve_position(inlet)
        time.sleep(0.2)
        pump.pull_plunger(float(volume))
        time.sleep(0.3)
        pump.set_valve_position(outlet)
        time.sleep(0.2)
        pump.push_plunger(float(volume))
        self.logger.info(f"Pump {pump_address}: {liquid_source} -> {column_target}, {volume} mL done.")
        return True

    def add_sample(self, pump_address: str = "1", liquid_source: str = "液体1",
                   column_target: str = "柱1", volume: float = 1.0) -> bool:
        """
        加样品操作：从指定样品口吸取 → 注入指定柱子。
        """
        return self.add_liquid(pump_address, liquid_source, column_target, volume)

    # ------------------------------------------------------------------
    # 传感器操作
    # ------------------------------------------------------------------

    def read_sensor(self, device_id: int = 1) -> Dict[str, Any]:
        """立即读取指定站号传感器"""
        device_id = int(device_id)
        if device_id not in self.sensors:
            return {"liquid_detected": False, "rssi": 0, "error": "未配置该站号"}
        data = self.sensors[device_id].read()
        if data is None:
            return {"liquid_detected": False, "rssi": 0, "error": "读取失败"}
        return self._apply_threshold(data)

    def set_threshold(self, threshold: int = 0) -> bool:
        self.threshold = int(threshold)
        self.logger.info(f"Threshold set to {self.threshold}")
        return True

    def continuous_monitor(self, device_id: int = 1, threshold: int = 0,
                           duration: int = 0, interval: float = 0.5) -> bool:
        """
        对指定传感器进行连续液位检测，达到阈值时自动停止。
        """
        device_id = int(device_id)
        if device_id not in self.sensors:
            self.logger.error(f"Sensor {device_id} not found, available: {list(self.sensors.keys())}")
            return False

        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)

        old_threshold = self.threshold
        if threshold > 0:
            self.threshold = int(threshold)

        sensor = self.sensors[device_id]
        self.logger.info(
            f"Continuous monitor: ID={device_id}, threshold={self.threshold}, "
            f"duration={'∞' if duration == 0 else f'{duration}s'}"
        )

        start = time.time()
        count = 0
        error_count = 0
        try:
            while True:
                if duration > 0 and (time.time() - start) >= duration:
                    break
                count += 1
                data = sensor.read()
                if data:
                    result = self._apply_threshold(data)
                    self._sensor_cache[device_id] = result
                    status_str = "有液 ●" if result["liquid_detected"] else "无液 ○"
                    self.logger.info(
                        f"[{count:4d}] ID{device_id}: {status_str}  "
                        f"RSSI={result['rssi']:5d}  threshold={self.threshold}"
                    )
                    error_count = 0
                    if result["liquid_detected"]:
                        self.logger.info(f"ID{device_id} 达到阈值 (RSSI={result['rssi']}), 停止监测")
                        break
                else:
                    error_count += 1
                    self.logger.warning(f"[{count:4d}] ID{device_id}: 读取失败 (连续{error_count}次)")
                time.sleep(interval)
        finally:
            self.threshold = old_threshold
            self.logger.info(f"Monitor stopped: ID={device_id}, reads={count}")
            self._start_polling()

        return True

    def execute_command_from_outer(self, command_dict: Dict[str, Any]) -> bool:
        return super().execute_command_from_outer(command_dict)


# ==============================================================================
# 独立运行测试
# ==============================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    PORT = "COM9"

    print("=" * 55)
    print("  WXF 工作站测试")
    print(f"  串口: {PORT}  泵地址: 1,2  传感器站号: 1,2")
    print("=" * 55)
    print("  1 - 泵初始化")
    print("  2 - 传感器持续检测")
    print("  3 - 加液操作")
    print("=" * 55)

    ws = WxfWorkstation(port=PORT, pump_addresses=["1", "2"], sensor_ids=[1, 2])
    if not ws.is_connected:
        print("连接失败")
        exit(1)

    choice = input("  输入 1 / 2 / 3: ").strip()
    try:
        if choice == "1":
            addr = input("  泵地址 (1 或 2): ").strip()
            ws.pump_initialize(addr)
            print("初始化完成")
        elif choice == "2":
            sid = int(input("  传感器站号: ").strip())
            th = int(input("  阈值 (0=硬件检测): ").strip())
            ws.continuous_monitor(device_id=sid, threshold=th)
        elif choice == "3":
            addr = input("  泵地址 (1 或 2): ").strip()
            src = input("  液体来源 (液体1/液体2/液体3): ").strip()
            tgt = input("  目标柱子 (柱1/柱2/柱3): ").strip()
            vol = float(input("  体积 (mL): ").strip())
            ws.add_liquid(addr, src, tgt, vol)
    finally:
        ws.disconnect()

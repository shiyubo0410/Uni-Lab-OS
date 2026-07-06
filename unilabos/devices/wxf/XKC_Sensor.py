# -*- coding: utf-8 -*-
"""
XKC 非接触式液位传感器驱动 (Modbus RTU)
默认串口: COM9, 波特率: 9600

支持同一 RS485 总线上挂接多个传感器（不同站号），通过共享
XKCSerialBus 实例实现总线互斥。

通信协议:
  读取数据:  TX 01 03 00 01 00 02 CRC
             RX 01 03 04 [level_H] [level_L] [rssi_H] [rssi_L] [crc_L] [crc_H]
  设置地址:  TX 01 06 00 04 00 [new_addr] [crc_L] [crc_H]
  设置波特率: TX 01 06 00 05 00 [baud_code] [crc_L] [crc_H]
"""

import struct
import time
import threading
import logging
from typing import Optional, Dict, Any, List

from unilabos.devices.wxf.shared_bus import get_serial, release_serial

try:
    from unilabos.device_comms.universal_driver import UniversalDriver
except ImportError:
    class UniversalDriver:
        def __init__(self):
            self.logger = logging.getLogger(self.__class__.__name__)

        def execute_command_from_outer(self, command: str):
            pass


# 波特率代码对照表 (寄存器值 -> 波特率)
BAUD_CODE_MAP = {
    0x05: 2400,
    0x06: 4800,
    0x07: 9600,
    0x08: 14400,
    0x09: 19200,
    0x0A: 28800,
    0x0C: 57600,
    0x0D: 115200,
    0x0E: 128000,
    0x0F: 256000,
}
BAUD_TO_CODE = {v: k for k, v in BAUD_CODE_MAP.items()}


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


# ==============================================================================
# 共享串口总线（通过 shared_bus 公共池，与泵驱动共享同一个 Serial）
# ==============================================================================

class XKCSerialBus:
    """
    XKC 传感器总线接口，底层使用 shared_bus 公共串口池，
    可以和同端口的注射泵驱动安全共存。
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 3.0):
        self.port = port
        self.baudrate = baudrate
        self._serial, self.lock = get_serial(port, baudrate, timeout)

    def close(self):
        release_serial(self.port)

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def send_recv(self, request: bytes, expected_len: int) -> Optional[bytes]:
        with self.lock:
            if not self.is_open:
                return None
            try:
                self._serial.reset_input_buffer()
                self._serial.write(request)
                response = self._serial.read(expected_len)
                return response if len(response) == expected_len else None
            except Exception:
                return None

    def send_only(self, request: bytes):
        with self.lock:
            if not self.is_open:
                return
            try:
                self._serial.reset_input_buffer()
                self._serial.write(request)
            except Exception:
                pass


# ==============================================================================
# 单个传感器节点
# ==============================================================================

class XKCSensor:
    """
    单个 XKC 液位传感器节点，绑定到一个 XKCSerialBus 和指定站号。
    """

    def __init__(self, device_id: int, bus: XKCSerialBus):
        self.device_id = device_id
        self.bus = bus
        self.logger = logging.getLogger(f"XKCSensor[{device_id}]")

    def read(self) -> Optional[Dict[str, Any]]:
        """
        读取液位数据。
        返回: {'liquid_detected': bool, 'rssi': int}，失败返回 None。
        """
        payload = struct.pack('>BBHH', self.device_id, 0x03, 0x0001, 0x0002)
        request = payload + _calc_crc16(payload)
        response = self.bus.send_recv(request, expected_len=9)
        if response is None:
            return None

        addr, func, byte_count = response[0], response[1], response[2]
        if addr != self.device_id or func != 0x03 or byte_count != 0x04:
            self.logger.debug(f"Unexpected header: {response.hex()}")
            return None

        if response[7:9] != _calc_crc16(response[:7]):
            self.logger.debug(f"CRC error: {response.hex()}")
            return None

        raw_level = (response[3] << 8) | response[4]
        rssi      = (response[5] << 8) | response[6]
        return {
            "liquid_detected": raw_level == 0x0001,
            "rssi": rssi,
        }

    def set_address(self, new_address: int) -> bool:
        """修改传感器站号 (1-255)，成功时 LED 闪烁"""
        if not 1 <= new_address <= 255:
            return False
        payload = struct.pack('>BBHH', self.device_id, 0x06, 0x0004, new_address)
        request = payload + _calc_crc16(payload)
        response = self.bus.send_recv(request, expected_len=7)
        if response is None:
            return False
        success = response[4] == (new_address & 0xFF)
        if success:
            self.logger.info(f"Address changed to {new_address}.")
        return success

    def set_baudrate(self, baudrate: int) -> bool:
        """修改波特率，无响应，成功时 LED 闪烁"""
        code = BAUD_TO_CODE.get(baudrate)
        if code is None:
            self.logger.error(f"Unsupported baudrate: {baudrate}")
            return False
        payload = struct.pack('>BBHH', self.device_id, 0x06, 0x0005, code)
        request = payload + _calc_crc16(payload)
        self.bus.send_only(request)
        self.logger.info(f"Baudrate set command sent ({baudrate}).")
        return True


# ==============================================================================
# 多传感器驱动（UniversalDriver，管理一条总线上的所有传感器）
# ==============================================================================

class XKCSensorDriver(UniversalDriver):
    """
    XKC RS485 液位传感器驱动。

    单传感器用法:
        drv = XKCSensorDriver(port="COM9", device_ids=[1])

    多传感器用法（同一串口，不同站号）:
        drv = XKCSensorDriver(port="COM9", device_ids=[1, 2])
        print(drv.liquid_detected)           # 传感器1（默认第一个）状态
        print(drv.get_sensor_data(2))        # 传感器2状态
    """

    def __init__(
        self,
        port: str = "COM9",
        baudrate: int = 9600,
        device_ids: List[int] = None,
        threshold: int = 0,
        timeout: float = 3.0,
        poll_interval: float = 0.5,
    ):
        """
        :param threshold: RSSI 阈值，大于此值判定为有液。
                          设为 0 时使用传感器自身的硬件检测结果。
        """
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.device_ids = device_ids if device_ids else [1]
        self.threshold = threshold
        self.timeout = timeout
        self.poll_interval = poll_interval

        self._bus: Optional[XKCSerialBus] = None
        self._is_connected = False

        self._stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

        # 每个传感器节点
        self.sensors: Dict[int, XKCSensor] = {}
        # 每个传感器的状态缓存
        self._cache: Dict[int, Dict[str, Any]] = {}

        if self.port:
            self.connect()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        if self._is_connected:
            return True
        try:
            self._bus = XKCSerialBus(self.port, self.baudrate, self.timeout)
            for did in self.device_ids:
                self.sensors[did] = XKCSensor(did, self._bus)
                self._cache[did] = {"liquid_detected": False, "rssi": 0}
            self._is_connected = True
            self.logger.info(
                f"XKC Bus connected: {self.port} @ {self.baudrate} baud, "
                f"sensors={self.device_ids}"
            )
            self._start_polling()
            return True
        except Exception as e:
            self.logger.error(f"XKC connect failed: {e}")
            self._is_connected = False
            return False

    def disconnect(self):
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)
        if self._bus:
            self._bus.close()
        self._is_connected = False
        self.logger.info("XKC disconnected.")

    # ------------------------------------------------------------------
    # 轮询（依次查询每个传感器）
    # ------------------------------------------------------------------

    def _start_polling(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._polling_loop, daemon=True, name="XKCSensorPoll"
        )
        self._poll_thread.start()

    def _apply_threshold(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """如果设置了 threshold，使用 RSSI 阈值覆盖硬件检测结果"""
        if self.threshold > 0:
            data = dict(data)
            data["liquid_detected"] = data["rssi"] > self.threshold
        return data

    def _polling_loop(self):
        self.logger.info(f"Polling started for sensors: {self.device_ids}")
        error_counts = {did: 0 for did in self.device_ids}
        while not self._stop_event.is_set():
            if not self._is_connected:
                time.sleep(1.0)
                continue
            for did, sensor in self.sensors.items():
                data = sensor.read()
                if data:
                    self._cache[did] = self._apply_threshold(data)
                    error_counts[did] = 0
                else:
                    error_counts[did] += 1
                    if error_counts[did] % 10 == 0:
                        self.logger.warning(
                            f"Sensor[{did}] read failed {error_counts[did]} times."
                        )
            time.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # 对外属性（兼容单传感器场景，默认取 device_ids[0]）
    # ------------------------------------------------------------------

    @property
    def liquid_detected(self) -> bool:
        return self._cache[self.device_ids[0]]["liquid_detected"]

    @property
    def rssi(self) -> int:
        return self._cache[self.device_ids[0]]["rssi"]

    def get_sensor_data(self, device_id: int) -> Dict[str, Any]:
        """获取指定站号传感器的缓存状态"""
        return dict(self._cache.get(device_id, {"liquid_detected": False, "rssi": 0}))

    def read_sensor_by_id(self, device_id: int) -> Dict[str, Any]:
        """
        立即读取指定站号传感器数据（非缓存）。
        返回: {'liquid_detected': bool, 'rssi': int}
        """
        device_id = int(device_id)
        if device_id not in self.sensors:
            self.logger.error(f"Sensor ID {device_id} not configured.")
            return {"liquid_detected": False, "rssi": 0, "error": "未配置该站号"}
        data = self.sensors[device_id].read()
        if data is None:
            return {"liquid_detected": False, "rssi": 0, "error": "读取失败"}
        return self._apply_threshold(data)

    def set_threshold(self, threshold: int) -> bool:
        """
        设置 RSSI 阈值。大于此值判定为有液，0 表示使用硬件检测。
        """
        self.threshold = int(threshold)
        self.logger.info(f"Threshold set to {self.threshold}")
        return True

    def continuous_monitor(self, device_id: int = 1, threshold: int = 0,
                           duration: int = 0, interval: float = 0.5) -> bool:
        """
        对指定站号传感器进行连续液位检测，达到阈值时自动停止。

        :param device_id:  传感器站号
        :param threshold:  RSSI 阈值（>0 时覆盖全局阈值，0 使用硬件检测）
        :param duration:   持续时长（秒），0 表示无限运行直到检测到液位或外部停止
        :param interval:   检测间隔（秒）
        """
        device_id = int(device_id)
        if device_id not in self.sensors:
            self.logger.error(f"Sensor ID {device_id} not configured, available: {list(self.sensors.keys())}")
            return False

        # 停止后台轮询，避免总线冲突
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)

        old_threshold = self.threshold
        if threshold > 0:
            self.threshold = int(threshold)

        sensor = self.sensors[device_id]
        self.logger.info(
            f"Continuous monitor started: ID={device_id}, "
            f"threshold={self.threshold}, duration={'∞' if duration == 0 else f'{duration}s'}, "
            f"interval={interval}s"
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
                    self._cache[device_id] = result
                    status_str = "有液 ●" if result["liquid_detected"] else "无液 ○"
                    self.logger.info(
                        f"[{count:4d}] ID{device_id}: {status_str}  "
                        f"RSSI={result['rssi']:5d}  threshold={self.threshold}"
                    )
                    error_count = 0
                    if result["liquid_detected"]:
                        self.logger.info(
                            f"ID{device_id} 达到阈值 (RSSI={result['rssi']}), 停止监测"
                        )
                        break
                else:
                    error_count += 1
                    self.logger.warning(f"[{count:4d}] ID{device_id}: 读取失败 (连续{error_count}次)")

                time.sleep(interval)
        finally:
            self.threshold = old_threshold
            self.logger.info(f"Continuous monitor stopped: ID={device_id}, total reads={count}")
            self._start_polling()

        return True

    def detect(self, channel: int = 1, rssi_threshold: int = 0,
               interval: float = 0.5, timeout: int = 0) -> bool:
        """
        等待指定通道电导传感器检测到无水后结束。

        :param channel:        传感器通道号 (1-5，对应地址 1-5)
        :param rssi_threshold: RSSI 阈值，当 RSSI 低于此值判定为无水并结束；
                               0 表示使用传感器硬件检测结果
        :param interval:       检测间隔（秒）
        :param timeout:        超时时间（秒），0 表示无限等待直到无水
        :return: True 表示检测到无水正常结束，False 表示超时或出错
        """
        channel = int(channel)
        rssi_threshold = int(rssi_threshold)
        if channel < 1 or channel > 5:
            self.logger.error(f"通道号 {channel} 超出范围，仅支持 1-5")
            return False
        if channel not in self.sensors:
            self.logger.error(
                f"通道 {channel} 未配置，当前已配置的传感器: {list(self.sensors.keys())}"
            )
            return False

        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=3.0)

        sensor = self.sensors[channel]
        self.logger.info(
            f"等待无水检测启动: 通道={channel}, RSSI阈值={rssi_threshold}, "
            f"超时={'无限' if timeout == 0 else f'{timeout}s'}, 间隔={interval}s"
        )

        start = time.time()
        count = 0
        error_count = 0
        detected_no_water = False
        try:
            while True:
                if timeout > 0 and (time.time() - start) >= timeout:
                    self.logger.warning(f"通道 {channel} 等待无水超时 ({timeout}s)")
                    break

                count += 1
                data = sensor.read()
                if data:
                    self._cache[channel] = data
                    rssi = data["rssi"]
                    hw_detected = data["liquid_detected"]

                    if rssi_threshold > 0:
                        no_water = rssi < rssi_threshold
                    else:
                        no_water = not hw_detected

                    status_str = "有水 ●" if not no_water else "无水 ○"
                    self.logger.info(
                        f"[{count:4d}] 通道{channel}: {status_str}  "
                        f"RSSI={rssi:5d}  阈值={rssi_threshold}"
                    )
                    error_count = 0
                    if no_water:
                        self.logger.info(
                            f"通道 {channel} 检测到无水 "
                            f"(RSSI={rssi}, 阈值={rssi_threshold})，动作结束"
                        )
                        detected_no_water = True
                        break
                else:
                    error_count += 1
                    self.logger.warning(
                        f"[{count:4d}] 通道{channel}: 读取失败 (连续{error_count}次)"
                    )

                time.sleep(interval)
        finally:
            self.logger.info(
                f"等待无水检测结束: 通道={channel}, 总读取={count}, "
                f"结果={'无水' if detected_no_water else '超时/失败'}"
            )
            self._start_polling()

        return detected_no_water

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def execute_command_from_outer(self, command_dict: Dict[str, Any]) -> bool:
        return super().execute_command_from_outer(command_dict)


# ==============================================================================
# 独立运行示例
# ==============================================================================

def _scan_bus(port: str, baudrate: int, scan_range: range = range(1, 17)) -> List[int]:
    """扫描总线，返回有响应的站号列表"""
    print(f"  正在扫描站号 {scan_range.start}~{scan_range.stop - 1}，请稍候...")
    found = []
    try:
        bus = XKCSerialBus(port, baudrate, timeout=0.3)
    except Exception as e:
        print(f"  扫描失败，无法打开串口: {e}")
        return found
    for did in scan_range:
        sensor = XKCSensor(did, bus)
        data = sensor.read()
        if data is not None:
            found.append(did)
            print(f"  发现传感器  站号={did}  {'有液 ●' if data['liquid_detected'] else '无液 ○'}  RSSI={data['rssi']}")
    bus.close()
    if not found:
        print("  未发现任何传感器响应。")
    return found


def _example_read(drv: XKCSensorDriver, sensor_ids: List[int]):
    """示例1：持续读取所有传感器液位数据"""
    drv._stop_event.set()
    if drv._poll_thread and drv._poll_thread.is_alive():
        drv._poll_thread.join(timeout=3.0)

    print("开始持续读取传感器数据 (Ctrl+C 退出):")
    print("-" * 55)
    try:
        count = 0
        while True:
            count += 1
            parts = []
            for did in sensor_ids:
                data = drv.sensors[did].read()
                if data is None:
                    parts.append(f"  ID{did}: 读取失败")
                else:
                    status = "有液 ●" if data["liquid_detected"] else "无液 ○"
                    parts.append(f"  ID{did}: {status}  RSSI={data['rssi']:5d}")
            print(f"[{count:4d}]" + "  |".join(parts))
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n已停止。")


def _example_set_address(drv: XKCSensorDriver, sensor_ids: List[int]):
    """示例2：修改传感器站号"""
    print()
    print(f"当前已连接的传感器站号: {sensor_ids}")
    try:
        old_id = int(input("  请输入要修改的传感器当前站号: ").strip())
        new_id = int(input("  请输入新站号 (1-255): ").strip())
    except ValueError:
        print("输入无效，已取消。")
        return

    if old_id not in drv.sensors:
        print(f"站号 {old_id} 不在已连接列表 {sensor_ids} 中，已取消。")
        return
    if not 1 <= new_id <= 255:
        print("新站号超出范围 (1-255)，已取消。")
        return

    drv._stop_event.set()
    if drv._poll_thread and drv._poll_thread.is_alive():
        drv._poll_thread.join(timeout=3.0)

    print(f"  正在将站号 {old_id} → {new_id} ...")
    ok = drv.sensors[old_id].set_address(new_id)
    if ok:
        print(f"  成功！传感器 LED 应已闪烁。")
        print(f"  请用新站号 {new_id} 重新初始化驱动后再进行数据读取。")
    else:
        print("  设置失败，请检查连接或当前站号是否正确。")


def _example_set_baudrate(drv: XKCSensorDriver, sensor_ids: List[int]):
    """示例3：修改传感器波特率"""
    supported = sorted(BAUD_TO_CODE.keys())
    print()
    print(f"当前已连接的传感器站号: {sensor_ids}")
    print(f"支持的波特率: {supported}")
    try:
        did  = int(input("  请输入要修改的传感器站号: ").strip())
        baud = int(input("  请输入新波特率: ").strip())
    except ValueError:
        print("输入无效，已取消。")
        return

    if did not in drv.sensors:
        print(f"站号 {did} 不在已连接列表 {sensor_ids} 中，已取消。")
        return

    drv._stop_event.set()
    if drv._poll_thread and drv._poll_thread.is_alive():
        drv._poll_thread.join(timeout=3.0)

    ok = drv.sensors[did].set_baudrate(baud)
    if ok:
        print(f"  命令已发送（无响应），传感器 LED 应已闪烁。")
        print(f"  请将串口波特率切换到 {baud} 后重新初始化驱动。")
    else:
        print("  发送失败。")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    PORT     = "COM6"
    BAUDRATE = 9600

    print("=" * 55)
    print("  XKC 液位传感器驱动")
    print(f"  串口: {PORT}  波特率: {BAUDRATE}")
    print("=" * 55)

    # 扫描总线，自动发现在线传感器站号
    found_ids = _scan_bus(PORT, BAUDRATE)
    print()

    # 交互式输入站号，支持多个（逗号分隔）
    if found_ids:
        default_str = ",".join(str(x) for x in found_ids)
        print(f"  检测到的站号: {found_ids}（直接回车使用全部检测到的站号）")
    else:
        default_str = "1"
        print("  未扫描到传感器，默认使用站号 1（直接回车使用）")
    while True:
        raw = input(f"  请输入传感器站号（多个用逗号分隔）[默认: {default_str}]: ").strip()
        if not raw:
            SENSOR_IDS = found_ids if found_ids else [1]
            break
        try:
            SENSOR_IDS = [int(x.strip()) for x in raw.split(",") if x.strip()]
            if SENSOR_IDS:
                break
        except ValueError:
            pass
        print("  输入无效，请重新输入（例如: 1 或 1,2）")

    print(f"  已选择站号: {SENSOR_IDS}")
    print("=" * 55)
    print("  请选择示例:")
    print("  1 - 持续读取液位数据 (Ctrl+C 退出)")
    print("  2 - 修改传感器站号")
    print("  3 - 修改传感器波特率")
    print("=" * 55)
    while True:
        choice = input("  输入 1 / 2 / 3: ").strip()
        if choice in ("1", "2", "3"):
            break
        print("  请输入 1、2 或 3")

    drv = XKCSensorDriver(port=PORT, baudrate=BAUDRATE, device_ids=SENSOR_IDS)
    if not drv.is_connected:
        print("连接失败，请检查串口配置。")
        exit(1)

    try:
        if choice == "1":
            _example_read(drv, SENSOR_IDS)
        elif choice == "2":
            _example_set_address(drv, SENSOR_IDS)
        elif choice == "3":
            _example_set_baudrate(drv, SENSOR_IDS)
    finally:
        drv.disconnect()

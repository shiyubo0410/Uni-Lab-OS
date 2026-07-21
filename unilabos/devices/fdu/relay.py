# -*- coding: utf-8 -*-
"""科星 16 路 Modbus-RTU 继电器驱动（FDU 改写）

整合自 ``unilabos/devices/ctr/skills/jidianqi/relay_utils.py`` 与
``unilabos/devices/ctr/utils/gripper_pushrod_utils.py`` 中的
``PushRodControl`` 业务逻辑，重构为 Uni-Lab 标准设备驱动：

* 通过 ``@device`` 装饰器自动注册到注册表
* 每个动作均为带 ``@action`` 的方法，可在工作流中直接调用
* 内部维持每个继电器通道的开/关状态，并周期广播
* 同时提供推杆（上推杆 / 下推杆 / 旋涂仪推杆）封装动作，
  对应继电器对：12 / 13、10 / 11、14 / 15

串口默认参数与原 ``gui_config.json`` 保持一致：``COM11 9600 8N1``。
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode


PARITY_MAP = {
    "NONE": serial.PARITY_NONE,
    "EVEN": serial.PARITY_EVEN,
    "ODD": serial.PARITY_ODD,
}

DATA_BITS_MAP = {
    5: serial.FIVEBITS,
    6: serial.SIXBITS,
    7: serial.SEVENBITS,
    8: serial.EIGHTBITS,
}

STOP_BITS_MAP = {
    1: serial.STOPBITS_ONE,
    1.5: serial.STOPBITS_ONE_POINT_FIVE,
    2: serial.STOPBITS_TWO,
}


PUSHROD_PAIRS = {
    "upper": (13, 12),         # (推出通道, 收回通道)
    "lower": (11, 10),
    "spin_coater": (14, 15),
}

# 推杆机械动作较慢，发完继电器命令后还需要等待推杆实际走到位，
# 该延迟之后才认为动作真正完成（单位：秒）。
# 不同推杆行程不同：上/下推杆较短 ~2s；旋涂仪推杆行程长 ~11s。
# 注意：下列字面量与各推杆 action 方法的 delay_s 默认值需保持一致
# （AST 注册表扫描器不支持下标默认值，故 action 签名里用字面量）。
PUSHROD_ACTION_DELAY_S = 2.0
PUSHROD_DELAY_UPPER_S = 2.0
PUSHROD_DELAY_LOWER_S = 2.0
PUSHROD_DELAY_SPIN_COATER_S = 11.0
PUSHROD_ACTION_DELAYS_S: Dict[str, float] = {
    "upper": PUSHROD_DELAY_UPPER_S,
    "lower": PUSHROD_DELAY_LOWER_S,
    "spin_coater": PUSHROD_DELAY_SPIN_COATER_S,
}


def _crc16_modbus(data: bytes) -> bytes:
    """标准 Modbus CRC16（多项式 0xA001），返回 ``crc_lo, crc_hi`` 两个字节。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


@device(
    id="fdu.relay.kexing_16ch",
    category=["relay"],
    description="科星 16 路 Modbus-RTU 继电器（含上/下推杆与旋涂仪推杆封装动作）",
    display_name="FDU科星16路继电器",
)
class KexingRelay:
    """16 路 Modbus-RTU 继电器控制器。"""

    _ros_node: BaseROS2DeviceNode

    def __init__(
        self,
        port: str = "COM11",
        baudrate: int = 9600,
        data_bits: int = 8,
        stop_bits: float = 1,
        parity: str = "NONE",
        device_address: int = 1,
        channel_count: int = 16,
        timeout: float = 1.0,
        auto_connect: bool = True,
        pushrod_action_delay_s: float = PUSHROD_ACTION_DELAY_S,
        pushrod_action_delays_s: Optional[Dict[str, float]] = None,
        **kwargs: Any,
    ) -> None:
        self.port = port
        self.baudrate = int(baudrate)
        self.data_bits = int(data_bits)
        self.stop_bits = stop_bits
        self.parity = parity.upper() if isinstance(parity, str) else "NONE"
        self.device_address = int(device_address)
        self.channel_count = int(channel_count)
        self.timeout = float(timeout)
        # 全局回退值，用于未在 pushrod_action_delays_s 中单独配置的推杆
        self.pushrod_action_delay_s = float(pushrod_action_delay_s)
        # 每根推杆单独的到位等待时间（秒）：先用内置默认，再用用户覆盖
        self._pushrod_delays: Dict[str, float] = dict(PUSHROD_ACTION_DELAYS_S)
        if pushrod_action_delays_s:
            for name, value in pushrod_action_delays_s.items():
                try:
                    self._pushrod_delays[name] = float(value)
                except (TypeError, ValueError):
                    continue

        self.logger = logging.getLogger(f"KexingRelay.{port}")

        self._lock = threading.Lock()
        self._ser: Optional[serial.Serial] = None
        self._is_connected = False

        self._channel_states: Dict[int, bool] = {ch: False for ch in range(1, self.channel_count + 1)}
        self._pushrod_states: Dict[str, Optional[bool]] = {
            "upper": None,        # True=推出, False=收回, None=未知
            "lower": None,
            "spin_coater": None,
        }
        self._last_error: str = ""

        if auto_connect and self.port:
            try:
                self._do_connect()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(f"自动连接继电器失败: {exc}")

    # ---------- 生命周期 ----------

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @not_action
    def _do_connect(self) -> bool:
        """内部连接逻辑。"""
        if self._is_connected and self._ser and self._ser.is_open:
            return True
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=DATA_BITS_MAP.get(self.data_bits, serial.EIGHTBITS),
                parity=PARITY_MAP.get(self.parity, serial.PARITY_NONE),
                stopbits=STOP_BITS_MAP.get(self.stop_bits, serial.STOPBITS_ONE),
                timeout=self.timeout,
            )
            self._is_connected = self._ser.is_open
            if self._is_connected:
                self.logger.info(f"继电器已连接: {self.port} @ {self.baudrate}")
            return self._is_connected
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"connect: {exc}"
            self.logger.error(self._last_error)
            self._is_connected = False
            return False

    @action(description="打开串口，连接继电器")
    def connect(self) -> Dict[str, Any]:
        ok = self._do_connect()
        return {
            "success": ok,
            "port": self.port,
            "baudrate": self.baudrate,
            "message": "继电器已连接" if ok else f"继电器连接失败: {self._last_error}",
        }

    @action(description="关闭串口，断开继电器")
    def disconnect(self) -> Dict[str, Any]:
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:  # noqa: BLE001
                pass
        self._is_connected = False
        return {"success": True, "message": "继电器已断开"}

    # ---------- 内部协议封装 ----------

    @not_action
    def _ensure_connected(self) -> bool:
        if not self._is_connected or self._ser is None or not self._ser.is_open:
            return self._do_connect()
        return True

    @not_action
    def _send_frame(self, payload: bytes) -> Optional[bytes]:
        """发送原始 Modbus 帧并读取响应。"""
        if not self._ensure_connected():
            return None
        frame = payload + _crc16_modbus(payload)
        with self._lock:
            try:
                assert self._ser is not None
                self._ser.reset_input_buffer()
                self._ser.write(frame)
                self._ser.flush()
                time.sleep(0.05)
                response = self._ser.read(64)
                return response
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"send: {exc}"
                self.logger.error(self._last_error)
                return None

    @not_action
    def _write_single_coil(self, channel: int, value: bool) -> bool:
        """05 功能码：写单个线圈。"""
        if not 1 <= channel <= self.channel_count:
            self._last_error = f"通道号超界: {channel}"
            self.logger.error(self._last_error)
            return False
        addr = (channel - 1) & 0xFFFF
        coil_value = 0xFF00 if value else 0x0000
        payload = bytes([
            self.device_address & 0xFF,
            0x05,
            (addr >> 8) & 0xFF, addr & 0xFF,
            (coil_value >> 8) & 0xFF, coil_value & 0xFF,
        ])
        resp = self._send_frame(payload)
        ok = resp is not None and len(resp) >= 6
        if ok:
            self._channel_states[channel] = value
        return ok

    # ---------- 通道级动作 ----------

    @action(description="开启指定继电器通道")
    def turn_on(self, channel: int = 1) -> Dict[str, Any]:
        ch = int(channel)
        ok = self._write_single_coil(ch, True)
        return {
            "success": ok,
            "channel": ch,
            "state": "on" if ok else "unknown",
            "message": f"通道 {ch} 开启{'成功' if ok else '失败'}",
        }

    @action(description="关闭指定继电器通道")
    def turn_off(self, channel: int = 1) -> Dict[str, Any]:
        ch = int(channel)
        ok = self._write_single_coil(ch, False)
        return {
            "success": ok,
            "channel": ch,
            "state": "off" if ok else "unknown",
            "message": f"通道 {ch} 关闭{'成功' if ok else '失败'}",
        }

    @action(description="切换通道状态（已知则反转，未知默认开启）")
    def toggle(self, channel: int = 1) -> Dict[str, Any]:
        ch = int(channel)
        current = self._channel_states.get(ch, False)
        new_state = not current
        ok = self._write_single_coil(ch, new_state)
        return {
            "success": ok,
            "channel": ch,
            "state": "on" if new_state else "off",
            "message": f"通道 {ch} 已切换为 {'开' if new_state else '关'}",
        }

    @action(description="对指定通道发送固定 2 秒点动脉冲（05 功能码 + 0x3000 偏移）")
    def pulse_fixed(self, channel: int = 1) -> Dict[str, Any]:
        ch = int(channel)
        if not 1 <= ch <= self.channel_count:
            return {"success": False, "channel": ch, "error": "通道号超界"}
        addr = 0x3000 + (ch - 1)
        payload = bytes([
            self.device_address & 0xFF, 0x05,
            (addr >> 8) & 0xFF, addr & 0xFF,
            0xFF, 0x00,
        ])
        resp = self._send_frame(payload)
        ok = resp is not None and len(resp) >= 6
        return {"success": ok, "channel": ch, "message": "固定 2s 脉冲" + ("已发送" if ok else "失败")}

    @action(description="对指定通道发送可变时间脉冲（毫秒，06 功能码）")
    def pulse_variable(self, channel: int = 1, time_ms: int = 1000) -> Dict[str, Any]:
        ch = int(channel)
        ms = int(time_ms) & 0xFFFF
        if not 1 <= ch <= self.channel_count:
            return {"success": False, "channel": ch, "error": "通道号超界"}
        addr = (ch - 1) & 0xFFFF
        payload = bytes([
            self.device_address & 0xFF, 0x06,
            (addr >> 8) & 0xFF, addr & 0xFF,
            (ms >> 8) & 0xFF, ms & 0xFF,
        ])
        resp = self._send_frame(payload)
        ok = resp is not None and len(resp) >= 6
        return {"success": ok, "channel": ch, "duration_ms": ms,
                "message": f"可变脉冲 {ms}ms" + ("已发送" if ok else "失败")}

    @action(description="同时控制一对通道（一开一关），用于推杆等互斥继电器")
    def set_pair(self, channel_on: int = 0, channel_off: int = 0,
                 inter_delay_s: float = 0.1) -> Dict[str, Any]:
        ch_on = int(channel_on)
        ch_off = int(channel_off)
        results = {"on": None, "off": None}
        if ch_off > 0:
            results["off"] = self._write_single_coil(ch_off, False)
            time.sleep(inter_delay_s)
        if ch_on > 0:
            results["on"] = self._write_single_coil(ch_on, True)
            time.sleep(inter_delay_s)
        ok = all(v is not False for v in results.values())
        return {
            "success": ok,
            "channel_on": ch_on,
            "channel_off": ch_off,
            "results": results,
            "message": f"通道对 ({ch_on} ON / {ch_off} OFF) {'成功' if ok else '失败'}",
        }

    @action(description="关闭所有通道")
    def all_off(self) -> Dict[str, Any]:
        failures = []
        for ch in range(1, self.channel_count + 1):
            if not self._write_single_coil(ch, False):
                failures.append(ch)
            time.sleep(0.02)
        return {
            "success": not failures,
            "failed_channels": failures,
            "message": "全部通道已关闭" if not failures else f"以下通道关闭失败: {failures}",
        }

    # ---------- 通用工具动作 ----------

    @action(description="纯等待（与继电器无关）：阻塞 duration_s 秒后再结束动作节点")
    def wait(self, duration_s: float = 1.0) -> Dict[str, Any]:
        try:
            seconds = float(duration_s)
        except (TypeError, ValueError):
            seconds = 0.0
        seconds = max(0.0, seconds)
        self.logger.info(f"wait: 开始等待 {seconds:.2f}s")
        if seconds > 0:
            time.sleep(seconds)
        self.logger.info(f"wait: 等待 {seconds:.2f}s 结束")
        return {
            "success": True,
            "duration_s": seconds,
            "message": f"等待 {seconds:.2f} 秒完成",
        }

    # ---------- 推杆封装动作 ----------

    @not_action
    def _get_pushrod_delay(self, name: str) -> float:
        """获取指定推杆的到位等待时间（秒）。"""
        value = self._pushrod_delays.get(name, self.pushrod_action_delay_s)
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return max(0.0, float(self.pushrod_action_delay_s))

    @not_action
    def _drive_pair(self, name: str, extend: bool,
                    delay_s: Optional[float] = None) -> Dict[str, Any]:
        on_ch, off_ch = PUSHROD_PAIRS[name]
        if not extend:
            on_ch, off_ch = off_ch, on_ch
        result = self.set_pair(channel_on=on_ch, channel_off=off_ch)
        pair_success = bool(result.get("success"))
        # 解析前端/调用方传入的 delay_s：
        #   None / 非法 / <= 0 → 视为"用设备默认"，避免空输入被当成 0 跳过等待
        #   > 0                → 使用调用方指定的秒数（覆盖默认）
        default_delay = self._get_pushrod_delay(name)
        raw_delay = delay_s
        if delay_s is None:
            delay = default_delay
        else:
            try:
                parsed = float(delay_s)
            except (TypeError, ValueError):
                parsed = None
            if parsed is None or parsed <= 0:
                delay = default_delay
            else:
                delay = parsed

        self.logger.info(
            f"推杆 {name} {'推出' if extend else '收回'}：前端 delay_s={raw_delay!r}, "
            f"设备默认 {default_delay}s, 实际等待 {delay:.2f}s, set_pair_success={pair_success}"
        )

        if pair_success:
            self._pushrod_states[name] = extend
        # 推杆机械动作较慢，即使 Modbus 响应回读失败，继电器通常也已经动作，
        # 因此只要走到这里都按 delay 秒等待推杆到位（除非 delay<=0）
        if delay > 0:
            time.sleep(delay)

        result.update({
            "pushrod": name,
            "action": "extend" if extend else "retract",
            "action_delay_s": delay,
            "delay_s_received": raw_delay,
        })
        return result

    # NOTE: 下列 action 的 delay_s 默认值必须是字面量数字，
    # 因为 AST 注册表扫描器仅支持 Constant / Name / Attribute 求值，
    # 下标或变量名都会被前端显示为 "<ast:...>" 或原样字符串。
    # 如需调整默认值，请同步修改 PUSHROD_ACTION_DELAYS_S。

    @action(description="上推杆推出（13 开 / 12 关），delay_s 为推杆到位等待秒数")
    def upper_pushrod_extend(self, delay_s: float = 2.0) -> Dict[str, Any]:
        return self._drive_pair("upper", True, delay_s=delay_s)

    @action(description="上推杆收回（12 开 / 13 关），delay_s 为推杆到位等待秒数")
    def upper_pushrod_retract(self, delay_s: float = 2.0) -> Dict[str, Any]:
        return self._drive_pair("upper", False, delay_s=delay_s)

    @action(description="上推杆切换（已知反转，未知默认推出），delay_s 为推杆到位等待秒数")
    def upper_pushrod_toggle(self, delay_s: float = 2.0) -> Dict[str, Any]:
        state = self._pushrod_states.get("upper")
        return self._drive_pair(
            "upper", not state if state is not None else True, delay_s=delay_s
        )

    @action(description="下推杆推出（11 开 / 10 关），delay_s 为推杆到位等待秒数")
    def lower_pushrod_extend(self, delay_s: float = 2.0) -> Dict[str, Any]:
        return self._drive_pair("lower", True, delay_s=delay_s)

    @action(description="下推杆收回（10 开 / 11 关），delay_s 为推杆到位等待秒数")
    def lower_pushrod_retract(self, delay_s: float = 2.0) -> Dict[str, Any]:
        return self._drive_pair("lower", False, delay_s=delay_s)

    @action(description="下推杆切换，delay_s 为推杆到位等待秒数")
    def lower_pushrod_toggle(self, delay_s: float = 2.0) -> Dict[str, Any]:
        state = self._pushrod_states.get("lower")
        return self._drive_pair(
            "lower", not state if state is not None else True, delay_s=delay_s
        )

    @action(description="旋涂仪推杆推出（14 开 / 15 关），delay_s 为推杆到位等待秒数（行程较长，默认 11s）")
    def spin_coater_pushrod_extend(self, delay_s: float = 11.0) -> Dict[str, Any]:
        return self._drive_pair("spin_coater", True, delay_s=delay_s)

    @action(description="旋涂仪推杆收回（15 开 / 14 关），delay_s 为推杆到位等待秒数（行程较长，默认 11s）")
    def spin_coater_pushrod_retract(self, delay_s: float = 11.0) -> Dict[str, Any]:
        return self._drive_pair("spin_coater", False, delay_s=delay_s)

    @action(description="旋涂仪推杆切换，delay_s 为推杆到位等待秒数（行程较长，默认 11s）")
    def spin_coater_pushrod_toggle(self, delay_s: float = 11.0) -> Dict[str, Any]:
        state = self._pushrod_states.get("spin_coater")
        return self._drive_pair(
            "spin_coater", not state if state is not None else True, delay_s=delay_s
        )

    # ---------- 状态属性 ----------

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def channel_states(self) -> str:
        """通道状态汇总，例如 ``1:关 2:关 ... 13:开``。"""
        items = [f"{ch}:{'开' if on else '关'}" for ch, on in sorted(self._channel_states.items())]
        return " ".join(items)

    @property
    @topic_config(period=2.0)
    def pushrod_status(self) -> str:
        def _fmt(name: str) -> str:
            v = self._pushrod_states[name]
            return f"{name}:{'?' if v is None else ('推出' if v else '收回')}"
        return " ".join(_fmt(n) for n in ("upper", "lower", "spin_coater"))

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    relay = KexingRelay(port="COM11", baudrate=9600, auto_connect=True)
    if relay._is_connected:
        print(relay.turn_on(channel=1))
        time.sleep(1)
        print(relay.turn_off(channel=1))
        relay.disconnect()
    else:
        print("继电器连接失败，请检查串口与硬件。")

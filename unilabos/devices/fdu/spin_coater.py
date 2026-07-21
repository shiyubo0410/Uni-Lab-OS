# -*- coding: utf-8 -*-
"""旋图（Xuantu）旋涂仪驱动（FDU 改写）

整合自 ``unilabos/devices/ctr/scripts/spin_coater_controller.py`` 与
``unilabos/devices/ctr/skills/xuantu/xuantu_utils.py``，重构为
Uni-Lab 标准设备驱动：

* 通过 ``@device`` 装饰器自动注册
* 支持上电使能 / 真空 / 单步 / 多步 / 对中 / 摆动等所有原始指令
* 多步参数批量配置 ``configure_multi_step_params`` 与等待完成
  ``wait_for_spin_completion``
* 周期广播连接状态、使能状态、运行速度、当前真空显示等

通信协议：Modbus-RTU。设备启动时先用 9600 baud 握手，再切到 19200。
默认串口 ``COM6``。
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode


# ===== 寄存器地址 =====
ADDR_ENABLE_COIL = 0x0010
ADDR_VACUUM_COIL = 0x0032
ADDR_HOME_COIL = 0x0014
ADDR_SINGLE_STEP_COIL = 0x0007

ADDR_ENABLE_STATUS = 0x001F
ADDR_VACUUM_STATUS = 0x6000
ADDR_SINGLE_STEP_RUNNING = 0x0001
ADDR_MULTI_STEP_RUNNING = 0x0002
ADDR_SPIN_STOP_SIGNAL = 0x005B

ADDR_VACUUM_DISPLAY = 0x00DC
ADDR_RUN_SPEED = 0x007A
ADDR_RUN_TIME = 0x0046
ADDR_MULTI_TOTAL_TIME = 0x0048
ADDR_MULTI_CURRENT_STEP = 0x005C
ADDR_PAGE_CURRENT = 0x0003
ADDR_PAGE_SET = 0x0006

# 单步参数
ADDR_SINGLE_SPEED = 0xA0DA
ADDR_SINGLE_TIME = 0xA0DB
ADDR_SINGLE_ACC = 0xA0DC
ADDR_DECELERATION = 0xA09E

# 对中参数
ADDR_ALIGN_SPEED = 0xA0A0
ADDR_ALIGN_TIME = 0xA0A2

# 摆动参数
ADDR_OSC_SPEED = 0xA0A4
ADDR_OSC_ACC = 0xA0A6
ADDR_OSC_TIME = 0xA0A8
ADDR_OSC_COUNT = 0xAA0A

# 真空保护
ADDR_VACUUM_PROTECT = 0xA096

# 多步参数基地址（每步 3 个寄存器）
ADDR_MULTI_BASE = 0xA0E4   # +0=speed, +1=time(ms), +2=acc

# 页码
PAGE_SINGLE = 0x0003
PAGE_MULTI = 0x001B


def _crc16_modbus(data: bytes) -> bytes:
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
    id="fdu.spin_coater.xuantu",
    category=["spin_coater"],
    description="旋图旋涂仪（Modbus-RTU，9600→19200 切换波特率）",
    display_name="FDU 旋图旋涂仪",
)
class XuantuSpinCoater:
    """旋图旋涂仪 Uni-Lab 驱动。"""

    _ros_node: BaseROS2DeviceNode

    def __init__(
        self,
        port: str = "COM6",
        station: int = 1,
        baudrate: int = 19200,
        boot_baudrate: int = 9600,
        timeout: float = 1.0,
        auto_connect: bool = True,
        **kwargs: Any,
    ) -> None:
        self.port = port
        self.station = int(station)
        self.baudrate = int(baudrate)
        self.boot_baudrate = int(boot_baudrate)
        self.timeout = float(timeout)

        self.logger = logging.getLogger(f"XuantuSpinCoater.{port}")
        self._lock = threading.Lock()

        self._ser: Optional[serial.Serial] = None
        self._is_connected = False

        self._enabled = False
        self._vacuum_on = False
        self._cached_run_speed: int = 0
        self._cached_vacuum_display: int = 0
        self._cached_current_step: int = 0
        self._last_error: str = ""

        if auto_connect and self.port:
            try:
                self.connect()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(f"自动连接旋涂仪失败: {exc}")

    # ---------- 生命周期 ----------

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @action(description="连接旋涂仪：先以 9600 握手，再切换到目标波特率")
    def connect(self) -> Dict[str, Any]:
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.boot_baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            if not self._ser.is_open:
                self._is_connected = False
                return {"success": False, "message": f"打开串口 {self.port} 失败"}
            time.sleep(0.05)
            self._ser.baudrate = self.baudrate
            self._is_connected = True
            self.logger.info(f"旋涂仪已连接: {self.port} → {self.baudrate} baud")
            return {"success": True, "port": self.port, "baudrate": self.baudrate,
                    "message": f"连接成功（已切换到 {self.baudrate}）"}
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"connect: {exc}"
            self._is_connected = False
            self.logger.error(self._last_error)
            return {"success": False, "message": self._last_error}

    @action(description="断开旋涂仪连接")
    def disconnect(self) -> Dict[str, Any]:
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:  # noqa: BLE001
                pass
        self._is_connected = False
        return {"success": True, "message": "旋涂仪已断开"}

    # ---------- Modbus 基础 ----------

    @not_action
    def _ensure_connected(self) -> bool:
        if self._is_connected and self._ser and self._ser.is_open:
            return True
        return self.connect().get("success", False)

    @not_action
    def _send_frame(self, payload: bytes, expect_len: int = 8,
                    settle_s: float = 0.05) -> Optional[bytes]:
        if not self._ensure_connected():
            return None
        frame = payload + _crc16_modbus(payload)
        with self._lock:
            try:
                assert self._ser is not None
                self._ser.reset_input_buffer()
                self._ser.write(frame)
                self._ser.flush()
                time.sleep(settle_s)
                response = self._ser.read(expect_len)
                return response if response else None
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"send: {exc}"
                self.logger.error(self._last_error)
                return None

    @not_action
    def _write_coil_pulse(self, address: int) -> bool:
        """写线圈：先 FF00 置位，再 0000 复位，模拟瞬时按键。"""
        on_payload = bytes([
            self.station & 0xFF, 0x05,
            (address >> 8) & 0xFF, address & 0xFF,
            0xFF, 0x00,
        ])
        off_payload = bytes([
            self.station & 0xFF, 0x05,
            (address >> 8) & 0xFF, address & 0xFF,
            0x00, 0x00,
        ])
        r1 = self._send_frame(on_payload, expect_len=8)
        time.sleep(0.2)
        r2 = self._send_frame(off_payload, expect_len=8)
        return r1 is not None and r2 is not None

    @not_action
    def _read_coil(self, address: int) -> Optional[bool]:
        payload = bytes([
            self.station & 0xFF, 0x01,
            (address >> 8) & 0xFF, address & 0xFF,
            0x00, 0x01,
        ])
        resp = self._send_frame(payload, expect_len=6)
        if not resp or len(resp) < 4:
            return None
        return bool(resp[3] & 0x01)

    @not_action
    def _read_holding(self, address: int) -> Optional[int]:
        payload = bytes([
            self.station & 0xFF, 0x03,
            (address >> 8) & 0xFF, address & 0xFF,
            0x00, 0x01,
        ])
        resp = self._send_frame(payload, expect_len=7)
        if not resp or len(resp) < 5:
            return None
        return (resp[3] << 8) | resp[4]

    @not_action
    def _write_holding(self, address: int, value: int) -> bool:
        v = int(value) & 0xFFFF
        payload = bytes([
            self.station & 0xFF, 0x06,
            (address >> 8) & 0xFF, address & 0xFF,
            (v >> 8) & 0xFF, v & 0xFF,
        ])
        resp = self._send_frame(payload, expect_len=8)
        return resp is not None and len(resp) >= 6

    # ---------- 使能 / 真空 / 复位 ----------

    @action(description="切换上电使能（脉冲指令）")
    def enable_toggle(self) -> Dict[str, Any]:
        ok = self._write_coil_pulse(ADDR_ENABLE_COIL)
        if ok:
            self._enabled = not self._enabled
        return {"success": ok, "enabled": self._enabled,
                "message": f"使能切换为 {self._enabled}" if ok else "使能切换失败"}

    @action(description="读取使能状态")
    def get_enable_status(self) -> Dict[str, Any]:
        s = self._read_coil(ADDR_ENABLE_STATUS)
        if s is not None:
            self._enabled = s
        return {"enabled": self._enabled}

    @action(description="切换真空泵开/关（脉冲指令）")
    def vacuum_toggle(self) -> Dict[str, Any]:
        ok = self._write_coil_pulse(ADDR_VACUUM_COIL)
        if ok:
            self._vacuum_on = not self._vacuum_on
        return {"success": ok, "vacuum_on": self._vacuum_on,
                "message": f"真空切换为 {self._vacuum_on}" if ok else "真空切换失败"}

    @action(description="读取真空状态")
    def get_vacuum_status(self) -> Dict[str, Any]:
        s = self._read_coil(ADDR_VACUUM_STATUS)
        if s is not None:
            self._vacuum_on = s
        return {"vacuum_on": self._vacuum_on}

    @action(description="读取真空显示值")
    def get_vacuum_display(self) -> int:
        v = self._read_holding(ADDR_VACUUM_DISPLAY)
        if v is not None:
            self._cached_vacuum_display = v
            return v
        return self._cached_vacuum_display

    @action(description="设置真空保护值（10-50）")
    def set_vacuum_protection(self, value: int = 30) -> Dict[str, Any]:
        v = int(value)
        if not 10 <= v <= 50:
            return {"success": False, "error": "真空保护值必须在 10-50 之间"}
        ok = self._write_holding(ADDR_VACUUM_PROTECT, v)
        return {"success": ok, "value": v}

    @action(description="手动回零")
    def manual_home(self) -> Dict[str, Any]:
        ok = self._write_coil_pulse(ADDR_HOME_COIL)
        return {"success": ok, "message": "回零指令已发送" if ok else "回零失败"}

    # ---------- 单步 / 多步 启停 ----------

    @action(description="单步运行启动/停止（同一脉冲指令）")
    def single_step_toggle(self) -> Dict[str, Any]:
        ok = self._write_coil_pulse(ADDR_SINGLE_STEP_COIL)
        return {"success": ok, "message": "单步启停指令已发送" if ok else "失败"}

    @action(description="读取单步运行状态")
    def get_single_step_running(self) -> bool:
        return self._read_coil(ADDR_SINGLE_STEP_RUNNING) or False

    @action(description="多步运行启动/停止（与单步共用同一线圈）")
    def multi_step_toggle(self) -> Dict[str, Any]:
        ok = self._write_coil_pulse(ADDR_SINGLE_STEP_COIL)
        return {"success": ok, "message": "多步启停指令已发送" if ok else "失败"}

    @action(description="读取多步运行状态")
    def get_multi_step_running(self) -> bool:
        return self._read_coil(ADDR_MULTI_STEP_RUNNING) or False

    @action(description="读取旋涂停止信号（用于判断是否结束）")
    def get_spin_stop_signal(self) -> bool:
        return self._read_coil(ADDR_SPIN_STOP_SIGNAL) or False

    # ---------- 单步参数 ----------

    @action(description="设置单步速度（10-10000 rpm）")
    def set_single_step_speed(self, speed: int = 1000) -> Dict[str, Any]:
        v = int(speed)
        if not 10 <= v <= 10000:
            return {"success": False, "error": "单步速度必须在 10-10000 之间"}
        return {"success": self._write_holding(ADDR_SINGLE_SPEED, v), "speed": v}

    @action(description="设置单步运行时间（0-3000，单位由设备定义）")
    def set_single_step_time(self, time_value: int = 30) -> Dict[str, Any]:
        v = int(time_value)
        if not 0 <= v <= 3000:
            return {"success": False, "error": "单步时间必须在 0-3000 之间"}
        return {"success": self._write_holding(ADDR_SINGLE_TIME, v), "time": v}

    @action(description="设置单步加速度（200-30000）")
    def set_single_step_acceleration(self, acceleration: int = 1000) -> Dict[str, Any]:
        v = int(acceleration)
        if not 200 <= v <= 30000:
            return {"success": False, "error": "单步加速度必须在 200-30000 之间"}
        return {"success": self._write_holding(ADDR_SINGLE_ACC, v), "acceleration": v}

    @action(description="设置统一减速度（100-2500）")
    def set_deceleration(self, deceleration: int = 500) -> Dict[str, Any]:
        v = int(deceleration)
        if not 100 <= v <= 2500:
            return {"success": False, "error": "减速度必须在 100-2500 之间"}
        return {"success": self._write_holding(ADDR_DECELERATION, v), "deceleration": v}

    # ---------- 多步参数 ----------

    @action(description="设置第 N 步速度（step_num: 1-100，speed: 0-10000）")
    def set_multi_step_speed(self, step_num: int = 1, speed: int = 1000) -> Dict[str, Any]:
        n = int(step_num)
        s = int(speed)
        if not 1 <= n <= 100:
            return {"success": False, "error": "步骤号必须在 1-100"}
        if not 0 <= s <= 10000:
            return {"success": False, "error": "速度必须在 0-10000"}
        return {"success": self._write_holding(ADDR_MULTI_BASE + (n - 1) * 3, s),
                "step": n, "speed": s}

    @action(description="设置第 N 步时间（0-3000）")
    def set_multi_step_time(self, step_num: int = 1, time_value: int = 30) -> Dict[str, Any]:
        n = int(step_num)
        t = int(time_value)
        if not 1 <= n <= 100:
            return {"success": False, "error": "步骤号必须在 1-100"}
        if not 0 <= t <= 3000:
            return {"success": False, "error": "时间必须在 0-3000"}
        return {"success": self._write_holding(ADDR_MULTI_BASE + 1 + (n - 1) * 3, t),
                "step": n, "time": t}

    @action(description="设置第 N 步加速度（200-30000）")
    def set_multi_step_acceleration(self, step_num: int = 1,
                                    acceleration: int = 1000) -> Dict[str, Any]:
        n = int(step_num)
        a = int(acceleration)
        if not 1 <= n <= 100:
            return {"success": False, "error": "步骤号必须在 1-100"}
        if not 200 <= a <= 30000:
            return {"success": False, "error": "加速度必须在 200-30000"}
        return {"success": self._write_holding(ADDR_MULTI_BASE + 2 + (n - 1) * 3, a),
                "step": n, "acceleration": a}

    @action(description="批量设置多步参数。steps 形如 [{speed,time,acceleration},...]")
    def configure_multi_step_params(self, steps: List[Dict[str, int]]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for idx, step in enumerate(steps, start=1):
            r_speed = self.set_multi_step_speed(step_num=idx,
                                                speed=step.get("speed", 0))
            r_time = self.set_multi_step_time(step_num=idx,
                                              time_value=step.get("time", 0))
            r_acc = self.set_multi_step_acceleration(
                step_num=idx, acceleration=step.get("acceleration", 1000))
            results.append({
                "step": idx,
                "speed_ok": r_speed.get("success", False),
                "time_ok": r_time.get("success", False),
                "acc_ok": r_acc.get("success", False),
            })
        ok = all(r["speed_ok"] and r["time_ok"] and r["acc_ok"] for r in results)
        return {"success": ok, "step_count": len(steps), "results": results}

    # ---------- 对中 / 摆动参数 ----------

    @action(description="设置对中速度（100-500）")
    def set_alignment_speed(self, speed: int = 200) -> Dict[str, Any]:
        v = int(speed)
        if not 100 <= v <= 500:
            return {"success": False, "error": "对中速度必须在 100-500"}
        return {"success": self._write_holding(ADDR_ALIGN_SPEED, v), "speed": v}

    @action(description="设置对中时间（1-100）")
    def set_alignment_time(self, time_value: int = 10) -> Dict[str, Any]:
        v = int(time_value)
        if not 1 <= v <= 100:
            return {"success": False, "error": "对中时间必须在 1-100"}
        return {"success": self._write_holding(ADDR_ALIGN_TIME, v), "time": v}

    @action(description="设置摆动速度（10-800）")
    def set_oscillation_speed(self, speed: int = 100) -> Dict[str, Any]:
        v = int(speed)
        if not 10 <= v <= 800:
            return {"success": False, "error": "摆动速度必须在 10-800"}
        return {"success": self._write_holding(ADDR_OSC_SPEED, v), "speed": v}

    @action(description="设置摆动加速度（10-2000）")
    def set_oscillation_acceleration(self, acceleration: int = 200) -> Dict[str, Any]:
        v = int(acceleration)
        if not 10 <= v <= 2000:
            return {"success": False, "error": "摆动加速度必须在 10-2000"}
        return {"success": self._write_holding(ADDR_OSC_ACC, v), "acceleration": v}

    @action(description="设置摆动时间（1-100）")
    def set_oscillation_time(self, time_value: int = 10) -> Dict[str, Any]:
        v = int(time_value)
        if not 1 <= v <= 100:
            return {"success": False, "error": "摆动时间必须在 1-100"}
        return {"success": self._write_holding(ADDR_OSC_TIME, v), "time": v}

    @action(description="设置摆动次数（1-20）")
    def set_oscillation_count(self, count: int = 1) -> Dict[str, Any]:
        v = int(count)
        if not 1 <= v <= 20:
            return {"success": False, "error": "摆动次数必须在 1-20"}
        return {"success": self._write_holding(ADDR_OSC_COUNT, v), "count": v}

    # ---------- 状态 / 页面 ----------

    @action(description="读取实时运行速度")
    def get_run_speed(self) -> int:
        v = self._read_holding(ADDR_RUN_SPEED)
        if v is not None:
            self._cached_run_speed = v
            return v
        return self._cached_run_speed

    @action(description="读取本次运行总时长")
    def get_run_time(self) -> Optional[int]:
        return self._read_holding(ADDR_RUN_TIME)

    @action(description="读取多步运行总时长")
    def get_multi_step_total_time(self) -> Optional[int]:
        return self._read_holding(ADDR_MULTI_TOTAL_TIME)

    @action(description="读取多步当前步数")
    def get_multi_step_current_step(self) -> int:
        v = self._read_holding(ADDR_MULTI_CURRENT_STEP)
        if v is not None:
            self._cached_current_step = v
            return v
        return self._cached_current_step

    @action(description="读取当前页面（0x0003=单步，0x001B=多步）")
    def get_current_page(self) -> Optional[int]:
        return self._read_holding(ADDR_PAGE_CURRENT)

    @action(description="切换到指定页面（0x0003=单步，0x001B=多步）")
    def set_page(self, page_num: int = 0x0003) -> Dict[str, Any]:
        try:
            page = int(page_num)
        except (TypeError, ValueError):
            return {"success": False, "error": f"非法页面参数 {page_num!r}"}
        if page not in (PAGE_SINGLE, PAGE_MULTI):
            return {"success": False, "error": "页面号必须是 0x0003 或 0x001B"}
        return {"success": self._write_holding(ADDR_PAGE_SET, page), "page": page}

    @action(description="等待旋涂结束（轮询单步/多步运行状态或停止信号）")
    def wait_for_spin_completion(self, timeout: float = 600.0,
                                 poll_interval: float = 1.0) -> Dict[str, Any]:
        deadline = time.time() + float(timeout)
        elapsed = 0.0
        while time.time() < deadline:
            if self.get_spin_stop_signal():
                return {"success": True, "elapsed_s": elapsed,
                        "message": "检测到停止信号，旋涂结束"}
            single = self._read_coil(ADDR_SINGLE_STEP_RUNNING) or False
            multi = self._read_coil(ADDR_MULTI_STEP_RUNNING) or False
            if not single and not multi and elapsed > 1.0:
                return {"success": True, "elapsed_s": elapsed,
                        "message": "运行状态已停止"}
            time.sleep(poll_interval)
            elapsed += poll_interval
        return {"success": False, "elapsed_s": elapsed, "message": "等待超时"}

    # ---------- 周期广播属性 ----------

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def enabled(self) -> bool:
        return self._enabled

    @property
    @topic_config(period=2.0)
    def vacuum_on(self) -> bool:
        return self._vacuum_on

    @property
    @topic_config(period=2.0)
    def run_speed(self) -> int:
        return self._cached_run_speed

    @property
    @topic_config(period=2.0)
    def vacuum_display(self) -> int:
        return self._cached_vacuum_display

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sc = XuantuSpinCoater(port="COM6", auto_connect=True)
    if sc._is_connected:
        print(sc.enable_toggle())
        time.sleep(0.5)
        print(sc.set_single_step_speed(speed=2000))
        print(sc.set_single_step_time(time_value=10))
        print(sc.single_step_toggle())
        time.sleep(2)
        print(sc.get_run_speed())
        sc.disconnect()
    else:
        print("旋涂仪连接失败，请检查串口与硬件。")

# -*- coding: utf-8 -*-
"""PGE-A 系列驱控一体平行电爪驱动（FDU 改写）

整合自 ``unilabos/devices/ctr/skills/pgea_gripper_skill/gripper.py``，
重构为 Uni-Lab 标准设备驱动：

* 通过 ``@device`` 注册到注册表
* 每个动作（连接、初始化、张开、闭合、移动、设速度/力等）均为
  带 ``@action`` 的方法
* 周期广播连接状态、当前位置、夹持状态、错误码

通信协议：Modbus-RTU，默认 ``115200 8N1``，常用串口 ``COM4``。
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode


REG_INIT_GRIPPER = 0x0100
REG_INIT_STATUS = 0x0200
REG_FORCE = 0x0101
REG_POSITION = 0x0103
REG_SPEED = 0x0104
REG_POSITION_FEEDBACK = 0x0202
REG_GRIP_STATUS = 0x0201
REG_ERROR_CODE = 0x0205

INIT_STATUS_NOT_INIT = 0
INIT_STATUS_SUCCESS = 1
INIT_STATUS_RUNNING = 2
INIT_STATUS_STROKE_ERROR = 0xFFFF

GRIP_STATUS_MOVING = 0
GRIP_STATUS_IN_POSITION = 1
GRIP_STATUS_GRIPPED = 2
GRIP_STATUS_DROPPED = 3

GRIP_STATUS_DESC = {
    GRIP_STATUS_MOVING: "运动中",
    GRIP_STATUS_IN_POSITION: "到位",
    GRIP_STATUS_GRIPPED: "已夹住物体",
    GRIP_STATUS_DROPPED: "物体掉落",
}

POSITION_MIN = 0
POSITION_MAX = 1000
FORCE_MIN = 20
FORCE_MAX = 100
SPEED_MIN = 1
SPEED_MAX = 100


def _crc16_modbus(data: bytes) -> bytes:
    """标准 Modbus CRC16，返回 ``crc_lo, crc_hi``。"""
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
    id="fdu.gripper.pgea",
    category=["gripper"],
    description="PGE-A 系列驱控一体式平行电爪（Modbus-RTU）",
    display_name="FDU PGE-A 平行电爪",
)
class PGEAGripperDevice:
    """PGE-A 平行电爪 Uni-Lab 驱动。"""

    _ros_node: BaseROS2DeviceNode

    def __init__(
        self,
        port: str = "COM4",
        slave_id: int = 1,
        baudrate: int = 115200,
        timeout: float = 1.0,
        auto_connect: bool = True,
        **kwargs: Any,
    ) -> None:
        self.port = port
        self.slave_id = int(slave_id)
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)

        self.logger = logging.getLogger(f"PGEAGripper.{port}")
        self._lock = threading.Lock()

        self._ser: Optional[serial.Serial] = None
        self._is_connected = False
        self._initialized = False
        self._target_position = POSITION_MAX
        self._current_force = 50
        self._current_speed = 50
        self._cached_position = 0
        self._cached_grip_status = 0
        self._cached_error_code = 0
        self._last_error: str = ""

        if auto_connect and self.port:
            try:
                self.connect()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(f"自动连接夹爪失败: {exc}")

    # ---------- 生命周期 ----------

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @not_action
    def _open_serial(self) -> bool:
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            self._is_connected = self._ser.is_open
            return self._is_connected
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"open: {exc}"
            self.logger.error(self._last_error)
            self._is_connected = False
            return False

    @not_action
    def _ensure_connected(self) -> bool:
        if self._is_connected and self._ser and self._ser.is_open:
            return True
        return self._open_serial()

    # ---------- Modbus-RTU 基础 ----------

    @not_action
    def _send_frame(self, payload: bytes, expect_len: int = 8) -> Optional[bytes]:
        if not self._ensure_connected():
            return None
        frame = payload + _crc16_modbus(payload)
        with self._lock:
            try:
                assert self._ser is not None
                self._ser.reset_input_buffer()
                self._ser.write(frame)
                self._ser.flush()
                time.sleep(0.02)
                response = self._ser.read(expect_len)
                return response if response else None
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"send: {exc}"
                self.logger.error(self._last_error)
                return None

    @not_action
    def _write_register(self, address: int, value: int) -> bool:
        payload = bytes([
            self.slave_id & 0xFF, 0x06,
            (address >> 8) & 0xFF, address & 0xFF,
            (value >> 8) & 0xFF, value & 0xFF,
        ])
        resp = self._send_frame(payload, expect_len=8)
        return resp is not None and len(resp) >= 6 and resp[0] == self.slave_id and resp[1] == 0x06

    @not_action
    def _read_register(self, address: int) -> Optional[int]:
        payload = bytes([
            self.slave_id & 0xFF, 0x03,
            (address >> 8) & 0xFF, address & 0xFF,
            0x00, 0x01,
        ])
        resp = self._send_frame(payload, expect_len=7)
        if not resp or len(resp) < 5 or resp[0] != self.slave_id or resp[1] != 0x03:
            return None
        return (resp[3] << 8) | resp[4]

    # ---------- 连接管理 ----------

    @action(description="打开串口连接夹爪")
    def connect(self) -> Dict[str, Any]:
        ok = self._open_serial()
        return {
            "success": ok,
            "port": self.port,
            "baudrate": self.baudrate,
            "message": "夹爪连接成功" if ok else f"夹爪连接失败: {self._last_error}",
        }

    @action(description="断开夹爪串口连接")
    def disconnect(self) -> Dict[str, Any]:
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:  # noqa: BLE001
                pass
        self._is_connected = False
        return {"success": True, "message": "夹爪已断开"}

    # ---------- 初始化与运动控制 ----------

    @action(description="初始化夹爪（标定零点）。full_calibration=True 时进行完全初始化")
    def initialize(self, full_calibration: bool = False, wait: bool = True,
                   timeout: float = 10.0) -> Dict[str, Any]:
        init_value = 0xA5 if full_calibration else 0x01
        if not self._write_register(REG_INIT_GRIPPER, init_value):
            return {"success": False, "message": "发送初始化指令失败"}
        if not wait:
            return {"success": True, "message": "初始化指令已发送（未等待）"}

        deadline = time.time() + float(timeout)
        last_status = INIT_STATUS_NOT_INIT
        while time.time() < deadline:
            status = self._read_register(REG_INIT_STATUS)
            if status is None:
                time.sleep(0.1)
                continue
            last_status = status
            if status == INIT_STATUS_SUCCESS:
                self._initialized = True
                return {"success": True, "message": "夹爪初始化完成", "init_status": status}
            if status == INIT_STATUS_STROKE_ERROR:
                return {"success": False, "message": "行程标定异常，请检查是否被阻挡",
                        "init_status": status}
            time.sleep(0.1)
        return {"success": False, "message": "初始化超时", "init_status": last_status}

    @action(description="设置夹持力（20%-100%）")
    def set_force(self, force: int = 50) -> Dict[str, Any]:
        f = max(FORCE_MIN, min(FORCE_MAX, int(force)))
        ok = self._write_register(REG_FORCE, f)
        if ok:
            self._current_force = f
        return {"success": ok, "force": f, "message": f"力值已设置为 {f}%" if ok else "设置失败"}

    @action(description="设置运动速度（1%-100%）")
    def set_speed(self, speed: int = 50) -> Dict[str, Any]:
        s = max(SPEED_MIN, min(SPEED_MAX, int(speed)))
        ok = self._write_register(REG_SPEED, s)
        if ok:
            self._current_speed = s
        return {"success": ok, "speed": s, "message": f"速度已设置为 {s}%" if ok else "设置失败"}

    @action(description="移动到指定位置（0=完全闭合，1000=完全张开）")
    def move_to(self, position: int = 1000) -> Dict[str, Any]:
        try:
            pos_int = int(position)
        except (TypeError, ValueError):
            self.logger.warning(f"move_to 收到非法位置参数 {position!r}，回退到默认 {POSITION_MAX}")
            pos_int = POSITION_MAX
        p = max(POSITION_MIN, min(POSITION_MAX, pos_int))
        ok = self._write_register(REG_POSITION, p)
        if ok:
            self._target_position = p
        return {"success": ok, "target_position": p,
                "message": f"已发送移动命令至 {p}‰" if ok else "移动命令失败"}

    @action(description="夹爪张开（默认完全张开 1000）")
    def open_gripper(self, position: int = 1000, speed: Optional[int] = None,
                     wait: bool = True, timeout: float = 10.0) -> Dict[str, Any]:
        if speed is not None:
            self.set_speed(speed)
        move_res = self.move_to(position)
        if not move_res["success"]:
            return move_res
        if not wait:
            return {"success": True, "message": "张开命令已发送（未等待）", "position": position}
        status = self._wait_for_complete(timeout)
        return {
            "success": status == GRIP_STATUS_IN_POSITION,
            "grip_status": status,
            "grip_status_desc": GRIP_STATUS_DESC.get(status, "未知"),
            "position": self.get_current_position(),
            "message": f"张开完成（{GRIP_STATUS_DESC.get(status, '未知')}）",
        }

    @action(description="夹爪闭合夹持。force/speed 可选，wait=True 时返回是否成功夹住物体")
    def close_gripper(self, force: Optional[int] = None, speed: Optional[int] = None,
                      wait: bool = True, timeout: float = 10.0) -> Dict[str, Any]:
        if force is not None:
            self.set_force(force)
        if speed is not None:
            self.set_speed(speed)
        move_res = self.move_to(POSITION_MIN)
        if not move_res["success"]:
            return move_res
        if not wait:
            return {"success": True, "message": "闭合命令已发送（未等待）"}
        status = self._wait_for_complete(timeout)
        gripped = status == GRIP_STATUS_GRIPPED
        return {
            "success": True,
            "gripped": gripped,
            "grip_status": status,
            "grip_status_desc": GRIP_STATUS_DESC.get(status, "未知"),
            "position": self.get_current_position(),
            "message": "已夹住物体" if gripped else "已闭合（未检测到物体）",
        }

    @action(description="切换张开/闭合：当前接近闭合则张开，否则闭合")
    def toggle(self, position: int = 1000, force: int = 50,
               speed: int = 50) -> Dict[str, Any]:
        cur = self.get_current_position()
        if cur < POSITION_MAX // 2:
            return self.open_gripper(position=position, speed=speed)
        return self.close_gripper(force=force, speed=speed)

    @action(description="点动控制：1=正向，-1=反向，0=停止")
    def jog(self, direction: int = 0) -> Dict[str, Any]:
        d = int(direction)
        value = 0xFFFF if d < 0 else (1 if d > 0 else 0)
        ok = self._write_register(0x0102, value)
        return {"success": ok, "direction": d,
                "message": f"点动 direction={d} {'已发送' if ok else '失败'}"}

    @action(description="紧急停止当前运动")
    def stop(self) -> Dict[str, Any]:
        return self.jog(direction=0)

    # ---------- 状态读取 ----------

    @not_action
    def _wait_for_complete(self, timeout: float = 10.0, poll: float = 0.05) -> int:
        deadline = time.time() + float(timeout)
        status = GRIP_STATUS_MOVING
        while time.time() < deadline:
            s = self._read_register(REG_GRIP_STATUS)
            if s is not None:
                status = s
                self._cached_grip_status = s
                if s != GRIP_STATUS_MOVING:
                    return s
            time.sleep(poll)
        return status

    @action(description="读取夹爪当前实际位置（0-1000）")
    def get_current_position(self) -> int:
        v = self._read_register(REG_POSITION_FEEDBACK)
        if v is not None:
            self._cached_position = v
            return v
        return self._cached_position

    @action(description="读取当前夹持状态（0=运动中,1=到位,2=已夹住,3=掉落）")
    def get_grip_status(self) -> Dict[str, Any]:
        s = self._read_register(REG_GRIP_STATUS)
        if s is not None:
            self._cached_grip_status = s
        return {
            "grip_status": self._cached_grip_status,
            "description": GRIP_STATUS_DESC.get(self._cached_grip_status, "未知"),
        }

    @action(description="读取错误码（0 表示正常）")
    def get_error_code(self) -> int:
        v = self._read_register(REG_ERROR_CODE)
        if v is not None:
            self._cached_error_code = v
            return v
        return self._cached_error_code

    # ---------- 周期广播属性 ----------

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=5.0)
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    @topic_config(period=2.0)
    def position(self) -> int:
        """当前位置（0-1000）。"""
        return self._cached_position

    @property
    @topic_config(period=2.0)
    def grip_status(self) -> str:
        return GRIP_STATUS_DESC.get(self._cached_grip_status, "未知")

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    g = PGEAGripperDevice(port="COM6", auto_connect=True)
    if g._is_connected:
        print(g.initialize(full_calibration=False))
        print(g.open_gripper(position=1000))
        time.sleep(1)
        print(g.close_gripper(force=40, speed=30))
        g.disconnect()
    else:
        print("夹爪连接失败，请检查串口与硬件。")

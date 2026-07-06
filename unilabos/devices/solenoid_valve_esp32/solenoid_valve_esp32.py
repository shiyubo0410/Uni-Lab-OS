# -*- coding: utf-8 -*-
"""
ESP32 阀门控制器驱动
通过串口控制 ESP32 引脚高低电平，实现 5 路阀门开关。

通道映射:
  通道1 → GPIO2, 通道2 → GPIO15, 通道3 → GPIO4,
  通道4 → GPIO16, 通道5 → GPIO17

串口协议:
  打开: PIN:{pin}:ON\n
  关闭: PIN:{pin}:OFF\n
  握手: PING\n        -> 固件回 ESP32_VALVE\n （无副作用, 供网关探测识别 + 掉线心跳）
"""

import logging
import time
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config

# 仅用于类型注解: BaseROS2DeviceNode 会连带 import rclpy, 而网关(纯 Python 无 ROS2)
# 没有 rclpy。放进 TYPE_CHECKING, 运行时不导入, 避免网关加载驱动时崩在 import rclpy。
if TYPE_CHECKING:
    from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode

VALVE_CHANNEL_PIN_MAP = {
    1: 2,
    2: 15,
    3: 4,
    4: 16,
    5: 17,
}


@device(
    id="solenoid_valve_esp32",
    category=["valve", "wxf", "esp32"],
    description="ESP32 五路阀门控制器（GPIO 高低电平控制）",
    display_name="ESP32阀门控制器",
)
class ESP32ValveController:
    _ros_node: "BaseROS2DeviceNode"

    def __init__(self, port: str = "COM7", baudrate: int = 115200,
                 timeout: float = 1.0, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.logger = logging.getLogger(f"ESP32Valve.{port}")

        self._ser: Optional[serial.Serial] = None
        self._is_connected = False
        self._valve_states: Dict[int, bool] = {ch: False for ch in range(1, 6)}
        self._io_lock: Lock = Lock()

        # 网关健康检查约定 (与 journeyman 等 RS-485 驱动一致): 连上时 hardware_interface
        # 是串口对象, 未连上时退化成 port 字符串。网关据此判断重连是否真的成功——
        # 否则拔线后每次重建驱动都"成功"、错误计数被清零, 永远触发不了掉线下线。
        self.hardware_interface: Any = port

        if self.port:
            self.connect()

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode") -> None:
        self._ros_node = ros_node

    def _send_command(self, pin: int, on: bool) -> bool:
        """向 ESP32 发送引脚控制指令"""
        if not self._is_connected or self._ser is None:
            self.logger.error("串口未连接")
            return False
        cmd = f"PIN:{pin}:{'ON' if on else 'OFF'}\n"
        try:
            with self._io_lock:
                self._ser.write(cmd.encode("utf-8"))
                time.sleep(0.1)
                while self._ser.in_waiting:
                    resp = self._ser.readline().decode("utf-8", errors="ignore").strip()
                    if resp:
                        self.logger.info(f"ESP32 响应: {resp}")
            return True
        except Exception as e:
            self.logger.error(f"发送指令失败: {e}")
            return False

    def connect(self) -> bool:
        if self._is_connected:
            return True
        try:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self._is_connected = True
            self.hardware_interface = self._ser
            self.logger.info(f"ESP32 已连接: {self.port} @ {self.baudrate}")
            return True
        except Exception as e:
            self.logger.error(f"ESP32 连接失败: {e}")
            self._is_connected = False
            self.hardware_interface = self.port
            return False

    def disconnect(self) -> bool:
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._is_connected = False
        self.hardware_interface = self.port
        self.logger.info("ESP32 已断开")
        return True

    @action(description="打开指定通道的阀门（置高电平）")
    def open_valve(self, channel: int = 1) -> bool:
        channel = int(channel)
        pin = VALVE_CHANNEL_PIN_MAP.get(channel)
        if pin is None:
            self.logger.error(f"无效通道 {channel}，仅支持 1-5")
            return False
        ok = self._send_command(pin, on=True)
        if ok:
            self._valve_states[channel] = True
            self.logger.info(f"通道 {channel} (GPIO{pin}) 阀门已打开")
        return ok

    @action(description="关闭指定通道的阀门（置低电平）")
    def close_valve(self, channel: int = 1) -> bool:
        channel = int(channel)
        pin = VALVE_CHANNEL_PIN_MAP.get(channel)
        if pin is None:
            self.logger.error(f"无效通道 {channel}，仅支持 1-5")
            return False
        ok = self._send_command(pin, on=False)
        if ok:
            self._valve_states[channel] = False
            self.logger.info(f"通道 {channel} (GPIO{pin}) 阀门已关闭")
        return ok

    @property
    @topic_config(period=3.0)
    def firmware_alive(self) -> bool:
        """真读串口的心跳：发 PING 期望固件回 ESP32_VALVE。

        无副作用（不动 GPIO），读不到 / 不匹配则抛异常，供网关掉线检测。
        注意：不要用 is_connected / valve_states 这类纯缓存属性做心跳——它们
        从不抛异常，拔线后网关判断不出掉线。
        """
        if not self._is_connected or self._ser is None:
            raise RuntimeError("ESP32 串口未连接")
        with self._io_lock:
            self._ser.reset_input_buffer()
            self._ser.write(b"PING\n")
            time.sleep(0.1)
            resp = self._ser.readline().decode("utf-8", errors="ignore").strip()
        if not resp.startswith("ESP32_VALVE"):
            raise RuntimeError(f"ESP32 握手失败，PING 响应: {resp!r}")
        return True

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def valve_states(self) -> str:
        """各通道阀门状态，如 '1:开 2:关 3:关 4:关 5:关'"""
        parts = [f"{ch}:{'开' if on else '关'}" for ch, on in sorted(self._valve_states.items())]
        return " ".join(parts)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    ctrl = ESP32ValveController(port="COM8")
    if not ctrl.is_connected:
        print("连接失败")
        exit(1)

    try:
        ctrl.open_valve(channel=1)
        time.sleep(2)
        ctrl.close_valve(channel=1)
    finally:
        ctrl.disconnect()

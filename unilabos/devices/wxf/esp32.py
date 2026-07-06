# -*- coding: utf-8 -*-
"""
ESP32 三通切换阀驱动（通信转发 / hardware_proxy 版）

一块 ESP32 通过“一个串口”同时控制 5 路三通阀（GPIO 高低电平）。
本驱动把每一路阀做成一个“独立设备”，5 个阀共用同一个串口通信设备
（框架内置的 `serial` 节点 ROS2SerialNode）。

工作原理（hardware_proxy，与 runze 泵同款）：
  - 图里放 1 个 `serial` 通信节点（如 id=serial_esp32），它独占串口。
  - 每个阀设备 __init__ 时把 self.hardware_interface 设为通信节点的 id 字符串。
  - 阀设备自身实现 send_command()，内部操作 self.hardware_interface。
  - 工作站 ROS2WorkstationNode 初始化子设备后，检测到 self.hardware_interface 是字符串
    且等于某个通信子设备 id，于是把通信设备的“真实串口句柄”替换进 self.hardware_interface，
    并把 5 个阀的串口锁统一成同一把总线锁（自动串行化，避免交叉读写）。
  - 之后阀的 send_command() 就直接作用在真实串口上，完成转发。

通道 → GPIO 映射：
  通道1 → GPIO2, 通道2 → GPIO15, 通道3 → GPIO4, 通道4 → GPIO16, 通道5 → GPIO17

串口协议：
  打开: PIN:{pin}:ON      关闭: PIN:{pin}:OFF
"""

import logging
import time
from threading import Lock
from typing import Optional

from unilabos.registry.decorators import (
    action,
    device,
    not_action,
    topic_config,
    HardwareInterface,
    InputHandle,
    OutputHandle,
    Side,
)
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode

VALVE_CHANNEL_PIN_MAP = {
    1: 2,
    2: 15,
    3: 4,
    4: 16,
    5: 17,
}


@device(
    id="wxf_esp32_valve",
    category=["valve", "wxf", "esp32"],
    description="ESP32 三通切换阀（单路，经串口通信设备转发控制 GPIO 高低电平）",
    display_name="ESP32三通阀",
    icon="e30f06b7-7828-472e-b840-89e7fe068f06.ico",
    handles=[
        InputHandle(key="1", data_type="fluid", label="进液(common)", side=Side.NORTH),
        OutputHandle(key="2", data_type="fluid", label="收集(A)", side=Side.SOUTH),
        OutputHandle(key="3", data_type="fluid", label="废液(B)", side=Side.EAST),
    ],
    hardware_interface=HardwareInterface(
        name="hardware_interface",
        read="send_command",
        write="send_command",
    ),
)
class ESP32ThreeWayValve:
    _ros_node: BaseROS2DeviceNode

    def __init__(self, channel: int = 1, communication: str = "serial_esp32", **kwargs):
        self.channel = int(channel)
        # 关键：初值为通信设备 id 字符串；工作站 hardware_proxy 会把它替换为真实串口句柄。
        self.hardware_interface = communication
        # 会被工作站替换为所有共享同一串口的设备统一的总线锁
        self._query_lock = Lock()
        self._valve_state = False
        self.logger = logging.getLogger(f"ESP32Valve.ch{self.channel}")

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @not_action
    def send_command(self, command: str) -> str:
        """向 ESP32 发送一条指令并读回响应。self.hardware_interface 由工作站代理注入为真实串口。"""
        iface = self.hardware_interface
        if not hasattr(iface, "write"):
            # 还未被工作站代理注入真实串口（说明该阀没和 serial 通信节点在同一工作站下）
            self.logger.error(
                f"串口未就绪(hardware_interface={iface!r})：请确认阀与 serial 通信节点同属一个工作站"
            )
            return ""
        full = f"{command}\n".encode("ascii")
        with self._query_lock:
            iface.write(full)
            time.sleep(0.05)
            resp = iface.read_until(b"\n")
        return resp.decode("utf-8", errors="ignore").strip()

    @not_action
    def _switch(self, on: bool) -> bool:
        pin = VALVE_CHANNEL_PIN_MAP.get(self.channel)
        if pin is None:
            self.logger.error(f"无效通道 {self.channel}，仅支持 1-5")
            return False
        resp = self.send_command(f"PIN:{pin}:{'ON' if on else 'OFF'}")
        self._valve_state = on
        self.logger.info(f"通道 {self.channel} (GPIO{pin}) -> {'ON' if on else 'OFF'}, resp={resp!r}")
        return True

    @action(description="打开阀门（置高电平 / 切到 A 路）")
    def open_valve(self) -> bool:
        return self._switch(True)

    @action(description="关闭阀门（置低电平 / 切到 B 路）")
    def close_valve(self) -> bool:
        return self._switch(False)

    @action(description="切换三通阀位置：command 取 ON/OFF、A/B 或 1/0")
    def set_valve_position(self, command: str = "OFF") -> bool:
        on = str(command).strip().upper() in ("ON", "A", "1", "OPEN", "HIGH")
        return self._switch(on)

    @property
    @topic_config(period=2.0)
    def valve_position(self) -> str:
        """当前阀位：A(开) / B(关)"""
        return "A(开)" if self._valve_state else "B(关)"

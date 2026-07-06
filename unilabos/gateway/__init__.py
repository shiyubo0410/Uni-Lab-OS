"""
Uni-Lab IoT 网关 - 极简版 WebSocket 客户端

不依赖 ROS 2、不依赖 HostNode，单进程 asyncio 模型。
适用于：香橙派 Zero 2W / RPi Zero 2W / ESP32 桥接卡等轻量边缘设备。

使用方式：
    unilab-gateway --config gateway.yaml --ak XXX --sk XXX
"""

from unilabos.gateway.device import DeviceWorker, MockDevice
from unilabos.gateway.ws import GatewayClient

__all__ = ["GatewayClient", "DeviceWorker", "MockDevice"]

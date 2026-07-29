"""
Uni-Lab IoT 网关 - 极简版 WebSocket 客户端

不依赖 ROS 2、不依赖 HostNode，单进程 asyncio 模型。
适用于：香橙派 Zero 2W / RPi Zero 2W / ESP32 桥接卡等轻量边缘设备。

使用方式：
    unilab-gateway --config gateway.yaml --ak XXX --sk XXX
"""

__all__ = ["GatewayClient", "DeviceWorker", "MockDevice"]

# 惰性导入（PEP 562）：只在真正访问这些名字时才加载对应模块。
# 目的：`python -m unilabos.gateway.agent.local_cli` 等只用到 agent 子包的场景，
# 不会因为父包急切 import ws（依赖 websockets）而在没装 websockets 的开发机上报错。
_LAZY = {
    "GatewayClient": ("unilabos.gateway.ws", "GatewayClient"),
    "DeviceWorker": ("unilabos.gateway.device", "DeviceWorker"),
    "MockDevice": ("unilabos.gateway.device", "MockDevice"),
}


def __getattr__(name):  # noqa: D401
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    mod = importlib.import_module(target[0])
    return getattr(mod, target[1])


def __dir__():
    return sorted(list(globals().keys()) + list(_LAZY.keys()))

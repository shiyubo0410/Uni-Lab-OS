"""
设备自动发现模块

通过串口指纹识别自动发现并配置设备，实现"插上线看到数"的零配置体验。
"""

from .scanner import scan_all_ports

__all__ = ["scan_all_ports"]

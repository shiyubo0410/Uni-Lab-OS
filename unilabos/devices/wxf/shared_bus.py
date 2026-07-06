# -*- coding: utf-8 -*-
"""
共享串口池。
同一串口的多个设备驱动（泵、传感器等）通过此模块复用同一个 Serial 对象。

用法:
    from unilabos.devices.wxf.shared_bus import get_serial, release_serial

    ser, lock = get_serial("COM9", 9600)
    with lock:
        ser.write(...)
        resp = ser.read(...)

    # 设备断开时释放引用
    release_serial("COM9")
"""

import threading
from typing import Tuple
from serial import Serial

_pool: dict[str, Serial] = {}
_locks: dict[str, threading.RLock] = {}
_ref_counts: dict[str, int] = {}
_pool_lock = threading.Lock()


def get_serial(port: str, baudrate: int = 9600, timeout: float = 3.0) -> Tuple[Serial, threading.RLock]:
    """
    获取共享的 Serial 对象和对应的线程锁。
    相同 port 复用同一个连接，引用计数 +1。
    """
    with _pool_lock:
        if port not in _pool or not _pool[port].is_open:
            _pool[port] = Serial(
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=timeout,
            )
            _locks[port] = threading.RLock()
            _ref_counts[port] = 0
        _ref_counts[port] += 1
        return _pool[port], _locks[port]


def release_serial(port: str):
    """
    释放引用，引用计数归零时关闭串口。
    """
    with _pool_lock:
        if port in _ref_counts:
            _ref_counts[port] -= 1
            if _ref_counts[port] <= 0:
                ser = _pool.pop(port, None)
                if ser and ser.is_open:
                    ser.close()
                _locks.pop(port, None)
                _ref_counts.pop(port, None)

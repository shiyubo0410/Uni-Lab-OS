# -*- coding: utf-8 -*-
"""加载 ``cr_sdk.dll`` 及其全部运行时依赖。

本模块对外只暴露一个函数 ``get_cr_sdk()``，它幂等地返回已经预装好的
``ctypes.WinDLL`` 句柄。进程第一次调用会：

1. 把 ``sdk/libs/x64`` 目录加进 Windows 的 DLL 搜索路径
   （``os.add_dll_directory``，Python 3.8+ 必需）。
2. 逐个 ``WinDLL`` 预加载 12 个依赖 DLL（vc runtime、protobuf-c、
   pthreadVC2、厂家组件等）。
3. 最后加载主 ``cr_sdk.dll``。

之后所有调用都复用缓存句柄。预加载这一步在
``unilabos/devices/fdu/probe_sdk.py`` 里已于 Python 3.11.11 环境实测通过。
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---- 路径：DLL 都放在 C# SDK 的 sdk/libs/x64 目录下 ----------------------
_PKG_DIR = Path(__file__).resolve().parent               # .../fdu/cgxi_native
_FDU_DIR = _PKG_DIR.parent                               # .../fdu
DLL_DIR = (
    _FDU_DIR
    / "CGXi-Robot-SDK-C#-v2.2e"
    / "CGXi-Robot-SDK-C#-v2.2e"
    / "sdk"
    / "libs"
    / "x64"
).resolve()

MAIN_DLL = "cr_sdk.dll"

# ---- 依赖清单：顺序按依赖链「VC 运行时 → 第三方 → 厂家组件」给 -----------
_DEPENDENCIES = [
    # VC 运行时
    "msvcp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "ucrtbase.dll",
    "msvcr100.dll",
    # 第三方
    "pthreadVC2.dll",
    "zlib.dll",
    "protobuf-c.dll",
    "protobuf-rpc.dll",
    # 厂家组件
    "LogStorageDll.dll",
    "RobotConfigDll.dll",
    "CGXIZip.dll",
]

# ---- 单例缓存 -------------------------------------------------------------
_cr_sdk_handle: Optional[ctypes.WinDLL] = None
_load_lock = threading.Lock()


def _preload_dependencies() -> None:
    """预加载全部依赖 DLL，忽略不存在或加载失败的项。

    失败项只做 warning，因为部分 DLL（如 msvcr100.dll）在新机器上可能本就存在
    于系统路径而不在 SDK 目录里，不必硬性要求。
    """
    for name in _DEPENDENCIES:
        path = DLL_DIR / name
        if not path.is_file():
            logger.debug("依赖 DLL 不在目录内，跳过: %s", name)
            continue
        try:
            ctypes.WinDLL(str(path))
            logger.debug("已预加载依赖 DLL: %s", name)
        except OSError as exc:
            logger.warning("预加载依赖 DLL 失败（%s）: %s", name, exc)


def get_cr_sdk() -> ctypes.WinDLL:
    """幂等地返回已加载好的 ``cr_sdk.dll`` 句柄。

    Raises
    ------
    FileNotFoundError
        DLL 目录或主 DLL 不存在。
    OSError
        主 DLL 加载失败（会在日志里附带错误码）。
    """
    global _cr_sdk_handle
    if _cr_sdk_handle is not None:
        return _cr_sdk_handle

    with _load_lock:
        if _cr_sdk_handle is not None:
            return _cr_sdk_handle

        if not DLL_DIR.is_dir():
            raise FileNotFoundError(f"cr_sdk DLL 目录不存在: {DLL_DIR}")

        main_path = DLL_DIR / MAIN_DLL
        if not main_path.is_file():
            raise FileNotFoundError(f"主 DLL 不存在: {main_path}")

        # Python 3.8+ 必须显式 add_dll_directory 才能找到同目录里的间接依赖
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(DLL_DIR))
            except OSError as exc:  # pragma: no cover - 目录存在性已提前校验
                logger.warning("add_dll_directory 失败: %s", exc)

        _preload_dependencies()

        try:
            handle = ctypes.WinDLL(str(main_path))
        except OSError as exc:
            raise OSError(
                f"加载 {MAIN_DLL} 失败（可能缺依赖或 32/64 位不匹配）: {exc}"
            ) from exc

        logger.info("cr_sdk.dll 加载成功: %s", main_path)
        _cr_sdk_handle = handle
        return handle


__all__ = ["DLL_DIR", "MAIN_DLL", "get_cr_sdk"]

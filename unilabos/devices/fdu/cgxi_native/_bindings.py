# -*- coding: utf-8 -*-
"""给 ``cr_sdk.dll`` 里待用函数打 ``argtypes`` / ``restype``。

全部函数签名来自厂家 C# SDK 手册
《CGXi-协作机器人-sdk使用手册（C#）-v2.20e.pdf》，章节号在每个绑定的注释里标出。

C# → Python ctypes 对应关系
----------------------------
- ``int``                → ``c_int``
- ``uint``               → ``c_uint``
- ``bool``               → ``c_bool`` (1 字节)
- ``ref int``            → ``POINTER(c_int)``  —— 调用时用 ``byref(x)``
- ``string``             → ``c_char_p``        —— ANSI/UTF-8 编码后的 bytes
- ``byte[]``             → ``c_char_p`` / 预分配 ``ctypes.create_string_buffer(N)``
- ``double[N]``          → ``POINTER(c_double)`` / ``(c_double * N)()``
- ``PointControlPara``   → ``PointControlPara``（按值，ctypes 会按 MSVC x64 ABI
  自动在栈上分配并传指针，调用层 **不需要** ``byref``）
- ``ref PointControlPara`` → ``POINTER(PointControlPara)`` —— 调用时用 ``byref``

大 struct 按值传参的 ABI 提示
-----------------------------
C# 里 ``CRresult cr_moveJ(int, PointControlPara)`` 看起来是"值传递"，但
底层 ``cr_sdk.dll`` 的 C 函数原型按 MSVC x64 ABI 规则为：结构体 > 8 字节的
参数由调用方在栈上分配并传指针。ctypes 对 ``argtypes = [c_int, Struct]``
的实现已自动处理这一层，所以 Python 侧直接传 ``Struct()`` 实例即可。
"""

from __future__ import annotations

import logging
import threading
from ctypes import (
    POINTER,
    c_bool,
    c_char_p,
    c_double,
    c_int,
    c_uint,
)
from typing import Optional, Sequence

from ._loader import get_cr_sdk
from ._structs import (
    Lua_ScriptStatus,
    PointControlPara,
    PointControlParaSimple,
    RobotModes,
)

logger = logging.getLogger(__name__)

_BIND_LOCK = threading.Lock()
_BOUND = False
MISSING_FUNCTIONS: list[str] = []  # 运行时记录 DLL 里实际找不到的函数名


def _bind(
    cr,
    name: str,
    argtypes: Sequence,
    restype,
) -> None:
    """单独给一个函数打签名；不存在时记录到 MISSING_FUNCTIONS 而不抛异常。

    这样即使厂家某个小版本暂时没导出某个接口，整个包仍然可用。
    """
    try:
        fn = getattr(cr, name)
    except AttributeError:
        MISSING_FUNCTIONS.append(name)
        logger.warning("cr_sdk.dll 未导出函数 %s，相关功能将不可用", name)
        return
    fn.argtypes = list(argtypes)
    fn.restype = restype


def bind_all() -> "object":
    """幂等地给 DLL 全部函数打签名，返回绑定好的 DLL 句柄。"""
    global _BOUND
    cr = get_cr_sdk()
    if _BOUND:
        return cr
    with _BIND_LOCK:
        if _BOUND:
            return cr
        _apply_signatures(cr)
        _BOUND = True
    return cr


def _apply_signatures(cr) -> None:
    # ============================================================
    # 3.1.1 基础接口 / 连接
    # ============================================================

    # 3.1.1.1  CRresult cr_create_robot(ref int robotHandle, string ipAddr,
    #                                    int port, string passwd)
    _bind(cr, "cr_create_robot",
          [POINTER(c_int), c_char_p, c_int, c_char_p], c_int)

    # 3.1.1.2  CRresult cr_destroy_robot(int robotHandle)
    _bind(cr, "cr_destroy_robot", [c_int], c_int)

    # 3.1.1.12 CRresult cr_get_sdk_version(byte[] version)
    #   传入预分配缓冲区（手册示例用 32 字节已足够）
    _bind(cr, "cr_get_sdk_version", [c_char_p], c_int)

    # ============================================================
    # 3.1.1.x  电源 / 使能 / 故障复位
    # ============================================================
    for fname in ("cr_poweron", "cr_poweroff", "cr_enable", "cr_disable",
                  "cr_FaultReset"):
        _bind(cr, fname, [c_int], c_int)

    # ============================================================
    # 状态读取
    # ============================================================

    # CRresult cr_get_robotMode(int robotHandle, ref RobotModes robotMode)
    _bind(cr, "cr_get_robotMode", [c_int, POINTER(c_int)], c_int)

    # CRresult cr_get_jointActualPos(int robotHandle, double[6] jointPos)
    _bind(cr, "cr_get_jointActualPos", [c_int, POINTER(c_double)], c_int)

    # CRresult cr_get_tcpActualPose(int robotHandle, double[6] pose)
    _bind(cr, "cr_get_tcpActualPose", [c_int, POINTER(c_double)], c_int)

    # 3.2.1.11 CRresult cr_get_robotMoveStatus(int robotHandle, ref int isRobotMoving)
    _bind(cr, "cr_get_robotMoveStatus", [c_int, POINTER(c_int)], c_int)

    # CRresult cr_get_robotSpeedPercent(int robotHandle, ref uint speedPercent)
    _bind(cr, "cr_get_robotSpeedPercent", [c_int, POINTER(c_uint)], c_int)

    # CRresult cr_set_robotSpeedPercent(int robotHandle, uint speedPercent)
    _bind(cr, "cr_set_robotSpeedPercent", [c_int, c_uint], c_int)

    # ============================================================
    # 3.2.1  运动控制
    # ============================================================

    # 3.2.1.1 CRresult cr_moveJ(int robotHandle, PointControlPara pointControlPara)
    _bind(cr, "cr_moveJ", [c_int, PointControlPara], c_int)

    # 3.2.1.2 CRresult cr_move_joint(int robotHandle, PointControlPara pointControlPara,
    #                                 bool isBlock)
    _bind(cr, "cr_move_joint", [c_int, PointControlPara, c_bool], c_int)

    # 3.2.1.3 CRresult cr_moveL(int robotHandle, PointControlPara pointControlPara)
    _bind(cr, "cr_moveL", [c_int, PointControlPara], c_int)

    # 3.2.1.4 CRresult cr_move_line(int robotHandle, PointControlPara pointControlPara,
    #                                bool isBlock)
    _bind(cr, "cr_move_line", [c_int, PointControlPara, c_bool], c_int)

    # 3.2.1.9 CRresult cr_move_pointControlPara_transfer(int robotHandle,
    #           PointControlParaSimple in, ref PointControlPara out)
    _bind(cr, "cr_move_pointControlPara_transfer",
          [c_int, PointControlParaSimple, POINTER(PointControlPara)], c_int)

    # ============================================================
    # 3.1.2  程序 / 工程
    # ============================================================

    # 3.1.2.1  CRresult cr_downloadProgram(int robotHandle, string programfile)
    _bind(cr, "cr_downloadProgram", [c_int, c_char_p], c_int)

    # 3.1.2.10 CRresult cr_downloadProject(int robotHandle, string crpFilepathname,
    #                                       string crscriptFilepathname)
    _bind(cr, "cr_downloadProject", [c_int, c_char_p, c_char_p], c_int)

    # 3.1.2.4  CRresult cr_play(int robotHandle)
    # 3.1.2.5  CRresult cr_stop(int robotHandle)
    # 3.1.2.6  CRresult cr_pause(int robotHandle)
    # 注：手册里**没有** cr_resume——恢复语义由上层再调用 cr_play 实现。
    # 若将来 DLL 导出了 cr_resume，下面的动态绑定会自动生效；否则 _bind
    # 会把它记入 MISSING_FUNCTIONS，上层据此回退到 cr_play。
    for fname in ("cr_play", "cr_pause", "cr_resume", "cr_stop"):
        _bind(cr, fname, [c_int], c_int)

    # 3.1.2.8  CRresult cr_get_lua_scriptstatus(int robotHandle,
    #              ref Lua_ScriptStatus scriptstatus)
    _bind(cr, "cr_get_lua_scriptstatus", [c_int, POINTER(c_int)], c_int)


__all__ = ["bind_all", "MISSING_FUNCTIONS"]

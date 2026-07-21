# -*- coding: utf-8 -*-
"""CGXi 协作机器人的 Python 3.11 原生绑定（方案 6）。

背景
----
厂家 Python SDK (``cgxiapi.pyd``) 只编译了 **Python 3.7** 版本，无法被
Uni-Lab 环境（Python 3.11.11）加载，见 `probe_sdk.py` 的诊断记录。

本包用 ``ctypes`` 直接调用厂家发布的原生 C 库 ``cr_sdk.dll``（随 C# SDK 一起
附送，是 C ABI，与 Python 版本无关），做出一个 **完全跨 Python 版本** 的替代
实现 ``CGXiRobotNative``，其 API 与旧
``unilabos.devices.ctr.skills.changguangxi.robot_utils.CGXiRobot`` 保持一致，
方便上层 ``fdu/robot.py`` 驱动 **无缝切换**。

模块划分
--------
- ``_structs``   —— 所有 ``ctypes.Structure`` 定义（照搬 Py37 SDK 的 ``basestruct.py``）
- ``_loader``    —— 单例方式加载 ``cr_sdk.dll`` + 12 个依赖 DLL
- ``_bindings``  —— 给 DLL 里待用的 25+ 个函数打上 ``argtypes`` / ``restype``
- ``robot``      —— ``CGXiRobotNative`` 高层控制类

验证状态
--------
2026-04-22 在 Python 3.11.11 (conda ``unilab`` env) 下已通过 ``probe_sdk``
跑通 ``cr_get_sdk_version`` → ``v2.20e``；后续运动函数签名基于手册 v2.20e 第
3.1 / 3.2 节 C# 原型推导，待真机联调最终校验。
"""

from __future__ import annotations

from ._structs import (  # noqa: F401  (re-export commonly used enums/structs)
    CoordinateType,
    CRresult,
    JointModes,
    MotiontriggerMode,
    MoveType,
    PointControlPara,
    PointControlParaSimple,
    PointTransType,
    PoseTranType,
    RobotModes,
)
from .robot import CGXiRobotNative  # noqa: F401

__all__ = [
    "CGXiRobotNative",
    "CoordinateType",
    "CRresult",
    "JointModes",
    "MotiontriggerMode",
    "MoveType",
    "PointControlPara",
    "PointControlParaSimple",
    "PointTransType",
    "PoseTranType",
    "RobotModes",
]

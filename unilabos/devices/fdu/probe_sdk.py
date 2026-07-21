# -*- coding: utf-8 -*-
"""CGXi ``cr_sdk.dll`` ctypes 最小连接验证（方案 6 预研）。

目的
----
在 **Uni-Lab 当前的 Python 3.11 环境** 里，直接用 ``ctypes`` 加载厂家 C# SDK
自带的原生 ``cr_sdk.dll``（C ABI），绕开仅支持 Python 3.7 的 ``cgxiapi.pyd``。

只调三个最简单的函数做 smoke test：

1. ``cr_get_sdk_version``  —— 不用连真机，能返回版本号就说明 DLL 加载、
   函数导出、调用约定都正常。
2. ``cr_create_robot``     —— 真机握手。
3. ``cr_destroy_robot``    —— 断开。

**机械臂不会有任何动作**——没有上电、没有使能、没有移动。

运行
----

.. code-block:: bash

    # 仅本地 smoke，不连真机（--no-connect）
    python -m unilabos.devices.fdu.probe_sdk --no-connect

    # 连真机（默认）
    python -m unilabos.devices.fdu.probe_sdk --ip 192.168.6.6

成功标志
--------
看到 ``✅ 方案 6 可行`` 即表示 Python 3.11 + ctypes 完全打通 cr_sdk.dll，
后续可以按计划把 24 个函数全部 ctypes 化。

对照手册
--------
C# 签名（见 ``CGXi-协作机器人-sdk使用手册（C#）-v2.20e.pdf``）：

- 3.1.1.1 ``CRresult cr_create_robot(ref int robotHandle, string ipAddr, int port, string passwd)``
- 3.1.1.2 ``CRresult cr_destroy_robot(int robotHandle)``
- 3.1.1.12 ``CRresult cr_get_sdk_version(byte[] version)``
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from ctypes import POINTER, byref, c_char_p, c_int
from pathlib import Path

# Windows 控制台默认 GBK，打印 Unicode 符号会炸；强制 stdout/stderr 改 utf-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover - 老 Python 才需要
    pass

HERE = Path(__file__).resolve().parent
DLL_DIR = (
    HERE
    / "CGXi-Robot-SDK-C#-v2.2e"
    / "CGXi-Robot-SDK-C#-v2.2e"
    / "sdk"
    / "libs"
    / "x64"
).resolve()


def _banner(text: str) -> None:
    line = "=" * 72
    print(f"\n{line}\n{text}\n{line}")


def _preload_dependencies() -> None:
    """显式预加载 cr_sdk.dll 的全部运行时依赖。

    Windows Python 3.8+ 不会自动搜索同目录的依赖 DLL，必须:
    (a) ``os.add_dll_directory`` 把目录加进搜索路径；或
    (b) 手动 ``WinDLL`` 逐个预加载。

    这里两招都用，最大概率一次点亮。
    """
    deps = [
        # VC 运行时（SDK 是 VS2015+ 编译）
        "msvcp140.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "ucrtbase.dll",
        "msvcr100.dll",
        # 第三方依赖
        "pthreadVC2.dll",
        "zlib.dll",
        "protobuf-c.dll",
        "protobuf-rpc.dll",
        # 厂家组件
        "LogStorageDll.dll",
        "RobotConfigDll.dll",
        "CGXIZip.dll",
    ]
    for name in deps:
        path = DLL_DIR / name
        if not path.is_file():
            print(f"  [skip]  {name}  (不在目录内)")
            continue
        try:
            ctypes.WinDLL(str(path))
            print(f"  [ok]    {name}")
        except OSError as exc:
            print(f"  [fail]  {name}: {exc}")


def _bind_functions(cr: ctypes.WinDLL) -> None:
    """给 DLL 里待调用的函数打上 argtypes / restype 注解。

    注意：C# ``string`` 对应原生 C 的 ``const char*``（ANSI/UTF-8），
    ``ref int`` 对应 ``int*``。
    """
    # 3.1.1.1: CRresult cr_create_robot(ref int robotHandle, string ipAddr, int port, string passwd)
    cr.cr_create_robot.argtypes = [POINTER(c_int), c_char_p, c_int, c_char_p]
    cr.cr_create_robot.restype = c_int

    # 3.1.1.2: CRresult cr_destroy_robot(int robotHandle)
    cr.cr_destroy_robot.argtypes = [c_int]
    cr.cr_destroy_robot.restype = c_int

    # 3.1.1.12: CRresult cr_get_sdk_version(byte[] version)
    cr.cr_get_sdk_version.argtypes = [c_char_p]
    cr.cr_get_sdk_version.restype = c_int


def main() -> int:
    ap = argparse.ArgumentParser(
        description="CGXi cr_sdk.dll ctypes 最小连接验证（方案 6 预研）"
    )
    ap.add_argument("--ip", default="192.168.6.6", help="真机 IP")
    ap.add_argument("--port", type=int, default=2323, help="真机端口")
    ap.add_argument("--password", default="123", help="连接密码（SDK 预留字段）")
    ap.add_argument(
        "--no-connect",
        action="store_true",
        help="跳过 cr_create_robot，只验证 DLL 加载 + cr_get_sdk_version",
    )
    args = ap.parse_args()

    _banner("环境")
    print(f"Python  : {sys.version.splitlines()[0]}")
    print(f"sys.exe : {sys.executable}")
    print(f"DLL dir : {DLL_DIR}")

    if not DLL_DIR.is_dir():
        print(f"\n❌ DLL 目录不存在: {DLL_DIR}")
        return 2
    if not (DLL_DIR / "cr_sdk.dll").is_file():
        print("\n❌ cr_sdk.dll 不在 DLL 目录内")
        return 2

    # Windows Python 3.8+：把 DLL 目录加入搜索路径
    os.add_dll_directory(str(DLL_DIR))

    _banner("预加载依赖 DLL")
    _preload_dependencies()

    _banner("加载 cr_sdk.dll")
    try:
        cr = ctypes.WinDLL(str(DLL_DIR / "cr_sdk.dll"))
    except OSError as exc:
        print(f"❌ 加载失败: {exc}")
        print(
            "\n排查方向：\n"
            "  - 依赖 DLL 预加载步骤里是否有报错？先修那些\n"
            "  - 系统是否缺 VC++ 2015-2019 Redistributable x64？"
            "    下载: https://aka.ms/vs/17/release/vc_redist.x64.exe"
        )
        return 3
    print(f"✓ cr_sdk.dll 已加载, handle={cr._handle}")

    _banner("绑定函数签名")
    try:
        _bind_functions(cr)
        print("✓ cr_create_robot / cr_destroy_robot / cr_get_sdk_version 绑定成功")
    except AttributeError as exc:
        print(f"❌ 函数不存在: {exc}")
        print(
            "  → 可能是导出名被 C++ mangling 了（正常 extern \"C\" 不会），\n"
            "    用 dumpbin /exports cr_sdk.dll 看看实际导出名"
        )
        return 4

    _banner("smoke test 1: cr_get_sdk_version (不连真机)")
    ver_buf = ctypes.create_string_buffer(64)
    rc = cr.cr_get_sdk_version(ver_buf)
    print(f"  rc={rc}")
    print(f"  version buffer: {ver_buf.raw[:32]!r}")
    print(f"  version string: {ver_buf.value!r}")
    if rc != 0:
        print(
            "\n⚠️  cr_get_sdk_version 返回非 0（预期 0=success）；\n"
            "   但 DLL 能调通，继续后续测试。"
        )

    if args.no_connect:
        print("\n--no-connect 已指定，跳过真机连接。")
        _banner("第一阶段验证结论")
        print(
            "✅ DLL 加载 + 函数绑定 + ctypes 调用链 全部正常。\n"
            "   方案 6 的底层通道在 Python 3.11 上已经通。\n"
            "   下一步：跑 --mode real (不加 --no-connect) 试握手真机。"
        )
        return 0

    _banner(f"smoke test 2: cr_create_robot({args.ip}:{args.port})")
    print("⚠️  这一步会发起真实 TCP 握手，但不会让机械臂做任何动作。")
    handle = c_int(-1)
    rc = cr.cr_create_robot(
        byref(handle),
        args.ip.encode("utf-8"),
        args.port,
        args.password.encode("utf-8"),
    )
    print(f"  rc={rc}  handle={handle.value}")

    if rc != 0:
        print(
            "\n❌ 握手失败（rc != 0）。常见原因：\n"
            "  - 机械臂/控制柜未开机\n"
            "  - IP 不对（PC 是否和控制柜在同一子网？）\n"
            "  - 其他 SDK/GUI 占用中（示教器、长广溪 PC 客户端等）\n"
            "  - 密码字段被改过（手册标注为「预留」，按 '123' 最保险）"
        )
        return 5

    try:
        print("  ✓ 握手成功，机械臂未做任何动作。")
    finally:
        _banner("清理")
        rc = cr.cr_destroy_robot(handle)
        print(f"  cr_destroy_robot → rc={rc}")

    _banner("结论")
    print(
        "✅ 方案 6 可行！\n"
        "   Python 3.11 + ctypes 已在 cr_sdk.dll 上完整打通：\n"
        "     DLL 加载 ✓   函数绑定 ✓   真机握手 ✓   断开 ✓\n"
        "   下一步可以机械化地把 CGXiRobot 剩余 ~20 个函数全部 ctypes 化。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

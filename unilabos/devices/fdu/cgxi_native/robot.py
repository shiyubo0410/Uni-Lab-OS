# -*- coding: utf-8 -*-
"""CGXi 协作机器人 Python 3.11 原生控制类 ``CGXiRobotNative``。

与旧 ``unilabos.devices.ctr.skills.changguangxi.robot_utils.CGXiRobot``
**完全同 API**，区别仅在内部：旧类依赖 ``cgxiapi.pyd``（仅 Py37 ABI），本类
通过 ``ctypes`` 直接调用 ``cr_sdk.dll``，因此能跑在任意 Python 版本上。

已对齐的公共接口一览::

    属性:    ip, port, password, virtual, connected, robotHandle
    生命周期: connect, disconnect, __enter__, __exit__
    电源:    power_on, power_off, enable, disable, fault_reset
    状态:    get_robot_mode, get_joint_position, get_tcp_pose,
             get_move_status, get_speed_percent, set_speed_percent
    运动:    movej, movel
    程序:    download_program, download_project, play, pause, resume,
             stop, get_script_status, wait_move_complete

实现备忘
--------
- ``PointControlPara`` 按 MSVC x64 ABI 是"调用方分配+传指针"，ctypes 里声明
  为 ``argtypes=[c_int, PointControlPara]`` 后直接传 struct 实例即可。
- ``cr_create_robot`` 的 ``ref int`` 返回参数通过 ``byref(c_int)`` 出参。
- 所有 ``get_xxx`` 走 ``byref`` 写回用户变量。
- 错误码 0 = 成功，其它非 0 为厂家定义（见 ``_structs.CRresult``）。
"""

from __future__ import annotations

import logging
import time
from ctypes import byref, c_double, c_int, c_uint, create_string_buffer
from typing import List, Optional, Tuple

from ._bindings import bind_all
from ._structs import (
    CoordinateType,
    MotiontriggerMode,
    PointControlPara,
    PointControlParaSimple,
    PointTransType,
    PoseTranType,
)

logger = logging.getLogger(__name__)


class CGXiRobotNative:
    """CGXi 协作机器人控制类（ctypes 原生实现，跨 Python 版本）。"""

    def __init__(
        self,
        ip: str = "192.168.6.6",
        port: int = 2323,
        password: str = "123",
        virtual: bool = False,
    ) -> None:
        self.ip: str = "127.0.0.1" if virtual else ip
        self.port: int = 2325 if virtual else int(port)
        self.password: str = password
        self.virtual: bool = bool(virtual)
        self.robotHandle: Optional[int] = None
        self.connected: bool = False

        # 懒加载 DLL：一旦实例化就绑好全部签名，后续调用无开销
        self._cr = bind_all()

    # ------------------------------------------------------------------
    # 连接 / 生命周期
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """连接机器人，失败返回 ``False`` 并打印错误码。"""
        try:
            handle = c_int(1)
            rc = self._cr.cr_create_robot(
                byref(handle),
                self.ip.encode("utf-8"),
                c_int(self.port),
                self.password.encode("utf-8"),
            )
            if rc == 0:
                self.robotHandle = handle.value
                self.connected = True
                print(f"机器人连接成功 (Handle: {self.robotHandle})")
                return True
            print(f"机器人连接失败，错误码: {rc}")
            return False
        except Exception as exc:  # noqa: BLE001 - SDK 侧任何异常都需要兜底
            print(f"连接异常: {exc}")
            return False

    def disconnect(self) -> None:
        if not (self.connected and self.robotHandle is not None):
            return
        try:
            rc = self._cr.cr_destroy_robot(c_int(self.robotHandle))
            if rc == 0:
                print("机器人断开连接成功")
            else:
                print(f"断开连接失败，错误码: {rc}")
        except Exception as exc:  # noqa: BLE001
            print(f"断开连接异常: {exc}")
        finally:
            self.connected = False
            self.robotHandle = None

    def __enter__(self) -> "CGXiRobotNative":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _check_connected(self) -> bool:
        if not self.connected or self.robotHandle is None:
            print("错误: 机器人未连接")
            return False
        return True

    def _handle(self) -> c_int:
        """避免到处写 ``c_int(self.robotHandle)``。"""
        return c_int(self.robotHandle)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # 电源 / 使能
    # ------------------------------------------------------------------

    def _has_fn(self, fn_name: str) -> bool:
        """DLL 是否真的导出了该函数（避免 AttributeError 把业务弄挂）。"""
        fn = getattr(self._cr, fn_name, None)
        return callable(fn)

    def _simple_call(self, fn_name: str, label: str) -> bool:
        if not self._check_connected():
            return False
        if not self._has_fn(fn_name):
            print(f"{label}失败: cr_sdk.dll 未导出函数 {fn_name}")
            return False
        rc = getattr(self._cr, fn_name)(self._handle())
        ok = rc == 0
        print(f"{label}{'成功' if ok else '失败'}")
        return ok

    def power_on(self) -> bool:
        return self._simple_call("cr_poweron", "上电")

    def power_off(self) -> bool:
        return self._simple_call("cr_poweroff", "断电")

    def enable(self) -> bool:
        return self._simple_call("cr_enable", "使能")

    def disable(self) -> bool:
        return self._simple_call("cr_disable", "去使能")

    def fault_reset(self) -> bool:
        return self._simple_call("cr_FaultReset", "故障复位")

    # ------------------------------------------------------------------
    # 状态读取
    # ------------------------------------------------------------------

    def get_robot_mode(self) -> Tuple[bool, Optional[int]]:
        if not self._check_connected():
            return (False, None)
        mode = c_int(0)
        rc = self._cr.cr_get_robotMode(self._handle(), byref(mode))
        return (rc == 0, int(mode.value) if rc == 0 else None)

    def get_joint_position(self) -> Tuple[bool, Optional[List[float]]]:
        if not self._check_connected():
            return (False, None)
        buf = (c_double * 6)()
        rc = self._cr.cr_get_jointActualPos(self._handle(), buf)
        if rc == 0:
            return (True, [float(x) for x in buf])
        return (False, None)

    def get_tcp_pose(self) -> Tuple[bool, Optional[List[float]]]:
        if not self._check_connected():
            return (False, None)
        buf = (c_double * 6)()
        rc = self._cr.cr_get_tcpActualPose(self._handle(), buf)
        if rc == 0:
            return (True, [float(x) for x in buf])
        return (False, None)

    def get_move_status(self) -> Tuple[bool, Optional[int]]:
        if not self._check_connected():
            return (False, None)
        status = c_int(0)
        rc = self._cr.cr_get_robotMoveStatus(self._handle(), byref(status))
        return (rc == 0, int(status.value) if rc == 0 else None)

    def get_speed_percent(self) -> Tuple[bool, Optional[int]]:
        if not self._check_connected():
            return (False, None)
        sp = c_uint(0)
        rc = self._cr.cr_get_robotSpeedPercent(self._handle(), byref(sp))
        return (rc == 0, int(sp.value) if rc == 0 else None)

    def set_speed_percent(self, speed_percent: int) -> bool:
        if not self._check_connected():
            return False
        rc = self._cr.cr_set_robotSpeedPercent(self._handle(), c_uint(int(speed_percent)))
        ok = rc == 0
        print(f"设置速度百分比 {speed_percent}% {'成功' if ok else '失败'}")
        return ok

    # ------------------------------------------------------------------
    # 运动（关节/直线）
    # ------------------------------------------------------------------

    def _build_pcp(
        self,
        *,
        joint_pos=(0, 0, 0, 0, 0, 0),
        pose=(0, 0, 0, 0, 0, 0),
        speed,
        acc,
        coordinate: int,
    ) -> Optional[PointControlPara]:
        """用 simple + transfer 构造一个合法 PointControlPara。"""
        simple = PointControlParaSimple()
        simple.jointpos = tuple(joint_pos)
        simple.pose = tuple(pose)
        simple.tcpOffset = (0, 0, 0, 0, 0, 0)
        simple.coordinatePose = (0, 0, 0, 0, 0, 0)
        simple.speed = tuple(speed)
        simple.acc = tuple(acc)
        simple.coordinateType = coordinate
        simple.pointTransType = PointTransType.pointTransStop
        simple.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc

        pcp = PointControlPara()
        rc = self._cr.cr_move_pointControlPara_transfer(self._handle(), simple, byref(pcp))
        if rc != 0:
            print(f"参数转换失败: {rc}")
            return None
        return pcp

    def movej(self, joint_pos, speed=None, acc=None, block: bool = False) -> bool:
        if not self._check_connected():
            return False
        if speed is None:
            speed = (30, 30, 30, 30, 30, 30)
        if acc is None:
            acc = (60, 60, 60, 60, 60, 60)

        pcp = self._build_pcp(
            joint_pos=joint_pos,
            speed=speed,
            acc=acc,
            coordinate=CoordinateType.jointCoordinate,
        )
        if pcp is None:
            return False

        if block:
            rc = self._cr.cr_move_joint(self._handle(), pcp, True)
        else:
            rc = self._cr.cr_moveJ(self._handle(), pcp)

        ok = rc == 0
        print(f"MoveJ运动{'成功' if ok else '失败'}: {list(joint_pos)}, 返回值: {rc}")
        return ok

    def movel(self, pose, speed=None, acc=None, block: bool = False) -> bool:
        if not self._check_connected():
            return False
        if speed is None:
            speed = (30, 30, 30, 30, 30, 30)
        if acc is None:
            acc = (60, 60, 60, 60, 60, 60)

        pcp = self._build_pcp(
            pose=pose,
            speed=speed,
            acc=acc,
            coordinate=CoordinateType.baseCoordinate,
        )
        if pcp is None:
            return False

        # 先非阻塞下发，再根据 block 参数自己轮询运动状态
        rc = self._cr.cr_moveL(self._handle(), pcp)
        ok = rc == 0

        if ok and block:
            print("  等待运动完成...")
            self.wait_move_complete(timeout=30)

        print(f"MoveL运动{'成功' if ok else '失败'}: {list(pose)}, 返回值: {rc}")
        return ok

    # ------------------------------------------------------------------
    # 程序 / 工程
    # ------------------------------------------------------------------

    def download_program(self, program: str) -> bool:
        if not self._check_connected():
            return False
        rc = self._cr.cr_downloadProgram(self._handle(), program.encode("utf-8"))
        ok = rc == 0
        print(f"加载程序{'成功' if ok else '失败'}")
        return ok

    def download_project(self, crp_path: str, crscript_path: str) -> bool:
        if not self._check_connected():
            return False
        rc = self._cr.cr_downloadProject(
            self._handle(),
            crp_path.encode("utf-8"),
            crscript_path.encode("utf-8"),
        )
        ok = rc == 0
        print(f"下载工程{'成功' if ok else '失败'}")
        return ok

    def play(self) -> bool:
        return self._simple_call("cr_play", "运行程序")

    def pause(self) -> bool:
        return self._simple_call("cr_pause", "暂停程序")

    def resume(self) -> bool:
        # 手册里没有独立的 cr_resume；恢复语义由再次 cr_play 实现。
        # 如果将来 DLL 真的导出了 cr_resume，则优先使用它。
        if self._has_fn("cr_resume"):
            return self._simple_call("cr_resume", "恢复程序")
        return self._simple_call("cr_play", "恢复程序(回退到cr_play)")

    def stop(self) -> bool:
        return self._simple_call("cr_stop", "停止程序")

    def get_script_status(self) -> Tuple[bool, Optional[int]]:
        if not self._check_connected():
            return (False, None)
        status = c_int(0)
        rc = self._cr.cr_get_lua_scriptstatus(self._handle(), byref(status))
        return (rc == 0, int(status.value) if rc == 0 else None)

    # ------------------------------------------------------------------
    # 辅助：等待运动完成 / 获取 SDK 版本
    # ------------------------------------------------------------------

    def wait_move_complete(self, timeout: float = 30.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            ok, status = self.get_move_status()
            if ok and status == 0:
                return True
            time.sleep(0.1)
        print("等待运动完成超时")
        return False

    def get_sdk_version(self) -> Optional[str]:
        """读取 SDK 版本号，不需要连接。"""
        buf = create_string_buffer(32)
        rc = self._cr.cr_get_sdk_version(buf)
        if rc == 0:
            return buf.value.decode("utf-8", errors="replace")
        return None


__all__ = ["CGXiRobotNative"]

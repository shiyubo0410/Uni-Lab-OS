# -*- coding: utf-8 -*-
"""CGXi（长光希）六轴协作机械臂 Uni-Lab 驱动（FDU 版本）。

整合自：

* ``unilabos/devices/ctr/skills/changguangxi/robot_utils.py`` —— SDK 低层封装
  ``CGXiRobot``（connect/enable/movej/movel/...）
* ``unilabos/devices/ctr/utils/robot_control_utils.py`` —— 业务层
  ``RobotController``（路点库、两点移动、世界系 Z 轴、TCP 垂直等）
* ``unilabos/devices/fdu/waypoints.json`` —— 示教好的命名路点库

设计要点
--------
* 整个驱动脱离原 PySide2 GUI，所有动作通过 Uni-Lab `@action` 远程触发。
* 实例化时自动从 ``waypoints_file`` 加载路点库，前端可直接按名字调用。
* 运动类接口默认 ``block=True``（同步等待机械臂运动完成），
  便于 workflow 编排；用户可显式传 ``block=False`` 让动作立即返回。
* 状态（连接、使能、当前关节角、TCP、速度）通过 ``@topic_config`` 周期广播。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from unilabos.registry.decorators import action, device, not_action, topic_config
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode

# 低层 SDK：走 Python 3.11 兼容的 ctypes 原生绑定（方案 6），API 与旧
# ``ctr.skills.changguangxi.robot_utils.CGXiRobot`` 完全一致。
# RobotController 仍复用 ctr 层的业务工具（waypoint 管理、复合动作）。
from unilabos.devices.fdu.cgxi_native import CGXiRobotNative as CGXiRobot  # noqa: E402
from unilabos.devices.ctr.utils.robot_control_utils import (  # noqa: E402
    RobotController,
    Waypoint,
)


DEFAULT_WAYPOINTS_FILE = str(Path(__file__).resolve().parent / "waypoints.json")

# 运动 action 的 speed/acc 前端默认：Uni-Lab 的 schema 扫描是 AST 静态解析，
# 如果签名里写的是常量引用（例如 DEFAULT_MOVE_SPEED），前端会显示成符号名
# 而不是数字。因此所有运动 action 的签名默认值都直写字面量 20.0 / 10.0。
# 当前端下发 0/None/负数时，会在 _resolve_sa 里回退到 __init__ 的
# default_speed / default_acc（由 graph 可配）。

ROBOT_MODE_TEXT = {
    0: "初始化",
    1: "未连接",
    2: "未上电",
    3: "上电中",
    4: "去使能",
    5: "使能中",
    6: "使能",
    7: "运行中",
    8: "本体已上电",
    9: "暂停",
    10: "恢复中",
    11: "拖动中",
}


@device(
    id="fdu.robot.cgxi",
    category=["arm"],
    description="长光希 CGXi 六轴协作机械臂（通过 SDK/TCP 控制，内置 waypoints 路点库）",
    display_name="FDU CGXi 协作机械臂",
)
class CGXiRobotDevice:
    """长光希 CGXi 协作机械臂 Uni-Lab 驱动。"""

    _ros_node: BaseROS2DeviceNode

    def __init__(
        self,
        ip: str = "192.168.6.6",
        port: int = 2323,
        password: str = "123",
        virtual: bool = False,
        waypoints_file: Optional[str] = DEFAULT_WAYPOINTS_FILE,
        default_speed: float = 20.0,
        default_acc: float = 10.0,
        auto_connect: bool = False,
        **kwargs: Any,
    ) -> None:
        self.ip = ip
        self.port = int(port)
        self.password = password
        self.virtual = bool(virtual)
        # 显式传 None / "" 都回退到默认路径，避免 graph 配置漏填时加载不到路点
        self.waypoints_file = waypoints_file or DEFAULT_WAYPOINTS_FILE
        self.default_speed = float(default_speed)
        self.default_acc = float(default_acc)

        self.logger = logging.getLogger(f"CGXiRobot.{self.ip}")
        self._lock = threading.RLock()

        self._sdk = CGXiRobot(
            ip=self.ip, port=self.port, password=self.password, virtual=self.virtual
        )
        self._ctrl = RobotController(self._sdk)
        self._last_error: str = ""

        # 缓存状态（由动作 & 广播属性更新）
        self._cached_joint_pos: List[float] = [0.0] * 6
        self._cached_tcp_pose: List[float] = [0.0] * 6
        self._cached_mode: int = -1
        self._cached_move_status: int = -1
        self._cached_speed_percent: int = -1

        # 启动时加载路点库
        if self.waypoints_file and Path(self.waypoints_file).exists():
            try:
                ok = self._ctrl.load_waypoints(self.waypoints_file, format="auto")
                if ok:
                    self.logger.info(
                        f"已加载 {len(self._ctrl.waypoints)} 个路点：{self.waypoints_file}"
                    )
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"load waypoints: {exc}"
                self.logger.warning(self._last_error)

        if auto_connect:
            try:
                self.connect()
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(f"自动连接机械臂失败: {exc}")

    # ---------- 生命周期 ----------

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    # ---------- 内部辅助 ----------

    @not_action
    def _waypoint_by_name(self, name: str) -> Optional[Waypoint]:
        for wp in self._ctrl.waypoints:
            if wp.name == name:
                return wp
        return None

    @not_action
    def _waypoint_index(self, name: str) -> int:
        for i, wp in enumerate(self._ctrl.waypoints):
            if wp.name == name:
                return i
        return -1

    @not_action
    def _result(self, ok: bool, message: str, **data: Any) -> Dict[str, Any]:
        return {"success": bool(ok), "message": message, **data}

    @not_action
    def _resolve_sa(
        self, speed: Optional[float], acc: Optional[float]
    ) -> tuple[float, float]:
        """把 action 传进来的 speed/acc 归一化成 SDK 可用的正值。

        规则：
        * ``None``、``0``、负数 → 回退到 ``self.default_speed`` / ``self.default_acc``
        * 正数 → 按原值使用（仍限制在 (0, 100] 内，避免越界）
        """
        def _pick(v: Optional[float], fallback: float) -> float:
            try:
                fv = float(v) if v is not None else 0.0
            except (TypeError, ValueError):
                fv = 0.0
            if fv <= 0.0:
                fv = float(fallback)
            # 速度/加速度是百分比（0-100），做个上限保护
            return max(1.0, min(100.0, fv))

        return _pick(speed, self.default_speed), _pick(acc, self.default_acc)

    # ================================================================
    # 连接 / 电源 / 使能
    # ================================================================

    @action(description="连接机械臂控制器")
    def connect(self) -> Dict[str, Any]:
        ok = self._sdk.connect()
        return self._result(
            ok,
            "机械臂连接成功" if ok else "机械臂连接失败，请检查 IP/端口/密码",
            ip=self.ip,
            port=self.port,
        )

    @action(description="断开机械臂连接")
    def disconnect(self) -> Dict[str, Any]:
        self._sdk.disconnect()
        return self._result(True, "机械臂已断开")

    @action(description="机械臂上电")
    def power_on(self) -> Dict[str, Any]:
        ok = self._sdk.power_on()
        return self._result(ok, "上电成功" if ok else "上电失败")

    @action(description="机械臂下电")
    def power_off(self) -> Dict[str, Any]:
        ok = self._sdk.power_off()
        return self._result(ok, "下电成功" if ok else "下电失败")

    @action(description="机械臂使能（开伺服）")
    def enable(self) -> Dict[str, Any]:
        ok = self._sdk.enable()
        return self._result(ok, "使能成功" if ok else "使能失败")

    @action(description="机械臂去使能（关伺服）")
    def disable(self) -> Dict[str, Any]:
        ok = self._sdk.disable()
        return self._result(ok, "去使能成功" if ok else "去使能失败")

    @action(description="故障复位")
    def fault_reset(self) -> Dict[str, Any]:
        ok = self._sdk.fault_reset()
        return self._result(ok, "故障复位成功" if ok else "故障复位失败")

    @action(description="停止当前运动")
    def stop(self) -> Dict[str, Any]:
        ok = self._sdk.stop()
        return self._result(ok, "已发送停止" if ok else "停止失败")

    # ================================================================
    # 速度
    # ================================================================

    @action(description="设置全局速度百分比 (0-100)")
    def set_speed_percent(self, speed_percent: int) -> Dict[str, Any]:
        sp = max(1, min(100, int(speed_percent)))
        ok = self._sdk.set_speed_percent(sp)
        if ok:
            self._cached_speed_percent = sp
        return self._result(ok, f"速度百分比={sp}%", speed_percent=sp)

    # ================================================================
    # 基础运动
    # ================================================================

    @action(description="关节空间运动 MoveJ。传入 6 个关节角度（度）")
    def move_joint(
        self,
        joint_pos: Sequence[float],
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> Dict[str, Any]:
        if len(joint_pos) != 6:
            return self._result(False, "joint_pos 必须是 6 个角度")
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._sdk.movej(list(joint_pos), speed=[sp] * 6, acc=[ac] * 6, block=block)
        return self._result(
            ok,
            "MoveJ 成功" if ok else "MoveJ 失败",
            joint_pos=list(joint_pos),
            speed=sp,
            acc=ac,
        )

    @action(description="直线运动 MoveL（笛卡尔）。传入 6 维 TCP 位姿 [x,y,z,rx,ry,rz]")
    def move_linear(
        self,
        pose: Sequence[float],
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> Dict[str, Any]:
        if len(pose) != 6:
            return self._result(False, "pose 必须是 6 维 [x,y,z,rx,ry,rz]")
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._sdk.movel(list(pose), speed=[sp] * 6, acc=[ac] * 6, block=block)
        return self._result(
            ok,
            "MoveL 成功" if ok else "MoveL 失败",
            pose=list(pose),
            speed=sp,
            acc=ac,
        )

    @action(description="世界坐标系相对移动 (dx,dy,dz 单位 mm)")
    def move_world_relative(
        self,
        dx: float = 0.0,
        dy: float = 0.0,
        dz: float = 0.0,
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> Dict[str, Any]:
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._ctrl.move_world_relative(
            dx=float(dx), dy=float(dy), dz=float(dz), speed=sp, acc=ac, block=block
        )
        return self._result(
            ok,
            "世界系相对移动成功" if ok else "世界系相对移动失败",
            dx=dx, dy=dy, dz=dz,
        )

    @action(description="世界 Z 轴移动（正值向上、负值向下，单位 mm）")
    def move_world_z(
        self,
        distance: float,
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> Dict[str, Any]:
        # 说明：原 RobotController.move_world_z 先用 cgxiapi.cr_kineInverse 做
        # 逆运动学预验证，但当前环境已经换成 cgxi_native(ctypes) SDK，
        # cgxiapi.pyd 的 DLL 在 Python 3.11 下加载不起来，会直接抛
        # "DLL load failed while importing cgxiapi" 并 return False。
        # 实际运动本来就是用 MoveL 走的，IK 只是预校验。
        # 这里直接复用 move_world_relative(dz=distance)：
        # 底层只调用 self.robot.movel(target_pose, ...)，不依赖 cgxiapi，
        # 语义等价（保持 TCP 姿态，世界系 Z 位移）。
        sp, ac = self._resolve_sa(speed, acc)
        self.logger.info(
            f"move_world_z: distance={distance:+.2f} mm, speed={sp}, acc={ac}, block={block}"
        )
        ok = self._ctrl.move_world_relative(
            dx=0.0, dy=0.0, dz=float(distance), speed=sp, acc=ac, block=block
        )
        return self._result(
            ok,
            f"Z 轴移动 {distance:+.2f} mm {'成功' if ok else '失败'}",
            distance=distance,
        )

    @action(description="把末端 TCP 调整为垂直向下（Rx=180°, Ry=0°, Rz=0°）")
    def set_tcp_vertical(
        self,
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> Dict[str, Any]:
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._ctrl.set_tcp_vertical(speed=sp, acc=ac, block=block)
        return self._result(ok, "TCP 已垂直向下" if ok else "TCP 垂直调整失败")

    @not_action
    def _set_tcp_orientation(
        self,
        rx: float,
        ry: float,
        rz: float,
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> bool:
        sp, ac = self._resolve_sa(speed, acc)
        return self._ctrl.set_tcp_orientation(
            rx=float(rx), ry=float(ry), rz=float(rz), speed=sp, acc=ac, block=block
        )

    # ================================================================
    # 路点相关（按名字调用）
    # ================================================================

    @action(description="按路点名称运动。use_joint_space=True 用 MoveJ, False 用 MoveL")
    def move_to_waypoint(
        self,
        name: str,
        speed: float = 20.0,
        acc: float = 10.0,
        use_joint_space: bool = True,
        block: bool = True,
    ) -> Dict[str, Any]:
        idx = self._waypoint_index(name)
        if idx < 0:
            return self._result(False, f"路点不存在: {name}", waypoint=name)
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._ctrl.move_to_waypoint(
            index=idx, speed=sp, acc=ac, use_joint_space=use_joint_space, block=block
        )
        return self._result(
            ok,
            f"移动到路点 [{name}] {'成功' if ok else '失败'}",
            waypoint=name,
            index=idx,
        )

    @action(description="从路点 A 移动到路点 B（内部会先到 start，再到 end）")
    def move_between_waypoints(
        self,
        start_name: str,
        end_name: str,
        speed: float = 20.0,
        acc: float = 10.0,
        use_joint_space: bool = True,
        block: bool = True,
    ) -> Dict[str, Any]:
        s, e = self._waypoint_index(start_name), self._waypoint_index(end_name)
        if s < 0 or e < 0:
            return self._result(
                False,
                f"路点不存在: start={start_name} end={end_name}",
                start=start_name,
                end=end_name,
            )
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._ctrl.move_between_waypoints(
            start_idx=s, end_idx=e, speed=sp, acc=ac,
            use_joint_space=use_joint_space, block=block,
        )
        return self._result(
            ok,
            f"[{start_name}]→[{end_name}] {'成功' if ok else '失败'}",
            start=start_name,
            end=end_name,
        )

    @action(description="按顺序穿过一串路点（传路点名字列表）")
    def move_along_waypoints(
        self,
        names: Sequence[str],
        speed: float = 20.0,
        acc: float = 10.0,
        use_joint_space: bool = True,
        dwell_time: float = 0.0,
    ) -> Dict[str, Any]:
        indices: List[int] = []
        missing: List[str] = []
        for n in names:
            i = self._waypoint_index(n)
            if i < 0:
                missing.append(n)
            else:
                indices.append(i)
        if missing:
            return self._result(False, f"路点不存在: {missing}", missing=missing)
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._ctrl.move_along_waypoints(
            indices=indices, speed=sp, acc=ac,
            use_joint_space=use_joint_space, dwell_time=float(dwell_time),
        )
        return self._result(
            ok,
            f"路径 {list(names)} {'完成' if ok else '失败'}",
            names=list(names),
        )

    @action(description="回到 '初始化' 路点（机械臂 home 位置）")
    def go_home(
        self,
        speed: float = 20.0,
        acc: float = 10.0,
        block: bool = True,
    ) -> Dict[str, Any]:
        # 优先找名为 '初始化' 的路点，找不到则找 0 号路点
        home_name = "初始化" if self._waypoint_by_name("初始化") else None
        if home_name:
            return self.move_to_waypoint(
                name=home_name, speed=speed, acc=acc,
                use_joint_space=True, block=block,
            )
        if not self._ctrl.waypoints:
            return self._result(False, "无可用路点，无法回 home")
        sp, ac = self._resolve_sa(speed, acc)
        ok = self._ctrl.move_to_waypoint(
            index=0, speed=sp, acc=ac, use_joint_space=True, block=block
        )
        return self._result(
            ok,
            f"回到 [{self._ctrl.waypoints[0].name}] {'成功' if ok else '失败'}",
            waypoint=self._ctrl.waypoints[0].name,
        )

    # ================================================================
    # 示教 / 路点库管理
    # ================================================================

    @action(description="记录当前位姿为命名路点（替代 GUI 示教）")
    def record_current_waypoint(
        self, name: str, description: str = "", auto_save: bool = True
    ) -> Dict[str, Any]:
        if not name:
            return self._result(False, "name 不能为空")
        # 如果已存在同名路点，先删除旧的，避免重名
        existing = self._waypoint_index(name)
        if existing >= 0:
            self._ctrl.waypoints.pop(existing)
        wp = self._ctrl.record_current_waypoint(name=name, description=description)
        if wp is None:
            return self._result(False, "记录路点失败（机械臂未连接或读取位姿失败）")
        saved = False
        if auto_save and self.waypoints_file:
            try:
                saved = self._ctrl.save_waypoints(self.waypoints_file, format="json")
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"save waypoints: {exc}"
        return self._result(
            True,
            f"已记录路点 [{name}]" + ("，已持久化" if saved else ""),
            waypoint=name,
            joint_pos=wp.joint_pos,
            tcp_pose=wp.tcp_pose,
            saved=saved,
        )

    @action(description="列出所有已加载的路点名")
    def list_waypoints(self) -> Dict[str, Any]:
        names = [wp.name for wp in self._ctrl.waypoints]
        return {
            "success": True,
            "count": len(names),
            "names": names,
            "message": f"共 {len(names)} 个路点",
        }

    @action(description="按名字获取路点详情")
    def get_waypoint(self, name: str) -> Dict[str, Any]:
        wp = self._waypoint_by_name(name)
        if wp is None:
            return self._result(False, f"路点不存在: {name}")
        return {
            "success": True,
            "name": wp.name,
            "joint_pos": wp.joint_pos,
            "tcp_pose": wp.tcp_pose,
            "description": wp.description,
            "timestamp": wp.timestamp,
        }

    @action(description="按名字删除路点")
    def delete_waypoint(self, name: str, auto_save: bool = True) -> Dict[str, Any]:
        idx = self._waypoint_index(name)
        if idx < 0:
            return self._result(False, f"路点不存在: {name}")
        self._ctrl.waypoints.pop(idx)
        saved = False
        if auto_save and self.waypoints_file:
            try:
                saved = self._ctrl.save_waypoints(self.waypoints_file, format="json")
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"save waypoints: {exc}"
        return self._result(True, f"已删除路点 [{name}]", saved=saved)

    @action(description="重命名路点")
    def rename_waypoint(
        self, old_name: str, new_name: str, auto_save: bool = True
    ) -> Dict[str, Any]:
        wp = self._waypoint_by_name(old_name)
        if wp is None:
            return self._result(False, f"路点不存在: {old_name}")
        if self._waypoint_by_name(new_name):
            return self._result(False, f"新名字已被占用: {new_name}")
        wp.name = new_name
        saved = False
        if auto_save and self.waypoints_file:
            try:
                saved = self._ctrl.save_waypoints(self.waypoints_file, format="json")
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"save waypoints: {exc}"
        return self._result(True, f"[{old_name}] → [{new_name}]", saved=saved)

    @action(description="保存全部路点到文件（默认写回启动时的 waypoints_file）")
    def save_waypoints(
        self, filepath: Optional[str] = None, format: str = "json"
    ) -> Dict[str, Any]:
        path = filepath or self.waypoints_file
        if not path:
            return self._result(False, "未指定保存路径")
        ok = self._ctrl.save_waypoints(path, format=format)
        return self._result(
            ok,
            f"已保存 {len(self._ctrl.waypoints)} 个路点到 {path}" if ok else "保存失败",
            filepath=path,
        )

    @action(description="从文件重新加载路点（覆盖当前路点库）")
    def reload_waypoints(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        path = filepath or self.waypoints_file
        if not path or not Path(path).exists():
            return self._result(False, f"文件不存在: {path}")
        ok = self._ctrl.load_waypoints(path, format="auto", replace=True)
        return self._result(
            ok,
            f"已加载 {len(self._ctrl.waypoints)} 个路点" if ok else "加载失败",
            filepath=path,
            count=len(self._ctrl.waypoints),
        )

    # ================================================================
    # 状态查询（只读）
    # ================================================================

    @action(description="读取当前关节角度 [j1..j6]（度）")
    def get_joint_position(self) -> Dict[str, Any]:
        ok, jp = self._sdk.get_joint_position()
        if ok and jp is not None:
            self._cached_joint_pos = list(jp)
        return {
            "success": ok,
            "joint_position": self._cached_joint_pos,
            "message": "",
        }

    @action(description="读取当前 TCP 位姿 [x,y,z,rx,ry,rz]")
    def get_tcp_pose(self) -> Dict[str, Any]:
        ok, pose = self._sdk.get_tcp_pose()
        if ok and pose is not None:
            self._cached_tcp_pose = list(pose)
        return {
            "success": ok,
            "tcp_pose": self._cached_tcp_pose,
            "message": "",
        }

    @action(description="读取机器人模式（0-11）与描述文本")
    def get_robot_mode(self) -> Dict[str, Any]:
        ok, mode = self._sdk.get_robot_mode()
        if ok and mode is not None:
            self._cached_mode = int(mode)
        return {
            "success": ok,
            "mode": self._cached_mode,
            "description": ROBOT_MODE_TEXT.get(self._cached_mode, f"未知({self._cached_mode})"),
        }

    # ================================================================
    # 周期广播属性（@topic_config）
    # ================================================================

    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return bool(self._sdk.connected)

    @property
    @topic_config(period=2.0)
    def robot_mode_text(self) -> str:
        ok, mode = self._sdk.get_robot_mode() if self._sdk.connected else (False, None)
        if ok and mode is not None:
            self._cached_mode = int(mode)
        return ROBOT_MODE_TEXT.get(self._cached_mode, f"未知({self._cached_mode})")

    @property
    @topic_config(period=1.0)
    def joint_position(self) -> str:
        """当前关节角 JSON 字符串，形如 ``[j1,...,j6]``（单位：度）。"""
        if self._sdk.connected:
            ok, jp = self._sdk.get_joint_position()
            if ok and jp is not None:
                self._cached_joint_pos = list(jp)
        return json.dumps([round(float(v), 4) for v in self._cached_joint_pos])

    @property
    @topic_config(period=1.0)
    def tcp_pose(self) -> str:
        """当前 TCP 位姿 JSON 字符串，形如 ``[x,y,z,rx,ry,rz]``。"""
        if self._sdk.connected:
            ok, pose = self._sdk.get_tcp_pose()
            if ok and pose is not None:
                self._cached_tcp_pose = list(pose)
        return json.dumps([round(float(v), 4) for v in self._cached_tcp_pose])

    @property
    @topic_config(period=2.0)
    def move_status(self) -> str:
        if not self._sdk.connected:
            return "未连接"
        ok, status = self._sdk.get_move_status()
        if ok and status is not None:
            self._cached_move_status = int(status)
        return {0: "停止", 1: "运动中"}.get(self._cached_move_status, "未知")

    @property
    @topic_config(period=10.0)
    def speed_percent(self) -> int:
        if self._sdk.connected:
            ok, sp = self._sdk.get_speed_percent()
            if ok and sp is not None:
                self._cached_speed_percent = int(sp)
        return int(self._cached_speed_percent)

    @property
    @topic_config(period=30.0)
    def waypoint_count(self) -> int:
        return len(self._ctrl.waypoints)

    @property
    @topic_config(period=30.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    # 手动冒烟测试：连接虚拟臂、读状态、列路点
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    r = CGXiRobotDevice(virtual=True, auto_connect=True)
    print(r.list_waypoints())
    if r._sdk.connected:
        print(r.get_robot_mode())
        print(r.get_joint_position())
        print(r.get_tcp_pose())
        # 如果加载了路点且希望真实运动，请解开下行注释
        # print(r.go_home(block=True))
        r.disconnect()
    else:
        print("未连接，路点已加载但未执行运动测试")

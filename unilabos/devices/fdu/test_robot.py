# -*- coding: utf-8 -*-
"""CGXiRobotDevice 驱动独立冒烟测试脚本。

脱离 Uni-Lab / ROS 运行，直接实例化 :class:`CGXiRobotDevice`
调用其方法，用来快速验证驱动本身（路点加载、各 @action 方法签名、
参数校验、错误分支）是否正常。

运行方式（在仓库根目录）::

    # 1) 离线模式：完全不连硬件（默认），只验证驱动实例化 + 路点加载 + 只读接口
    python -m unilabos.devices.fdu.test_robot

    # 2) 虚拟臂模式：需要本机开 CGXi 仿真器（127.0.0.1:2325）
    python -m unilabos.devices.fdu.test_robot --mode virtual

    # 3) 真机模式：连实际机械臂
    python -m unilabos.devices.fdu.test_robot --mode real --ip 192.168.6.6

    # 4) 指定一个要移动到的路点（默认不移动）
    python -m unilabos.devices.fdu.test_robot --mode virtual --goto 初始化

注意
----
* 离线模式下，所有需要真连硬件的方法（connect/move/…）会失败，
  这是预期行为——脚本会把失败明确地打印出来，但不会中断流程。
* 真机模式移动前脚本会让你再次按回车确认，防止误动。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# 保证脚本能直接 python 跑（而不仅仅 python -m）
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from unilabos.devices.fdu.robot import (  # noqa: E402
    CGXiRobotDevice,
    DEFAULT_WAYPOINTS_FILE,
)


# ---------------------------------------------------------------------------
# 小工具：漂亮地打印 action 返回 dict
# ---------------------------------------------------------------------------

def _pp(title: str, obj: Any) -> None:
    """Pretty-print 一段结果。"""
    print(f"\n--- {title} ---")
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    else:
        print(obj)


def _banner(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


# ---------------------------------------------------------------------------
# 各阶段测试
# ---------------------------------------------------------------------------

def test_offline(r: CGXiRobotDevice) -> None:
    """完全离线：验证驱动本身 + 路点库 + 只读/查询接口。"""
    _banner("离线阶段：只验证路点库 & 只读接口（不连硬件）")

    wp_list = r.list_waypoints()
    _pp("list_waypoints", wp_list)
    assert wp_list["success"] is True, "list_waypoints 应永远返回 success=True"

    names = wp_list.get("names", [])
    if names:
        sample = names[0]
        _pp(f"get_waypoint('{sample}')", r.get_waypoint(sample))

    _pp("get_waypoint('不存在的路点')", r.get_waypoint("不存在的路点"))

    # 只读属性（@topic_config）——应该能在未连接状态下返回缓存/默认值
    _pp("is_connected", r.is_connected)
    _pp("robot_mode_text", r.robot_mode_text)
    _pp("joint_position (JSON str)", r.joint_position)
    _pp("tcp_pose (JSON str)", r.tcp_pose)
    _pp("move_status", r.move_status)
    _pp("speed_percent", r.speed_percent)
    _pp("waypoint_count", r.waypoint_count)
    _pp("last_error", r.last_error)

    # get_* 类动作：未连接时 success=False 是合理的
    _pp("get_joint_position()", r.get_joint_position())
    _pp("get_tcp_pose()", r.get_tcp_pose())
    _pp("get_robot_mode()", r.get_robot_mode())


def test_online(r: CGXiRobotDevice, goto: str | None, do_move: bool) -> None:
    """在线阶段：连接 → 上电 → 使能 → （可选）移动 → 关机。"""
    _banner(f"在线阶段：mode={'virtual' if r.virtual else 'real'} ip={r.ip}:{r.port}")

    res = r.connect()
    _pp("connect", res)
    if not res.get("success"):
        print("⚠️  连接失败，跳过后续在线动作。")
        return

    try:
        _pp("get_robot_mode", r.get_robot_mode())
        _pp("power_on", r.power_on())
        _pp("enable", r.enable())
        _pp("set_speed_percent(20)", r.set_speed_percent(20))
        _pp("get_joint_position", r.get_joint_position())
        _pp("get_tcp_pose", r.get_tcp_pose())

        if goto:
            names = [wp.name for wp in r._ctrl.waypoints]
            if goto not in names:
                _pp(f"⚠️ 路点不存在: {goto}（现有路点见下）", names[:10])
            elif not do_move:
                print(f"\n已跳过移动动作（--no-move 生效）。目标路点: {goto}")
            else:
                if not r.virtual:
                    input(
                        f"\n⚠️  即将真实移动机械臂到路点 '{goto}'，"
                        "请确认周围环境安全，按回车继续、Ctrl+C 取消…"
                    )
                _pp(
                    f"move_to_waypoint('{goto}', block=True)",
                    r.move_to_waypoint(goto, block=True),
                )
                _pp("get_joint_position (移动后)", r.get_joint_position())
                _pp("get_tcp_pose (移动后)", r.get_tcp_pose())
    finally:
        # 尽量把机械臂恢复到安全状态
        try:
            _pp("disable", r.disable())
        except Exception as exc:  # noqa: BLE001
            print(f"disable 时异常: {exc}")
        try:
            _pp("disconnect", r.disconnect())
        except Exception as exc:  # noqa: BLE001
            print(f"disconnect 时异常: {exc}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="CGXiRobotDevice 独立冒烟测试")
    parser.add_argument(
        "--mode",
        choices=["offline", "virtual", "real"],
        default="offline",
        help="offline=只本地验证；virtual=连仿真器；real=连真机（默认 offline）",
    )
    parser.add_argument("--ip", default="192.168.6.6", help="真机模式 IP")
    parser.add_argument("--port", type=int, default=2323, help="真机模式端口")
    parser.add_argument("--password", default="123", help="连接密码")
    parser.add_argument(
        "--waypoints",
        default=None,
        help="指定 waypoints.json 路径；不传则用驱动默认值",
    )
    parser.add_argument(
        "--goto",
        default=None,
        help="在线阶段移动到该命名路点（例如：初始化）",
    )
    parser.add_argument(
        "--no-move",
        action="store_true",
        help="即便传了 --goto 也只打印不实际移动（更安全）",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=20.0,
        help="默认运动速度百分比（建议先用 20 以内）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 没传 --waypoints 时显式回退到驱动默认路径（驱动里 Optional[str]=DEFAULT,
    # 但显式传 None 会把默认值覆盖掉导致不加载）
    waypoints_path = args.waypoints or DEFAULT_WAYPOINTS_FILE

    _banner("构造 CGXiRobotDevice")
    print(
        f"mode={args.mode}, ip={args.ip}, port={args.port}, "
        f"waypoints={waypoints_path}"
    )

    r = CGXiRobotDevice(
        ip=args.ip,
        port=args.port,
        password=args.password,
        virtual=(args.mode == "virtual"),
        waypoints_file=waypoints_path,
        default_speed=args.speed,
        auto_connect=False,
    )
    print(f"已加载 {len(r._ctrl.waypoints)} 个路点")

    # 阶段 1：完全离线——任何 mode 下都先跑一遍
    test_offline(r)

    # 阶段 2：如果不是 offline，就继续联机测试
    if args.mode != "offline":
        test_online(r, goto=args.goto, do_move=not args.no_move)

    _banner("测试结束")
    return 0


if __name__ == "__main__":
    sys.exit(main())

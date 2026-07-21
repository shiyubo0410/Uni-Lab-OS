"""无 ROS 环境下 registry 所需 ROS 符号的纯 Python 兜底实现.

仅当真实 ROS2(unilabos_msgs / message_converter / msgcenterpy.ros2_instance)
**无法 import** 时(典型: 香橙派网关)才会被 registry.py 启用。有 ROS 的 dev/工站
环境永远走真实实现, 本模块不参与, 行为零变化。

提供的符号与 registry.py 顶部 ROS import 一一对应:
    EmptyIn, ResourceCreateFromOuter, ResourceCreateFromOuterEasy, Resource,
    String, msg_converter_manager, ros_action_to_json_schema,
    ros_message_to_json_schema, ROS2MessageInstance
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

from unilabos.registry import idl_schema


# --- 桩类型: 仅承载 __name__, 上报时被转换为字符串 ----------------------------
def _make_stub(name: str):
    """生成一个名字为 name 的桩类, 带一个返回带标记 Goal 实例的 Goal()。"""

    class _StubGoal:
        _action_name = name

    stub = type(name, (), {})
    # Goal 作为可调用属性, 返回带 _action_name 标记的实例(供 ROS2MessageInstance 兜底用)
    stub.Goal = staticmethod(lambda: _StubGoal())  # type: ignore[attr-defined]
    return stub


ResourceCreateFromOuterEasy = _make_stub("ResourceCreateFromOuterEasy")
ResourceCreateFromOuter = _make_stub("ResourceCreateFromOuter")
EmptyIn = _make_stub("EmptyIn")
Resource = _make_stub("Resource")
String = _make_stub("String")


# --- 类型解析管理器兜底: 无 ROS 时一律返回 None, 调用方会退化为 String ---------
class _FallbackMsgConverterManager:
    def get_class(self, name: str):  # noqa: D401
        return None

    def search_class(self, name: str):
        return None


msg_converter_manager = _FallbackMsgConverterManager()


# --- schema/默认值: 委托给 idl_schema 从仓库内 .action/.msg 文本生成 -----------
def ros_action_to_json_schema(
    action_class: Any, description: str = "", previous_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    name = getattr(action_class, "__name__", str(action_class))
    return idl_schema.action_schema(name, description)


def ros_message_to_json_schema(msg_class: Any, field_name: str) -> Dict[str, Any]:
    name = getattr(msg_class, "__name__", str(msg_class))
    return idl_schema.message_schema(name, field_name)


class ROS2MessageInstance:
    """ROS2MessageInstance 的最小兜底: 仅支持 get_python_dict() 取动作 Goal 默认值。"""

    def __init__(self, goal_obj: Any):
        self._goal_obj = goal_obj

    def get_python_dict(self) -> Dict[str, Any]:
        action_name = getattr(self._goal_obj, "_action_name", None)
        if action_name:
            return copy.deepcopy(idl_schema.action_goal_default(action_name))
        return {}

    def get_json_schema(self) -> Dict[str, Any]:  # 兼容签名, 当前路径不依赖
        return {"type": "object", "properties": {}, "required": []}

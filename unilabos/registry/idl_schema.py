"""无 ROS 环境下的 ROS IDL(.msg/.action/.srv) → JSON Schema 纯 Python 解析器.

用途: 香橙派网关等**未安装 ROS2** 的环境中, 注册表里少数几个**系统固定**的
ROS 消息/动作(如 ResourceCreateFromOuterEasy / Resource)无法通过 import 真实
ROS 类来生成 schema. 本模块直接解析仓库内的 .action/.msg 文本定义, 复刻
unilabos.ros.msgs.message_converter 的 JSON Schema 形态, 实现零 ROS 依赖。

注意:
- dev / 工站等有 ROS 的环境**不会**走到这里(message_converter 优先)。
- 设备驱动(@device/@action)的 schema 由 registry 的纯 Python AST 路径生成,
  与本模块无关; 本模块只覆盖那几个系统固定的 ROS 定义。
"""

from __future__ import annotations

import copy
import os
import re
from typing import Any, Dict, List, Optional, Tuple

# 与 message_converter.basic_type_map 保持一致, 确保 schema 形态对齐
BASIC_TYPE_MAP: Dict[str, Dict[str, Any]] = {
    "bool": {"type": "boolean"},
    "int8": {"type": "integer", "minimum": -128, "maximum": 127},
    "uint8": {"type": "integer", "minimum": 0, "maximum": 255},
    "int16": {"type": "integer", "minimum": -32768, "maximum": 32767},
    "uint16": {"type": "integer", "minimum": 0, "maximum": 65535},
    "int32": {"type": "integer", "minimum": -2147483648, "maximum": 2147483647},
    "uint32": {"type": "integer", "minimum": 0, "maximum": 4294967295},
    "int64": {"type": "integer"},
    "uint64": {"type": "integer", "minimum": 0},
    "double": {"type": "number"},
    "float": {"type": "number"},
    "float32": {"type": "number"},
    "float64": {"type": "number"},
    "string": {"type": "string"},
    "boolean": {"type": "boolean"},
    "char": {"type": "string", "maxLength": 1},
    "byte": {"type": "integer", "minimum": 0, "maximum": 255},
}

# 数值/字符串/布尔的零值, 用于生成 goal_default
_DEFAULT_SCALAR = {
    "bool": False,
    "boolean": False,
    "int8": 0, "uint8": 0, "int16": 0, "uint16": 0,
    "int32": 0, "uint32": 0, "int64": 0, "uint64": 0, "byte": 0,
    "double": 0.0, "float": 0.0, "float32": 0.0, "float64": 0.0,
    "string": "", "char": "",
}

# 内置标准消息类型结构(humble), 供嵌套引用使用; 字段格式同 .msg
_BUILTIN_MSGS: Dict[str, str] = {
    "builtin_interfaces/Time": "int32 sec\nuint32 nanosec",
    "builtin_interfaces/Duration": "int32 sec\nuint32 nanosec",
    "geometry_msgs/Point": "float64 x\nfloat64 y\nfloat64 z",
    "geometry_msgs/Vector3": "float64 x\nfloat64 y\nfloat64 z",
    "geometry_msgs/Quaternion": "float64 x\nfloat64 y\nfloat64 z\nfloat64 w",
    "geometry_msgs/Pose": "geometry_msgs/Point position\ngeometry_msgs/Quaternion orientation",
    "std_msgs/Header": "builtin_interfaces/Time stamp\nstring frame_id",
}


def _msgs_root() -> Optional[str]:
    """定位仓库内 unilabos_msgs 源目录(含 action/ msg/ srv/)。"""
    # idl_schema.py 位于 unilabos/registry/, 仓库根的同级有 unilabos_msgs/
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))  # .../Uni-Lab-OS
    cand = os.path.join(repo_root, "unilabos_msgs")
    return cand if os.path.isdir(cand) else None


def _read_definition_text(type_name: str) -> Optional[str]:
    """根据类型名读取其 IDL 文本; 支持内置标准类型与仓库内 unilabos_msgs。"""
    if type_name in _BUILTIN_MSGS:
        return _BUILTIN_MSGS[type_name]

    root = _msgs_root()
    if root is None:
        return None

    # 形如 pkg/Msg 或 pkg/msg/Msg, 取最后一段作为类型名
    short = type_name.split("/")[-1]
    for sub in ("msg", "action", "srv"):
        for ext in (".msg", ".action", ".srv"):
            path = os.path.join(root, sub, short + ext)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
    return None


def _parse_field_line(line: str) -> Optional[Tuple[str, str, bool, Optional[str]]]:
    """解析一行字段定义, 返回 (base_type, name, is_array, raw_default)。

    跳过注释/空行/常量(含 '=' 的大写常量定义)。
    """
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    parts = line.split(None, 2)
    if len(parts) < 2:
        return None
    type_token, name_token = parts[0], parts[1]
    raw_default = parts[2].strip() if len(parts) >= 3 else None

    # 常量定义: TYPE NAME=VALUE (名字里带 =), 注册表 goal 不关心常量
    if "=" in name_token:
        return None

    is_array = False
    base_type = type_token
    # 数组: type[], type[N], type[<=N]
    m = re.match(r"^(.*?)\[[^\]]*\]$", type_token)
    if m:
        is_array = True
        base_type = m.group(1)
    # 有界字符串 string<=N
    base_type = re.sub(r"<=\d+$", "", base_type)
    return base_type, name_token, is_array, raw_default


def parse_fields(text: str) -> List[Tuple[str, str, bool, Optional[str]]]:
    fields: List[Tuple[str, str, bool, Optional[str]]] = []
    for line in text.splitlines():
        parsed = _parse_field_line(line)
        if parsed is not None:
            fields.append(parsed)
    return fields


def _field_type_schema(base_type: str) -> Dict[str, Any]:
    """单个(非数组)字段类型 → JSON Schema, 与 message_converter 对齐。"""
    if base_type in BASIC_TYPE_MAP:
        return copy.deepcopy(BASIC_TYPE_MAP[base_type])
    if base_type in ("time", "duration",
                      "builtin_interfaces/Time", "builtin_interfaces/Duration"):
        return {
            "type": "object",
            "properties": {
                "sec": {"type": "integer", "description": "秒"},
                "nanosec": {"type": "integer", "description": "纳秒"},
            },
            "required": ["sec", "nanosec"],
        }
    # 嵌套消息类型
    nested_text = _read_definition_text(base_type)
    if nested_text is not None:
        return _msg_schema_from_text(nested_text, base_type.split("/")[-1])
    # 未知类型, 退化为对象
    return {"type": "object"}


def _msg_schema_from_text(text: str, title: str) -> Dict[str, Any]:
    fields = parse_fields(text)
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for base_type, name, is_array, _default in fields:
        if is_array:
            properties[name] = {"type": "array", "items": _field_type_schema(base_type)}
        else:
            properties[name] = _field_type_schema(base_type)
        required.append(name)
    schema: Dict[str, Any] = {"type": "object", "properties": properties, "required": required}
    if title:
        schema["title"] = title
    return schema


def _default_from_fields(fields: List[Tuple[str, str, bool, Optional[str]]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for base_type, name, is_array, _default in fields:
        if is_array:
            out[name] = []
        elif base_type in _DEFAULT_SCALAR:
            out[name] = _DEFAULT_SCALAR[base_type]
        elif base_type in ("time", "duration",
                            "builtin_interfaces/Time", "builtin_interfaces/Duration"):
            out[name] = {"sec": 0, "nanosec": 0}
        else:
            nested_text = _read_definition_text(base_type)
            if nested_text is not None:
                out[name] = _default_from_fields(parse_fields(nested_text))
            else:
                out[name] = {}
    return out


def message_schema(type_name: str, field_name: str) -> Dict[str, Any]:
    """复刻 message_converter.ros_message_to_json_schema 的输出形态。"""
    text = _read_definition_text(type_name)
    if text is None:
        return {"type": "object", "title": field_name}
    schema = _msg_schema_from_text(text, field_name)
    return schema


def _split_action_sections(text: str) -> Tuple[str, str, str]:
    """.action 以 '---' 分为 goal / result / feedback 三段。"""
    sections = re.split(r"^\s*---\s*$", text, flags=re.MULTILINE)
    goal = sections[0] if len(sections) >= 1 else ""
    result = sections[1] if len(sections) >= 2 else ""
    feedback = sections[2] if len(sections) >= 3 else ""
    return goal, result, feedback


def action_schema(type_name: str, description: str = "") -> Dict[str, Any]:
    """复刻 message_converter.ros_action_to_json_schema 的输出形态。"""
    text = _read_definition_text(type_name)
    short = type_name.split("/")[-1]
    if text is None:
        return {
            "title": short,
            "description": description,
            "type": "object",
            "properties": {"goal": {}, "feedback": {}, "result": {}},
            "required": ["goal"],
        }
    goal_text, result_text, feedback_text = _split_action_sections(text)
    return {
        "title": short,
        "description": description,
        "type": "object",
        "properties": {
            "goal": _msg_schema_from_text(goal_text, f"{short}_Goal"),
            "feedback": _msg_schema_from_text(feedback_text, f"{short}_Feedback"),
            "result": _msg_schema_from_text(result_text, f"{short}_Result"),
        },
        "required": ["goal"],
    }


def action_goal_default(type_name: str) -> Dict[str, Any]:
    """动作 Goal 段的默认值(复刻 ROS2MessageInstance(Goal()).get_python_dict())。"""
    text = _read_definition_text(type_name)
    if text is None:
        return {}
    goal_text, _result, _feedback = _split_action_sections(text)
    return _default_from_fields(parse_fields(goal_text))

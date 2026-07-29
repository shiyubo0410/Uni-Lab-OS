"""设备控制 Skill —— 把网关本地 ``workers`` 暴露成 LLM 可调用的工具。

会议结论：Skill 放本地更贴合实际（读写路径本地化，避免 MCP 加载问题）。这里做
最小一套"看设备 / 查状态 / 下动作"三工具，直接复用网关既有执行链路：

* 只读：:meth:`list_devices` / :meth:`get_device_status` —— 读 ``worker.list_actions()``
  与遥测缓存 ``worker._last_values``，无副作用，Agent 可直接执行喂回 LLM；
* 写：:meth:`run_action` —— 调 ``worker.execute_action``（与云端 ``job_start`` 同一条路），
  会真正驱动硬件，**故 Agent 侧对该工具做二次确认**（见 :mod:`~unilabos.gateway.agent.agent`）。

设计原则：Skill 只依赖 ``workers`` 这个"设备ID→DeviceWorker"的活字典引用；网关热插拔
增删设备时字典原地变更，Skill 立即可见，无需重建。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("unilab.agent.skill")


class DeviceSkill:
    """基于网关 ``workers`` 的设备控制工具集。"""

    def __init__(self, workers: Dict[str, Any]) -> None:
        # workers: Dict[device_id, DeviceWorker]，与 main.py 中的活引用共享。
        self.workers = workers

    # ---- 工具 schema（喂给 LLM 的 function calling 定义）-------------------
    def tools_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_devices",
                    "description": (
                        "列出当前网关在线的所有设备，含设备ID(device_id)、类型、"
                        "可执行的动作名(actions)、以及最近读到的属性值(properties)。"
                        "当用户问'有哪些设备/设备状态如何/能做什么'时先调它。"
                    ),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_device_status",
                    "description": "查询某台设备的最新属性读数（温度、转速、状态等）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_id": {
                                "type": "string",
                                "description": "设备ID，如 ika_rct5_digital-auto-1",
                            }
                        },
                        "required": ["device_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_action",
                    "description": (
                        "给某台设备下发一个控制动作（如开始搅拌 start_stir）。"
                        "这是写操作，会真正驱动硬件。action 必须来自该设备 list_devices "
                        "里列出的 actions；args 按动作要求填键值，如 "
                        '{"stir_speed":300,"duration":60}。'
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "device_id": {"type": "string", "description": "设备ID"},
                            "action": {
                                "type": "string",
                                "description": "动作名，须来自该设备 actions 列表",
                            },
                            "args": {
                                "type": "object",
                                "description": "动作参数键值对（可为空对象）",
                            },
                        },
                        "required": ["device_id", "action"],
                    },
                },
            },
        ]

    # ---- 只读工具实现 -----------------------------------------------------
    def list_devices(self) -> Dict[str, Any]:
        devs: List[Dict[str, Any]] = []
        for did, w in self.workers.items():
            devs.append(
                {
                    "device_id": did,
                    "device_type": getattr(w.driver, "device_type", "unknown"),
                    "actions": sorted(w.list_actions().keys()),
                    "properties": dict(getattr(w, "_last_values", {}) or {}),
                }
            )
        return {"count": len(devs), "devices": devs}

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        w = self.workers.get(device_id)
        if w is None:
            return {
                "error": f"未找到设备 {device_id}",
                "known_devices": list(self.workers.keys()),
            }
        return {
            "device_id": device_id,
            "device_type": getattr(w.driver, "device_type", "unknown"),
            "properties": dict(getattr(w, "_last_values", {}) or {}),
            "actions": sorted(w.list_actions().keys()),
        }

    def call_read(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """执行只读工具（无副作用），返回结果 dict 喂回 LLM。"""
        if name == "list_devices":
            return self.list_devices()
        if name == "get_device_status":
            return self.get_device_status(str(arguments.get("device_id") or ""))
        return {"error": f"未知只读工具 {name}"}

    # ---- 写工具实现（Agent 确认后才调）------------------------------------
    async def run_action(
        self, device_id: str, action: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        w = self.workers.get(device_id)
        if w is None:
            return {
                "status": "failed",
                "return_info": {"error": f"未找到设备 {device_id}"},
            }
        logger.info("[SKILL] 下发 %s.%s args=%s", device_id, action, args)
        return await w.execute_action(action, args or {})

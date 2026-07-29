"""网关内常驻 Agent 主体（见《网关Agent_开发文档》§3、§6）。

职责：维护按 Runner 会话隔离的对话历史，收到用户消息后调 :class:`LLMClient`
推理，产出回复。两条入口：

* :meth:`handle_agent_msg` —— 处理 WS 下行 ``agent_msg``，回复经 ``send_fn`` 发
  ``agent_reply`` 上行（P2 联云用）；
* :meth:`chat_once`        —— 直接吃一句、返回一句，供本地 CLI Runner 自测用（P0）。

两条入口共用 :meth:`_generate` 内核，保证本地自测与联云行为一致。

Skill（设备控制）：可选注入 :class:`~unilabos.gateway.agent.skill.DeviceSkill`。挂了它
且 LLM 支持工具调用时，Agent 走"工具循环"——只读工具（列设备/查状态）直接执行喂回，
写动作（run_action）先拦截、向用户二次确认，用户回"确认"才真正下发到设备。没挂 skill
或 LLM 不支持工具时，退化为纯对话代理。
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .llm import EchoLLM, LLMClient, LLMError, LLMNotConfigured, Message

logger = logging.getLogger("unilab.agent")

SendFn = Callable[[Dict[str, Any]], Awaitable[None]]

# 每个会话保留的最近“轮”数（一轮=一条 user + 一条 assistant）。防止弱设备内存被
# 无限增长的历史撑爆。system 提示不计入、始终保留。
DEFAULT_MAX_TURNS = 10

# 记住最近处理过的 msg_id 数量（幂等去重用），超出后按 FIFO 淘汰。
_SEEN_MSG_CAP = 256

# 单次对话里工具调用的最大轮数（防止 LLM 反复调工具打转）。
_MAX_TOOL_ROUNDS = 5

# 二次确认：用户对"即将下发的写动作"的肯定/否定词。
_AFFIRMATIVE = {
    "确认", "确定", "是", "是的", "yes", "y", "ok", "okay", "好", "好的",
    "执行", "run", "可以", "同意", "对",
}
_NEGATIVE = {"取消", "否", "不", "不要", "no", "n", "算了", "停", "别", "cancel"}

DEFAULT_SYSTEM_PROMPT = (
    "你是 Uni-Lab 物联网网关内置的管理助手，跑在一台香橙派网关上。"
    "你的职责是帮助用户了解网关与所连设备的状态、协助排查问题、解释操作。"
    "当前版本你还不能直接执行网关上的操作（如重启服务、看日志、触发升级）——"
    "这些能力后续会以工具形式接入；在此之前，请用自然语言给出清晰的指导，"
    "并诚实说明你暂时无法亲自执行。回答简洁、用中文。"
)

# 挂了设备控制 Skill 后的系统提示：允许查设备/下动作，但强调写动作要经确认。
SKILL_SYSTEM_PROMPT = (
    "你是 Uni-Lab 物联网网关内置的管理助手，跑在一台香橙派网关上。"
    "你可以通过工具查看本网关所连设备并控制它们：\n"
    "- list_devices：列出在线设备、类型、可用动作、当前读数；\n"
    "- get_device_status：查某台设备实时属性；\n"
    "- run_action：给设备下发控制动作（写操作，会真正驱动硬件）。\n"
    "规则：回答用户前，凡涉及设备信息务必先调工具获取真实数据，不要编造设备或读数。"
    "下发 run_action 时，action 必须来自该设备 list_devices 返回的 actions 列表，"
    "参数按设备要求填。系统会在真正执行写动作前向用户二次确认，你只管发起调用即可。"
    "回答简洁、用中文。"
)


class GatewayAgent:
    """网关常驻对话 Agent。

    :param send_fn: 上行发送函数（发 ``agent_reply``）。本地 CLI 自测可传 ``None``。
    :param machine_name: 网关机器名，用于 system 提示与桩回复。
    :param llm: LLM 客户端；不传则用 :class:`EchoLLM` 桩。
    :param system_prompt: 系统提示；不传用默认。
    :param max_turns: 每会话保留的最近轮数。
    """

    def __init__(
        self,
        send_fn: Optional[SendFn] = None,
        machine_name: str = "",
        llm: Optional[LLMClient] = None,
        *,
        skill: Optional[Any] = None,
        system_prompt: Optional[str] = None,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self.send_fn = send_fn
        self.machine_name = machine_name
        self.llm = llm or EchoLLM(machine_name)
        # 设备控制 Skill（DeviceSkill）。挂了它且 LLM 支持工具调用时，Agent 才走
        # "工具循环"，能真正查设备/下动作；否则退化为纯对话。
        self.skill = skill
        # 系统提示：挂 skill 时用允许控制设备的版本；调用方显式给了 system_prompt 则尊重之。
        if system_prompt is not None:
            self.system_prompt = system_prompt
        elif skill is not None:
            self.system_prompt = SKILL_SYSTEM_PROMPT
        else:
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
        self.max_turns = max_turns

        # session_id -> 对话历史（不含 system，system 每次拼在最前）
        self._sessions: Dict[str, List[Message]] = {}
        # 幂等：记住已处理的 msg_id
        self._seen_msgs: "OrderedDict[str, float]" = OrderedDict()
        # session_id -> 待确认的写动作 {"device_id","action","args"}。二次确认用。
        self._pending: Dict[str, Dict[str, Any]] = {}

    @property
    def _tools_enabled(self) -> bool:
        return self.skill is not None and getattr(self.llm, "supports_tools", False)

    # ---- WS 入口（P2 联云）------------------------------------------------
    async def handle_agent_msg(self, data: Dict[str, Any]) -> None:
        """处理下行 ``agent_msg``，把回复经 ``send_fn`` 以 ``agent_reply`` 发回。"""
        session = str(data.get("session") or "default")
        msg_id = str(data.get("msg_id") or "")
        text = (data.get("text") or "").strip()

        if not text:
            logger.debug("[AGENT] 收到空 agent_msg，忽略 session=%s", session)
            return

        # 幂等：同一 msg_id 只处理一次（中转重投/网络抖动兜底）
        if msg_id and msg_id in self._seen_msgs:
            logger.info("[AGENT] 重复 msg_id=%s，跳过", msg_id)
            return
        if msg_id:
            self._remember_msg(msg_id)

        logger.info("[AGENT] session=%s 收到：%s", session, text[:80])
        try:
            reply = await self._generate(session, text)
            await self._reply(session, msg_id, reply, status="done")
        except Exception as e:  # noqa: BLE001
            logger.exception("[AGENT] 处理消息失败 session=%s", session)
            await self._reply(
                session, msg_id, self._friendly_error(e), status="error"
            )

    # ---- 本地入口（P0 自测）----------------------------------------------
    async def chat_once(self, session: str, text: str) -> str:
        """吃一句、返回一句（不走 WS）。供本地 CLI Runner 用。"""
        text = (text or "").strip()
        if not text:
            return ""
        try:
            return await self._generate(session, text)
        except Exception as e:  # noqa: BLE001
            logger.exception("[AGENT] chat_once 失败 session=%s", session)
            return self._friendly_error(e)

    def reset(self, session: str) -> None:
        """清空某会话的对话历史（本地 CLI 的 /reset 用）。"""
        self._sessions.pop(session, None)
        self._pending.pop(session, None)

    # ---- 内核 -------------------------------------------------------------
    async def _generate(self, session: str, text: str) -> str:
        """把用户输入并入历史，调 LLM（必要时走工具循环），返回 assistant 回复。"""
        # 若该会话有待确认的写动作，本条消息优先当作"确认/取消"处理。
        if session in self._pending:
            handled = await self._handle_pending(session, text)
            if handled is not None:
                return handled
            # 既非确认也非取消：放弃待确认动作，继续当作新消息处理。

        history = self._sessions.setdefault(session, [])
        history.append({"role": "user", "content": text})

        if self._tools_enabled:
            reply = await self._generate_with_tools(session, history)
        else:
            messages: List[Message] = [{"role": "system", "content": self.system_prompt}]
            messages.extend(history)
            reply = await self.llm.chat(messages)

        history.append({"role": "assistant", "content": reply})
        self._trim(history)
        return reply

    async def _generate_with_tools(
        self, session: str, history: List[Message]
    ) -> str:
        """工具循环：让 LLM 调只读工具（直接执行喂回），写动作则拦截转二次确认。"""
        # 工具上下文只在本次生成内有效，不写回 history（保持 history 为纯文本，
        # 避免后续轮次因缺少 tool 响应而消息结构非法）。
        messages: List[Message] = [{"role": "system", "content": self.system_prompt}]
        messages.extend(history)
        tools = self.skill.tools_schema()

        for _ in range(_MAX_TOOL_ROUNDS):
            resp = await self.llm.complete(messages, tools=tools)
            if not resp.tool_calls:
                return resp.content or ""

            # 先看这批调用里有没有写动作 run_action：有就拦截转确认，不再喂回 LLM。
            for tc in resp.tool_calls:
                if tc.get("name") == "run_action":
                    return self._stage_write_action(session, tc.get("arguments") or {})

            # 全是只读工具：执行并把结果喂回，进入下一轮让 LLM 组织回答。
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content or "",
                    "tool_calls": [self._to_openai_tc(tc) for tc in resp.tool_calls],
                }
            )
            for tc in resp.tool_calls:
                result = self.skill.call_read(tc.get("name") or "", tc.get("arguments") or {})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id") or "",
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        return "（工具调用轮次过多，已中止。请把需求说得更具体一些。）"

    @staticmethod
    def _to_openai_tc(tc: Dict[str, Any]) -> Dict[str, Any]:
        """把归一化 tool_call 还原成 OpenAI 消息里的结构（arguments 需为 JSON 字符串）。"""
        return {
            "id": tc.get("id") or "",
            "type": "function",
            "function": {
                "name": tc.get("name") or "",
                "arguments": json.dumps(tc.get("arguments") or {}, ensure_ascii=False),
            },
        }

    def _stage_write_action(self, session: str, args: Dict[str, Any]) -> str:
        """暂存一个待确认的写动作，返回给用户的确认提示。"""
        device_id = str(args.get("device_id") or "")
        action = str(args.get("action") or "")
        act_args = args.get("args")
        if not isinstance(act_args, dict):
            act_args = {}
        self._pending[session] = {
            "device_id": device_id,
            "action": action,
            "args": act_args,
        }
        arg_str = json.dumps(act_args, ensure_ascii=False) if act_args else "（无参数）"
        return (
            f"⚠️ 即将对设备 {device_id} 执行动作 {action}，参数 {arg_str}。\n"
            f'回复"确认"执行，回复"取消"放弃。'
        )

    async def _handle_pending(self, session: str, text: str) -> Optional[str]:
        """处理待确认写动作。确认→执行；取消→放弃；两者都不是→返回 None（转普通处理）。"""
        low = text.strip().lower()
        pend = self._pending.get(session)
        if pend is None:
            return None

        if low in _NEGATIVE:
            self._pending.pop(session, None)
            return "已取消，未下发任何动作。"

        if low in _AFFIRMATIVE:
            self._pending.pop(session, None)
            device_id = pend["device_id"]
            action = pend["action"]
            act_args = pend["args"]
            try:
                result = await self.skill.run_action(device_id, action, act_args)
            except Exception as e:  # noqa: BLE001
                logger.exception("[AGENT] 执行写动作失败 %s.%s", device_id, action)
                return f"❌ 执行 {action} 出错：{e}"
            return self._format_action_result(device_id, action, result)

        # 非确认非取消：不消费 pending（交回 _generate 走普通对话，并清掉 pending）
        self._pending.pop(session, None)
        return None

    @staticmethod
    def _format_action_result(
        device_id: str, action: str, result: Dict[str, Any]
    ) -> str:
        status = (result or {}).get("status")
        info = (result or {}).get("return_info") or {}
        if status == "success":
            inner = info.get("result", info)
            msg = ""
            if isinstance(inner, dict):
                msg = inner.get("message") or ""
            detail = f"：{msg}" if msg else ""
            return f"✅ 已对 {device_id} 执行 {action}{detail}"
        err = info.get("error") if isinstance(info, dict) else info
        return f"❌ {device_id} 执行 {action} 失败：{err or result}"

    def _trim(self, history: List[Message]) -> None:
        """按最近 max_turns 轮截断（一轮两条）。"""
        cap = self.max_turns * 2
        if len(history) > cap:
            del history[: len(history) - cap]

    def _remember_msg(self, msg_id: str) -> None:
        self._seen_msgs[msg_id] = time.time()
        while len(self._seen_msgs) > _SEEN_MSG_CAP:
            self._seen_msgs.popitem(last=False)

    async def _reply(
        self, session: str, msg_id: str, content: str, status: str
    ) -> None:
        if self.send_fn is None:
            return
        await self.send_fn(
            {
                "action": "agent_reply",
                "data": {
                    "session": session,
                    "msg_id": msg_id,
                    "status": status,
                    "content": content,
                    "machine_name": self.machine_name,
                    "timestamp": time.time(),
                },
            }
        )

    @staticmethod
    def _friendly_error(e: Exception) -> str:
        if isinstance(e, LLMNotConfigured):
            return "（LLM 暂未配置：请在 /etc/unilab-gateway.env 里设置 UNILABOS_AGENT_LLM_API_KEY）"
        if isinstance(e, LLMError):
            return f"（LLM 调用失败：{e}）"
        return f"（处理出错：{e}）"

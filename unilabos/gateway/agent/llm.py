"""网关 Agent 的 LLM 客户端抽象。

v1 现状：云端 LLM 的**调用端点 / 鉴权方式待后端确认**（见开发规划 §4-②，
决策："脑子在云 + key 不下发到每台设备"，倾向后端提供 LLM 代理端点，网关用自己的
Lab AKSK 去调，key 只在后端）。为了在后端就绪前就能把 "Runner ↔ 网关 Agent" 整条
链路自测通，这里提供三层：

* :class:`LLMClient`     —— 统一接口（``async def chat(messages) -> str``）；
* :class:`EchoLLM`       —— 零依赖桩实现，回显 + 少量固定话术，用于链路自测；
* :class:`CloudProxyLLM` —— 后端 LLM 代理端点的骨架，端点/鉴权定了填 :meth:`_post` 即可。

设计原则：Agent 只依赖 :class:`LLMClient` 接口，换真实现不动 Agent 代码。
"""

from __future__ import annotations

import abc
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("unilab.agent.llm")

# 网关直连 LLM 的默认配置（GpuGeek，OpenAI 兼容）。可被 env 覆盖，见 build_llm_from_env。
# 注意：设备控制 Skill 依赖 function calling，默认模型需选支持工具调用的（Claude 系列等）。
DEFAULT_LLM_BASE_URL = "https://api.gpugeek.com/v1"
DEFAULT_LLM_MODEL = "Vendor2/Claude-4.7-opus"

# 一条对话消息：``{"role": "system|user|assistant|tool", "content": "...", ...}``。
# 工具调用场景下 assistant 消息可带 ``tool_calls``、tool 消息带 ``tool_call_id``，
# 故值类型放宽为 Any（不再限定 str）。
Message = Dict[str, Any]


class LLMResponse:
    """一次 LLM 应答：要么是最终文本，要么是一批工具调用请求。

    :param content:    assistant 文本（可能为 None——纯工具调用时）。
    :param tool_calls: 归一化后的工具调用列表，每项 ``{"id", "name", "arguments"(dict)}``。
    """

    __slots__ = ("content", "tool_calls")

    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class LLMClient(abc.ABC):
    """LLM 客户端统一接口。

    Agent 侧只认这个接口：给一串对话消息，返回 assistant 的文本回复。
    具体是调云端代理、直连厂商 API、还是桩实现，对 Agent 透明。
    """

    # 是否支持 OpenAI 风格的工具调用（function calling）。默认 False；
    # 支持工具的实现（OpenAICompatLLM）置 True，Agent 据此决定是否挂 Skill。
    supports_tools: bool = False

    @abc.abstractmethod
    async def chat(self, messages: List[Message]) -> str:
        """给定完整对话历史（含 system），返回 assistant 回复文本。"""
        raise NotImplementedError

    async def complete(
        self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        """带工具的一次补全。默认实现不支持工具，退化为纯文本 :meth:`chat`。"""
        text = await self.chat(messages)
        return LLMResponse(content=text)


class EchoLLM(LLMClient):
    """零依赖桩实现：不联网，用于后端 LLM 端点就绪前跑通整条链路。

    行为：
    * 识别几个关键词（``help`` / ``帮助`` / ``ping`` / ``version``）给固定话术；
    * 其余输入回显，并带上当前轮次，方便验证多轮上下文确实在累积。
    """

    def __init__(self, machine_name: str = "") -> None:
        self.machine_name = machine_name

    async def chat(self, messages: List[Message]) -> str:
        user_turns = [m for m in messages if m.get("role") == "user"]
        turn = len(user_turns)
        last = user_turns[-1]["content"].strip() if user_turns else ""
        low = last.lower()

        if low in ("help", "帮助", "?", "？"):
            return (
                "我是网关内置管理 Agent（桩模式）。当前 LLM 端点未接入，仅用于链路自测。\n"
                "可用于验证：多轮对话上下文、消息往返、Runner 显示。\n"
                "后端提供 LLM 代理端点后即可切换到真实推理。"
            )
        if low == "ping":
            return "pong"
        if low in ("version", "版本"):
            return f"gateway-agent v1（桩 LLM）machine={self.machine_name or '?'}"
        return f"[echo·第{turn}轮] 你说的是：{last}"


class CloudProxyLLM(LLMClient):
    """后端 LLM 代理端点的客户端骨架（端点/鉴权确定后完善）。

    约定（待与后端最终对齐）：
    * 端点：``{base_url}{path}``（如 ``.../api/v1/agent/llm/chat``）；
    * 鉴权：沿用网关的 ``Authorization: Lab <base64(ak:sk)>``（key 只在后端，
      网关不持有厂商 API key）；
    * 请求体：``{"messages": [...], "model": "..."}``；
    * 响应体：``{"content": "assistant 文本"}``（字段名以后端为准，见 :meth:`_parse`）。

    端点未配置时 :meth:`chat` 抛 :class:`LLMNotConfigured`，Agent 会转成一句友好的
    "LLM 暂未接入" 提示，而不是崩溃。
    """

    def __init__(
        self,
        base_url: str,
        *,
        path: str = "/agent/llm/chat",
        model: str = "",
        auth_header: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.path = path
        self.model = model
        self.auth_header = auth_header
        self.timeout = timeout

    @property
    def _endpoint(self) -> str:
        return f"{self.base_url}{self.path}" if self.base_url else ""

    async def chat(self, messages: List[Message]) -> str:
        if not self._endpoint:
            raise LLMNotConfigured("后端 LLM 代理端点未配置（base_url 为空）")
        import asyncio

        loop = asyncio.get_running_loop()
        # urllib 是阻塞的，丢到线程池里跑，避免卡住 asyncio 事件循环。
        return await loop.run_in_executor(None, self._post, messages)

    # ---- 阻塞实现（在线程池里跑）----------------------------------------
    def _post(self, messages: List[Message]) -> str:
        body = json.dumps(
            {"messages": messages, "model": self.model},
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.auth_header:
            headers["Authorization"] = self.auth_header
        req = urllib.request.Request(
            self._endpoint, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            raise LLMError(f"LLM 代理返回 HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise LLMError(f"LLM 代理连接失败: {e}") from e
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> str:
        """从响应体里取 assistant 文本。字段名待后端确认，这里做多种兜底。"""
        try:
            data: Dict[str, Any] = json.loads(raw)
        except Exception:
            return raw.strip()
        # 兼容几种常见结构，后端定稿后收敛到一种即可。
        for key in ("content", "reply", "message", "text"):
            v = data.get(key)
            if isinstance(v, str) and v:
                return v
        # OpenAI 风格：choices[0].message.content
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            return raw.strip()


class OpenAICompatLLM(LLMClient):
    """OpenAI 兼容 API 直连客户端（key 写在网关本地）。

    适配 **GpuGeek**（``https://api.gpugeek.com/v1`` + ``Bearer <token>`` +
    标准 ``/chat/completions``），同时兼容其它 OpenAI 格式服务（硅基流动/DeepSeek/通义/
    自建 vLLM 等），换服务只需改 ``base_url`` + ``model`` + ``api_key``。

    为保持网关轻量、零新依赖，直接用 ``urllib`` 调用（不引入 ``openai`` SDK）。
    v1 用**非流式**（``stream=False``）一次性取回，够简单可靠；流式留到 P3。

    配置来源见 :func:`build_llm_from_env`（写在 ``/etc/unilab-gateway.env``）。
    """

    supports_tools = True

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        timeout: float = 90.0,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        # temperature 可选：部分模型（如 Claude）不接受该参数，传了会 400。
        # 因此默认 None=不发；需要时由 env 显式配置。
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @property
    def _endpoint(self) -> str:
        return f"{self.base_url}/chat/completions" if self.base_url else ""

    async def chat(self, messages: List[Message]) -> str:
        if not self._endpoint or not self.api_key:
            raise LLMNotConfigured("LLM 未配置（缺 base_url 或 api_key）")
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._post, messages)

    async def complete(
        self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        if not self._endpoint or not self.api_key:
            raise LLMNotConfigured("LLM 未配置（缺 base_url 或 api_key）")
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._complete_sync, messages, tools)

    # ---- 阻塞实现（在线程池里跑，避免卡住事件循环）------------------------
    def _build_payload(
        self, messages: List[Message], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        # 仅在显式配置了 temperature 时才发送（Claude 等模型不接受该参数）。
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发一次 /chat/completions，返回解析后的 JSON dict。"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(
            self._endpoint, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            raise LLMError(f"LLM 返回 HTTP {e.code}: {detail}") from e
        except TimeoutError as e:
            # 读超时（socket.timeout 在 3.10+ 即 TimeoutError）：模型太慢/排队/网络慢。
            raise LLMError(
                f"LLM 响应超时（>{self.timeout:.0f}s）：模型可能较慢或排队，"
                f"可换更快的模型或调大 UNILABOS_AGENT_LLM_TIMEOUT"
            ) from e
        except urllib.error.URLError as e:
            # URLError 可能包着 socket.timeout，一并识别为超时。
            if isinstance(getattr(e, "reason", None), TimeoutError):
                raise LLMError(
                    f"LLM 响应超时（>{self.timeout:.0f}s）：模型可能较慢或排队，"
                    f"可换更快的模型或调大 UNILABOS_AGENT_LLM_TIMEOUT"
                ) from e
            raise LLMError(f"LLM 连接失败: {e}") from e
        try:
            return json.loads(raw)
        except Exception as e:
            raise LLMError(f"LLM 响应非 JSON：{raw[:200]}") from e

    def _post(self, messages: List[Message]) -> str:
        data = self._request(self._build_payload(messages))
        return self._parse(data)

    def _complete_sync(
        self, messages: List[Message], tools: Optional[List[Dict[str, Any]]]
    ) -> LLMResponse:
        data = self._request(self._build_payload(messages, tools))
        try:
            msg = data["choices"][0]["message"]
        except Exception:
            logger.warning("[LLM] 响应缺少 choices[0].message：%s", str(data)[:300])
            return LLMResponse(content="")
        content = msg.get("content")
        content = content if isinstance(content, str) else None
        tool_calls: List[Dict[str, Any]] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args_raw = fn.get("arguments")
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw) if args_raw.strip() else {}
                except Exception:
                    args = {}
            elif isinstance(args_raw, dict):
                args = args_raw
            else:
                args = {}
            tool_calls.append(
                {"id": tc.get("id") or "", "name": fn.get("name") or "", "arguments": args}
            )
        return LLMResponse(content=content, tool_calls=tool_calls)

    @staticmethod
    def _parse(data: Dict[str, Any]) -> str:
        """从 OpenAI 兼容响应 dict 里取 ``choices[0].message.content``。"""
        try:
            msg = data["choices"][0]["message"]
            # 某些推理模型（如 DeepSeek-R1）会额外给 reasoning_content，
            # 正式答案在 content，这里只取 content。
            content = msg.get("content")
            if isinstance(content, str) and content:
                return content
        except Exception:
            pass
        logger.warning("[LLM] 未能从响应解析出 content：%s", str(data)[:300])
        return ""


def build_llm_from_env(machine_name: str = "") -> LLMClient:
    """按环境变量构建 LLM 客户端（网关启动时调用）。

    读取（写在 ``/etc/unilab-gateway.env``，systemd 注入）：

    * ``UNILABOS_AGENT_LLM_API_KEY``     —— GpuGeek API Key（**必填**，缺则回退 EchoLLM）；
    * ``UNILABOS_AGENT_LLM_BASE_URL``    —— 默认 ``https://api.gpugeek.com/v1``；
    * ``UNILABOS_AGENT_LLM_MODEL``       —— 默认 ``Vendor2/Claude-4.7-opus``（需支持工具调用）；
    * ``UNILABOS_AGENT_LLM_TEMPERATURE`` —— 默认不发（None）；显式配了才发；
    * ``UNILABOS_AGENT_LLM_MAX_TOKENS``  —— 默认 ``2048``；
    * ``UNILABOS_AGENT_LLM_TIMEOUT``     —— HTTP 读超时秒数，默认 ``90``（大模型+工具较慢时可调大）。

    **未配 key 时不报错**，回退 :class:`EchoLLM` 桩——保证没配也能跑通链路自测，
    配了就自动用真实模型，无需改代码。
    """
    api_key = os.environ.get("UNILABOS_AGENT_LLM_API_KEY", "").strip()
    if not api_key:
        logger.info("[LLM] 未配置 UNILABOS_AGENT_LLM_API_KEY，回退 EchoLLM 桩（链路仍可自测）")
        return EchoLLM(machine_name)

    base_url = os.environ.get("UNILABOS_AGENT_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).strip()
    model = os.environ.get("UNILABOS_AGENT_LLM_MODEL", DEFAULT_LLM_MODEL).strip()
    # temperature 默认不发（None）：Claude 等模型不接受该参数。仅当 env 显式给了才发。
    _temp_raw = os.environ.get("UNILABOS_AGENT_LLM_TEMPERATURE", "").strip()
    temperature: Optional[float]
    try:
        temperature = float(_temp_raw) if _temp_raw else None
    except ValueError:
        temperature = None
    try:
        max_tokens = int(os.environ.get("UNILABOS_AGENT_LLM_MAX_TOKENS", "2048"))
    except ValueError:
        max_tokens = 2048
    try:
        timeout = float(os.environ.get("UNILABOS_AGENT_LLM_TIMEOUT", "90"))
    except ValueError:
        timeout = 90.0

    logger.info(
        "[LLM] 直连 %s model=%s timeout=%.0fs（key 已配置）", base_url, model, timeout
    )
    return OpenAICompatLLM(
        base_url,
        api_key,
        model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


class LLMError(RuntimeError):
    """LLM 调用失败（网络/HTTP/解析等）。"""


class LLMNotConfigured(LLMError):
    """LLM 端点尚未配置（后端代理端点未就绪）。"""

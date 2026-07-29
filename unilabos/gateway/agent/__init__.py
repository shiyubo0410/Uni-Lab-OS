"""网关内常驻 Agent（开发规划 §4-②）。

一个跑在香橙派上的轻量管理智能体：接收来自 Runner（PC/手机）的自然语言消息，
调用**云端 LLM** 推理并回复。会议结论：脑子放云端（香橙派跑不动本地大模型），
网关只常驻一个轻量 Agent 进程 + 本地 Skill 工具；Runner 只是 Agent 的窗口。

v1 范围（本期）：
* 打通 "Runner ↔ 网关 Agent ↔ 云端 LLM" 整条对话链路；
* Skill（本地工具执行：看日志 / 重启服务 / 触发 OTA 等）**先不做**，后续挂到 Agent 上。

模块划分：
* :mod:`~unilabos.gateway.agent.llm`   —— LLM 客户端抽象 + 桩 + GpuGeek 直连 + env 工厂；
* :mod:`~unilabos.gateway.agent.agent` —— :class:`GatewayAgent` 会话与消息处理；
* :mod:`~unilabos.gateway.agent.local_cli` —— 本地 CLI Runner，后端中转就绪前自测用。

.. note::
    LLM 已选型 **GpuGeek**（OpenAI 兼容），网关**直连**、key 写在 ``/etc/unilab-gateway.env``。
    Agent 只依赖 :class:`~unilabos.gateway.agent.llm.LLMClient` 接口，
    换服务只需改 env 里的 base_url/model/key，不动 Agent 逻辑。
"""

from .agent import GatewayAgent
from .skill import DeviceSkill
from .llm import (
    LLMClient,
    LLMResponse,
    EchoLLM,
    CloudProxyLLM,
    OpenAICompatLLM,
    build_llm_from_env,
    Message,
)

__all__ = [
    "GatewayAgent",
    "DeviceSkill",
    "LLMClient",
    "LLMResponse",
    "EchoLLM",
    "CloudProxyLLM",
    "OpenAICompatLLM",
    "build_llm_from_env",
    "Message",
]

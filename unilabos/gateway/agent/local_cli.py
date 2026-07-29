"""本地 CLI Runner —— 后端中转就绪前，在本机直接和网关 Agent 对话自测。

它**不走 WS、不连后端**：直接构造一个 :class:`GatewayAgent`，把终端输入喂进
:meth:`GatewayAgent.chat_once`、打印回复。用来验证：多轮上下文、LLM 直连是否通。

用法::

    # 桩模式（不配 key，回显验证链路）
    python -m unilabos.gateway.agent.local_cli

    # 真实推理（配了 GpuGeek key）
    export UNILABOS_AGENT_LLM_API_KEY=xxxx
    python -m unilabos.gateway.agent.local_cli --model GpuGeek/Qwen3-32B

会话内命令：``/reset`` 清空上下文，``/exit`` 或 ``/quit`` 退出。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import sys

from .agent import GatewayAgent
from .llm import build_llm_from_env


async def _repl(agent: GatewayAgent, session: str) -> None:
    loop = asyncio.get_running_loop()
    print("网关 Agent 本地 CLI（/reset 清空上下文，/exit 退出）")
    print(f"LLM: {type(agent.llm).__name__}    session: {session}")
    print("-" * 50)
    while True:
        try:
            # input() 是阻塞的，丢到线程池，避免卡 asyncio。
            text = await loop.run_in_executor(None, lambda: input("你 > "))
        except (EOFError, KeyboardInterrupt):
            print()
            break

        text = text.strip()
        if not text:
            continue
        if text in ("/exit", "/quit"):
            break
        if text == "/reset":
            agent.reset(session)
            print("（已清空上下文）")
            continue

        reply = await agent.chat_once(session, text)
        print(f"Agent > {reply}")


def main() -> None:
    parser = argparse.ArgumentParser(description="网关 Agent 本地 CLI Runner")
    parser.add_argument("--machine-name", default=None, help="机器名（默认 hostname）")
    parser.add_argument("--model", default=None, help="覆盖 LLM 模型（否则读 env / 默认）")
    parser.add_argument("--session", default="cli", help="会话 id（默认 cli）")
    parser.add_argument(
        "--log-level", default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    machine_name = args.machine_name or socket.gethostname()
    if args.model:
        os.environ["UNILABOS_AGENT_LLM_MODEL"] = args.model

    llm = build_llm_from_env(machine_name)
    agent = GatewayAgent(send_fn=None, machine_name=machine_name, llm=llm)

    try:
        asyncio.run(_repl(agent, args.session))
    except KeyboardInterrupt:
        pass
    print("再见。")


if __name__ == "__main__":
    main()

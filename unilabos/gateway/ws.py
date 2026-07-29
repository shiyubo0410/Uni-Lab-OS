"""
极简网关 WebSocket 客户端。

设计目标：
- 完整兼容现有 Uni-Lab-OS ↔ Schedule Server 协议（{"action", "data"} 格式）
- 不依赖 HostNode / rclpy / FastAPI 等重型组件
- 单进程 asyncio，资源占用 < 50MB
- 自动重连（参数复用 unilabos.config.config.WSConfig）

协议参考 Uni-Lab-OS 设备即节点架构 §3.1 / §3.2。
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl as ssl_module
import time
import traceback
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

import websockets

from unilabos.config.config import BasicConfig, WSConfig

logger = logging.getLogger(__name__)


OnMessage = Callable[[Dict[str, Any]], Awaitable[None]]
OnReady = Callable[[], Awaitable[Dict[str, Any]]]


class GatewayClient:
    """
    极简网关 WS 客户端。

    一个客户端实例对应一条到 Schedule Server 的长连接。
    通过 send() 推送上行消息，通过 on_message 回调处理下行消息。
    ping/pong 在客户端内部直接处理，不会透传给 on_message。
    """

    def __init__(
        self,
        url: str,
        machine_name: str,
        on_message: OnMessage,
        on_ready: Optional[OnReady] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.url = url
        self.machine_name = machine_name
        self.session_id = uuid.uuid4().hex[:6]
        self.on_message = on_message
        self.on_ready = on_ready
        # 额外握手头（如 OTA 用的 ConnType/ProductKey/DeviceName），与默认头合并。
        self.extra_headers = dict(extra_headers or {})

        self._send_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_count = 0

    @property
    def is_connected(self) -> bool:
        """当前是否持有一条活动的 WS 连接（供外部断网看门狗判断）。"""
        return self._ws is not None

    async def run(self) -> None:
        """主循环。阻塞运行直到 stop() 被调用或达到最大重连次数。"""
        self._running = True
        while self._running:
            try:
                await self._connect_once()
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"[GW] 与服务端连接已关闭: {e}")
            except websockets.exceptions.InvalidStatus as e:
                logger.error(f"[GW] 握手失败 status={e.response.status_code}，请检查 ak/sk 是否正确")
                # ak/sk 错误时不要无限重连
                if e.response.status_code in (401, 403):
                    break
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning(f"[GW] 连接超时 (已尝试 {self._reconnect_count + 1} 次)")
            except Exception as e:
                logger.error(f"[GW] 连接异常: {e}")
                logger.debug(traceback.format_exc())
            finally:
                self._ws = None

            if not self._running:
                break

            self._reconnect_count += 1
            if self._reconnect_count > WSConfig.max_reconnect_attempts:
                logger.error(f"[GW] 达到最大重连次数 {WSConfig.max_reconnect_attempts}，停止")
                break

            backoff = WSConfig.reconnect_interval
            logger.info(
                f"[GW] {backoff}s 后重连 ({self._reconnect_count}/{WSConfig.max_reconnect_attempts})"
            )
            await asyncio.sleep(backoff)

    async def stop(self) -> None:
        """停止客户端，主动关闭连接。"""
        self._running = False
        ws = self._ws
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def send(self, msg: Dict[str, Any]) -> None:
        """异步发送消息。如果未连接，消息会丢弃（避免无限堆积）。"""
        if self._ws is None:
            logger.debug(f"[GW] 未连接，丢弃出站消息 action={msg.get('action')}")
            return
        await self._send_queue.put(msg)

    async def _connect_once(self) -> None:
        """建立一次连接并阻塞处理消息直到断开。"""
        ssl_ctx = ssl_module.create_default_context() if self.url.startswith("wss://") else None

        headers = {
            "Authorization": f"Lab {BasicConfig.auth_secret()}",
            "EdgeSession": self.session_id,
        }
        headers.update(self.extra_headers)

        async with websockets.connect(
            self.url,
            ssl=ssl_ctx,
            open_timeout=20,
            ping_interval=WSConfig.ws_ping_interval,
            ping_timeout=WSConfig.ws_ping_timeout,
            close_timeout=5,
            additional_headers=headers,
            max_size=10 * 1024 * 1024,
        ) as ws:
            self._ws = ws
            self._reconnect_count = 0
            logger.info(f"[GW] 已连接 {self.url} session={self.session_id}")

            if self.on_ready is not None:
                ready_msg = await self.on_ready()
                # on_ready 可返回单条消息或消息列表：列表按序 _send_raw 发出，
                # 用于"先发 report_action_lock 全量锁快照，再发 host_node_ready"
                # （后端 device_lock 依赖锁表，顺序与 PC 端 WebSocketClient 保持一致）。
                if isinstance(ready_msg, list):
                    for m in ready_msg:
                        if m:
                            await self._send_raw(m)
                elif ready_msg:
                    await self._send_raw(ready_msg)

            send_task = asyncio.create_task(self._send_loop(), name="gw-send")
            try:
                await self._recv_loop()
            finally:
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass

    async def _send_raw(self, msg: Dict[str, Any]) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps(msg, ensure_ascii=False))
        except Exception as e:
            logger.error(f"[GW] 发送失败 action={msg.get('action')}: {e}")

    async def _send_loop(self) -> None:
        while True:
            msg = await self._send_queue.get()
            await self._send_raw(msg)

    async def _recv_loop(self) -> None:
        if self._ws is None:
            return
        async for raw in self._ws:
            try:
                data = json.loads(raw)
            except Exception as e:
                logger.warning(f"[GW] 解析消息失败: {e}, raw={raw[:200]!r}")
                continue

            # 仅当 edge_session 非空且不等于自己时才跳过（防僵尸连接串消息）。
            # 空串 / 缺省表示云端未指定目标会话（广播语义），本机应正常处理，
            # 否则前端下发的 job_start / query_action_state 会被整台网关吞掉，表现为“按了设备不动”。
            edge_session = data.get("edge_session")
            if edge_session and edge_session != self.session_id:
                logger.debug(
                    f"[GW] 跳过非本会话消息 session={edge_session} action={data.get('action')}"
                )
                continue

            action = data.get("action")
            if action == "ping":
                ping_id = data.get("data", {}).get("ping_id")
                await self._send_raw(
                    {
                        "action": "pong",
                        "data": {
                            "ping_id": ping_id,
                            "client_timestamp": time.time(),
                        },
                    }
                )
                continue

            try:
                await self.on_message(data)
            except Exception as e:
                logger.error(f"[GW] 处理消息异常 action={action}: {e}")
                logger.debug(traceback.format_exc())

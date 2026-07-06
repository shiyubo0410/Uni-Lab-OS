"""ThingsBoard MQTT 客户端（OTA 专用）

封装 TB v2 chunk-based OTA 协议 + telemetry / attribute 上报订阅。
TB 官方协议参考：https://thingsboard.io/docs/reference/mqtt-api/

关键 topic：

    上行（Agent → TB）
      v1/devices/me/telemetry              ── 上报实时遥测（fw_state, fw_progress 等）
      v1/devices/me/attributes             ── 上报 client-side attributes（current_fw_*）
      v1/devices/me/attributes/request/<id> ── 主动拉取 shared attributes
      v2/fw/request/<rid>/chunk/<cid>      ── 请求 firmware chunk
      v2/sw/request/<rid>/chunk/<cid>      ── 请求 software chunk (D3.B+)

    下行（TB → Agent）
      v1/devices/me/attributes              ── shared attributes 实时推送（含 fw_title / sw_title 等）
      v1/devices/me/attributes/response/<id> ── shared attributes 拉取响应
      v2/fw/response/<rid>/chunk/<cid>      ── firmware chunk 数据
      v2/sw/response/<rid>/chunk/<cid>      ── software chunk 数据 (D3.B+)

认证方式：device access token 作为 MQTT username，password 留空。
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import aiomqtt

logger = logging.getLogger(__name__)


TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_ATTR_PUBLISH = "v1/devices/me/attributes"
TOPIC_ATTR_SUBSCRIBE = "v1/devices/me/attributes"
TOPIC_ATTR_REQUEST_PREFIX = "v1/devices/me/attributes/request/"
TOPIC_ATTR_RESPONSE_PREFIX = "v1/devices/me/attributes/response/"
TOPIC_ATTR_RESPONSE_WILDCARD = "v1/devices/me/attributes/response/+"
TOPIC_FW_REQUEST_TEMPLATE = "v2/fw/request/{rid}/chunk/{cid}"
TOPIC_FW_RESPONSE_WILDCARD = "v2/fw/response/+/chunk/+"
TOPIC_FW_RESPONSE_PREFIX = "v2/fw/response/"
TOPIC_SW_REQUEST_TEMPLATE = "v2/sw/request/{rid}/chunk/{cid}"
TOPIC_SW_RESPONSE_WILDCARD = "v2/sw/response/+/chunk/+"
TOPIC_SW_RESPONSE_PREFIX = "v2/sw/response/"


class TBClientError(Exception):
    """TB 客户端通用错误。"""


class TBClient:
    """ThingsBoard MQTT 客户端（asyncio + aiomqtt）。

    使用方式::

        async with TBClient(host, port, token) as tb:
            await tb.publish_client_attributes({"current_fw_title": "...", "current_fw_version": "1.0.0"})
            shared = await tb.request_shared_attributes(["fw_title", "fw_version", "fw_size", "fw_checksum", "fw_checksum_algorithm"])
            async for attrs in tb.attribute_updates():
                # attrs 形如 {'fw_title': '...', 'fw_version': '1.0.1', ...}
                ...
            chunk = await tb.request_firmware_chunk(rid=1, cid=0, chunk_size=524288)
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        token: str = "",
        qos: int = 1,
        keepalive: int = 60,
        chunk_timeout: float = 30.0,
        attr_response_timeout: float = 10.0,
    ) -> None:
        if not host:
            raise ValueError("TB host 不能为空")
        if not token:
            raise ValueError("TB device access token 不能为空")
        self.host = host
        self.port = port
        self.token = token
        self.qos = qos
        self.keepalive = keepalive
        self.chunk_timeout = chunk_timeout
        self.attr_response_timeout = attr_response_timeout

        self._client: Optional[aiomqtt.Client] = None
        self._client_cm = None
        self._dispatcher_task: Optional[asyncio.Task] = None

        self._attr_update_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pending_attr_responses: dict[int, asyncio.Future] = {}
        self._pending_fw_chunks: dict[tuple[int, int], asyncio.Future] = {}
        self._pending_sw_chunks: dict[tuple[int, int], asyncio.Future] = {}

        self._attr_request_id_counter = 0
        self._stop_event = asyncio.Event()

    async def __aenter__(self) -> "TBClient":
        await self._connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._disconnect()

    async def _connect(self) -> None:
        """连接 TB MQTT + 订阅必要 topic + 启动分发协程。"""
        logger.info("连接 TB MQTT: %s:%s", self.host, self.port)

        client = aiomqtt.Client(
            hostname=self.host,
            port=self.port,
            username=self.token,
            keepalive=self.keepalive,
        )
        # aiomqtt.Client 本身是 async context manager。
        # 用 __aenter__/__aexit__ 手动管理生命周期，让 TBClient 作为上层 CM 透传。
        await client.__aenter__()
        self._client = client

        await client.subscribe(TOPIC_ATTR_SUBSCRIBE, qos=self.qos)
        await client.subscribe(TOPIC_ATTR_RESPONSE_WILDCARD, qos=self.qos)
        await client.subscribe(TOPIC_FW_RESPONSE_WILDCARD, qos=self.qos)
        await client.subscribe(TOPIC_SW_RESPONSE_WILDCARD, qos=self.qos)

        self._stop_event.clear()
        self._dispatcher_task = asyncio.create_task(
            self._dispatcher_loop(), name="tb-msg-dispatcher"
        )
        logger.info("TB MQTT 已连接，订阅生效")

    async def _disconnect(self) -> None:
        """优雅断开：停 dispatcher → close MQTT。"""
        self._stop_event.set()
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dispatcher_task = None

        # 取消所有 pending Future，避免外部协程永久阻塞
        for fut in self._pending_attr_responses.values():
            if not fut.done():
                fut.cancel()
        self._pending_attr_responses.clear()
        for fut in self._pending_fw_chunks.values():
            if not fut.done():
                fut.cancel()
        self._pending_fw_chunks.clear()
        for fut in self._pending_sw_chunks.values():
            if not fut.done():
                fut.cancel()
        self._pending_sw_chunks.clear()

        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as exc:
                logger.warning("关闭 TB MQTT 时出错（忽略）: %s", exc)
            self._client = None
        logger.info("TB MQTT 已断开")

    async def _dispatcher_loop(self) -> None:
        """单 reader 循环：把 TB 推过来的所有消息按 topic 分发到 queue / future。

        aiomqtt 设计上要求只有一个 reader 在迭代 client.messages，所以所有订阅消息
        都通过这里出口。任何对外的 attribute_updates() / request_firmware_chunk() /
        request_shared_attributes() 都从这里下游消费。
        """
        assert self._client is not None
        try:
            async for msg in self._client.messages:
                topic = str(msg.topic)
                payload = msg.payload
                try:
                    if topic == TOPIC_ATTR_SUBSCRIBE:
                        # shared attribute 实时推送（例如 TB 分配了新 firmware）
                        data = self._safe_json(payload)
                        # TB 推送的 shared attribute 有时会包在 {"shared": {...}} 里
                        if isinstance(data, dict) and "shared" in data and isinstance(data["shared"], dict):
                            data = data["shared"]
                        await self._attr_update_queue.put(data)
                    elif topic.startswith(TOPIC_ATTR_RESPONSE_PREFIX):
                        rid = int(topic[len(TOPIC_ATTR_RESPONSE_PREFIX):])
                        fut = self._pending_attr_responses.pop(rid, None)
                        if fut and not fut.done():
                            fut.set_result(self._safe_json(payload))
                    elif topic.startswith(TOPIC_FW_RESPONSE_PREFIX):
                        # v2/fw/response/<rid>/chunk/<cid>
                        parts = topic.split("/")
                        if len(parts) >= 6:
                            rid = int(parts[3])
                            cid = int(parts[5])
                            key = (rid, cid)
                            fut = self._pending_fw_chunks.pop(key, None)
                            if fut and not fut.done():
                                # payload 是 binary chunk
                                fut.set_result(bytes(payload))
                    elif topic.startswith(TOPIC_SW_RESPONSE_PREFIX):
                        # v2/sw/response/<rid>/chunk/<cid>
                        parts = topic.split("/")
                        if len(parts) >= 6:
                            rid = int(parts[3])
                            cid = int(parts[5])
                            key = (rid, cid)
                            fut = self._pending_sw_chunks.pop(key, None)
                            if fut and not fut.done():
                                fut.set_result(bytes(payload))
                    else:
                        logger.debug("丢弃未知 topic: %s", topic)
                except Exception as exc:
                    logger.warning("分发消息时出错 topic=%s: %s", topic, exc)
        except asyncio.CancelledError:
            logger.debug("dispatcher 被取消")
            raise
        except Exception as exc:
            logger.error("dispatcher 异常退出: %s", exc, exc_info=True)
            # 让所有 pending future 失败，避免上层永久挂起
            for fut in list(self._pending_attr_responses.values()):
                if not fut.done():
                    fut.set_exception(TBClientError(f"MQTT 通道断开: {exc}"))
            for fut in list(self._pending_fw_chunks.values()):
                if not fut.done():
                    fut.set_exception(TBClientError(f"MQTT 通道断开: {exc}"))
            for fut in list(self._pending_sw_chunks.values()):
                if not fut.done():
                    fut.set_exception(TBClientError(f"MQTT 通道断开: {exc}"))

    @staticmethod
    def _safe_json(payload) -> dict:
        try:
            return json.loads(payload)
        except Exception:
            logger.warning("无法解析 JSON payload: %r", payload)
            return {}

    # ----------------- 对外 API -----------------

    async def publish_telemetry(self, data: dict) -> None:
        """上报遥测数据到 v1/devices/me/telemetry。"""
        if self._client is None:
            raise TBClientError("TB 客户端未连接")
        payload = json.dumps(data).encode("utf-8")
        await self._client.publish(TOPIC_TELEMETRY, payload=payload, qos=self.qos)
        logger.debug("publish telemetry: %s", data)

    async def publish_client_attributes(self, data: dict) -> None:
        """上报 client-side attributes 到 v1/devices/me/attributes。"""
        if self._client is None:
            raise TBClientError("TB 客户端未连接")
        payload = json.dumps(data).encode("utf-8")
        await self._client.publish(TOPIC_ATTR_PUBLISH, payload=payload, qos=self.qos)
        logger.debug("publish client attributes: %s", data)

    async def request_shared_attributes(
        self, keys: list[str], timeout: Optional[float] = None
    ) -> dict:
        """主动拉取 shared attributes（启动时用，避免错过历史推送）。

        Args:
            keys: 想要的 attribute key 列表。例如 ['fw_title', 'fw_version', 'fw_size',
                  'fw_checksum', 'fw_checksum_algorithm']。
            timeout: 超时秒数，None 用默认值。

        Returns:
            形如 ``{'shared': {'fw_title': '...', ...}}`` 或 ``{}``（拉不到）。
        """
        if self._client is None:
            raise TBClientError("TB 客户端未连接")

        self._attr_request_id_counter += 1
        rid = self._attr_request_id_counter
        topic = f"{TOPIC_ATTR_REQUEST_PREFIX}{rid}"
        payload = json.dumps({"sharedKeys": ",".join(keys)}).encode("utf-8")

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending_attr_responses[rid] = fut

        await self._client.publish(topic, payload=payload, qos=self.qos)
        try:
            result = await asyncio.wait_for(
                fut, timeout=timeout or self.attr_response_timeout
            )
        except asyncio.TimeoutError:
            self._pending_attr_responses.pop(rid, None)
            logger.warning("拉取 shared attributes 超时: keys=%s", keys)
            return {}
        return result if isinstance(result, dict) else {}

    async def attribute_updates(self) -> AsyncIterator[dict]:
        """订阅 shared attribute 的实时推送。

        例：TB 给本 device 分配新固件后，会推送一条
        ``{'fw_title': '...', 'fw_version': '1.0.1', 'fw_size': ..., 'fw_checksum': ...,
        'fw_checksum_algorithm': 'SHA256'}``。
        """
        while not self._stop_event.is_set():
            try:
                data = await asyncio.wait_for(self._attr_update_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            yield data

    async def request_firmware_chunk(
        self, rid: int, cid: int, chunk_size: int, timeout: Optional[float] = None
    ) -> bytes:
        """请求一个 firmware chunk，等响应。

        Args:
            rid: 本次升级会话的 request_id（同一固件下载用同一个 rid）。
            cid: chunk_id，从 0 开始。
            chunk_size: 单个 chunk 的字节数（TB 用这个作为 payload）。
            timeout: 单 chunk 超时秒数。

        Returns:
            binary chunk 数据。最后一块可能小于 chunk_size。
        """
        if self._client is None:
            raise TBClientError("TB 客户端未连接")

        key = (rid, cid)
        if key in self._pending_fw_chunks:
            raise TBClientError(f"chunk request 已存在: rid={rid} cid={cid}")

        topic = TOPIC_FW_REQUEST_TEMPLATE.format(rid=rid, cid=cid)
        # TB 协议：payload 是 chunk_size 的字符串
        payload = str(chunk_size).encode("ascii")

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending_fw_chunks[key] = fut

        await self._client.publish(topic, payload=payload, qos=self.qos)
        try:
            data: bytes = await asyncio.wait_for(
                fut, timeout=timeout or self.chunk_timeout
            )
        except asyncio.TimeoutError:
            self._pending_fw_chunks.pop(key, None)
            raise TBClientError(
                f"等待 firmware chunk 超时 rid={rid} cid={cid} timeout={timeout or self.chunk_timeout}s"
            )
        return data

    async def request_software_chunk(
        self, rid: int, cid: int, chunk_size: int, timeout: Optional[float] = None
    ) -> bytes:
        """请求一个 software chunk，等响应（D3.B+）。

        协议跟 firmware chunk 完全对称，只是 topic 用 ``v2/sw/*``。
        """
        if self._client is None:
            raise TBClientError("TB 客户端未连接")

        key = (rid, cid)
        if key in self._pending_sw_chunks:
            raise TBClientError(f"sw chunk request 已存在: rid={rid} cid={cid}")

        topic = TOPIC_SW_REQUEST_TEMPLATE.format(rid=rid, cid=cid)
        payload = str(chunk_size).encode("ascii")

        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending_sw_chunks[key] = fut

        await self._client.publish(topic, payload=payload, qos=self.qos)
        try:
            data: bytes = await asyncio.wait_for(
                fut, timeout=timeout or self.chunk_timeout
            )
        except asyncio.TimeoutError:
            self._pending_sw_chunks.pop(key, None)
            raise TBClientError(
                f"等待 software chunk 超时 rid={rid} cid={cid} timeout={timeout or self.chunk_timeout}s"
            )
        return data


@asynccontextmanager
async def open_tb_client(*args, **kwargs):
    """便捷工厂：``async with open_tb_client(host, port, token) as tb: ...``"""
    client = TBClient(*args, **kwargs)
    async with client as c:
        yield c

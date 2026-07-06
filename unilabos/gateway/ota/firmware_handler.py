"""固件下载 + 校验。

负责把 TB 推过来的 firmware 元数据，通过 chunk-based MQTT 协议分块拉到本地，
全部拉完后做 sha256 校验。**D2 阶段不调 ota CLI**——校验通过即结束。

下载文件命名：``{download_dir}/{title}-{version}.bin``

进度上报通过 ``progress_cb(received_chunks, total_chunks)`` 回调，
让上层（agent）每收 N 块就推一次 telemetry。
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .state import (
    STATE_DOWNLOADED,
    STATE_DOWNLOADING,
    STATE_FAILED,
    STATE_VERIFIED,
    OngoingUpdate,
    OtaState,
)
from .tb_client import TBClient, TBClientError

logger = logging.getLogger(__name__)


class FirmwareError(Exception):
    """固件下载/校验失败。"""


# (received_chunks, total_chunks) -> awaitable
ProgressCallback = Callable[[int, int], Awaitable[None]]


def _sanitize_filename(s: str) -> str:
    """避免文件名里出现奇怪字符。"""
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in s)


async def download_firmware(
    tb: TBClient,
    state: OtaState,
    rid: int,
    fw_title: str,
    fw_version: str,
    fw_size: int,
    fw_checksum: str,
    fw_checksum_alg: str,
    download_dir: Path,
    chunk_size: int,
    chunk_retry: int = 3,
    progress_cb: Optional[ProgressCallback] = None,
) -> Path:
    """下载固件 + sha256 校验。

    Args:
        tb: 已连接的 TBClient。
        state: OtaState，用于持久化进度。
        rid: 本次会话 request_id。
        fw_*: TB 推送的固件元数据。
        download_dir: chunk 拼装位置。
        chunk_size: 单 chunk 字节数。
        chunk_retry: 单 chunk 重试次数。
        progress_cb: 进度回调（每收一块调一次）。

    Returns:
        下载文件完整路径。

    Raises:
        FirmwareError: 下载或校验失败。
    """
    if fw_checksum_alg.upper() != "SHA256":
        raise FirmwareError(
            f"D2 仅支持 SHA256 校验，TB 推送的是 {fw_checksum_alg}"
        )

    download_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_sanitize_filename(fw_title)}-{_sanitize_filename(fw_version)}.bin"
    out_path = download_dir / filename

    ongoing = state.start_update(
        rid=rid,
        title=fw_title,
        version=fw_version,
        size=fw_size,
        checksum=fw_checksum,
        checksum_alg=fw_checksum_alg,
        chunk_size=chunk_size,
        download_path=out_path,
    )
    logger.info(
        "开始下载 %s-%s (size=%d, chunks=%d, chunk_size=%d) -> %s",
        fw_title,
        fw_version,
        fw_size,
        ongoing.total_chunks,
        chunk_size,
        out_path,
    )

    sha256 = hashlib.sha256()
    bytes_written = 0

    # D2 阶段：每次都从头下载（不做断点续传，简化逻辑）。
    # D3 阶段如果要做断点续传，可以在这里加 ongoing.received_chunks 校验逻辑。
    try:
        with open(out_path, "wb") as f:
            for cid in range(ongoing.total_chunks):
                chunk = await _request_chunk_with_retry(
                    tb=tb,
                    rid=rid,
                    cid=cid,
                    chunk_size=chunk_size,
                    retries=chunk_retry,
                )
                if not chunk:
                    raise FirmwareError(f"收到空 chunk: rid={rid} cid={cid}")
                f.write(chunk)
                sha256.update(chunk)
                bytes_written += len(chunk)

                state.update_progress(received_chunks=cid + 1)
                if progress_cb is not None:
                    try:
                        await progress_cb(cid + 1, ongoing.total_chunks)
                    except Exception as exc:
                        logger.warning("progress_cb 出错（忽略）: %s", exc)

                if (cid + 1) % 10 == 0 or cid + 1 == ongoing.total_chunks:
                    logger.info(
                        "下载进度: %d/%d chunks (%.1f%%)",
                        cid + 1,
                        ongoing.total_chunks,
                        100.0 * (cid + 1) / ongoing.total_chunks,
                    )
            f.flush()
            os.fsync(f.fileno())
    except Exception as exc:
        state.mark_state(STATE_FAILED, error=f"下载失败: {exc}")
        # 删掉半下载的文件，避免下次误认为完整
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise FirmwareError(f"chunk 下载失败: {exc}") from exc

    state.mark_state(STATE_DOWNLOADED)
    logger.info("下载完成: %s (%d bytes)", out_path, bytes_written)

    # ---------- 校验 ----------
    if bytes_written != fw_size:
        msg = (
            f"下载大小不符: 期望 {fw_size}, 实际 {bytes_written} "
            f"(file={out_path})"
        )
        state.mark_state(STATE_FAILED, error=msg)
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise FirmwareError(msg)

    actual = sha256.hexdigest()
    expected = fw_checksum.lower()
    logger.info("sha256 校验: 算出 %s 期望 %s", actual, expected)
    if actual != expected:
        msg = f"sha256 不匹配: 算出 {actual}, 期望 {expected}"
        state.mark_state(STATE_FAILED, error=msg)
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise FirmwareError(msg)

    state.mark_state(STATE_VERIFIED)
    logger.info(
        "校验通过 ✓ - D2 阶段到此结束（不调 ota CLI），文件留在: %s", out_path
    )
    return out_path


async def _request_chunk_with_retry(
    tb: TBClient,
    rid: int,
    cid: int,
    chunk_size: int,
    retries: int,
) -> bytes:
    """请求单个 chunk，带重试。"""
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return await tb.request_firmware_chunk(rid=rid, cid=cid, chunk_size=chunk_size)
        except TBClientError as exc:
            last_exc = exc
            logger.warning(
                "chunk 失败 rid=%d cid=%d attempt=%d/%d: %s",
                rid,
                cid,
                attempt + 1,
                retries + 1,
                exc,
            )
            if attempt < retries:
                # 指数退避：1s, 2s, 4s ...
                await asyncio.sleep(min(2**attempt, 10))
    raise FirmwareError(
        f"chunk rid={rid} cid={cid} 重试 {retries + 1} 次仍失败: {last_exc}"
    )

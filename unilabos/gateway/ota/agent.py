"""Uni-Lab OTA Agent - 主程序。

从 /etc/unilab-ota-agent.env 读配置，连 TB MQTT，监听 firmware / software 推送：

* **firmware** (D2)：v2/fw/* 协议，下载 + sha256 校验后停在 VERIFIED；D3.A 才调 ota CLI。
* **software** (D3.B)：v2/sw/* 协议，下载 + 校验 + 解压 + symlink 切换 + restart
  + health check + 失败自动回滚。

使用::

    python -m unilabos.gateway.ota.agent

或通过 systemd::

    systemctl start unilab-ota-agent
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .firmware_handler import FirmwareError, download_firmware
from .software_handler import install_software
from .state import (
    STATE_DOWNLOADING,
    STATE_FAILED,
    STATE_VERIFIED,
    CurrentFirmware,
    OtaState,
)
from .tb_client import TBClient


logger = logging.getLogger("unilab.ota.agent")


# ============== 配置 ==============

@dataclass
class AgentConfig:
    """Agent 运行配置，从环境变量读取。"""

    tb_host: str
    tb_token: str
    current_fw_title: str
    current_fw_version: str
    tb_port: int = 1883
    tb_qos: int = 1
    download_dir: Path = Path("/data/ota/download")
    state_file: Path = Path("/data/ota/agent_state.json")
    versions_root: Path = Path("/opt/unilab/versions")  # software 解压根目录 (D3.B)
    chunk_size: int = 8192  # 8KB（TB Cloud broker max packet size 65535，超过会被踢）
    chunk_timeout: float = 30.0
    chunk_retry: int = 3
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """从环境变量读配置。缺必填字段会抛 KeyError。"""
        required = ["TB_HOST", "TB_TOKEN", "CURRENT_FW_TITLE", "CURRENT_FW_VERSION"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise KeyError(f"缺少必填环境变量: {missing}")

        return cls(
            tb_host=os.environ["TB_HOST"].strip(),
            tb_token=os.environ["TB_TOKEN"].strip(),
            current_fw_title=os.environ["CURRENT_FW_TITLE"].strip(),
            current_fw_version=os.environ["CURRENT_FW_VERSION"].strip(),
            tb_port=int(os.environ.get("TB_PORT", "1883")),
            tb_qos=int(os.environ.get("TB_QOS", "1")),
            download_dir=Path(os.environ.get("DOWNLOAD_DIR", "/data/ota/download")),
            state_file=Path(os.environ.get("STATE_FILE", "/data/ota/agent_state.json")),
            versions_root=Path(os.environ.get("VERSIONS_ROOT", "/opt/unilab/versions")),
            chunk_size=int(os.environ.get("CHUNK_SIZE", "8192")),  # TB Cloud broker 上限 64KB，必须 ≤ 8KB
            chunk_timeout=float(os.environ.get("CHUNK_TIMEOUT", "30")),
            chunk_retry=int(os.environ.get("CHUNK_RETRY", "3")),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        )


# ============== 核心 Agent ==============

# 与 TB 协议字段一致的 fw_state 字符串
FW_STATE_DOWNLOADING = "DOWNLOADING"
FW_STATE_DOWNLOADED = "DOWNLOADED"
FW_STATE_VERIFIED = "VERIFIED"
FW_STATE_UPDATED = "UPDATED"
FW_STATE_FAILED = "FAILED"

# software 也对称用一套（TB UI 上以 sw_state 显示）
SW_STATE_DOWNLOADING = "DOWNLOADING"
SW_STATE_DOWNLOADED = "DOWNLOADED"
SW_STATE_VERIFIED = "VERIFIED"
SW_STATE_UPDATED = "UPDATED"
SW_STATE_FAILED = "FAILED"
SW_STATE_INCOMPATIBLE = "INCOMPATIBLE"
SW_STATE_ROLLED_BACK = "ROLLED_BACK"
SW_STATE_ALREADY_UP_TO_DATE = "ALREADY_UP_TO_DATE"


class OtaAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.state = OtaState.load(
            state_file=config.state_file,
            default_current_fw=CurrentFirmware(
                title=config.current_fw_title,
                version=config.current_fw_version,
            ),
        )
        self.stop_event = asyncio.Event()
        self._rid_counter = 0
        # 同一时刻只处理一个 firmware 更新
        self._update_lock = asyncio.Lock()
        # 正在处理的 fw_version，避免重复触发
        self._processing_version: Optional[str] = None
        # software 升级独立 lock & 去重（fw 和 sw 互不阻塞）
        self._sw_update_lock = asyncio.Lock()
        self._processing_sw_version: Optional[str] = None

    def request_stop(self) -> None:
        """请求 Agent 退出（信号处理）。"""
        logger.info("收到停止信号")
        self.stop_event.set()

    async def run(self) -> None:
        """主入口。"""
        cfg = self.config
        logger.info(
            "启动 OTA Agent: TB=%s:%s current=%s/%s chunk_size=%d",
            cfg.tb_host,
            cfg.tb_port,
            cfg.current_fw_title,
            cfg.current_fw_version,
            cfg.chunk_size,
        )

        async with TBClient(
            host=cfg.tb_host,
            port=cfg.tb_port,
            token=cfg.tb_token,
            qos=cfg.tb_qos,
            chunk_timeout=cfg.chunk_timeout,
        ) as tb:
            # 1. 上报当前固件 / 软件 + 状态 = UPDATED（首次连接的"心跳"）
            await self._report_initial_state(tb)

            # 2. 主动拉一次 shared attributes 防止启动前推送被错过
            await self._poll_initial_firmware(tb)
            await self._poll_initial_software(tb)

            # 3. 进 attribute 监听循环 + 等待 stop_event
            listen_task = asyncio.create_task(
                self._listen_loop(tb), name="ota-listen-loop"
            )
            stop_task = asyncio.create_task(
                self.stop_event.wait(), name="ota-stop-wait"
            )
            try:
                done, pending = await asyncio.wait(
                    [listen_task, stop_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                for t in pending:
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass
                # 检查 listen_task 是否异常退出
                if listen_task in done:
                    exc = listen_task.exception()
                    if exc is not None:
                        logger.error("listen_loop 异常退出: %s", exc, exc_info=True)
            finally:
                logger.info("OTA Agent 主循环退出")

    # ---------------- 上报 ----------------

    async def _report_initial_state(self, tb: TBClient) -> None:
        """启动时上报: 当前固件 + (如有) 当前软件 + fw_state=UPDATED。"""
        cur = self.state.current_fw
        attrs: dict = {"current_fw_title": cur.title, "current_fw_version": cur.version}
        telemetry: dict = {
            "current_fw_title": cur.title,
            "current_fw_version": cur.version,
            "fw_state": FW_STATE_UPDATED,
        }
        cur_sw = self.state.current_software
        if cur_sw is not None:
            attrs["current_sw_title"] = cur_sw.title
            attrs["current_sw_version"] = cur_sw.version
            telemetry["current_sw_title"] = cur_sw.title
            telemetry["current_sw_version"] = cur_sw.version
            telemetry["sw_state"] = SW_STATE_UPDATED

        await tb.publish_client_attributes(attrs)
        await tb.publish_telemetry(telemetry)
        if cur_sw is not None:
            logger.info(
                "已上报: fw=%s/%s sw=%s/%s",
                cur.title, cur.version, cur_sw.title, cur_sw.version,
            )
        else:
            logger.info("已上报当前固件: %s/%s 状态=UPDATED (无 current_software)", cur.title, cur.version)

    async def _report_state(
        self,
        tb: TBClient,
        fw_state: str,
        error: Optional[str] = None,
        fw_version: Optional[str] = None,
    ) -> None:
        """上报升级中的 fw_state 状态。"""
        data: dict = {"fw_state": fw_state}
        if error:
            data["fw_error"] = error
        if fw_version:
            data["fw_version"] = fw_version
        await tb.publish_telemetry(data)

    async def _report_sw_state(
        self,
        tb: TBClient,
        sw_state: str,
        error: Optional[str] = None,
        sw_version: Optional[str] = None,
    ) -> None:
        """上报升级中的 sw_state 状态。"""
        data: dict = {"sw_state": sw_state}
        if error:
            data["sw_error"] = error
        if sw_version:
            data["sw_version"] = sw_version
        await tb.publish_telemetry(data)

    # ---------------- 主流程 ----------------

    async def _poll_initial_firmware(self, tb: TBClient) -> None:
        """启动时主动拉 shared attributes，避免错过 TB 在 Agent 离线期间推送的固件。"""
        keys = [
            "fw_title",
            "fw_version",
            "fw_size",
            "fw_checksum",
            "fw_checksum_algorithm",
        ]
        try:
            resp = await tb.request_shared_attributes(keys)
        except Exception as exc:
            logger.warning("初始 shared attributes 拉取失败: %s", exc)
            return

        shared = resp.get("shared") if isinstance(resp, dict) else {}
        if not shared:
            logger.info("TB 未分配 firmware，等推送")
            return

        logger.info("启动时发现已分配 firmware: %s", shared)
        asyncio.create_task(
            self._maybe_handle_firmware(tb, shared),
            name="ota-initial-fw",
        )

    async def _listen_loop(self, tb: TBClient) -> None:
        """监听 TB 推送的 attribute 更新（fw_* 和 sw_* 都处理）。"""
        async for attrs in tb.attribute_updates():
            if not attrs:
                continue
            has_fw = any(k.startswith("fw_") for k in attrs.keys())
            has_sw = any(k.startswith("sw_") for k in attrs.keys())
            if has_fw:
                logger.info("收到 firmware 推送: %s", attrs)
                asyncio.create_task(
                    self._maybe_handle_firmware(tb, attrs),
                    name="ota-handle-fw",
                )
            if has_sw:
                logger.info("收到 software 推送: %s", attrs)
                asyncio.create_task(
                    self._maybe_handle_software(tb, attrs),
                    name="ota-handle-sw",
                )
            if not has_fw and not has_sw:
                logger.debug("忽略非 fw/sw 属性推送: %s", list(attrs.keys()))

    async def _maybe_handle_firmware(self, tb: TBClient, fw: dict) -> None:
        """收到 firmware 元数据后判断是否要下载。"""
        fw_title = fw.get("fw_title")
        fw_version = fw.get("fw_version")
        fw_size = fw.get("fw_size")
        fw_checksum = fw.get("fw_checksum")
        fw_checksum_alg = fw.get("fw_checksum_algorithm", "SHA256")

        if not all([fw_title, fw_version, fw_size, fw_checksum]):
            logger.warning("firmware 元数据不完整，忽略: %s", fw)
            return

        # 跟当前一致 → 跳过
        cur = self.state.current_fw
        if fw_title == cur.title and fw_version == cur.version:
            logger.info("固件版本与当前一致 (%s/%s)，跳过", fw_title, fw_version)
            return

        # 正在处理同版本 → 跳过
        if self._processing_version == fw_version:
            logger.info("已在处理该版本 (%s)，跳过", fw_version)
            return

        # 上一次 ongoing 已经 VERIFIED 同版本 → 跳过
        if (
            self.state.ongoing
            and self.state.ongoing.state == STATE_VERIFIED
            and self.state.ongoing.title == fw_title
            and self.state.ongoing.version == fw_version
        ):
            logger.info(
                "该版本之前已经下载并 VERIFIED (%s/%s)，D2 阶段不重复，跳过",
                fw_title,
                fw_version,
            )
            return

        async with self._update_lock:
            self._processing_version = fw_version
            try:
                await self._do_update(
                    tb=tb,
                    fw_title=str(fw_title),
                    fw_version=str(fw_version),
                    fw_size=int(fw_size),
                    fw_checksum=str(fw_checksum),
                    fw_checksum_alg=str(fw_checksum_alg),
                )
            finally:
                self._processing_version = None

    async def _do_update(
        self,
        tb: TBClient,
        fw_title: str,
        fw_version: str,
        fw_size: int,
        fw_checksum: str,
        fw_checksum_alg: str,
    ) -> None:
        """实际跑一次 OTA：下载 + 校验，全程上报 fw_state。"""
        cfg = self.config
        self._rid_counter += 1
        rid = self._rid_counter

        logger.info(
            "开始 OTA: rid=%d title=%s version=%s size=%d",
            rid,
            fw_title,
            fw_version,
            fw_size,
        )

        await self._report_state(
            tb, FW_STATE_DOWNLOADING, fw_version=fw_version
        )

        async def progress_cb(received: int, total: int) -> None:
            # 每 10% 推一次（避免刷屏 telemetry）
            percent = int(100 * received / total)
            if received == total or received == 1 or percent % 10 == 0:
                await tb.publish_telemetry({"fw_progress": percent})

        try:
            out_path = await download_firmware(
                tb=tb,
                state=self.state,
                rid=rid,
                fw_title=fw_title,
                fw_version=fw_version,
                fw_size=fw_size,
                fw_checksum=fw_checksum,
                fw_checksum_alg=fw_checksum_alg,
                download_dir=cfg.download_dir,
                chunk_size=cfg.chunk_size,
                chunk_retry=cfg.chunk_retry,
                progress_cb=progress_cb,
            )
        except FirmwareError as exc:
            logger.error("OTA 失败: %s", exc)
            await self._report_state(
                tb, FW_STATE_FAILED, error=str(exc), fw_version=fw_version
            )
            return
        except Exception as exc:
            logger.error("OTA 意外异常: %s", exc, exc_info=True)
            await self._report_state(
                tb, FW_STATE_FAILED, error=f"内部异常: {exc}", fw_version=fw_version
            )
            return

        # 下载 + 校验都通过
        await tb.publish_telemetry({"fw_progress": 100})
        await self._report_state(
            tb, FW_STATE_DOWNLOADED, fw_version=fw_version
        )
        await self._report_state(
            tb, FW_STATE_VERIFIED, fw_version=fw_version
        )
        logger.info(
            "✓ D2 完成: %s/%s 已下载并校验，文件: %s。"
            "D3 阶段才会调 ota write/switch。",
            fw_title,
            fw_version,
            out_path,
        )

    # ---------------- software 流程（D3.B） ----------------

    async def _poll_initial_software(self, tb: TBClient) -> None:
        """启动时主动拉 sw_*，避免错过 TB 离线期间的推送。"""
        keys = ["sw_title", "sw_version", "sw_size", "sw_checksum", "sw_checksum_algorithm"]
        try:
            resp = await tb.request_shared_attributes(keys)
        except Exception as exc:
            logger.warning("初始 sw shared attributes 拉取失败: %s", exc)
            return
        shared = resp.get("shared") if isinstance(resp, dict) else {}
        if not shared or not any(k.startswith("sw_") for k in shared.keys()):
            logger.info("TB 未分配 software，等推送")
            return
        logger.info("启动时发现已分配 software: %s", shared)
        asyncio.create_task(
            self._maybe_handle_software(tb, shared),
            name="ota-initial-sw",
        )

    async def _maybe_handle_software(self, tb: TBClient, sw: dict) -> None:
        """收到 software 元数据后判断是否要下载安装。"""
        sw_title = sw.get("sw_title")
        sw_version = sw.get("sw_version")
        sw_size = sw.get("sw_size")
        sw_checksum = sw.get("sw_checksum")
        sw_checksum_alg = sw.get("sw_checksum_algorithm", "SHA256")

        if not all([sw_title, sw_version, sw_size, sw_checksum]):
            logger.warning("software 元数据不完整，忽略: %s", sw)
            return

        # 跟当前 current_software 一致 → 跳过
        cur_sw = self.state.current_software
        if cur_sw and cur_sw.title == sw_title and cur_sw.version == sw_version:
            logger.info("software 版本与当前一致 (%s/%s)，跳过", sw_title, sw_version)
            return

        # 正在处理同版本 → 跳过
        if self._processing_sw_version == sw_version:
            logger.info("已在处理该 sw 版本 (%s)，跳过", sw_version)
            return

        async with self._sw_update_lock:
            self._processing_sw_version = str(sw_version)
            try:
                await self._do_software_update(
                    tb=tb,
                    sw_title=str(sw_title),
                    sw_version=str(sw_version),
                    sw_size=int(sw_size),
                    sw_checksum=str(sw_checksum),
                    sw_checksum_alg=str(sw_checksum_alg),
                )
            finally:
                self._processing_sw_version = None

    async def _do_software_update(
        self,
        tb: TBClient,
        sw_title: str,
        sw_version: str,
        sw_size: int,
        sw_checksum: str,
        sw_checksum_alg: str,
    ) -> None:
        """执行一次完整的 software 升级 + 上报每个阶段的 sw_state。"""
        cfg = self.config
        self._rid_counter += 1
        rid = self._rid_counter

        logger.info(
            "开始 software 升级: rid=%d title=%s version=%s size=%d",
            rid, sw_title, sw_version, sw_size,
        )
        await self._report_sw_state(tb, SW_STATE_DOWNLOADING, sw_version=sw_version)

        async def progress_cb(received: int, total: int) -> None:
            percent = int(100 * received / total)
            if received == total or received == 1 or percent % 10 == 0:
                await tb.publish_telemetry({"sw_progress": percent})

        try:
            result = await install_software(
                tb=tb,
                state=self.state,
                rid=rid,
                sw_title=sw_title,
                sw_version=sw_version,
                sw_size=sw_size,
                sw_checksum=sw_checksum,
                sw_checksum_alg=sw_checksum_alg,
                download_dir=cfg.download_dir,
                versions_root=cfg.versions_root,
                chunk_size=cfg.chunk_size,
                chunk_retry=cfg.chunk_retry,
                progress_cb=progress_cb,
            )
        except Exception as exc:
            logger.error("software 升级意外异常: %s", exc, exc_info=True)
            await self._report_sw_state(
                tb, SW_STATE_FAILED, error=f"内部异常: {exc}", sw_version=sw_version,
            )
            return

        outcome = result.get("result")
        err = result.get("error")
        logger.info("software 升级结果: %s (err=%s)", outcome, err)

        # 映射 install_software 返回值 → TB sw_state
        outcome_to_state = {
            "UPDATED": SW_STATE_UPDATED,
            "ALREADY_UP_TO_DATE": SW_STATE_ALREADY_UP_TO_DATE,
            "INCOMPATIBLE": SW_STATE_INCOMPATIBLE,
            "ROLLED_BACK": SW_STATE_ROLLED_BACK,
            "FAILED": SW_STATE_FAILED,
        }
        sw_state = outcome_to_state.get(outcome, SW_STATE_FAILED)

        await tb.publish_telemetry({"sw_progress": 100})
        await self._report_sw_state(tb, sw_state, error=err, sw_version=sw_version)

        # 成功 → 把 current_sw_* attribute 同步上去
        if outcome == "UPDATED" and self.state.current_software is not None:
            cs = self.state.current_software
            await tb.publish_client_attributes(
                {"current_sw_title": cs.title, "current_sw_version": cs.version}
            )


# ============== 入口 ==============

def _setup_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # aiomqtt 默认 DEBUG 太吵
    logging.getLogger("aiomqtt").setLevel(logging.WARNING)
    logging.getLogger("paho").setLevel(logging.WARNING)


def _install_signal_handlers(agent: OtaAgent) -> None:
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                loop.add_signal_handler(getattr(signal, sig_name), agent.request_stop)
            except NotImplementedError:
                # Windows 上 add_signal_handler 不支持 SIGTERM，忽略
                pass


async def _async_main() -> int:
    try:
        config = AgentConfig.from_env()
    except KeyError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 2

    _setup_logging(config.log_level)
    agent = OtaAgent(config)
    _install_signal_handlers(agent)

    try:
        await agent.run()
        return 0
    except Exception as exc:
        logger.error("Agent 主流程异常退出: %s", exc, exc_info=True)
        return 1


def main() -> int:
    try:
        return asyncio.run(_async_main())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())

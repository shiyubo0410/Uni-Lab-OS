"""OTA Agent 状态持久化。

把 Agent 的运行状态原子性地落盘到 ``/data/ota/agent_state.json``，
Agent 重启/崩溃后能恢复上次的进度（例如 chunk 下载到一半，下次启动继续）。

文件示例::

    {
      "current_fw": {"title": "uni-lab-gateway", "version": "1.0.0"},
      "ongoing": {
        "rid": 1,
        "title": "uni-lab-gateway",
        "version": "1.0.1",
        "size": 5242880,
        "checksum": "abc123...",
        "checksum_alg": "SHA256",
        "chunk_size": 524288,
        "total_chunks": 10,
        "received_chunks": 4,
        "state": "DOWNLOADING",
        "download_path": "/data/ota/download/uni-lab-gateway-1.0.1.bin",
        "error": null
      }
    }

D2 阶段 ``ongoing.state`` 取值: ``DOWNLOADING / DOWNLOADED / VERIFIED / FAILED``。
D3.A 会扩展 firmware 流到 ``WRITTEN / SWITCHED / PENDING_HEALTHCHECK / COMMIT_OK / ROLLBACK``。

D3.B (本阶段) 引入 software 流：``ongoing_software`` 字段，状态机包含
``DOWNLOADING / DOWNLOADED / VERIFIED / INSTALLED / ACTIVATED /
HEALTH_CHECKING / FAILED / ROLLED_BACK``。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


STATE_IDLE = "IDLE"
STATE_DOWNLOADING = "DOWNLOADING"
STATE_DOWNLOADED = "DOWNLOADED"
STATE_VERIFIED = "VERIFIED"
STATE_FAILED = "FAILED"
STATE_INSTALLED = "INSTALLED"            # software：tar.gz 解压到 versions/<ver>/ 完成
STATE_ACTIVATED = "ACTIVATED"            # software：symlink 已切换 + service 已 restart
STATE_HEALTH_CHECKING = "HEALTH_CHECKING"  # software：5 min watchdog 中
STATE_ROLLED_BACK = "ROLLED_BACK"        # software：health check 失败自动回滚到上个版本

VALID_STATES = {
    STATE_IDLE,
    STATE_DOWNLOADING,
    STATE_DOWNLOADED,
    STATE_VERIFIED,
    STATE_FAILED,
    STATE_INSTALLED,
    STATE_ACTIVATED,
    STATE_HEALTH_CHECKING,
    STATE_ROLLED_BACK,
}


@dataclass
class CurrentFirmware:
    """当前运行的固件信息（启动时上报给 TB）。"""

    title: str
    version: str


@dataclass
class OngoingUpdate:
    """正在进行的升级会话。"""

    rid: int
    title: str
    version: str
    size: int
    checksum: str
    checksum_alg: str
    chunk_size: int
    total_chunks: int
    received_chunks: int = 0
    state: str = STATE_DOWNLOADING
    download_path: str = ""
    error: Optional[str] = None

    def is_terminal(self) -> bool:
        """是否处于"不会再继续"的终态。"""
        return self.state in (STATE_VERIFIED, STATE_FAILED)


@dataclass
class CurrentSoftware:
    """当前已激活的应用层包信息（D3.B+）。"""

    title: str
    version: str
    install_path: str                          # /opt/unilab/versions/<version>
    activated_at: str                          # ISO timestamp
    manifest: Dict[str, Any] = field(default_factory=dict)  # 完整 manifest 备查
    healthy: bool = True                       # 最近一次 health check 结果


@dataclass
class OngoingSoftware:
    """正在进行的应用层升级会话（D3.B+）。"""

    rid: int
    title: str
    version: str
    size: int
    checksum: str
    checksum_alg: str
    chunk_size: int
    total_chunks: int
    received_chunks: int = 0
    state: str = STATE_DOWNLOADING
    download_path: str = ""                    # 下载到的 tar.gz 路径
    install_path: str = ""                     # 解压目标 /opt/unilab/versions/<version>
    manifest: Dict[str, Any] = field(default_factory=dict)
    previous_version: Optional[str] = None     # 失败时回滚定位
    started_at: str = ""                       # ISO timestamp
    error: Optional[str] = None

    def is_terminal(self) -> bool:
        """是否处于"不会再继续"的终态。"""
        return self.state in (STATE_VERIFIED, STATE_FAILED, STATE_ROLLED_BACK)


@dataclass
class OtaState:
    """Agent 状态根对象。"""

    current_fw: CurrentFirmware
    ongoing: Optional[OngoingUpdate] = None
    current_software: Optional[CurrentSoftware] = None
    ongoing_software: Optional[OngoingSoftware] = None
    state_file: Path = field(default=Path("/data/ota/agent_state.json"))

    # ---------------- 持久化 ----------------

    def save(self) -> None:
        """原子性保存到 state_file（先写临时文件再 rename）。"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_fw": asdict(self.current_fw),
            "ongoing": asdict(self.ongoing) if self.ongoing else None,
            "current_software": asdict(self.current_software) if self.current_software else None,
            "ongoing_software": asdict(self.ongoing_software) if self.ongoing_software else None,
        }

        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".agent_state.", suffix=".json", dir=str(self.state_file.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            # rename 原子（同一文件系统）
            os.replace(tmp_path, self.state_file)
            logger.debug("state 已保存: %s", self.state_file)
        except Exception:
            # 失败清理临时文件
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

    @classmethod
    def load(
        cls,
        state_file: Path,
        default_current_fw: CurrentFirmware,
    ) -> "OtaState":
        """从 state_file 加载；不存在/损坏则用 default_current_fw 创建新的。"""
        if not state_file.exists():
            logger.info("state.json 不存在，创建初始状态: %s", state_file)
            inst = cls(current_fw=default_current_fw, state_file=state_file)
            inst.save()
            return inst

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            logger.warning("state.json 解析失败，回退到默认: %s", exc)
            inst = cls(current_fw=default_current_fw, state_file=state_file)
            inst.save()
            return inst

        # 解析 current_fw
        cur_raw = data.get("current_fw") or {}
        if cur_raw.get("title") and cur_raw.get("version"):
            current_fw = CurrentFirmware(title=cur_raw["title"], version=cur_raw["version"])
        else:
            current_fw = default_current_fw

        # 解析 ongoing
        ongoing = None
        og_raw = data.get("ongoing")
        if og_raw:
            try:
                ongoing = OngoingUpdate(
                    rid=int(og_raw["rid"]),
                    title=og_raw["title"],
                    version=og_raw["version"],
                    size=int(og_raw["size"]),
                    checksum=og_raw["checksum"],
                    checksum_alg=og_raw.get("checksum_alg", "SHA256"),
                    chunk_size=int(og_raw["chunk_size"]),
                    total_chunks=int(og_raw["total_chunks"]),
                    received_chunks=int(og_raw.get("received_chunks", 0)),
                    state=og_raw.get("state", STATE_DOWNLOADING),
                    download_path=og_raw.get("download_path", ""),
                    error=og_raw.get("error"),
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("ongoing 字段无效，已丢弃: %s", exc)
                ongoing = None

        # 解析 current_software（D3.B+，向后兼容旧 state.json）
        current_software = None
        cs_raw = data.get("current_software")
        if cs_raw:
            try:
                current_software = CurrentSoftware(
                    title=cs_raw["title"],
                    version=cs_raw["version"],
                    install_path=cs_raw["install_path"],
                    activated_at=cs_raw["activated_at"],
                    manifest=cs_raw.get("manifest", {}) or {},
                    healthy=bool(cs_raw.get("healthy", True)),
                )
            except (KeyError, TypeError) as exc:
                logger.warning("current_software 字段无效，已丢弃: %s", exc)
                current_software = None

        # 解析 ongoing_software（D3.B+）
        ongoing_software = None
        os_raw = data.get("ongoing_software")
        if os_raw:
            try:
                ongoing_software = OngoingSoftware(
                    rid=int(os_raw["rid"]),
                    title=os_raw["title"],
                    version=os_raw["version"],
                    size=int(os_raw["size"]),
                    checksum=os_raw["checksum"],
                    checksum_alg=os_raw.get("checksum_alg", "SHA256"),
                    chunk_size=int(os_raw["chunk_size"]),
                    total_chunks=int(os_raw["total_chunks"]),
                    received_chunks=int(os_raw.get("received_chunks", 0)),
                    state=os_raw.get("state", STATE_DOWNLOADING),
                    download_path=os_raw.get("download_path", ""),
                    install_path=os_raw.get("install_path", ""),
                    manifest=os_raw.get("manifest", {}) or {},
                    previous_version=os_raw.get("previous_version"),
                    started_at=os_raw.get("started_at", ""),
                    error=os_raw.get("error"),
                )
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning("ongoing_software 字段无效，已丢弃: %s", exc)
                ongoing_software = None

        inst = cls(
            current_fw=current_fw,
            ongoing=ongoing,
            current_software=current_software,
            ongoing_software=ongoing_software,
            state_file=state_file,
        )
        logger.info(
            "state 已恢复: fw=%s/%s ongoing=%s sw=%s/%s ongoing_sw=%s",
            current_fw.title,
            current_fw.version,
            ongoing.state if ongoing else "None",
            current_software.title if current_software else "None",
            current_software.version if current_software else "None",
            ongoing_software.state if ongoing_software else "None",
        )
        return inst

    # ---------------- 状态变更便捷方法 ----------------

    def start_update(
        self,
        rid: int,
        title: str,
        version: str,
        size: int,
        checksum: str,
        checksum_alg: str,
        chunk_size: int,
        download_path: Path,
    ) -> OngoingUpdate:
        """开始一个新的升级会话。"""
        total_chunks = (size + chunk_size - 1) // chunk_size
        self.ongoing = OngoingUpdate(
            rid=rid,
            title=title,
            version=version,
            size=size,
            checksum=checksum,
            checksum_alg=checksum_alg,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            received_chunks=0,
            state=STATE_DOWNLOADING,
            download_path=str(download_path),
            error=None,
        )
        self.save()
        return self.ongoing

    def update_progress(self, received_chunks: int) -> None:
        if self.ongoing is None:
            return
        self.ongoing.received_chunks = received_chunks
        self.save()

    def mark_state(self, state: str, error: Optional[str] = None) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"无效状态: {state}")
        if self.ongoing is None:
            return
        self.ongoing.state = state
        if error is not None:
            self.ongoing.error = error
        self.save()

    def clear_ongoing(self) -> None:
        self.ongoing = None
        self.save()

    def update_current_fw(self, title: str, version: str) -> None:
        """更新"当前运行的固件"——D3.A 切分区成功后才会调用。D2 阶段用不上。"""
        self.current_fw = CurrentFirmware(title=title, version=version)
        self.save()

    # ---------------- Software 流（D3.B+） ----------------

    def start_software_update(
        self,
        rid: int,
        title: str,
        version: str,
        size: int,
        checksum: str,
        checksum_alg: str,
        chunk_size: int,
        download_path: Path,
        install_path: Path,
        started_at: str,
    ) -> OngoingSoftware:
        """开始一个新的 software 升级会话。"""
        total_chunks = (size + chunk_size - 1) // chunk_size
        previous_version = self.current_software.version if self.current_software else None
        self.ongoing_software = OngoingSoftware(
            rid=rid,
            title=title,
            version=version,
            size=size,
            checksum=checksum,
            checksum_alg=checksum_alg,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            received_chunks=0,
            state=STATE_DOWNLOADING,
            download_path=str(download_path),
            install_path=str(install_path),
            manifest={},
            previous_version=previous_version,
            started_at=started_at,
            error=None,
        )
        self.save()
        return self.ongoing_software

    def update_software_progress(self, received_chunks: int) -> None:
        if self.ongoing_software is None:
            return
        self.ongoing_software.received_chunks = received_chunks
        self.save()

    def attach_software_manifest(self, manifest: Dict[str, Any]) -> None:
        """下载完成后把 manifest dict 挂到 ongoing_software 上，供后续 install/health check 用。"""
        if self.ongoing_software is None:
            return
        self.ongoing_software.manifest = manifest
        self.save()

    def mark_software_state(self, state: str, error: Optional[str] = None) -> None:
        if state not in VALID_STATES:
            raise ValueError(f"无效状态: {state}")
        if self.ongoing_software is None:
            return
        self.ongoing_software.state = state
        if error is not None:
            self.ongoing_software.error = error
        self.save()

    def clear_ongoing_software(self) -> None:
        self.ongoing_software = None
        self.save()

    def activate_software(
        self,
        title: str,
        version: str,
        install_path: str,
        activated_at: str,
        manifest: Dict[str, Any],
    ) -> None:
        """software 升级成功（symlink 切换 + restart + health check 全部通过）后调用。"""
        self.current_software = CurrentSoftware(
            title=title,
            version=version,
            install_path=install_path,
            activated_at=activated_at,
            manifest=manifest,
            healthy=True,
        )
        self.save()

    def mark_current_software_unhealthy(self, error: Optional[str] = None) -> None:
        """运行中 health check 失败时调用（D3.B+ watchdog 触发）。"""
        if self.current_software is None:
            return
        self.current_software.healthy = False
        self.save()
        if error:
            logger.warning("current_software 标记为 unhealthy: %s", error)

"""自建 OTA 客户端（对接 uni-lab-backend 的设备 OTA，见 ota-design.md §13）。

与旧的 ThingsBoard 方案（``agent.py`` + ``tb_client.py``，MQTT）完全不同：

* **下发通道**：WS ``ota_cmd`` 主动推送（复用网关现有连接）+ HTTP 定时拉取兜底（§13.8）。
  HTTP 拉取**不依赖 WS 连接类型**，只凭 ``product_key`` + ``device_name`` + ``Lab`` 认证，
  故本模块可先只用 HTTP 拉取跑通，不必等"网关能否再开一条 device 连接"的结论。
* **下载**：从 ``download_url``（OSS 预签名 URL）直接 HTTP GET，不再走分块传输。
* **回报**：WS ``ota_status``（沿用现有信封），按 ``task_uuid`` 幂等。
* **应用**：按 ``object_type`` 分派。``edge_agent`` / ``config`` 复用 ``software_handler``
  现成的解压 / 切 symlink / 重启 / 健康检查原语；``device_driver`` / ``firmware`` 暂缓。

网关以"一台特殊 device"身份登记：``product_key`` 固定，``device_name`` 取 hostname 后缀
（如 ``unilab-gateway-33ed`` → ``33ed``）。网关本体版本单独一套（存 versions.json），
与挂在网关下的实验设备版本互不相干。
"""
from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from unilabos.config.config import BasicConfig, HTTPConfig

# 复用 software_handler 里与传输无关的"应用原语"（解压/切链/重启/健康检查）。
# software_handler 已做 aiomqtt 容错导入，缺 aiomqtt 也能安全 import 这些原语。
from .software_handler import (
    SoftwareError,
    _extract_tarball_atomic,
    _health_check,
    _install_incremental,
    _read_inner_manifest,
    _read_symlink,
    _switch_symlink,
    _systemctl_restart,
    _try_systemctl_restart,
    _verify_sha256,
)

logger = logging.getLogger("unilab.ota.selfhosted")


# ============================================================================
#                              常量 / 默认值
# ============================================================================

# 网关产品标识（与后端 device 表 / 产品定义对齐，所有网关同一个 pk）。
DEFAULT_PRODUCT_KEY = "pa7z23hl27x0"

# HTTP 兜底拉取路径（拼在 HTTPConfig.remote_addr 之后，remote_addr 形如 .../api/v1）。
OTA_TASK_PATH = "/edge/ota/task"

# 无任务时的默认轮询间隔（秒）；服务端会用响应里的 next_pull_after 覆盖。
DEFAULT_POLL_INTERVAL = 3600.0
# 拉到任务 / 刚处理完后，下次尽快跟进的兜底间隔（服务端未给 next_pull_after 时用）。
BUSY_POLL_INTERVAL = 30.0

# 升级对象类型（object_type）
OBJ_EDGE_AGENT = "edge_agent"
OBJ_DEVICE_DRIVER = "device_driver"
OBJ_CONFIG = "config"
OBJ_FIRMWARE = "firmware"

# ota_status.status 取值（映射 ota_device_task.status）
ST_UPGRADING = "upgrading"
ST_SUCCESS = "success"
ST_FAILED = "failed"
ST_SKIPPED = "skipped"

# 默认路径
_HOME = Path.home()
DEFAULT_STAGING_DIR = _HOME / ".unilab" / "ota" / "staging"
DEFAULT_VERSION_FILE = _HOME / ".unilab" / "ota" / "versions.json"
DEFAULT_VERSIONS_ROOT = Path("/opt/unilab/versions")
# 自重启待收尾标记：edge_agent/config 升级会重启网关自身，成功回报只能交给
# 重启后的新进程。这里记下"我刚切到哪个版本、对应哪条 task"，新进程据此补 success。
DEFAULT_PENDING_FILE = _HOME / ".unilab" / "ota" / "pending_ota.json"

# 本进程所属的 systemd 服务名。edge_agent/config 的 restart_services 命中它时，
# 说明"重启会杀掉正在执行重启的自己"，必须走 commit-before-restart + 重启后收尾。
DEFAULT_SELF_SERVICE = "unilab-gateway"


SendFn = Callable[[Dict[str, Any]], Awaitable[None]]


class _RestartPending(Exception):
    """内部信号（非错误）：edge_agent/config 已切链并触发自重启。

    此时进程即将被 systemd 终止，成功回报无法在本进程完成，交由重启后的新进程
    读 pending marker 补 ``ota_status=success``。调用方捕获后应静默返回，
    既不报 failed 也不报 success。
    """


# ============================================================================
#                              工具函数
# ============================================================================

def derive_sn(hostname: Optional[str] = None) -> str:
    """从 hostname 推设备 sn：取最后一个 '-' 之后的部分。

    ``unilab-gateway-33ed`` → ``33ed``；无 '-' 时返回整个 hostname。

    .. note::
        4 位后缀量产上千台有撞号风险，后续可换成 WiFi MAC / SoC serial 全串。
        当前按用户约定先用 hostname 后缀。
    """
    host = (hostname or socket.gethostname()).strip()
    if "-" in host:
        return host.rsplit("-", 1)[-1]
    return host


class VersionStore:
    """网关本体的当前版本持久化（单一版本线，与后端 device 一机一版本对齐）。

    edge_agent 和 config 两类升级都推进同一个版本号（网关整体版本）。
    """

    def __init__(self, path: Path = DEFAULT_VERSION_FILE, default: str = "0.0.0") -> None:
        self.path = path
        self._default = default

    def get(self) -> str:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            v = data.get("version")
            return str(v) if v else self._default
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return self._default

    def set(self, version: str) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": version, "updated_at": time.time()}, f)
            tmp.replace(self.path)
        except OSError as exc:
            logger.warning("写 versions.json 失败（忽略）: %s", exc)


# ============================================================================
#                              自建 OTA Agent
# ============================================================================

class SelfHostedOtaAgent:
    """自建 OTA 客户端。

    典型用法（在 run_gateway 内）::

        agent = SelfHostedOtaAgent(send_fn=send_fn, machine_name=machine_name)
        # WS 收到 ota_cmd / ota_cancel 时：
        await agent.handle_ota_cmd(data)
        await agent.handle_ota_cancel(data)
        # 并起一个 HTTP 兜底拉取任务：
        asyncio.create_task(agent.http_poll_loop())
    """

    def __init__(
        self,
        *,
        send_fn: SendFn,
        machine_name: str,
        product_key: str = DEFAULT_PRODUCT_KEY,
        device_name: Optional[str] = None,
        base_url: Optional[str] = None,
        staging_dir: Path = DEFAULT_STAGING_DIR,
        versions_root: Path = DEFAULT_VERSIONS_ROOT,
        version_store: Optional[VersionStore] = None,
        pending_file: Path = DEFAULT_PENDING_FILE,
        self_service: str = DEFAULT_SELF_SERVICE,
    ) -> None:
        self._send_fn = send_fn
        self.machine_name = machine_name
        self.product_key = product_key
        self.device_name = device_name or derive_sn(machine_name)
        self.base_url = (base_url or HTTPConfig.remote_addr).rstrip("/")
        self.staging_dir = staging_dir
        self.versions_root = versions_root
        self._vstore = version_store or VersionStore()
        self._pending_file = pending_file
        self.self_service = self_service

        # 同一时刻只处理一个 OTA 任务（对齐 D8 单任务串行）。
        self._task_lock = asyncio.Lock()
        # 已处理 / 处理中的 task_uuid，用于幂等去重。
        self._seen_tasks: set[str] = set()
        # 已请求取消（仅在进入 apply 前有效）的 task_uuid。
        self._cancelled: set[str] = set()

        self._running = False

    # ------------------------------------------------------------------ #
    #                          对外入口
    # ------------------------------------------------------------------ #

    @property
    def current_version(self) -> str:
        return self._vstore.get()

    async def handle_ota_cmd(self, data: Dict[str, Any]) -> None:
        """处理 WS 下行 ``ota_cmd``（与 HTTP 拉取到的任务结构一致，§13.3）。"""
        await self._run_task(data)

    async def handle_ota_cancel(self, data: Dict[str, Any]) -> None:
        """处理 ``ota_cancel``：仅能取消尚未进入 apply 的任务（§13.5）。"""
        task_uuid = data.get("task_uuid")
        if not task_uuid:
            return
        logger.info("[OTA] 收到取消请求 task=%s", task_uuid)
        self._cancelled.add(str(task_uuid))

    async def http_poll_loop(self) -> None:
        """HTTP 兜底拉取循环（§13.8）。启动即拉一次，之后按 next_pull_after 节奏。

        这条通道不依赖 WS 连接类型，是本期最稳的下发路径。
        """
        self._running = True
        logger.info(
            "[OTA] 自建 OTA 轮询启动: pk=%s sn=%s current_version=%s base_url=%s",
            self.product_key, self.device_name, self.current_version, self.base_url,
        )
        # 若本次是"自重启后"的首次启动，先补上上次升级的 success 回报。
        try:
            await self.finalize_pending()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[OTA] finalize_pending 异常（忽略）: %s", exc)
        # 启动 / 重连后立即拉一次
        while self._running:
            interval = DEFAULT_POLL_INTERVAL
            try:
                task, next_pull = await self._poll_once()
                if next_pull and next_pull > 0:
                    interval = float(next_pull)
                if task:
                    await self._run_task(task)
                    # 处理完一条后尽快再拉，看是否还有更高版本任务待推进
                    interval = min(interval, BUSY_POLL_INTERVAL)
                else:
                    logger.debug("[OTA] 本轮无任务 (task=null)，%.0fs 后再拉", interval)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[OTA] HTTP 拉取异常（下轮重试）: %s", exc)
                interval = min(interval, BUSY_POLL_INTERVAL * 2)
            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------ #
    #                          HTTP 拉取
    # ------------------------------------------------------------------ #

    async def _poll_once(self) -> tuple[Optional[Dict[str, Any]], Optional[float]]:
        """拉一次待执行任务。返回 (task|None, next_pull_after|None)。"""
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(None, self._http_get_task)
        if resp is None:
            return None, None
        # 兼容两种返回：标准信封 {"code":0,"data":{...}} 与裸 {...}。
        # 线上实测用的是带 code/data 的信封（see selftest_poll）。
        if isinstance(resp.get("data"), dict):
            payload = resp["data"]
        else:
            payload = resp
        task = payload.get("task")
        next_pull = payload.get("next_pull_after")
        if task:
            logger.info("[OTA] HTTP 拉到任务 task=%s version=%s object_type=%s",
                        task.get("task_uuid"), task.get("version"), task.get("object_type"))
        return (task if isinstance(task, dict) else None), next_pull

    def _http_get_task(self) -> Optional[Dict[str, Any]]:
        """同步 GET /edge/ota/task（在 executor 里跑）。"""
        from urllib.parse import urlencode

        query = urlencode({
            "product_key": self.product_key,
            "device_name": self.device_name,
            "current_version": self.current_version,
        })
        url = f"{self.base_url}{OTA_TASK_PATH}?{query}"
        req = urllib.request.Request(url, method="GET")
        secret = BasicConfig.auth_secret()
        if secret:
            req.add_header("Authorization", f"Lab {secret}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    logger.debug("[OTA] 拉取返回非 200: %s", resp.status)
                    return None
                body = resp.read().decode("utf-8")
            data = json.loads(body)
            return data if isinstance(data, dict) else None
        except urllib.error.HTTPError as exc:
            logger.debug("[OTA] 拉取 HTTPError %s: %s", exc.code, exc.reason)
            return None
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            logger.debug("[OTA] 拉取失败: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #                          任务主流程
    # ------------------------------------------------------------------ #

    async def _run_task(self, cmd: Dict[str, Any]) -> None:
        """执行一条 OTA 任务：下载 → 校验 → 应用 → 回报。全程 task_uuid 幂等。"""
        task_uuid = cmd.get("task_uuid")
        if not task_uuid:
            logger.warning("[OTA] 任务缺 task_uuid，忽略: %s", cmd)
            return
        task_uuid = str(task_uuid)

        object_type = str(cmd.get("object_type") or "")
        version = str(cmd.get("version") or "")
        download_url = cmd.get("download_url")
        sha256 = str(cmd.get("sha256") or "")
        file_size = cmd.get("file_size")

        if not all([object_type, version, download_url, sha256]):
            logger.warning("[OTA] 任务元数据不完整，忽略: %s", cmd)
            return

        from_version = self.current_version

        # 已是目标版本 → skipped（幂等）
        if version == from_version:
            logger.info("[OTA] 已是目标版本 %s，跳过 task=%s", version, task_uuid)
            await self._report(task_uuid, ST_SKIPPED, 100, from_version, version,
                               error_msg="already up to date")
            return

        # 幂等去重：同一 task_uuid 只执行一次
        if task_uuid in self._seen_tasks:
            logger.info("[OTA] task=%s 已在处理/已处理，跳过", task_uuid)
            return

        async with self._task_lock:
            if task_uuid in self._seen_tasks:
                return
            self._seen_tasks.add(task_uuid)
            try:
                await self._pipeline(
                    task_uuid=task_uuid,
                    object_type=object_type,
                    version=version,
                    download_url=str(download_url),
                    sha256=sha256,
                    file_size=int(file_size) if file_size else None,
                    from_version=from_version,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[OTA] task=%s 执行异常: %s", task_uuid, exc, exc_info=True)
                await self._report(task_uuid, ST_FAILED, 0, from_version, version,
                                   error_msg=f"内部异常: {exc}")
            finally:
                self._cancelled.discard(task_uuid)

    async def _pipeline(
        self,
        *,
        task_uuid: str,
        object_type: str,
        version: str,
        download_url: str,
        sha256: str,
        file_size: Optional[int],
        from_version: str,
    ) -> None:
        # 0) 进入前若已被取消 → skipped
        if task_uuid in self._cancelled:
            await self._report(task_uuid, ST_SKIPPED, 0, from_version, version,
                               error_msg="canceled")
            return

        await self._report(task_uuid, ST_UPGRADING, 0, from_version, version)

        # 1) 下载
        staging = self.staging_dir / task_uuid
        staging.mkdir(parents=True, exist_ok=True)
        tarball = staging / f"pkg-{version}.tar.gz"
        loop = asyncio.get_running_loop()

        async def dl_progress(pct: int) -> None:
            # 下载占总进度的前 70%
            await self._report(task_uuid, ST_UPGRADING, int(pct * 0.7),
                               from_version, version)

        logger.info("[OTA] 开始下载 task=%s url=%s", task_uuid, download_url.split("?", 1)[0])
        try:
            await loop.run_in_executor(
                None, self._download_file, download_url, tarball, file_size
            )
        except Exception as exc:  # noqa: BLE001
            await self._report(task_uuid, ST_FAILED, 0, from_version, version,
                               error_msg=f"下载失败: {exc}")
            return
        await self._report(task_uuid, ST_UPGRADING, 70, from_version, version)

        # 2) 校验 sha256（+ 大小）
        try:
            _verify_sha256(tarball, sha256, file_size if file_size else tarball.stat().st_size)
        except SoftwareError as exc:
            await self._report(task_uuid, ST_FAILED, 70, from_version, version,
                               error_msg=str(exc))
            return
        logger.info("[OTA] task=%s sha256 校验通过", task_uuid)

        # apply 前最后一次取消检查（进入 apply 后不可中断）
        if task_uuid in self._cancelled:
            await self._report(task_uuid, ST_SKIPPED, 70, from_version, version,
                               error_msg="canceled")
            return

        await self._report(task_uuid, ST_UPGRADING, 75, from_version, version)

        # 3) 按 object_type 应用
        #    bump_gateway_version 决定成功后是否推进网关本体版本号（versions.json）。
        #    edge_agent/config = 网关整体版本线；device_driver = 驱动自己的版本线，
        #    不动网关版本（否则 poll 上报的 current_version 会被驱动版本污染）。
        bump_gateway_version = False
        try:
            if object_type in (OBJ_EDGE_AGENT, OBJ_CONFIG):
                await self._apply_software_package(
                    tarball, version, from_version, task_uuid
                )
                bump_gateway_version = True
            elif object_type == OBJ_DEVICE_DRIVER:
                await self._apply_device_driver(tarball, version)
            elif object_type == OBJ_FIRMWARE:
                raise SoftwareError("firmware applier 暂缓（文档 §11 明确后续期）")
            else:
                raise SoftwareError(f"未知 object_type: {object_type}")
        except _RestartPending:
            # 自重启已触发：版本已提交、marker 已写、重启命令已下发（--no-block）。
            # 成功回报交给重启后的新进程 finalize_pending()，这里静默返回。
            logger.info(
                "[OTA] task=%s 已切链并触发自重启，success 回报交给重启后的新进程",
                task_uuid,
            )
            return
        except SoftwareError as exc:
            await self._report(task_uuid, ST_FAILED, 80, from_version, version,
                               error_msg=str(exc))
            return

        # 4) 成功回报（device_driver 不重启、不动网关版本；edge_agent/config 走不到这
        #    ——它们已在 _apply 内提交版本并抛 _RestartPending，由新进程回报）
        if bump_gateway_version:
            self._vstore.set(version)
        await self._report(task_uuid, ST_SUCCESS, 100, from_version, version)
        logger.info("[OTA] task=%s 升级成功 %s → %s", task_uuid, from_version, version)

    # ------------------------------------------------------------------ #
    #                          下载
    # ------------------------------------------------------------------ #

    def _download_file(self, url: str, dest: Path, expected_size: Optional[int]) -> None:
        """同步下载（在 executor 里跑）。当前不做 Range 断点续传（后续期补）。"""
        req = urllib.request.Request(url, method="GET")
        # OSS 预签名 URL 自带鉴权，通常不需要额外 header；带上 Lab 认证也无妨。
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
        if expected_size is not None:
            actual = dest.stat().st_size
            if actual != expected_size:
                raise SoftwareError(f"下载大小不符: 期望 {expected_size}, 实际 {actual}")

    # ------------------------------------------------------------------ #
    #                          应用（edge_agent / config）
    # ------------------------------------------------------------------ #

    async def _apply_software_package(
        self, tarball: Path, version: str, from_version: str, task_uuid: str = ""
    ) -> None:
        """把 tar.gz 应用为一个新版本目录并切 symlink + 重启（复用 software_handler 原语）。

        包由 build_software_package.py 产出，内嵌 manifest.json 决定 full/incremental、
        symlink 路径、重启哪个服务、健康检查参数。

        edge_agent 和 config 走同一套逻辑（都是"装个软件包到 versions 目录再切链重启"），
        object_type 仅作标签。
        """
        manifest = _read_inner_manifest(tarball)
        update_type = (manifest.get("update_type") or "full").lower()
        deploy = manifest.get("deploy", {})
        install_path = Path(deploy.get("install_path") or (self.versions_root / version))
        symlink_path = Path(deploy.get("symlink_path", "/opt/unilab/current"))

        # 安装到新版本目录
        if update_type == "incremental":
            base_version = manifest.get("base_version")
            if not base_version:
                raise SoftwareError("incremental 包缺 base_version")
            if base_version != from_version:
                raise SoftwareError(
                    f"base_version 不匹配: 包要求 {base_version}, 当前 {from_version}"
                )
            _install_incremental(
                tarball_path=tarball,
                install_path=install_path,
                base_dir=self.versions_root / base_version,
                changed_files=list(manifest.get("changed_files") or []),
                removed_files=list(manifest.get("removed_files") or []),
            )
        else:
            _extract_tarball_atomic(tarball, install_path)
        logger.info("[OTA] 已安装到 %s (update_type=%s)", install_path, update_type)

        # 切 symlink
        previous_target = _read_symlink(symlink_path)
        services = list(manifest.get("post_install", {}).get("restart_services", ["unilab-gateway"]))
        try:
            _switch_symlink(symlink_path, install_path)
        except SoftwareError as exc:
            logger.error("[OTA] 切 symlink 失败，本地回滚: %s", exc)
            if previous_target:
                try:
                    _switch_symlink(symlink_path, previous_target)
                except Exception as rb:  # noqa: BLE001
                    logger.error("[OTA] 回滚 symlink 也失败: %s", rb)
            raise

        # 关键分叉：restart_services 是否命中"本进程所属服务"。
        # 命中 → 自重启：重启会 SIGTERM 掉正在执行重启的自己，绝不能同步等待，
        #        否则 rc=-15 被误判失败 + 版本没提交 → 无限重启循环。
        #        改为：先提交版本 + 写 pending marker → --no-block 触发重启
        #        → 抛 _RestartPending，由重启后的新进程 finalize_pending() 补 success。
        self_restart = self.self_service in services
        if self_restart:
            # 先提交版本（乐观提交）：即便回报没发出去，新进程也已是目标版本，
            # _run_task 的 "version == from_version" 幂等分支会挡住重复安装，从根上断掉死循环。
            self._vstore.set(version)
            self._write_pending(task_uuid, from_version, version)
            logger.info(
                "[OTA] 自重启路径：已切链 + 提交版本 %s + 写 pending marker，"
                "即将 --no-block 重启 %s（收尾交给新进程）",
                version, self.self_service,
            )
            # 非自身的其他服务（若有）正常重启
            for svc in services:
                if svc == self.self_service:
                    continue
                try:
                    _systemctl_restart(svc)
                except SoftwareError as exc:
                    logger.warning("[OTA] 附带服务 %s 重启失败（忽略，继续自重启）: %s", svc, exc)
            # 尽量在被杀前把一条进度发出去（能发就发，发不出去无所谓，marker 兜底）
            if task_uuid:
                await self._report(task_uuid, ST_UPGRADING, 95, from_version, version,
                                   error_msg="restarting")
            self._systemctl_restart_noblock(self.self_service)
            raise _RestartPending()

        # 非自重启（当前 edge_agent/config 都会命中自重启，这里是为将来别的服务留的老路径）
        try:
            for svc in services:
                _systemctl_restart(svc)
        except SoftwareError as exc:
            logger.error("[OTA] 激活失败，本地回滚: %s", exc)
            if previous_target:
                try:
                    _switch_symlink(symlink_path, previous_target)
                    for svc in services:
                        _try_systemctl_restart(svc)
                except Exception as rb:  # noqa: BLE001
                    logger.error("[OTA] 回滚也失败: %s", rb)
            raise

        # 健康检查（不过则本地回滚，向上抛错由调用方报 failed）
        hc = manifest.get("health_check", {})
        healthy = await _health_check(hc)
        if not healthy:
            logger.error("[OTA] 健康检查失败，本地回滚到 %s", previous_target)
            if previous_target:
                try:
                    _switch_symlink(symlink_path, previous_target)
                    for svc in services:
                        _try_systemctl_restart(svc)
                except Exception as rb:  # noqa: BLE001
                    logger.error("[OTA] 回滚失败: %s", rb)
            raise SoftwareError("健康检查失败（已本地回滚，请发新版本向前修复）")

    # ------------------------------------------------------------------ #
    #                     应用（device_driver）
    # ------------------------------------------------------------------ #

    async def _apply_device_driver(self, tarball: Path, version: str) -> None:
        """应用一个设备驱动包（复用 driver_fetch）。

        与 edge_agent/config 的本质区别：**不切 symlink、不重启整机、不动网关版本线**。
        只把驱动 tar.gz 解压进 ``unilabos/devices/``（顶层即包目录，如 ``ika/ika.py``），
        装依赖、失效 import 缓存。这样：

        * 已连接的同类设备：下次被扫描发现 / 重连时按新驱动加载；
        * 未连接的设备：驱动就位，插上即用。

        包格式（顶层驱动目录）不同于软件包（manifest.json + files/），故走这条独立路径。

        .. note::
            当前不做"运行中设备的在线热重载"（停 worker→reimport→起 worker），
            那是更重的一步，后续按需补。本期保证驱动文件正确落地 + 可 import。
        """
        # driver_fetch 依赖运行环境里的 unilabos.devices 包路径，延迟导入避免循环依赖。
        from unilabos.gateway.discovery.driver_fetch import install_driver_package

        loop = asyncio.get_running_loop()
        try:
            top_dirs = await loop.run_in_executor(
                None, install_driver_package, tarball
            )
        except Exception as exc:  # noqa: BLE001
            raise SoftwareError(f"device_driver 解压/安装失败: {exc}") from exc
        logger.info(
            "[OTA] device_driver 应用完成 version=%s 安装包目录=%s（不重启整机）",
            version, ", ".join(top_dirs) or "(空)",
        )

    # ------------------------------------------------------------------ #
    #                     自重启：pending marker + 收尾
    # ------------------------------------------------------------------ #

    @staticmethod
    def _systemctl_restart_noblock(service: str) -> None:
        """非阻塞重启：把重启作业排进 systemd 后立即返回，不等它完成。

        自重启场景必须用这个——若同步等待，systemd 会 SIGTERM 掉正在等待的自己，
        重启命令 rc=-15 被误判为失败。``--no-block`` 只入队作业即返回，本进程能干净退出，
        随后由 systemd 停旧起新。
        """
        import subprocess

        try:
            subprocess.run(
                ["systemctl", "restart", "--no-block", service],
                check=False, timeout=10,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[OTA] --no-block 重启 %s 下发异常（忽略）: %s", service, exc)

    def _write_pending(self, task_uuid: str, from_version: str, to_version: str) -> None:
        data = {
            "task_uuid": task_uuid,
            "from_version": from_version,
            "to_version": to_version,
            "ts": time.time(),
        }
        try:
            self._pending_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._pending_file.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            tmp.replace(self._pending_file)
        except OSError as exc:
            logger.warning("[OTA] 写 pending marker 失败（忽略）: %s", exc)

    def _read_pending(self) -> Optional[Dict[str, Any]]:
        try:
            with open(self._pending_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def _clear_pending(self) -> None:
        try:
            self._pending_file.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("[OTA] 清除 pending marker 失败（忽略）: %s", exc)

    async def finalize_pending(self) -> None:
        """重启后收尾：若存在 pending marker，补发上次自重启升级的 ``ota_status``。

        判定依据：本进程现在跑的版本（``current_version``）是否已等于 marker 里的目标版本。
        相等 → 说明新代码起来了 → 回报 ``success``；否则回报 ``failed``。
        无论成败都会清除 marker，并把 task_uuid 记入已处理，避免重复安装。
        """
        pending = self._read_pending()
        if not pending:
            return
        task_uuid = str(pending.get("task_uuid") or "")
        to_version = str(pending.get("to_version") or "")
        from_version = str(pending.get("from_version") or "")
        if task_uuid:
            self._seen_tasks.add(task_uuid)

        cur = self.current_version
        # 等 WS 连上再回报（send_fn 在断网/未连接时会静默丢弃）。
        await asyncio.sleep(3.0)

        if cur == to_version:
            logger.info("[OTA] 重启后确认升级成功 → %s，补回报 success task=%s",
                        to_version, task_uuid)
            if task_uuid:
                await self._report(task_uuid, ST_SUCCESS, 100, from_version, to_version)
        else:
            logger.warning(
                "[OTA] 重启后版本不符 cur=%s expect=%s，补回报 failed task=%s",
                cur, to_version, task_uuid,
            )
            if task_uuid:
                await self._report(task_uuid, ST_FAILED, 100, from_version, to_version,
                                   error_msg=f"重启后版本校验失败 cur={cur} expect={to_version}")
        self._clear_pending()

    # ------------------------------------------------------------------ #
    #                          回报
    # ------------------------------------------------------------------ #

    async def _report(
        self,
        task_uuid: str,
        status: str,
        progress: int,
        from_version: str,
        to_version: str,
        error_msg: str = "",
    ) -> None:
        """发 ``ota_status``（§13.4），走现有 WS send_fn，按 task_uuid 幂等。"""
        msg = {
            "action": "ota_status",
            "data": {
                "task_uuid": task_uuid,
                "status": status,
                "progress": int(progress),
                "from_version": from_version,
                "to_version": to_version,
                "error_msg": error_msg,
                "timestamp": time.time(),
            },
        }
        try:
            await self._send_fn(msg)
        except Exception as exc:  # noqa: BLE001
            # 断网期间发不出去：本期先记日志（§6.6 的断网缓存补发后续补）
            logger.warning("[OTA] 上报 ota_status 失败 task=%s status=%s: %s",
                           task_uuid, status, exc)

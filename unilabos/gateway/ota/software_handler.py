"""应用层 OTA 处理器（D3.B+）。

接收 TB 推送的 software 元数据 + manifest，完成完整的应用层升级流程。

两种 ``update_type``：

* **full**（默认）—— manifest 不带 ``update_type`` 或为 ``"full"``::

      1. 兼容性检查 → 2. 重复检查 → 3. 分块下载 → 4. SHA256
      5. 解压到 versions/<new>/ → 6. 切 symlink → 7. restart
      8. health check → 9a. 成功落 state / 9b. 失败回滚到上一个版本

* **incremental** —— manifest.update_type == ``"incremental"``::

      1. 下载 + 校验 (同 full)
      2. 检查 manifest.base_version == 当前 current_software.version
         (链式增量允许：base 不必是 full 装的，只要等于当前激活版即可)
      3. cp -al base_dir → versions/<new>.tmp/    (hard link, 接近 0 拷贝成本)
      4. 解压 tarball 里 files/* 到 .tmp（先 unlink 再写，避免改到 base 的 inode）
      5. 应用 manifest.removed_files
      6. 原子 rename .tmp → versions/<new>/
      7-9 同 full 路径（切 symlink + restart + health check）
      失败回滚：切回 base_version + restart

所有外部行为都通过 manifest.deploy / manifest.post_install / manifest.health_check 驱动，
handler 本身无副作用（不依赖固定路径、固定服务名、固定端口）。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from .state import (
    STATE_ACTIVATED,
    STATE_DOWNLOADED,
    STATE_DOWNLOADING,
    STATE_FAILED,
    STATE_HEALTH_CHECKING,
    STATE_INSTALLED,
    STATE_ROLLED_BACK,
    STATE_VERIFIED,
    OngoingSoftware,
    OtaState,
)
from .tb_client import TBClient, TBClientError

logger = logging.getLogger(__name__)


class SoftwareError(Exception):
    """software 升级失败的通用异常。"""


# (received_chunks, total_chunks) -> awaitable
ProgressCallback = Callable[[int, int], Awaitable[None]]


# ============================================================================
#                              公开入口
# ============================================================================


async def install_software(
    tb: TBClient,
    state: OtaState,
    rid: int,
    sw_title: str,
    sw_version: str,
    sw_size: int,
    sw_checksum: str,
    sw_checksum_alg: str,
    download_dir: Path,
    versions_root: Path,
    chunk_size: int,
    chunk_retry: int = 3,
    progress_cb: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """执行一次完整的 software 升级。

    Args:
        tb: 已连接的 TBClient。
        state: 全局 OtaState（持久化）。
        rid: 本次会话 request_id。
        sw_*: TB 推送的 software 元数据。
        download_dir: tar.gz 临时存放目录，例如 ``/data/ota/download/``。
        versions_root: 解压根目录，例如 ``/opt/unilab/versions/``。
        chunk_size: 单 chunk 字节数。
        chunk_retry: 单 chunk 重试次数。
        progress_cb: 下载进度回调。

    Returns:
        ``{"result": "UPDATED" | "ALREADY_UP_TO_DATE" | "INCOMPATIBLE" | "ROLLED_BACK" | "FAILED",
           "error": str|None}``
        永远不会抛出 SoftwareError——所有失败都通过返回值告知（方便上层统一上报）。

    流程：
        1. 预先版本检查（state.current_software == sw_version → 跳过）
        2. 下载 chunks
        3. SHA256 校验
        4. 从 tar 读 manifest.json（内嵌在根目录）
        5. 兼容性检查
        6. 解压全部
        7. 切 symlink + restart
        8. health check
        9. 成功 → 写 current_software；失败 → 回滚 symlink + restart
    """
    started_at = _iso_now()

    # 1. 预先版本检查（带 sw_version 来的，不必下载就能判断）
    if state.current_software and state.current_software.version == sw_version:
        logger.info("software %s 已是当前版本，跳过", sw_version)
        return {"result": "ALREADY_UP_TO_DATE", "error": None}

    # ---- 启动新会话（注意 install_path 等读到 manifest 后才能最终确定） ----
    install_path_tentative = versions_root / sw_version
    tarball_path = download_dir / f"{_sanitize(sw_title)}-{_sanitize(sw_version)}.tar.gz"
    state.start_software_update(
        rid=rid,
        title=sw_title,
        version=sw_version,
        size=sw_size,
        checksum=sw_checksum,
        checksum_alg=sw_checksum_alg,
        chunk_size=chunk_size,
        download_path=tarball_path,
        install_path=install_path_tentative,
        started_at=started_at,
    )
    ongoing = state.ongoing_software
    assert ongoing is not None

    logger.info(
        "开始 software 升级: %s/%s (size=%d, chunks=%d) -> %s",
        sw_title,
        sw_version,
        sw_size,
        ongoing.total_chunks,
        install_path_tentative,
    )

    # 2. 下载
    try:
        await _download_software(
            tb=tb,
            state=state,
            ongoing=ongoing,
            tarball_path=tarball_path,
            chunk_retry=chunk_retry,
            progress_cb=progress_cb,
        )
    except SoftwareError as exc:
        _safe_unlink(tarball_path)
        state.mark_software_state(STATE_FAILED, error=f"下载失败: {exc}")
        return {"result": "FAILED", "error": str(exc)}

    # 3. SHA256 校验
    try:
        _verify_sha256(tarball_path, sw_checksum, sw_size)
    except SoftwareError as exc:
        _safe_unlink(tarball_path)
        state.mark_software_state(STATE_FAILED, error=str(exc))
        return {"result": "FAILED", "error": str(exc)}
    state.mark_software_state(STATE_VERIFIED)
    logger.info("software 包 SHA256 校验通过")

    # 4. 读 tar 里的 manifest.json
    try:
        manifest = _read_inner_manifest(tarball_path)
    except SoftwareError as exc:
        _safe_unlink(tarball_path)
        state.mark_software_state(STATE_FAILED, error=str(exc))
        return {"result": "FAILED", "error": str(exc)}
    state.attach_software_manifest(manifest)
    logger.info("读取内嵌 manifest 完成: version=%s, schema=%s",
                manifest.get("version"), manifest.get("schema_version"))

    # 5. 兼容性检查（这一步出错就丢包不解压，下载成本可控 ≤ MB 级）
    compat_err = _check_compat(manifest.get("compat", {}), state)
    if compat_err is not None:
        logger.warning("software 兼容性检查失败: %s", compat_err)
        _safe_unlink(tarball_path)
        state.mark_software_state(STATE_FAILED, error=f"incompatible: {compat_err}")
        return {"result": "INCOMPATIBLE", "error": compat_err}

    # manifest 里可能指定具体 install_path（覆盖 tentative）
    deploy = manifest.get("deploy", {})
    install_path = Path(deploy.get("install_path") or install_path_tentative)
    if install_path != install_path_tentative:
        # 同步 ongoing 信息让 state.json 一致
        ongoing.install_path = str(install_path)

    # 6. 安装：根据 update_type 走不同分支
    update_type = (manifest.get("update_type") or "full").lower()
    if update_type == "incremental":
        base_version = manifest.get("base_version")
        if not base_version:
            err = "incremental 包缺少 base_version"
            state.mark_software_state(STATE_FAILED, error=err)
            return {"result": "FAILED", "error": err}
        # 链式增量允许：只要 current_software.version == base_version 即可
        cur_sw = state.current_software
        cur_v = cur_sw.version if cur_sw else None
        if cur_v != base_version:
            err = f"base_version 不匹配: 包要求 {base_version}, 当前 {cur_v}"
            logger.warning(err)
            _safe_unlink(tarball_path)
            state.mark_software_state(STATE_FAILED, error=err)
            return {"result": "INCOMPATIBLE", "error": err}
        try:
            _install_incremental(
                tarball_path=tarball_path,
                install_path=install_path,
                base_dir=versions_root / base_version,
                changed_files=list(manifest.get("changed_files") or []),
                removed_files=list(manifest.get("removed_files") or []),
            )
        except SoftwareError as exc:
            state.mark_software_state(STATE_FAILED, error=f"增量安装失败: {exc}")
            return {"result": "FAILED", "error": str(exc)}
        logger.info(
            "increment 完成: base=%s → %s (%d changed, %d removed)",
            base_version, install_path,
            len(manifest.get("changed_files") or []),
            len(manifest.get("removed_files") or []),
        )
    else:
        try:
            _extract_tarball_atomic(tarball_path, install_path)
        except SoftwareError as exc:
            state.mark_software_state(STATE_FAILED, error=f"解压失败: {exc}")
            return {"result": "FAILED", "error": str(exc)}
        logger.info("software 已解压到 %s", install_path)

    state.mark_software_state(STATE_INSTALLED)

    # 7. 切换 symlink + restart
    symlink_path = Path(deploy.get("symlink_path", "/opt/unilab/current"))
    previous_target = _read_symlink(symlink_path)
    post_install = manifest.get("post_install", {})
    services_to_restart = list(post_install.get("restart_services", ["unilab-gateway"]))

    try:
        _switch_symlink(symlink_path, install_path)
        for svc in services_to_restart:
            _systemctl_restart(svc)
    except SoftwareError as exc:
        # 切 symlink 或 restart 失败 → 立即回滚
        logger.error("activation 失败，尝试回滚: %s", exc)
        if previous_target:
            try:
                _switch_symlink(symlink_path, previous_target)
                for svc in services_to_restart:
                    _try_systemctl_restart(svc)
            except Exception as rb_exc:
                logger.error("回滚也失败: %s", rb_exc)
        state.mark_software_state(STATE_FAILED, error=f"activation: {exc}")
        return {"result": "FAILED", "error": str(exc)}

    state.mark_software_state(STATE_ACTIVATED)
    logger.info("symlink 已切换 %s -> %s，service 已 restart", symlink_path, install_path)

    # 8. Health check
    state.mark_software_state(STATE_HEALTH_CHECKING)
    hc = manifest.get("health_check", {})
    healthy = await _health_check(hc)
    if healthy:
        # 9a. 成功路径
        state.activate_software(
            title=sw_title,
            version=sw_version,
            install_path=str(install_path),
            activated_at=_iso_now(),
            manifest=manifest,
        )
        state.mark_software_state(STATE_VERIFIED)
        state.clear_ongoing_software()
        _cleanup_old_versions(
            versions_root=versions_root,
            keep=int(manifest.get("rollback", {}).get("keep_versions", 3)),
            current_dir=install_path,
        )
        _safe_unlink(tarball_path)
        logger.info("software 升级成功 ✓ %s", sw_version)
        return {"result": "UPDATED", "error": None}

    # 9b. 失败 → 回滚
    logger.error("health check 失败，开始回滚到 %s", previous_target)
    if previous_target is None:
        # 没有上个版本可回 → 设备首次部署失败，只能上报失败让人工介入
        state.mark_software_state(STATE_FAILED, error="health_check failed, no previous to rollback")
        return {"result": "FAILED", "error": "health check 失败且无回滚目标（首次部署）"}

    try:
        _switch_symlink(symlink_path, previous_target)
        for svc in services_to_restart:
            _try_systemctl_restart(svc)
    except Exception as rb_exc:
        logger.error("回滚失败: %s", rb_exc)
        state.mark_software_state(STATE_FAILED, error=f"rollback failed: {rb_exc}")
        return {"result": "FAILED", "error": f"rollback failed: {rb_exc}"}

    state.mark_software_state(STATE_ROLLED_BACK, error="health check failed")
    state.mark_current_software_unhealthy(error="health check failed during upgrade")
    return {"result": "ROLLED_BACK", "error": "health check 失败，已回滚到 " + str(previous_target)}


# ============================================================================
#                              内部子流程
# ============================================================================


def _check_compat(compat: Dict[str, Any], state: OtaState) -> Optional[str]:
    """简单版本范围校验。失败返回原因字符串，通过返回 None。"""
    min_fw = compat.get("min_firmware")
    if not min_fw:
        return None
    cur_fw = state.current_fw.version
    if _version_lt(cur_fw, min_fw):
        return f"当前 firmware {cur_fw} < 包要求 min_firmware {min_fw}"
    # max_firmware 通常带通配符（如 "2.x"），简化：只检查 major
    max_fw = compat.get("max_firmware")
    if max_fw and not max_fw.endswith(".x"):
        if _version_lt(max_fw, cur_fw):
            return f"当前 firmware {cur_fw} > 包要求 max_firmware {max_fw}"
    return None


async def _download_software(
    tb: TBClient,
    state: OtaState,
    ongoing: OngoingSoftware,
    tarball_path: Path,
    chunk_retry: int,
    progress_cb: Optional[ProgressCallback],
) -> None:
    """分块下载 software 包到 tarball_path。"""
    tarball_path.parent.mkdir(parents=True, exist_ok=True)
    state.mark_software_state(STATE_DOWNLOADING)

    bytes_written = 0
    with open(tarball_path, "wb") as f:
        for cid in range(ongoing.total_chunks):
            chunk = await _request_sw_chunk_with_retry(
                tb=tb,
                rid=ongoing.rid,
                cid=cid,
                chunk_size=ongoing.chunk_size,
                retries=chunk_retry,
            )
            if not chunk:
                raise SoftwareError(f"收到空 chunk: rid={ongoing.rid} cid={cid}")
            f.write(chunk)
            bytes_written += len(chunk)

            state.update_software_progress(received_chunks=cid + 1)
            if progress_cb is not None:
                try:
                    await progress_cb(cid + 1, ongoing.total_chunks)
                except Exception as exc:
                    logger.warning("progress_cb 出错（忽略）: %s", exc)

            if (cid + 1) % 50 == 0 or cid + 1 == ongoing.total_chunks:
                logger.info(
                    "sw 下载进度: %d/%d chunks (%.1f%%)",
                    cid + 1,
                    ongoing.total_chunks,
                    100.0 * (cid + 1) / ongoing.total_chunks,
                )
        f.flush()
        os.fsync(f.fileno())

    state.mark_software_state(STATE_DOWNLOADED)
    logger.info("sw 下载完成: %s (%d bytes)", tarball_path, bytes_written)


async def _request_sw_chunk_with_retry(
    tb: TBClient, rid: int, cid: int, chunk_size: int, retries: int
) -> bytes:
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            return await tb.request_software_chunk(rid=rid, cid=cid, chunk_size=chunk_size)
        except TBClientError as exc:
            last_exc = exc
            logger.warning(
                "sw chunk 失败 rid=%d cid=%d attempt=%d/%d: %s",
                rid, cid, attempt + 1, retries + 1, exc,
            )
            if attempt < retries:
                await asyncio.sleep(min(2 ** attempt, 10))
    raise SoftwareError(
        f"sw chunk rid={rid} cid={cid} 重试 {retries + 1} 次仍失败: {last_exc}"
    )


def _verify_sha256(file_path: Path, expected_hex: str, expected_size: int) -> None:
    actual_size = file_path.stat().st_size
    if actual_size != expected_size:
        raise SoftwareError(
            f"包大小不符: 期望 {expected_size}, 实际 {actual_size}"
        )
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for buf in iter(lambda: f.read(65536), b""):
            sha.update(buf)
    actual = sha.hexdigest()
    if actual != expected_hex.lower():
        raise SoftwareError(
            f"sha256 不匹配: 算出 {actual}, 期望 {expected_hex}"
        )


def _read_inner_manifest(tarball_path: Path) -> Dict[str, Any]:
    """从 tar.gz 根目录的 manifest.json 读元数据（不解压全部）。"""
    try:
        with tarfile.open(tarball_path, "r:gz") as tar:
            member = None
            for m in tar.getmembers():
                if m.name in ("manifest.json", "./manifest.json"):
                    member = m
                    break
            if member is None:
                raise SoftwareError("tar 根目录缺少 manifest.json")
            f = tar.extractfile(member)
            if f is None:
                raise SoftwareError("无法读取 manifest.json entry")
            data = json.loads(f.read().decode("utf-8"))
    except tarfile.TarError as exc:
        raise SoftwareError(f"tar 文件损坏: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SoftwareError(f"manifest.json 解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise SoftwareError("manifest.json 不是 dict")
    return data


def _extract_tarball_atomic(tarball_path: Path, install_path: Path) -> None:
    """先解压到 install_path.parent / (name + '.tmp')，校验通过后 rename 成 install_path。"""
    install_path.parent.mkdir(parents=True, exist_ok=True)
    if install_path.exists():
        # 目标已存在（可能是上次失败留下的）→ 直接清除重来
        logger.warning("install_path 已存在，清除后重建: %s", install_path)
        shutil.rmtree(install_path, ignore_errors=True)

    tmp_path = install_path.parent / (install_path.name + ".tmp")
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=False)

    try:
        with tarfile.open(tarball_path, "r:gz") as tar:
            _safe_extract(tar, tmp_path)
        os.replace(tmp_path, install_path)
    except Exception:
        shutil.rmtree(tmp_path, ignore_errors=True)
        raise


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    """tar 解压防止 path traversal (CVE-2007-4559)。"""
    dest_abs = dest.resolve()
    for member in tar.getmembers():
        target = (dest / member.name).resolve()
        try:
            target.relative_to(dest_abs)
        except ValueError:
            raise SoftwareError(f"危险的 tar entry: {member.name}")
    tar.extractall(dest)


def _install_incremental(
    tarball_path: Path,
    install_path: Path,
    base_dir: Path,
    changed_files: list,
    removed_files: list,
) -> None:
    """增量安装：cp -al base → patch → 原子 rename。

    关键陷阱：hard link 复制后 base/x.py 和 new/x.py 是**同一个 inode**。
    直接对 new/x.py 写入会**改到 base 的内容**，污染 base 版本目录。
    所以解压每个文件前必须先 ``unlink()`` 断开链接。
    """
    if not base_dir.is_dir():
        raise SoftwareError(f"base 版本目录不存在: {base_dir}")

    install_path.parent.mkdir(parents=True, exist_ok=True)
    if install_path.exists():
        logger.warning("install_path 已存在（上次失败遗留？），清除后重建: %s", install_path)
        shutil.rmtree(install_path, ignore_errors=True)

    tmp_path = install_path.parent / (install_path.name + ".tmp")
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)

    try:
        _hardlink_copy_tree(base_dir, tmp_path)
        logger.info("已 hard-link 复制 base: %s → %s", base_dir, tmp_path)

        _extract_files_subdir(tarball_path, tmp_path)
        logger.info("已 patch %d 个变动文件到 %s", len(changed_files), tmp_path)

        for rel in removed_files:
            f = tmp_path / rel
            if f.exists() or f.is_symlink():
                try:
                    if f.is_dir() and not f.is_symlink():
                        shutil.rmtree(f)
                    else:
                        f.unlink()
                    logger.info("已删除: %s", rel)
                except OSError as exc:
                    logger.warning("删除 %s 失败（忽略）: %s", rel, exc)

        os.replace(tmp_path, install_path)
    except Exception:
        shutil.rmtree(tmp_path, ignore_errors=True)
        raise


def _hardlink_copy_tree(src: Path, dst: Path) -> None:
    """hard link 复制目录树：文件用硬链接，目录递归创建。

    优先 ``cp -al``（Linux GNU coreutils，原子且最快）；
    回退到 Python 实现（Windows 测试用，跨设备/不支持 hard link 时再退化为 copy2）。
    """
    if os.name == "posix" and shutil.which("cp"):
        # cp -al src/. dst/ 把 src 内容（不含 src 自己）链接到 dst
        # 注意 dst 不能预先存在，否则 cp 会把 src 整个套到 dst 里
        result = subprocess.run(
            ["cp", "-al", f"{src}/.", str(dst)],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise SoftwareError(
                f"cp -al 失败: rc={result.returncode} stderr={result.stderr.strip()}"
            )
        return

    # 回退（Windows 测试 / 没有 cp 的环境）
    dst.mkdir(parents=True, exist_ok=False)
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        dst_root = dst / rel
        dst_root.mkdir(parents=True, exist_ok=True)
        for f in files:
            src_file = Path(root) / f
            dst_file = dst_root / f
            try:
                os.link(src_file, dst_file)
            except OSError:
                shutil.copy2(src_file, dst_file)


def _extract_files_subdir(tarball_path: Path, dest: Path) -> None:
    """只解压 tar.gz 里 ``files/*`` 前缀的成员到 dest（去掉 files/ 前缀）。

    每个目标文件解压前先 ``unlink()``，避免修改 hard link 共享的 inode。
    """
    dest_abs = dest.resolve()
    with tarfile.open(tarball_path, "r:gz") as tar:
        for m in tar.getmembers():
            if not m.name.startswith("files/"):
                continue
            rel = m.name[len("files/"):]
            if not rel:
                continue

            target = (dest / rel).resolve()
            try:
                target.relative_to(dest_abs)
            except ValueError:
                raise SoftwareError(f"危险的 tar entry: {m.name}")

            target_path = dest / rel
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if m.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            if m.isfile():
                # 关键：先断开 hard link，再写新内容
                if target_path.exists() or target_path.is_symlink():
                    target_path.unlink()
                src = tar.extractfile(m)
                if src is None:
                    continue
                with open(target_path, "wb") as out:
                    shutil.copyfileobj(src, out)
                if m.mode:
                    try:
                        target_path.chmod(m.mode & 0o7777)
                    except OSError:
                        pass
            elif m.issym():
                if target_path.exists() or target_path.is_symlink():
                    target_path.unlink()
                target_path.symlink_to(m.linkname)
            # 其它类型（设备节点等）跳过


def _switch_symlink(symlink: Path, target: Path) -> None:
    """原子切换 symlink：先建 .new 再 rename，保证旧链接随时可用。"""
    symlink.parent.mkdir(parents=True, exist_ok=True)
    new_link = symlink.parent / (symlink.name + ".new")
    if new_link.exists() or new_link.is_symlink():
        new_link.unlink()
    new_link.symlink_to(target)
    os.replace(new_link, symlink)


def _read_symlink(symlink: Path) -> Optional[Path]:
    """读 symlink 当前指向，没有则 None。"""
    try:
        if symlink.is_symlink():
            return Path(os.readlink(symlink))
        return None
    except OSError:
        return None


def _systemctl_restart(service: str) -> None:
    """同步调 systemctl restart，失败抛 SoftwareError。"""
    logger.info("systemctl restart %s", service)
    proc = subprocess.run(
        ["systemctl", "restart", service],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise SoftwareError(
            f"systemctl restart {service} 失败: rc={proc.returncode} stderr={proc.stderr.strip()}"
        )


def _try_systemctl_restart(service: str) -> None:
    """systemctl restart 但不抛异常（回滚路径用）。"""
    try:
        _systemctl_restart(service)
    except Exception as exc:
        logger.error("回滚 systemctl restart %s 也失败: %s", service, exc)


async def _health_check(hc: Dict[str, Any]) -> bool:
    """执行 manifest.health_check 指定的健康检查。

    支持的 method: ``systemctl_and_http`` (默认)。
    其他 method 默认通过（不阻断）。
    """
    method = hc.get("method", "systemctl_and_http")
    if method != "systemctl_and_http":
        logger.warning("未知 health_check method=%s，默认通过", method)
        return True

    service = hc.get("service", "unilab-gateway")
    http_url = hc.get("http_url", "http://localhost:8002/")
    http_timeout = float(hc.get("http_timeout_seconds", 5))
    retry_count = int(hc.get("retry_count", 6))
    retry_interval = float(hc.get("retry_interval_seconds", 30))
    watchdog_min = float(hc.get("watchdog_minutes", 5))
    deadline = time.monotonic() + watchdog_min * 60

    for i in range(retry_count):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.error("health_check watchdog (%.1f min) 超时", watchdog_min)
            return False

        svc_ok = _systemctl_is_active(service)
        http_ok = _http_get_ok(http_url, http_timeout) if svc_ok else False
        logger.info(
            "health_check #%d/%d service=%s http=%s (剩余 %.0fs)",
            i + 1, retry_count, svc_ok, http_ok, remaining,
        )
        if svc_ok and http_ok:
            return True

        await asyncio.sleep(min(retry_interval, remaining))
    return False


def _systemctl_is_active(service: str) -> bool:
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, timeout=10,
        )
        return proc.stdout.strip() == "active"
    except Exception:
        return False


def _http_get_ok(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, OSError):
        return False


def _cleanup_old_versions(
    versions_root: Path, keep: int, current_dir: Path
) -> None:
    """删除老旧版本目录，保留最近 ``keep`` 个 + current_dir。"""
    if not versions_root.exists():
        return
    entries = [p for p in versions_root.iterdir() if p.is_dir() and not p.name.endswith(".tmp")]
    # 按 mtime 倒序
    entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    to_keep = set(entries[:keep])
    to_keep.add(current_dir.resolve())
    for p in entries:
        if p.resolve() in to_keep:
            continue
        try:
            shutil.rmtree(p, ignore_errors=True)
            logger.info("清理旧版本: %s", p)
        except Exception as exc:
            logger.warning("清理 %s 失败: %s", p, exc)


# ============================================================================
#                              工具函数
# ============================================================================


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sanitize(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in s)


def _version_lt(a: str, b: str) -> bool:
    """简易语义化版本比较 a < b。无法解析的部分按字符串比。"""
    def parse(v: str) -> tuple:
        out = []
        for part in v.split("."):
            try:
                out.append((0, int(part)))
            except ValueError:
                out.append((1, part))
        return tuple(out)

    return parse(a) < parse(b)

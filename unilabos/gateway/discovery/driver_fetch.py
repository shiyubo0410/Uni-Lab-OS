"""
驱动自动下载与安装。

设想：以后只维护指纹库即可，驱动按需下载。指纹库给设备配 ``driver_url``
(指向一个 ``.tar.gz`` 包)。当网关要加载某设备驱动、但对应 Python 模块在本地
不存在时，自动从 ``driver_url`` 下载压缩包并解压到 ``unilabos/devices/`` 目录，
使 ``importlib`` 能直接 import 到驱动类，然后设备正常启动。

压缩包约定布局(顶层即包目录)：

    ika/
      ika.py          # 含 @device / @action 的驱动
      ika.json        # 物模型(可选)
      pyproject.toml  # 依赖声明(可选)

解压到 ``<unilabos/devices>/`` 后即得 ``<unilabos/devices>/ika/ika.py``，
对应 import 路径 ``unilabos.devices.ika.ika``。

只依赖标准库(urllib + tarfile)，OPi 网关无需额外安装包。下载是幂等的：
模块一旦解压到本地，下次启动 ``find_spec`` 命中就直接跳过下载。
"""

import importlib
import importlib.util
import logging
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# 下载超时(秒)：OSS 公网包通常几百 KB ~ 几 MB，60s 足够
_DOWNLOAD_TIMEOUT = 60


def _module_available(module_path: str) -> bool:
    """判断点分模块路径是否可被 import（不真正执行 import）。"""
    try:
        return importlib.util.find_spec(module_path) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        # 父包缺失时 find_spec 会抛 ModuleNotFoundError，等价于"不可用"
        return False


def _devices_dir() -> Path:
    """返回 unilabos/devices 目录的绝对路径(解压目标)。"""
    import unilabos.devices as devpkg

    return Path(devpkg.__file__).resolve().parent


def _pkg_dir_for(module_path: str) -> "Path | None":
    """由模块路径推出它在 unilabos/devices 下的顶层包目录(pyproject.toml 所在)。

    例: unilabos.devices.solenoid_valve_esp32.solenoid_valve_esp32
        -> <unilabos/devices>/solenoid_valve_esp32
    """
    prefix = "unilabos.devices."
    if not module_path.startswith(prefix):
        return None
    top = module_path[len(prefix):].split(".")[0]
    if not top:
        return None
    return _devices_dir() / top


def _read_pyproject_version(pyproject: Path) -> "str | None":
    """解析 pyproject.toml 的 [project].version。"""
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return (data.get("project") or {}).get("version")


def _local_driver_version(module_path: str) -> "str | None":
    """读取本地已装驱动包的版本(包目录下 pyproject.toml 的 [project].version)。"""
    pkg_dir = _pkg_dir_for(module_path)
    if pkg_dir is None:
        return None
    pyproject = pkg_dir / "pyproject.toml"
    if not pyproject.exists():
        return None
    return _read_pyproject_version(pyproject)


def _remove_local_pkg(module_path: str) -> None:
    """删除本地驱动包目录, 便于按 driver_url 重新下载新版本。"""
    pkg_dir = _pkg_dir_for(module_path)
    if pkg_dir and pkg_dir.is_dir():
        shutil.rmtree(pkg_dir, ignore_errors=True)
        logger.info(f"[DRV] 已删除旧驱动目录以便更新: {pkg_dir}")


def _download(url: str, dst: Path) -> None:
    """流式下载 url 到本地文件 dst。"""
    req = urllib.request.Request(url, headers={"User-Agent": "unilab-gateway"})
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp:
        with open(dst, "wb") as f:
            shutil.copyfileobj(resp, f)


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> List[str]:
    """安全解压：拒绝绝对路径 / 目录穿越(..)，返回顶层目录名列表。"""
    dest = dest.resolve()
    top_dirs = set()
    for member in tar.getmembers():
        target = (dest / member.name).resolve()
        # 解压目标必须落在 dest 之内，防止 ../../ 之类的目录穿越
        if dest != target and dest not in target.parents:
            raise RuntimeError(f"压缩包包含非法路径(目录穿越): {member.name}")
        top = member.name.replace("\\", "/").split("/")[0]
        if top and top not in (".", ".."):
            top_dirs.add(top)
    tar.extractall(dest)
    return sorted(top_dirs)


def _install_deps(pyproject: Path) -> None:
    """best-effort：解析 pyproject.toml 的 [project].dependencies 并 pip 安装。

    失败只告警、不阻断——很多驱动(如 ika 只用 pyserial)依赖在基础环境里已具备。
    """
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        logger.debug("[DRV] 无 tomllib，跳过依赖解析")
        return

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[DRV] 解析 {pyproject} 失败，跳过依赖安装: {e}")
        return

    deps = (data.get("project") or {}).get("dependencies") or []
    if not deps:
        return

    logger.info(f"[DRV] 安装驱动依赖: {deps}")
    cmd = [sys.executable, "-m", "pip", "install", *deps]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
        logger.info("[DRV] 依赖安装完成")
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[DRV] 依赖安装失败(不阻断，可能已满足): {e}。如导入仍失败请手动 pip install {deps}"
        )


def ensure_driver_available(driver_path: str, driver_url: str = "", driver_version: str = "") -> bool:
    """确保 driver_path(形如 pkg.module.Class)对应的模块可 import。

    若模块已存在:
      - 未配 driver_version → 直接返回 True(旧行为, 命中即用)。
      - 配了 driver_version → 比对本地包版本(pyproject.toml 的 [project].version):
          * 版本一致 → 返回 True;
          * 版本不一致且有 driver_url → 删旧包, 走下载流程装新版;
          * 版本不一致但无 driver_url → 告警, 继续用本地旧版。
    若模块缺失且提供了 driver_url → 下载 tar.gz 解压到 unilabos/devices/ 后重试。

    Returns:
        驱动最终是否可用。
    """
    module_path = driver_path.rpartition(".")[0] or driver_path

    if _module_available(module_path):
        if not driver_version:
            return True
        local_ver = _local_driver_version(module_path)
        if local_ver == driver_version:
            logger.debug(f"[DRV] {module_path} 本地版本 {local_ver} 已是期望版本，跳过下载")
            return True
        logger.info(
            f"[DRV] {module_path} 本地版本={local_ver} != 期望={driver_version}，准备更新驱动"
        )
        if not driver_url:
            logger.warning(
                f"[DRV] {module_path} 版本不一致但未配 driver_url，继续沿用本地旧版 {local_ver}"
            )
            return True
        # 删旧包 + 失效 import 缓存, 落到下面的下载流程重新装新版
        _remove_local_pkg(module_path)
        importlib.invalidate_caches()

    if not driver_url:
        logger.debug(f"[DRV] 模块 {module_path} 缺失且未配 driver_url，无法自动下载")
        return False

    dest = _devices_dir()
    logger.info(f"[DRV] 驱动 {module_path} 需安装/更新，开始从 {driver_url} 下载 -> {dest}")

    try:
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "driver.tar.gz"
            _download(driver_url, archive)
            logger.info(f"[DRV] 下载完成 ({archive.stat().st_size} bytes)，开始解压")
            with tarfile.open(archive, "r:gz") as tar:
                top_dirs = _safe_extract(tar, dest)
            logger.info(f"[DRV] 已解压到 {dest}: {', '.join(top_dirs) or '(空)'}")
            for d in top_dirs:
                pyproject = dest / d / "pyproject.toml"
                if pyproject.exists():
                    _install_deps(pyproject)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[DRV] 下载/解压驱动失败 ({driver_url}): {e}")
        return False

    # 解压出新文件后必须让 import 系统重新扫描目录，否则 find_spec 仍命中旧缓存
    importlib.invalidate_caches()

    ok = _module_available(module_path)
    if ok:
        new_ver = _local_driver_version(module_path)
        logger.info(f"[DRV] ✓ 驱动 {module_path} 安装成功(版本 {new_ver})，可正常加载")
        if driver_version and new_ver != driver_version:
            logger.warning(
                f"[DRV] 注意: 下载后版本={new_ver} 仍与期望={driver_version} 不一致，"
                f"请确认 driver_url 指向的包版本正确"
            )
    else:
        logger.error(
            f"[DRV] 解压后仍无法导入 {module_path}，请检查压缩包布局是否为 "
            f"'<包名>/<模块>.py'(解压到 {dest} 下)"
        )
    return ok

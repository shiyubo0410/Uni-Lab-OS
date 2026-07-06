#!/usr/bin/env python3
"""Uni-Lab Software OTA 包打包脚本（在 dev 机运行）

把当前仓库的"网关运行必需"目录精筛打包成 tar.gz + 生成 manifest.json，
之后到 ThingsBoard UI 的 Software Library 上传这两个文件即可下发到所有 OPi。

两种打包模式：

**全包模式（默认）** —— 整个仓库一次性升级 (~2.7 MB)::

    python build_software_package.py 1.0.3
    python build_software_package.py 1.0.3 --changelog "修复 pH 计驱动温度补偿"

**增量模式** —— 只打改动的文件 (~KB 级，量产时省带宽)::

    # 必须指定 --base 和至少一个文件
    python build_software_package.py 1.0.6 --incremental --base 1.0.5 \\
        unilabos/gateway/ota/agent.py

    # 多个文件
    python build_software_package.py 1.0.6 --incremental --base 1.0.5 \\
        unilabos/gateway/ota/agent.py \\
        unilabos/gateway/ota/software_handler.py

    # 同时删除某些文件
    python build_software_package.py 1.0.6 --incremental --base 1.0.5 \\
        --remove unilabos/devices/deprecated.py \\
        unilabos/gateway/ota/agent.py

输出（两种模式相同）：

    dist/unilabos-app-<version>.tar.gz          # 推送给 OPi 的包
    dist/unilabos-app-<version>.manifest.json   # 元数据

详见 unilabos/gateway/ota/README.md "D3.B 应用层 OTA 打包" 一节。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]


INCLUDE_PATHS: List[str] = [
    "unilabos/__init__.py",
    "unilabos/app",
    "unilabos/compile",
    "unilabos/config",
    "unilabos/device_comms",
    "unilabos/devices",
    "unilabos/gateway",
    "unilabos/messages",
    "unilabos/registry",
    "unilabos/resources",
    "unilabos/utils",
    "unilabos/workflow",
    "setup.py",
    "setup.cfg",
]


EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".vs",
    ".idea",
    ".vscode",
}

EXCLUDE_FILE_SUFFIXES = (
    ".pyc", ".pyo", ".pyd",
    ".exe", ".msi",
    ".rar", ".zip", ".7z", ".tar", ".tgz",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".ipynb",
    ".ide", ".ide-wal", ".ide-shm",
    ".db", ".sqlite", ".sqlite3",
    ".bak", ".tmp", ".log",
)

EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

SHARED_LIB_RE = re.compile(
    r"(?:\.(?:so|dylib)(?:\.\d+)*|\.(?:dll|lib|pdb|exp|obj|o|a))$",
    re.IGNORECASE,
)


DEFAULT_COMPAT = {
    "min_firmware": "1.0.0",
    "max_firmware": "2.x",
}

DEFAULT_DEPLOY = {
    "symlink_path": "/opt/unilab/current",
    "install_path_template": "/opt/unilab/versions/{version}",
    "extract_strip_components": 0,
}

DEFAULT_POST_INSTALL = {
    "restart_services": ["unilab-gateway"],
    "skip_services": ["unilab-ota-agent"],
}

DEFAULT_HEALTH_CHECK = {
    "method": "systemctl_and_http",
    "service": "unilab-gateway",
    # gateway 跑 root（参见 unilab-gateway.service） → 监听 80 端口。
    # 跑普通用户时（测试/开发）会自动降级到 8080，那种情况自己改 manifest。
    "http_url": "http://localhost/",
    "http_timeout_seconds": 5,
    "retry_count": 6,
    "retry_interval_seconds": 30,
    "watchdog_minutes": 5,
}

DEFAULT_ROLLBACK = {
    "policy": "auto_on_health_fail",
    "keep_versions": 3,
}


def _run_git(*args: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def get_git_info() -> dict:
    commit = _run_git("rev-parse", "--short", "HEAD") or "unknown"
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    dirty = bool(_run_git("status", "--porcelain"))
    return {"commit": commit, "branch": branch, "dirty": dirty}


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True
    name = path.name
    if name in EXCLUDE_FILE_NAMES:
        return True
    if name.endswith(EXCLUDE_FILE_SUFFIXES):
        return True
    if SHARED_LIB_RE.search(name):
        return True
    return False


def collect_files() -> List[Path]:
    files: List[Path] = []
    missing: List[str] = []
    for entry in INCLUDE_PATHS:
        target = REPO_ROOT / entry
        if not target.exists():
            missing.append(entry)
            continue
        if target.is_file():
            if not _should_skip(target):
                files.append(target)
            continue
        for p in target.rglob("*"):
            if p.is_file() and not _should_skip(p):
                files.append(p)
    if missing:
        print("[warn] 以下白名单条目不存在，已跳过：", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
    files.sort()
    return files


def collect_incremental_files(specs: List[str]) -> List[Path]:
    """增量模式：用户在命令行指定的文件清单。

    - 不走 INCLUDE_PATHS 全量扫描
    - 路径相对仓库根
    - 支持目录（会递归展开），但不建议——增量包应该精确
    - 仍走 _should_skip 黑名单（防止误打 .pyc、__pycache__ 等）
    """
    files: List[Path] = []
    seen: set = set()
    for spec in specs:
        target = (REPO_ROOT / spec).resolve()
        try:
            target.relative_to(REPO_ROOT)
        except ValueError:
            print(f"[error] {spec!r} 不在仓库根 {REPO_ROOT} 下，已跳过", file=sys.stderr)
            continue
        if not target.exists():
            print(f"[error] 文件不存在: {spec}", file=sys.stderr)
            continue
        if target.is_file():
            if _should_skip(target):
                print(f"[warn] 文件命中黑名单，已跳过: {spec}", file=sys.stderr)
                continue
            if target not in seen:
                files.append(target)
                seen.add(target)
        elif target.is_dir():
            # 目录：递归展开
            for p in target.rglob("*"):
                if p.is_file() and not _should_skip(p) and p not in seen:
                    files.append(p)
                    seen.add(p)
    files.sort()
    return files


def compute_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def build_inner_manifest(
    version: str,
    files_count: int,
    changelog: str,
    git_info: dict,
    update_type: str = "full",
    base_version: Optional[str] = None,
    changed_files: Optional[List[str]] = None,
    removed_files: Optional[List[str]] = None,
) -> dict:
    """嵌进 tar 根目录的 manifest，不含 sha256/size_bytes（无法自指）。

    Args:
        update_type: ``"full"``（默认，整个仓库）或 ``"incremental"``（仅含变动文件）
        base_version: 增量包必填。OPi 当前必须运行这个版本才允许装这个增量
        changed_files: 增量包必填。包内 ``files/`` 子目录的文件清单
        removed_files: 增量包可选。要从 base 中删除的文件
    """
    deploy = dict(DEFAULT_DEPLOY)
    deploy["install_path"] = deploy.pop("install_path_template").format(version=version)

    manifest: dict = {
        "schema_version": "1",
        "version": version,
        "type": "software",
        "update_type": update_type,
        "files_count": files_count,
        "build": {
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "git_commit": git_info["commit"],
            "git_branch": git_info["branch"],
            "git_dirty": git_info["dirty"],
            "builder": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
            "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown",
        },
        "compat": dict(DEFAULT_COMPAT),
        "deploy": deploy,
        "post_install": dict(DEFAULT_POST_INSTALL),
        "health_check": dict(DEFAULT_HEALTH_CHECK),
        "rollback": dict(DEFAULT_ROLLBACK),
        "changelog": changelog,
    }
    if update_type == "incremental":
        manifest["base_version"] = base_version
        manifest["changed_files"] = list(changed_files or [])
        manifest["removed_files"] = list(removed_files or [])
    return manifest


def build_tarball(
    files: List[Path],
    inner_manifest: dict,
    out_path: Path,
    incremental: bool = False,
) -> None:
    """把 files + inner manifest 打成 tar.gz。

    manifest.json 放在 tar 根目录的第一个 entry，方便 OPi 端只读这一条做
    早期兼容性检查（无需先全部解压）。

    布局差异：

    * full 模式 (incremental=False)::

          tar.gz/
          ├── manifest.json
          └── unilabos/...                 ← 文件相对仓库根

    * 增量模式 (incremental=True)::

          tar.gz/
          ├── manifest.json                ← update_type=incremental
          └── files/
              └── unilabos/...             ← 同样路径，但加 files/ 前缀
                                           ← 避免和 full 包混淆，OPi 端按
                                           ← update_type 走不同分支
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    manifest_bytes = json.dumps(inner_manifest, ensure_ascii=False, indent=2).encode("utf-8")
    with tarfile.open(out_path, "w:gz") as tar:
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        info.mode = 0o644
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        import io as _io
        tar.addfile(info, _io.BytesIO(manifest_bytes))

        for f in files:
            rel = f.relative_to(REPO_ROOT).as_posix()
            arcname = f"files/{rel}" if incremental else rel
            tar.add(f, arcname=arcname, recursive=False)


def build_outer_manifest(inner: dict, tarball: Path) -> dict:
    """外部 manifest.json：内嵌 manifest + sha256 + size_bytes + package_file。"""
    outer = dict(inner)
    outer["package_file"] = tarball.name
    outer["sha256"] = compute_sha256(tarball)
    outer["size_bytes"] = tarball.stat().st_size
    return outer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Uni-Lab Software OTA 包打包脚本（dev 机运行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("version", help="版本号，例如 1.0.3")
    p.add_argument(
        "-o", "--output-dir", default="dist",
        help="输出目录（默认 dist/，相对仓库根）",
    )
    p.add_argument(
        "-c", "--changelog", default="",
        help="本次升级说明（也可通过环境变量 CHANGELOG 提供）",
    )
    p.add_argument(
        "--allow-dirty", action="store_true",
        help="允许工作区有未提交修改时打包（默认会警告但不阻塞）",
    )
    # ---- 增量模式参数 ----
    p.add_argument(
        "--incremental", action="store_true",
        help="打增量包：只含指定文件 + base_version 元信息。"
             "OPi 端必须从 --base 版本升过来才能装。",
    )
    p.add_argument(
        "--base", default="",
        help="增量包基线版本号（与 --incremental 配合，必填）",
    )
    p.add_argument(
        "--remove", action="append", default=[],
        help="增量升级时要删除的文件（相对仓库根，可多次指定）。"
             "仅 --incremental 模式有效。",
    )
    p.add_argument(
        "files", nargs="*",
        help="增量模式下指定要打的文件（相对仓库根，必须至少 1 个）。"
             "全包模式忽略此参数。",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    version = args.version.strip()
    if not version:
        print("[error] version 不能为空", file=sys.stderr)
        return 2

    # --- 模式校验 ---
    incremental = args.incremental
    if incremental:
        if not args.base:
            print("[error] --incremental 必须搭配 --base <version>", file=sys.stderr)
            return 2
        if not args.files:
            print("[error] --incremental 必须至少指定一个文件", file=sys.stderr)
            return 2
        if args.base == version:
            print(f"[error] --base 不能和目标版本相同（都是 {version}）", file=sys.stderr)
            return 2
    else:
        if args.files:
            print("[warn] 全包模式忽略位置参数文件清单；如要增量请加 --incremental", file=sys.stderr)
        if args.base:
            print("[warn] 全包模式忽略 --base", file=sys.stderr)
        if args.remove:
            print("[warn] 全包模式忽略 --remove", file=sys.stderr)

    changelog = args.changelog.strip() or os.environ.get("CHANGELOG", "").strip()

    out_dir = REPO_ROOT / args.output_dir
    tarball = out_dir / f"unilabos-app-{version}.tar.gz"
    manifest_path = out_dir / f"unilabos-app-{version}.manifest.json"

    mode_label = f"incremental (base={args.base})" if incremental else "full"
    print("=== Uni-Lab Software 包打包 ===")
    print(f"  仓库根:    {REPO_ROOT}")
    print(f"  版本:      {version}")
    print(f"  模式:      {mode_label}")
    print(f"  输出 tar:  {tarball}")
    print(f"  manifest:  {manifest_path}")
    print()

    git_info = get_git_info()
    print(f"  git commit: {git_info['commit']} ({git_info['branch']})"
          + ("  [DIRTY]" if git_info["dirty"] else ""))
    if git_info["dirty"] and not args.allow_dirty:
        print("  [warn] 工作区有未提交修改，打包仍会进行；--allow-dirty 可静默此警告。",
              file=sys.stderr)

    print("  收集文件 ...")
    if incremental:
        files = collect_incremental_files(args.files)
    else:
        files = collect_files()
    print(f"  收集到 {len(files)} 个文件")

    if incremental and not files:
        print("[error] 增量模式下未收集到任何有效文件，中止打包", file=sys.stderr)
        return 2

    changed_files_rel = [f.relative_to(REPO_ROOT).as_posix() for f in files] if incremental else None

    print("  构造内嵌 manifest ...")
    inner = build_inner_manifest(
        version, len(files), changelog, git_info,
        update_type="incremental" if incremental else "full",
        base_version=args.base if incremental else None,
        changed_files=changed_files_rel,
        removed_files=list(args.remove) if incremental else None,
    )

    if incremental:
        print(f"  [incr] base_version: {args.base}")
        print(f"  [incr] changed_files: {len(changed_files_rel or [])} 个")
        for f in (changed_files_rel or [])[:10]:
            print(f"           - {f}")
        if len(changed_files_rel or []) > 10:
            print(f"           ... 还有 {len(changed_files_rel) - 10} 个")
        if args.remove:
            print(f"  [incr] removed_files: {len(args.remove)} 个")
            for f in args.remove:
                print(f"           - {f}")

    print(f"  打包 {tarball.name}（含内嵌 manifest.json）...")
    build_tarball(files, inner, tarball, incremental=incremental)
    size_kb = tarball.stat().st_size / 1024
    size_label = f"{size_kb / 1024:.2f} MB" if size_kb >= 1024 else f"{size_kb:.1f} KB"
    print(f"  [ok] tar.gz 完成: {size_label}")

    print("  生成外部 manifest ...")
    outer = build_outer_manifest(inner, tarball)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(outer, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"  [ok] manifest.json 完成: sha256={outer['sha256'][:16]}...")

    print()
    print("=== 完成 ===")
    print()
    print("下一步：登录 ThingsBoard UI，进入 Software Library，上传以下文件：")
    print(f"  - {tarball}")
    print(f"  - {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

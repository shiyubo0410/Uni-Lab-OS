"""本地干跑自建 OTA 整条流水线（下载→校验→应用→回报），不连后端。

构造一个假的 ``ota_cmd``，``download_url`` 用本地 ``file://`` 指向 ``--tarball``，
直接喂给 ``SelfHostedOtaAgent.handle_ota_cmd()``，在真机上验证：
下载 → sha256 校验 → 按 object_type 应用（切 symlink + 重启 + 健康检查）→ ota_status 回报。

⚠️ 这会**真的**切 ``/opt/unilab/current`` 并重启 ``unilab-gateway``（config/edge_agent 类）。
用指纹库更新包当载荷是安全的。

在 OPi 上（需 sudo：要写 /opt/unilab/versions、切 symlink、systemctl restart）::

    sudo /opt/unilab/venv/bin/python -m unilabos.gateway.ota.selftest_apply \\
        --tarball /home/orangepi/unilabos-app-0.0.3.tar.gz \\
        --version 0.0.3 --object-type config --from-version 0.0.2

``--from-version`` 会写入版本基线（versions.json），使增量包 ``base_version`` 匹配。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from .selfhosted import SelfHostedOtaAgent, VersionStore


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


async def _run(args: argparse.Namespace) -> int:
    tar = Path(args.tarball).expanduser().resolve()
    if not tar.exists():
        print(f"[!] 包不存在: {tar}", file=sys.stderr)
        return 2

    sha = _sha256(tar)
    size = tar.stat().st_size
    url = tar.as_uri()  # file:///...

    reports: List[Dict[str, Any]] = []

    async def send_fn(msg: Dict[str, Any]) -> None:
        d = msg.get("data", {})
        print(f"  → ota_status: status={d.get('status')} "
              f"progress={d.get('progress')} err={d.get('error_msg')!r}")
        reports.append(d)

    vstore = VersionStore()
    if args.from_version:
        vstore.set(args.from_version)
        print(f"[i] 版本基线设为 {args.from_version} ({vstore.path})")

    agent = SelfHostedOtaAgent(
        send_fn=send_fn,
        machine_name=args.hostname or "selftest",
        version_store=vstore,
    )

    fake_cmd = {
        "task_uuid": f"selftest-{int(time.time())}",
        "release_uuid": "selftest",
        "product_key": agent.product_key,
        "object_type": args.object_type,
        "device_name": agent.device_name,
        "version": args.version,
        "download_url": url,
        "file_size": size,
        "sha256": sha,
    }

    print("=" * 60)
    print("[selftest] 干跑自建 OTA 流水线（本地 file://，不连后端）")
    print(f"  tarball     : {tar}")
    print(f"  sha256      : {sha}")
    print(f"  size        : {size}")
    print(f"  version     : {args.version}   object_type={args.object_type}")
    print(f"  current_ver : {agent.current_version}")
    print("=" * 60)

    await agent.handle_ota_cmd(fake_cmd)

    finals = [r for r in reports if r.get("status") in ("success", "failed", "skipped")]
    print("-" * 60)
    if finals and finals[-1].get("status") == "success":
        print(f"[✓] 流水线成功。当前版本 → {agent.current_version}")
        return 0
    print(f"[×] 未成功，终态: {finals[-1] if finals else '(无终态)'}")
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="本地干跑自建 OTA 流水线")
    p.add_argument("--tarball", required=True, help="本地升级包 tar.gz 路径")
    p.add_argument("--version", required=True, help="包的目标版本，如 0.0.3")
    p.add_argument("--object-type", default="config",
                   choices=["config", "edge_agent"],
                   help="升级对象类型（本地测目前支持 config/edge_agent）")
    p.add_argument("--from-version", default=None,
                   help="设版本基线（增量包 base_version 需与之匹配）")
    p.add_argument("--hostname", default=None, help="覆盖 hostname（推 sn 用）")
    args = p.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())

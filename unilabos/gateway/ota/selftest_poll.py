"""探活自建 OTA 的 HTTP 拉取端点（ota-design.md §13.8）。

不碰应用逻辑，只对 ``GET /edge/ota/task`` 打一次，把 HTTP 状态码 + 原始返回都打出来，
用于快速验证：后端端点是否 ready、Lab 认证是否通过、device 是否需要预登记。

用法（dev 机或 OPi 均可）::

    python -m unilabos.gateway.ota.selftest_poll --ak <AK> --sk <SK> \\
        [--base-url https://leap-lab.test.bohrium.com/api/v1] \\
        [--sn 33ed] [--current-version 0.0.0]

不传 --sn 时用 hostname 后缀（unilab-gateway-33ed → 33ed）。
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from urllib.parse import urlencode

from unilabos.config.config import BasicConfig, HTTPConfig

from .selfhosted import DEFAULT_PRODUCT_KEY, OTA_TASK_PATH, derive_sn


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="探活自建 OTA HTTP 拉取端点")
    p.add_argument("--ak", default=BasicConfig.ak, help="AK（默认读配置）")
    p.add_argument("--sk", default=BasicConfig.sk, help="SK（默认读配置）")
    p.add_argument("--base-url", default=HTTPConfig.remote_addr,
                   help=f"HTTP 基地址（默认 {HTTPConfig.remote_addr}）")
    p.add_argument("--product-key", default=DEFAULT_PRODUCT_KEY)
    p.add_argument("--sn", default=None, help="设备名/sn（默认 hostname 后缀）")
    p.add_argument("--hostname", default=None, help="覆盖 hostname（用于推 sn）")
    p.add_argument("--current-version", default="0.0.0",
                   help="上报的当前版本（默认 0.0.0，尽量拉到有任务）")
    args = p.parse_args(argv)

    if not args.ak or not args.sk:
        print("[!] 缺 ak/sk：--ak/--sk 或先配置 BasicConfig", file=sys.stderr)
        return 2

    sn = args.sn or derive_sn(args.hostname)
    secret_raw = f"{args.ak}:{args.sk}"
    import base64
    secret = base64.b64encode(secret_raw.encode()).decode()

    query = urlencode({
        "product_key": args.product_key,
        "device_name": sn,
        "current_version": args.current_version,
    })
    url = f"{args.base_url.rstrip('/')}{OTA_TASK_PATH}?{query}"

    print("=" * 60)
    print("[探活] 自建 OTA HTTP 拉取端点")
    print(f"  URL          : {url}")
    print(f"  product_key  : {args.product_key}")
    print(f"  device_name  : {sn}")
    print(f"  current_ver  : {args.current_version}")
    print("=" * 60)

    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Lab {secret}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
        print(f"[✓] HTTP {status}")
        _pretty(body)
        _interpret(status, body)
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"[×] HTTP {exc.code} {exc.reason}")
        _pretty(body)
        _interpret(exc.code, body)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"[×] 连接失败: {exc}")
        return 1


def _pretty(body: str) -> None:
    try:
        print("  返回体:")
        print(json.dumps(json.loads(body), ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(f"  返回体(非 JSON): {body[:500]!r}")


def _interpret(status: int, body: str) -> None:
    print("-" * 60)
    if status == 404:
        print("结论：端点不存在 → 后端还没实现 §13.8 拉取接口，需等后端 ready。")
    elif status in (401, 403):
        print("结论：认证/权限失败 → 检查 ak/sk 是否为该 lab 的凭证。")
    elif status == 200:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            print("结论：200 但返回非 JSON，格式对不上，需和后端核对。")
            return
        # 兼容标准信封 {"code":0,"data":{...}} 与裸 {...}
        if isinstance(data.get("data"), dict):
            data = data["data"]
        if data.get("task"):
            print("结论：端点 OK，且已有待执行任务 → 可直接进第二步跑整条流水线。")
        else:
            print("结论：端点 OK（task=null，暂无任务）。说明认证/寻址通了；")
            print("      接下来让后端针对 (product_key, device_name) 建一条 release 再拉即可。")
            print("      若从未登记过该 device，也顺便确认后端是否靠本次 poll 自动登记。")
    else:
        print(f"结论：未预期状态码 {status}，需和后端核对。")


if __name__ == "__main__":
    sys.exit(main())

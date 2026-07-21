"""
STA 在线试连去风险脚本（蓝牙配网方案的地基验证）

背景：现有 AP 配网之所以要整机 reboot，是因为 unisoc sprdwl_ng 驱动从
**AP 模式**切回 STA 不可靠。蓝牙配网全程不进 AP，wlan0 一直是 STA/managed
状态，理论上可以「在线切换 WiFi + 验证公网」而无需 reboot。本脚本就是要在真机
（OPi Zero 2W）上把这个「理论」验证成「事实」——这是决定蓝牙方案是否成立的
关键前提，必须最先跑通。

它做的事：
1. 打印当前网络状态（is_connected）
2. 纯 STA 模式扫描周围 WiFi（强制 ``_in_ap_mode=False``，不碰 create_ap）
3. 可选：反复连接指定 SSID N 次，统计每次是否成功连上并 connectivity=full、
   每次耗时，以此暴露 unisoc 在线切换的偶发不稳定（如果有的话）

用法（在 OPi 上，gateway 的 venv 里）：

    # 只扫描，不连接
    python -m unilabos.gateway.provisioning.check_sta_connect --scan-only

    # 连一次
    python -m unilabos.gateway.provisioning.check_sta_connect --ssid MyWiFi --password 12345678

    # 连 5 次测稳定性（每次之间断开重连，模拟反复配网）
    python -m unilabos.gateway.provisioning.check_sta_connect \
        --ssid MyWiFi --password 12345678 --repeat 5

判据：
- 如果 --repeat N 次里成功率 100%、每次都能 connectivity=full、全程 wlan0 没
  卡死（脚本能正常跑完、后续 nmcli 命令不超时），说明「STA 在线配网不 reboot」
  成立 → 蓝牙方案地基 OK。
- 如果出现连不上 / 卡死 / wlan0 消失，则需要在蓝牙方案里保留 reboot 兜底，
  把结论反馈上来再决定编排。
"""

import argparse
import logging
import sys
import time

from unilabos.gateway.provisioning import WiFiManager


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


def _print_status(mgr: WiFiManager, prefix: str) -> bool:
    connected = mgr.is_connected()
    print(f"{prefix} is_connected={connected}")
    return connected


def _do_scan(mgr: WiFiManager) -> None:
    print("\n===== 扫描 WiFi（纯 STA 模式）=====")
    t0 = time.time()
    wifi_list = mgr.scan_wifi()
    dt = time.time() - t0
    print(f"扫描到 {len(wifi_list)} 个 WiFi，耗时 {dt:.1f}s：")
    for w in wifi_list:
        print(f"  - {w.get('ssid'):<32} signal={w.get('signal'):>3} "
              f"security={w.get('security')}")


def _do_connect_once(mgr: WiFiManager, ssid: str, password: str, idx: int) -> bool:
    """执行一次 STA 在线连接，返回是否成功。"""
    print(f"\n===== 第 {idx} 次连接：{ssid} =====")
    t0 = time.time()
    success, err = mgr.connect_wifi(ssid, password)
    dt = time.time() - t0
    if success:
        # 再确认一次真正 connectivity=full
        ok = mgr.is_connected()
        print(f"[第 {idx} 次] connect_wifi 返回成功，耗时 {dt:.1f}s，"
              f"复核 is_connected={ok}")
        return ok
    else:
        print(f"[第 {idx} 次] ✗ 连接失败，耗时 {dt:.1f}s，原因：{err}")
        return False


def main(argv=None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="STA 在线试连去风险脚本（不进 AP、不 reboot）"
    )
    parser.add_argument("--ssid", help="目标 WiFi SSID（不填则只扫描）")
    parser.add_argument("--password", default="", help="目标 WiFi 密码")
    parser.add_argument("--scan-only", action="store_true", help="只扫描不连接")
    parser.add_argument("--repeat", type=int, default=1,
                        help="连接次数（用于测在线切换稳定性，默认 1）")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="每次连接之间的间隔秒数（默认 3）")
    args = parser.parse_args(argv)

    mgr = WiFiManager()
    # 关键：强制走纯 STA 路径，绝不进 AP（本脚本不调用 start_ap）
    mgr._in_ap_mode = False

    print("========================================")
    print("STA 在线试连去风险验证")
    print(f"AP SSID（仅供识别本机，不会启用）: {mgr.ap_ssid}")
    print("========================================")

    _print_status(mgr, "[初始状态]")
    _do_scan(mgr)

    if args.scan_only or not args.ssid:
        print("\n（未指定 --ssid 或 --scan-only，结束。仅验证了扫描能力）")
        return 0

    results = []
    for i in range(1, args.repeat + 1):
        ok = _do_connect_once(mgr, args.ssid, args.password, i)
        results.append(ok)
        if i < args.repeat:
            print(f"...等待 {args.interval}s 后进行下一次...")
            time.sleep(args.interval)

    success_cnt = sum(1 for r in results if r)
    print("\n========== 汇总 ==========")
    print(f"连接尝试 {len(results)} 次，成功 {success_cnt} 次，"
          f"成功率 {success_cnt / len(results) * 100:.0f}%")
    if success_cnt == len(results):
        print("✓ 结论：纯 STA 在线试连稳定，蓝牙配网可不依赖 reboot。")
        return 0
    else:
        print("✗ 结论：存在失败，需保留 reboot 兜底或进一步排查 unisoc 驱动。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

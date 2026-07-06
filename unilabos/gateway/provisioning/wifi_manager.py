"""
WiFi 管理器 - 负责网络检测、AP 热点管理、WiFi 配置保存

核心功能：
- 检测当前网络连接状态（``is_connected`` / ``wait_for_connection``）
- 启动/停止 AP 热点（基于 OPi 官方推荐的 ``create_ap`` 脚本）
- 扫描可用 WiFi 列表（AP 模式下返回进 AP 前预扫的缓存）
- 保存 WiFi 凭证到 NetworkManager（``connect_wifi``）
- 配网完成后重启系统（``reboot_system``）

OPi Zero 2W (unisoc SC2355B / sprdwl_ng) 两个关键设计决策：

1. **AP 热点用 create_ap 而不是 NetworkManager**：unisoc 驱动在 NM ↔
   wpa_supplicant ↔ driver 这条链路下切 AP 时会触发
   ``NETDEV WATCHDOG: wlan0: transmit queue 0 timed out``，hostapd 几秒后就
   被驱动整崩。``create_ap`` 直接调 hostapd 走 nl80211 → driver 绕过 NM 这层，
   实测稳定。

2. **配网成功后整机 reboot 而不是在线切 STA**：unisoc 从 AP 切回 STA 在程序里
   不可靠，``rmmod/modprobe sprdwl_ng`` 手动 shell OK 但集成进 gateway 后
   ``modprobe`` 会让 wlan0 60s 都不出现，``systemctl restart NetworkManager``
   也救不回。整机 reboot 是唯一 100% 可靠路径——开机后 NM autoconnect 保存的
   WiFi + systemd 拉起 unilab-gateway，30~60 秒就绪。配网是一次性动作，
   重启一次完全可接受。
"""

import logging
import os
import signal
import subprocess
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

# NM keyfile 后端的存储目录。系统是 ifupdown 的话改这里没意义，
# 但 Debian/Ubuntu 默认用 keyfile，香橙派 Bookworm 也用 keyfile。
_NM_KEYFILE_DIR = "/etc/NetworkManager/system-connections"

logger = logging.getLogger("wifi_manager")


class WiFiManager:
    """WiFi 配网管理器"""

    AP_SSID_PREFIX = "UniLab-Gateway"
    # WPA2-PSK，hostapd 路径稳定，开放网络在新版 Android/iOS 上会被警告"无法加入"。
    # 8 位以上是 WPA2 规范要求。
    AP_PASSWORD = "unilab1234"
    AP_INTERFACE = "wlan0"
    AP_CHANNEL = 6  # 信道 6 兼容性最好，2.4G 中段
    AP_GATEWAY_IP = "192.168.12.1"  # create_ap 默认就是 192.168.12.1
    CONNECTION_TIMEOUT = 30  # 连接超时（秒）
    AP_BRINGUP_TIMEOUT = 25  # 等 "AP-ENABLED" 出现的超时（秒）

    def __init__(self, ap_ssid: Optional[str] = None, ap_password: Optional[str] = None):
        """
        :param ap_ssid: 热点 SSID（默认 UniLab-Gateway-<MAC后4位>）
        :param ap_password: 热点密码（默认 ``AP_PASSWORD``，WPA2-PSK）
        """
        self.ap_ssid = ap_ssid or self._generate_ap_ssid()
        self.ap_password = ap_password if ap_password is not None else self.AP_PASSWORD
        self._ap_connection_name = "unilab-provisioning-ap"  # 仅用于清理历史 NM 残留

        # create_ap 子进程相关（start_ap 期间持有）
        self._create_ap_proc: Optional[subprocess.Popen] = None
        self._ap_log: Deque[str] = deque(maxlen=200)
        self._ap_enabled_event = threading.Event()
        self._reader_thread: Optional[threading.Thread] = None

        # AP 模式下 wlan0 不能再扫 STA 列表（unisoc / 入门级单芯片硬件限制：
        # AP 和 station-scan 不能 concurrent）。所以 start_ap 之前先扫一次缓存，
        # 配网页面读这个缓存，避免列表是空的、用户找不到自家 WiFi。
        self._cached_wifi_list: List[Dict[str, str]] = []
        self._in_ap_mode: bool = False

    def _generate_ap_ssid(self) -> str:
        """生成唯一的 AP SSID（基于网卡 MAC 后 4 位 hex，无冒号）。

        例：MAC ``f4:1a:c1:66:51:21`` → ``UniLab-Gateway-5121``。

        优先从 sysfs 读 —— Linux 内核标准接口，格式恒定 ``xx:xx:xx:xx:xx:xx``，
        不依赖 nmcli 输出格式（旧版会用 ``\\:`` 转义、新版不转义）。
        """
        # ① sysfs（首选）
        mac_path = f"/sys/class/net/{self.AP_INTERFACE}/address"
        try:
            with open(mac_path, "r", encoding="ascii") as f:
                mac = f.read().strip()
            mac_suffix = mac.replace(":", "")[-4:].upper()
            if mac_suffix:
                return f"{self.AP_SSID_PREFIX}-{mac_suffix}"
        except Exception as e:
            logger.warning(f"sysfs 读 MAC 失败 ({mac_path}): {e}; 走 nmcli 退路")

        # ② nmcli 退路。坑：'GENERAL.HWADDR:F4:1A:C1:66:51:21' 用 split(':')
        # 拆完会被切成 7 段，[-1] 只是 MAC 最后一段 '21'。必须 partition 在
        # 第一个 ':' 处切一次。
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "GENERAL.HWADDR", "device", "show", self.AP_INTERFACE],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                _, _, mac = result.stdout.strip().partition(":")
                # 处理某些 nmcli 版本用 '\:' 转义 MAC 里的 ':'
                mac_suffix = mac.replace("\\:", "").replace(":", "")[-4:].upper()
                if mac_suffix:
                    return f"{self.AP_SSID_PREFIX}-{mac_suffix}"
        except Exception as e:
            logger.warning(f"nmcli 取 MAC 也失败: {e}")

        return f"{self.AP_SSID_PREFIX}-0000"

    def is_connected(self) -> bool:
        """检查是否已**真正**连接到 WiFi（必须能出公网）。

        踩过的坑：以前只看 STATE 字段含 "connected"，但 NM 在 AP 模式 / 局域网
        路由不通时会返回 "connected (local only)"——表面上 has_ip=True 但根本
        ping 不通公网，DNS 也解析失败。
        正确判断必须看 connectivity 字段（full=真连公网）。
        """
        try:
            # nmcli general state CONNECTIVITY 字段：
            #   full=真互联网 / portal=门户 / limited=只有局域网 / none=没网
            result = subprocess.run(
                ["nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general"],
                capture_output=True, text=True, timeout=10,
            )
            line = result.stdout.strip() if result.returncode == 0 else ""
            parts = line.split(":", 1)
            state = parts[0].strip() if parts else ""
            connectivity = parts[1].strip() if len(parts) > 1 else ""

            ip_result = subprocess.run(
                ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", self.AP_INTERFACE],
                capture_output=True, text=True, timeout=5,
            )
            has_ip = bool(ip_result.stdout.strip())

            # 真正算"连上"：connectivity=full（NM 实测能 GET 检测 URL）
            # 或者 state == "connected" 干净没带 (local only) / (site only)
            is_clean_state = (
                state == "connected"
                and "local" not in state.lower()
                and "site" not in state.lower()
            )
            is_truly_connected = (connectivity == "full") or (is_clean_state and has_ip)

            logger.info(
                f"网络状态: state='{state}', connectivity='{connectivity}', "
                f"has_ip={has_ip}, truly={is_truly_connected}"
            )
            return is_truly_connected

        except Exception as e:
            logger.error(f"检查网络连接失败: {e}")
            return False

    def _get_connection_ssid(self, conn_name: str) -> str:
        """读取一个 NM connection 的 802-11-wireless.ssid 字段"""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "802-11-wireless.ssid",
                 "connection", "show", conn_name],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return ""
            line = result.stdout.strip()
            return line.split(":", 1)[1] if ":" in line else ""
        except Exception:
            return ""

    def _purge_self_ap_connections(self) -> int:
        """删除所有 NAME 或 SSID 等于本网关 AP SSID 的脏连接（除 AP 自己）。

        日志里看到过 NM 残留了一个 name=UniLab-Gateway-XX 的 STA connection，
        会让 has_saved_wifi 误判 + is_connected 进入 local-only 假阳性。
        每次进入配网模式之前调一次清场。
        """
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,NAME", "connection", "show"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return 0
            purged = 0
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                conn_type, conn_name = line.split(":", 1)
                if conn_type != "802-11-wireless":
                    continue
                if conn_name == self._ap_connection_name:
                    continue
                same_ssid = (
                    conn_name == self.ap_ssid
                    or self._get_connection_ssid(conn_name) == self.ap_ssid
                )
                if same_ssid:
                    logger.warning(f"清理与 AP 同 SSID 的脏 connection: {conn_name}")
                    subprocess.run(
                        ["nmcli", "connection", "delete", conn_name],
                        capture_output=True, timeout=10,
                    )
                    purged += 1
            return purged
        except Exception as e:
            logger.warning(f"清理脏 connection 异常: {e}")
            return 0

    def has_saved_wifi(self) -> bool:
        """检查是否有已保存的真实 WiFi 配置（排除 AP 残留 / 同 SSID 脏数据）"""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "TYPE,NAME", "connection", "show"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return False

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                conn_type, conn_name = line.split(":", 1)
                if conn_type != "802-11-wireless":
                    continue
                if conn_name == self._ap_connection_name:
                    continue  # AP connection 自己
                if conn_name == self.ap_ssid:
                    continue  # NAME 跟 AP SSID 同名的脏数据
                if self._get_connection_ssid(conn_name) == self.ap_ssid:
                    continue  # SSID 字段等于 AP SSID 的脏数据
                logger.info(f"发现已保存的 WiFi 配置: {conn_name}")
                return True

            logger.info("未发现已保存的 WiFi 配置")
            return False

        except Exception as e:
            logger.error(f"检查 WiFi 配置失败: {e}")
            return False

    def wait_for_connection(self, timeout: int = CONNECTION_TIMEOUT) -> bool:
        """
        等待网络连接建立

        :param timeout: 超时时间（秒）
        :return: 是否成功连接
        """
        logger.info(f"等待网络连接（超时 {timeout} 秒）...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_connected():
                logger.info("✓ 网络连接成功")
                return True
            time.sleep(2)

        logger.warning(f"✗ 网络连接超时（{timeout} 秒）")
        return False

    # =====================================================================
    # AP 热点：基于 create_ap 实现
    # =====================================================================
    #
    # 历史方案（已废弃）：用 nmcli 的 wifi-share 模式启 AP，但 unisoc_wifi 驱动
    # 在 NM ↔ wpa_supplicant ↔ driver 链路下反复触发 NETDEV WATCHDOG。
    #
    # 现行方案：用 OPi 镜像预装的 create_ap (v0.4.6, /usr/bin/create_ap)。
    # 它本质上是个 bash 脚本，自己拉起 hostapd + dnsmasq，绕过 NM 中间层。
    # 验证结论：从 STA 直接切 AP 0 崩溃，hostapd 输出 "AP-ENABLED" 即认为成功。
    #
    # 关键依赖：orangepi 用户必须能免密 sudo 跑 create_ap / pkill / nmcli。
    # 部署时需要在 /etc/sudoers.d/unilab-gateway 加一条规则，详见
    # ``scripts/install_sudoers.sh`` 或 README 部署文档。

    @staticmethod
    def _sudo_run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
        """``sudo -n`` 包裹 + ``subprocess.run``。

        ``-n`` 表示 non-interactive：sudoers 没免密就直接失败而不会卡住等密码。
        其它 kwargs 透传给 ``subprocess.run``。
        """
        return subprocess.run(["sudo", "-n", *cmd], **kwargs)

    def _read_create_ap_stdout(self, proc: subprocess.Popen) -> None:
        """后台线程：实时读 create_ap 子进程 stdout，把每行存进环形缓冲区。

        监听到 ``AP-ENABLED`` 就 set ``_ap_enabled_event``，让 ``start_ap``
        知道 AP 真的起来了；监听到 ``AP-DISABLED`` 时 clear 事件。

        必须用线程而不是 asyncio：调用者多半在主 asyncio 事件循环里，
        不能阻塞 readline。
        """
        try:
            for raw_line in proc.stdout:  # type: ignore[union-attr]
                line = raw_line.rstrip()
                self._ap_log.append(line)
                # 这条日志比较吵（每个 STA 的 EAPOL 全过程），调到 debug
                logger.debug(f"[create_ap] {line}")
                if "AP-ENABLED" in line:
                    self._ap_enabled_event.set()
                    logger.info(f"[AP] hostapd 报告 AP-ENABLED: {line}")
                elif "AP-DISABLED" in line:
                    self._ap_enabled_event.clear()
                elif "AP-STA-CONNECTED" in line:
                    logger.info(f"[AP] 客户端接入: {line}")
                elif "AP-STA-DISCONNECTED" in line:
                    logger.info(f"[AP] 客户端断开: {line}")
        except Exception as e:
            logger.debug(f"[AP] stdout 读取线程退出: {e}")

    def _release_wlan0_to_hostapd(self) -> None:
        """把 wlan0 从 NetworkManager 手里拿出来，交给 hostapd。

        必须 ``nmcli dev set wlan0 managed no``，否则 NM 会跟 hostapd 抢 wlan0：
        hostapd 起 AP 之后 NM 看到 wlan0 状态变化会尝试 reconnect 之前的 STA，
        反复 deauth 直到 driver 崩。
        """
        # 先把当前激活的 STA 连接 down 掉（如果有），避免 NM 自动重连。
        # 不删除 connection，stop_ap 之后 nmcli connection up 还能恢复。
        try:
            self._sudo_run(
                ["nmcli", "device", "disconnect", self.AP_INTERFACE],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass
        time.sleep(1)
        self._sudo_run(
            ["nmcli", "device", "set", self.AP_INTERFACE, "managed", "no"],
            capture_output=True, timeout=10,
        )
        time.sleep(2)

    def _reclaim_wlan0_to_nm(self) -> None:
        """把 wlan0 还给 NetworkManager。stop_ap 调用。"""
        self._sudo_run(
            ["nmcli", "device", "set", self.AP_INTERFACE, "managed", "yes"],
            capture_output=True, timeout=10,
        )
        time.sleep(2)

    def reboot_system(self) -> None:
        """异步触发系统重启（``sudo -n reboot``）。

        为什么配网完成后要 reboot 而不是在线切回 STA：

        unisoc SC2355B 的 ``sprdwl_ng`` 驱动从 AP 模式切回 STA 在 OPi Zero 2W 上
        **极度不稳定**，实测：

        1. 直接 ``stop_ap`` → ``nmcli connection up <ssid>``：driver scan 不到 AP，
           connection up 报 "The Wi-Fi network could not be found"。
        2. 加 ``rmmod sprdwl_ng + modprobe sprdwl_ng``：手动 shell 里跑 OK
           （25s 内 wlan0 + NM autoconnect 都恢复），但**集成在 gateway 进程里**
           做完全相同的事，``modprobe`` 后 ``/sys/class/net/wlan0`` 60s 都不出现，
           driver probe 静默失败。原因猜测是 stop_ap 之后 driver 状态机在 AP/STA
           交叉态，rmmod 时清理不干净，modprobe 加载新实例就 probe 失败。
        3. 加 ``systemctl restart NetworkManager``：解不了根本问题。

        **唯一 100% 可靠的路径就是 reboot。** 开机后 NM autoconnect 保存的 WiFi
        + systemd 拉起 unilab-gateway，整个过程 30~60 秒，用户体验完全 OK——
        而且配网本来就是一次性动作，重启一次完全可接受。

        ``sudo -n reboot`` 走 sudoers 免密；用 ``Popen`` 不等待，因为 reboot
        会马上 SIGTERM 我们自己。
        """
        logger.warning(
            "[REBOOT] 配网完成，调用 reboot 让系统重启 → 开机后 NM autoconnect 新 WiFi"
        )
        try:
            subprocess.Popen(
                ["sudo", "-n", "reboot"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error(f"[REBOOT] sudo -n reboot 调用失败: {e}")

    def start_ap(self) -> bool:
        """启动 AP 热点（基于 create_ap）。

        正常配网流程下，每次进 AP 模式前 wlan0 都是 cold boot 状态：要么是开机
        第一次（has_saved_wifi 为 False 直接进配网），要么是上次配网完已经 reboot 了
        （配网成功后 ``_run_provisioning_mode`` 会调 ``reboot_system``）。所以这里
        不需要任何 driver reset / NM restart 兜底。
        """
        return self._start_ap_once()

    def _start_ap_once(self) -> bool:
        """单次启动 AP 热点的实际逻辑（被 ``start_ap`` 包了一层重试）。"""
        try:
            logger.info(
                f"[AP] 启动 create_ap: SSID={self.ap_ssid} 密码={self.ap_password} "
                f"信道={self.AP_CHANNEL} 网段={self.AP_GATEWAY_IP}/24"
            )

            # 0) 关键：进 AP 模式之前先扫一次 WiFi 列表缓存起来！
            #    unisoc 单芯片在 AP 模式下不能 station-scan，配网页扫不到列表，
            #    用户就找不到自家 WiFi。所以提前在 STA 模式下扫一次缓存。
            #    （只在第一次扫一下，重试时如果上次有缓存就保留）
            if not self._cached_wifi_list:
                logger.info("[AP] 进 AP 模式前预扫一次 WiFi 列表，用于配网页展示")
                try:
                    self._cached_wifi_list = self.scan_wifi()
                    logger.info(
                        f"[AP] 预扫到 {len(self._cached_wifi_list)} 个 WiFi，"
                        f"AP 模式下 /api/scan 将返回这个缓存"
                    )
                except Exception as e:
                    logger.warning(f"[AP] 预扫 WiFi 失败（继续，配网页将依赖手动输入）: {e}")
                    self._cached_wifi_list = []

            # 1) 兜底：如果上次异常退出留了残骸，先清干净（这次 reset_radio=False，
            #    因为外层 start_ap 自己会负责失败重试时的 reset）
            self.stop_ap()

            # 2) 清掉历史 NM AP connection 残留（兼容旧版本的 keyfile）
            self._purge_self_ap_connections()
            self._purge_ap_keyfile_from_disk()

            # 3) 把 wlan0 从 NM 手里拿走，交给 hostapd
            self._release_wlan0_to_hostapd()

            # 4) 启动 create_ap 子进程
            #    -n          关闭 internet 共享（我们只需要本地 AP，不做 NAT）
            #    --no-virt   用物理 wlan0 而不创建虚拟网卡（OPi 推荐用法）
            #    -c 6        信道 6（兼容性最好）
            #    -w 2        WPA2-PSK
            #    --country CN 设置 regulatory domain
            cmd = [
                "sudo", "-n", "create_ap",
                "-n",
                "--no-virt",
                "-c", str(self.AP_CHANNEL),
                "-w", "2",
                "--country", "CN",
                "--no-haveged",  # 防止依赖 haveged（部分镜像可能没装）
                self.AP_INTERFACE,
                self.ap_ssid,
                self.ap_password,
            ]
            self._ap_log.clear()
            self._ap_enabled_event.clear()
            self._create_ap_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # line-buffered
            )
            self._reader_thread = threading.Thread(
                target=self._read_create_ap_stdout,
                args=(self._create_ap_proc,),
                daemon=True,
                name="create_ap-stdout",
            )
            self._reader_thread.start()

            # 5) 等 hostapd 输出 "AP-ENABLED"
            ok = self._ap_enabled_event.wait(timeout=self.AP_BRINGUP_TIMEOUT)
            if not ok:
                # 可能 create_ap 早早 die 了，把最后日志打出来好排查
                logger.error(
                    f"[AP] {self.AP_BRINGUP_TIMEOUT}s 内未看到 AP-ENABLED，"
                    f"create_ap 最近输出: {list(self._ap_log)[-15:]}"
                )
                self.stop_ap()
                return False

            # 6) 进程是否还活着
            if self._create_ap_proc.poll() is not None:
                logger.error(
                    f"[AP] create_ap 启动后立刻退出 (rc={self._create_ap_proc.returncode}), "
                    f"日志: {list(self._ap_log)[-20:]}"
                )
                self.stop_ap()
                return False

            # 7) iw 二次确认 wlan0 进入了 AP 模式
            try:
                info = subprocess.run(
                    ["iw", "dev", self.AP_INTERFACE, "info"],
                    capture_output=True, text=True, timeout=5,
                )
                if info.returncode == 0:
                    for line in info.stdout.split("\n"):
                        line = line.strip()
                        if line.startswith("type "):
                            iface_type = line[5:].strip()
                            if iface_type != "AP":
                                logger.error(
                                    f"[AP] hostapd 报告 AP-ENABLED 但 iw 看到 type={iface_type}"
                                )
                                self.stop_ap()
                                return False
                            logger.info("[AP] iw 验证 wlan0 type=AP 通过")
                            break
            except FileNotFoundError:
                logger.debug("[AP] iw 命令不存在，跳过类型校验")

            self._in_ap_mode = True
            logger.info(f"✓ AP 热点已启动: {self.ap_ssid} ({self.AP_GATEWAY_IP})")
            return True

        except Exception as e:
            logger.error(f"[AP] 启动 AP 热点异常: {e}", exc_info=True)
            try:
                self.stop_ap()
            except Exception:
                pass
            return False

    def stop_ap(self) -> bool:
        """停止 create_ap 子进程并归还 wlan0。

        分三步：
        1. 给 create_ap 主进程 SIGINT，让它走自己的 cleanup（关 hostapd / dnsmasq /
           恢复 ip_forward / 清 iptables）；正常 ~3 秒能退干净。
        2. 兜底 ``pkill -9 hostapd / dnsmasq``，防 create_ap 已经异常死掉而残留。
        3. ``nmcli dev set wlan0 managed yes`` 把 wlan0 还给 NM。

        注意：unisoc sprdwl_ng 驱动从 AP 切回 STA 在程序内**不可靠**——rmmod/modprobe
        手动 shell OK，集成到 gateway 进程里 ``modprobe`` 会 probe 失败、wlan0 60s
        都不出现。所以配网流程里 ``stop_ap`` 之后**不再尝试在线切 STA**，由
        ``_run_provisioning_mode`` 直接调用 ``reboot_system`` 让系统重启——cold boot
        驱动干净，开机后 NM autoconnect 一气呵成。
        """
        proc = self._create_ap_proc
        try:
            if proc and proc.poll() is None:
                logger.info(f"[AP] 终止 create_ap (pid={proc.pid})")
                # SIGINT 触发 create_ap 自己的 cleanup
                try:
                    proc.send_signal(signal.SIGINT)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("[AP] create_ap SIGINT 后 10s 未退出，SIGTERM")
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        logger.warning("[AP] SIGTERM 也不退，SIGKILL")
                        proc.kill()
        finally:
            self._create_ap_proc = None
            self._ap_enabled_event.clear()

        # 兜底：清理孤儿进程
        for prog in ("hostapd", "dnsmasq"):
            try:
                self._sudo_run(
                    ["pkill", "-f", f"create_ap.{self.AP_INTERFACE}.conf.*{prog}"],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

        # 也要清掉历史 NM AP connection（兼容回滚场景）
        try:
            subprocess.run(
                ["nmcli", "connection", "delete", self._ap_connection_name],
                capture_output=True, timeout=5,
            )
        except Exception:
            pass

        # 把 wlan0 还给 NM
        self._reclaim_wlan0_to_nm()
        self._in_ap_mode = False

        logger.info("✓ AP 热点已停止，wlan0 已还给 NetworkManager")
        return True

    def _purge_ap_keyfile_from_disk(self) -> None:
        """清掉磁盘上残留的 ``unilab-provisioning-ap.nmconnection`` keyfile。

        历史包袱：旧版本用 nmcli 路径启 AP 时会写一个 NM keyfile，异常退出
        会留下 0 字节坏文件。新版本（create_ap 路径）不会再产生，但已经升级
        过来的设备磁盘上可能有旧残留，第一次 start_ap 时清掉。
        """
        try:
            removed: list[str] = []
            for fname in os.listdir(_NM_KEYFILE_DIR):
                if fname == f"{self._ap_connection_name}.nmconnection":
                    fpath = os.path.join(_NM_KEYFILE_DIR, fname)
                    try:
                        os.remove(fpath)
                        removed.append(fname)
                    except OSError as oe:
                        logger.warning(f"[AP] 无法删除 {fpath}: {oe}")
            if removed:
                logger.info(f"[AP] 清理历史 NM keyfile: {removed}")
                self._sudo_run(
                    ["nmcli", "connection", "reload"],
                    capture_output=True, timeout=5,
                )
        except FileNotFoundError:
            pass
        except PermissionError:
            # 不是 root 也不是 sudoers 免密的话进不去，无所谓——新代码也不写文件
            logger.debug(f"[AP] 没有权限读 {_NM_KEYFILE_DIR}（不影响 create_ap 路径）")
        except Exception as e:
            logger.warning(f"[AP] 清理 keyfile 异常（继续）: {e}")

    def scan_wifi(self) -> List[Dict[str, str]]:
        """
        扫描可用的 WiFi 列表

        重要：在 AP 模式下，wlan0 不能再做 station-scan（unisoc 单芯片硬件限制），
        nmcli rescan 会立即返回但 list 是空的。所以这里如果检测到自己处于 AP 模式，
        就直接返回 ``_cached_wifi_list``——这是 ``start_ap`` 之前预扫到的结果。

        :return: WiFi 列表，每项包含 ssid, signal, security
        """
        if self._in_ap_mode:
            logger.info(
                f"[SCAN] 当前处于 AP 模式，wlan0 无法 station-scan，"
                f"返回 AP 启动前缓存的 {len(self._cached_wifi_list)} 个 WiFi"
            )
            return list(self._cached_wifi_list)

        try:
            # 先触发扫描
            subprocess.run(
                ["nmcli", "device", "wifi", "rescan"],
                capture_output=True,
                timeout=10,
            )
            time.sleep(2)  # 等待扫描完成

            # 获取 WiFi 列表
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error(f"扫描 WiFi 失败: {result.stderr}")
                return []

            wifi_list = []
            seen_ssids = set()

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue

                ssid, signal, security = parts
                ssid = ssid.strip()

                # 跳过空 SSID、重复项、以及自己的 AP
                if not ssid or ssid in seen_ssids or ssid == self.ap_ssid:
                    continue

                seen_ssids.add(ssid)
                wifi_list.append({
                    "ssid": ssid,
                    "signal": int(signal) if signal.isdigit() else 0,
                    "security": security or "Open",
                })

            # 按信号强度排序
            wifi_list.sort(key=lambda x: x["signal"], reverse=True)
            logger.info(f"扫描到 {len(wifi_list)} 个 WiFi")
            return wifi_list

        except Exception as e:
            logger.error(f"扫描 WiFi 异常: {e}")
            return []

    def connect_wifi(self, ssid: str, password: str) -> tuple[bool, str]:
        """
        连接到指定 WiFi 并保存配置。

        AP 模式下的特殊路径（关键）：
        - 当前如果处于 AP 模式（``_in_ap_mode == True``），wlan0 不能 station-scan，
          直接 ``nmcli dev wifi connect <ssid>`` 会报 "No network with SSID found"
          （因为 nmcli 依赖 scan list 才能 join）。所以必须先：
            1) 用 ``nmcli connection add`` 创建 profile（不依赖 scan）
            2) ``stop_ap()`` 把 wlan0 还给 NM
            3) 等 NM 接管 + rescan
            4) ``nmcli connection up`` 激活（wpa_supplicant 自己会 scan+join，
               不依赖 nmcli 的 scan list）

        非 AP 模式（一般是已经在 STA 模式下手动调用）走原始路径。

        失败语义（很重要）：
        - nmcli 失败时会留一个 broken connection 占用 wlan0，必须 delete。
        - 密码错时 nmcli 报 "Secrets were required..."，要透传给前端让用户重输。

        :return: (success, error_message)
            success=True 时 error_message="" ，否则是给前端展示的中文错误
        """
        try:
            logger.info(f"尝试连接 WiFi: {ssid} (当前 in_ap_mode={self._in_ap_mode})")

            if not password:
                logger.warning("connect_wifi 收到空密码")
                self._cleanup_failed_connection(ssid)
                return False, "密码不能为空"

            # 先删除同名的旧连接（避免复用 cached 错密码 / 旧 profile）
            subprocess.run(
                ["nmcli", "connection", "delete", ssid],
                capture_output=True, timeout=10,
            )

            if self._in_ap_mode:
                return self._connect_wifi_from_ap_mode(ssid, password)
            else:
                return self._connect_wifi_in_sta_mode(ssid, password)

        except subprocess.TimeoutExpired:
            logger.error(f"连接 WiFi 超时: {ssid}")
            self._cleanup_failed_connection(ssid)
            return False, "连接超时（45 秒），可能是 AP 不在附近或信号太弱"
        except Exception as e:
            logger.error(f"连接 WiFi 异常: {e}", exc_info=True)
            self._cleanup_failed_connection(ssid)
            return False, f"内部错误：{e}"

    def _connect_wifi_in_sta_mode(self, ssid: str, password: str) -> tuple[bool, str]:
        """非 AP 模式下的连接（原始流程，依赖 nmcli scan list）。"""
        cmd = [
            "nmcli", "device", "wifi", "connect", ssid,
            "password", password,
            "ifname", self.AP_INTERFACE,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            logger.error(f"连接 WiFi 失败: {stderr}")
            self._cleanup_failed_connection(ssid)
            return False, self._translate_nmcli_error(stderr)

        time.sleep(3)

        if self.is_connected():
            logger.info(f"✓ 成功连接到 {ssid}")
            return True, ""
        else:
            logger.warning(f"✗ 连接到 {ssid} 后无网络（local only 或无 DNS）")
            self._cleanup_failed_connection(ssid)
            return False, f"已连接 {ssid} 但无法访问公网，请检查路由器是否能上网"

    def _connect_wifi_from_ap_mode(self, ssid: str, password: str) -> tuple[bool, str]:
        """
        AP 模式下处理配网请求 —— 只 add profile，**不真正切换 STA**。

        为什么这样设计：
        - AP 模式下手机连在 AP 上才能看到这个 web 页面。如果在 connect_wifi 里直接
          ``stop_ap`` 切回 STA，手机会立刻从 AP 上掉下来，HTTP 200 响应根本送不回，
          前端 fetch 卡死，用户看到 loading 一直转。
        - 所以这里只做"快速、同步、不影响 AP"的事：
            1) 删除可能存在的同名旧 profile
            2) ``nmcli connection add`` 创建新 profile（不激活，不需要 scan）
        - 创建成功立即返回 → web 能正常发回 200 → 前端显示"已收到"。
        - 然后回调 ``on_success(ssid)`` 触发 ``main.py`` 走原有路径：
          ``stop_ap`` → ``ensure_sta_active(ssid)``（这里才真正激活 connection）
        - 如果密码错，``ensure_sta_active`` 会失败 → ``run_gateway`` ``sys.exit(1)``
          → systemd 拉起 → 重新进配网模式 → AP 重新出现，用户能重试。

        注意：这里只能 catch 密码"格式不合法"（比如 PSK 长度错），catch 不到
        "密码错"。"密码错"的反馈靠 systemd 重启后 AP 重新出现来体现。
        """
        logger.info(f"[配网] AP 模式下创建 connection profile: {ssid}（暂不激活）")
        cmd_add = [
            "nmcli", "connection", "add",
            "type", "wifi",
            "con-name", ssid,
            "ifname", self.AP_INTERFACE,
            "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", password,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", "10",
        ]
        r = subprocess.run(cmd_add, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            stderr = (r.stderr or "").strip()
            logger.error(f"[配网] 创建 connection profile 失败: {stderr}")
            self._cleanup_failed_connection(ssid)
            return False, self._translate_nmcli_error(stderr)

        logger.info(
            f"[配网] connection profile {ssid} 已就绪。"
            f"AP 即将由 main.py 关闭并切到 STA，本函数立即返回让 web 能发回 200"
        )
        return True, ""

    def _cleanup_failed_connection(self, ssid: str) -> None:
        """nmcli 连接失败时会留一个 broken connection 占着 wlan0，必须清理"""
        try:
            subprocess.run(
                ["nmcli", "connection", "down", ssid],
                capture_output=True, timeout=5,
            )
            subprocess.run(
                ["nmcli", "connection", "delete", ssid],
                capture_output=True, timeout=5,
            )
            logger.info(f"已清理失败的 connection: {ssid}")
        except Exception as e:
            logger.debug(f"清理 broken connection 异常（可能已不存在）: {e}")

    @staticmethod
    def _translate_nmcli_error(stderr: str) -> str:
        """把 nmcli 原始报错翻成中文，给前端看"""
        s = stderr.lower()
        if "secrets were required" in s or "no key available" in s:
            return "密码错误，请重新输入"
        if "no network with ssid" in s or "ssid not found" in s:
            return "找不到该 WiFi（可能已离开范围）"
        if "timeout" in s or "timed out" in s:
            return "连接超时，请检查信号或重试"
        if "auth" in s and "fail" in s:
            return "认证失败（密码错或路由器拒绝）"
        return f"连接失败：{stderr[:200]}"

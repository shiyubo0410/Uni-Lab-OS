"""
网关入口 - 极简版。

启动示例：
    # 用环境变量传 ak/sk
    export UNILABOS_BASICCONFIG_AK=xxxxxxxx
    export UNILABOS_BASICCONFIG_SK=yyyyyyyy
    python -m unilabos.gateway.main --config gateway.yaml

    # 或者命令行
    python -m unilabos.gateway.main --config gateway.yaml --ak xxx --sk yyy

    # 首次启动时把设备注册到 Lab 资源树
    python -m unilabos.gateway.main --config gateway.yaml --register

    # 自定义 WS URL（不走 Bohrium 默认地址）
    python -m unilabos.gateway.main --config gateway.yaml --ws-url ws://localhost:8081/ws/schedule
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from unilabos.config.config import BasicConfig, HTTPConfig, WSConfig
from unilabos.gateway.device import DeviceWorker, MockDevice
from unilabos.gateway.register import register_async
from unilabos.gateway.ws import GatewayClient
from unilabos.gateway.ota.selfhosted import SelfHostedOtaAgent
from unilabos.gateway.provisioning import (
    WiFiManager,
    ProvisioningServer,
    BLEProvisioningServer,
)

logger = logging.getLogger("gateway")


def _load_class(class_path: str):
    """从形如 "pkg.module.ClassName" 的字符串动态加载类。"""
    if "." not in class_path:
        raise ValueError(f"驱动路径格式错误: {class_path}（期望 pkg.module.Class）")
    module_path, _, class_name = class_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _build_workers(
    devices_cfg: List[Dict[str, Any]],
    send_fn,
    machine_name: str,
    on_device_lost=None,
) -> Dict[str, DeviceWorker]:
    workers: Dict[str, DeviceWorker] = {}
    for cfg in devices_cfg:
        device_id = cfg["device_id"]
        cls_path = cfg["driver"]
        init_kwargs = cfg.get("init", {}) or {}
        properties = cfg.get("properties", []) or []
        poll_interval = float(cfg.get("poll_interval", 1.0))
        report_unchanged = bool(cfg.get("report_unchanged", False))
        property_timeout = float(cfg.get("property_timeout", 5.0))
        action_timeout = float(cfg.get("action_timeout", 60.0))

        # 包装成 factory，供 DeviceWorker 在 USB 热拔后重建 driver 用。
        # 单个设备的驱动下载/导入/实例化失败时，只跳过该设备并继续加载其它设备，
        # 绝不让一个坏驱动（缺模块、依赖缺失、指纹路径写错等）拖垮整台网关。
        try:
            if cls_path == "MOCK":
                def _factory(_id=device_id):
                    return MockDevice(name=_id)
            else:
                # 驱动按需下载：指纹库里给设备配了 driver_url 时，若本地缺对应
                # 驱动模块，先从 driver_url 下载 tar.gz 解压到 unilabos/devices/，
                # 再 import。以后只维护指纹库即可，驱动自动装。
                driver_url = cfg.get("driver_url", "") or ""
                driver_version = cfg.get("driver_version", "") or ""
                if driver_url:
                    from unilabos.gateway.discovery.driver_fetch import ensure_driver_available

                    if not ensure_driver_available(cls_path, driver_url, driver_version):
                        logger.error(
                            f"[GW] 跳过设备 {device_id}: 驱动 {cls_path} 不可用"
                            f"（下载/解压失败或压缩包布局与模块路径不匹配），不影响其它设备"
                        )
                        continue
                cls = _load_class(cls_path)

                def _factory(_cls=cls, _kwargs=init_kwargs):
                    return _cls(**_kwargs)

            driver = _factory()

            worker = DeviceWorker(
                device_id=device_id,
                driver=driver,
                properties=properties,
                send_fn=send_fn,
                poll_interval=poll_interval,
                machine_name=machine_name,
                report_unchanged=report_unchanged,
                property_timeout=property_timeout,
                action_timeout=action_timeout,
                driver_factory=_factory,
                on_device_lost=on_device_lost,
            )
            # 记录设备占用的串口路径，供 hotplug 时按 port 去重，避免同一 port
            # 上同时存在多个 worker 抢占串口造成 RS-485 总线串扰
            port = init_kwargs.get("port")
            if port:
                setattr(worker, "port", port)
            workers[device_id] = worker
            logger.info(f"[GW] 已加载设备 {device_id} -> {cls_path} (port={port})")
        except Exception as e:
            # 任一环节（下载/导入/实例化/构造 worker）失败都只跳过该设备，
            # 记录堆栈便于排查，绝不让一个坏设备拖垮整台网关。
            logger.exception(
                f"[GW] 跳过设备 {device_id} ({cls_path}): 加载失败: {e}"
            )
            continue
    return workers


def _safe_unlink(path: Path) -> bool:
    """
    尽量删一个文件。

    背景：信号文件 owner=root（udev 写的）、gateway 进程=orangepi。
    `chmod` 会因为 owner 不匹配抛 PermissionError，但只要目录有 w 权限（0777）
    `unlink` 本身就能成功。所以**先直接 unlink**，失败再退回到 chmod+unlink。
    """
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return True
    except PermissionError:
        pass
    except Exception as e:
        logger.warning(f"[GW] unlink {path} 失败: {e}")
        return False
    # 走到这说明是 PermissionError，再试一次 chmod 后 unlink
    try:
        path.chmod(0o666)
        path.unlink()
        return True
    except Exception as e:
        logger.warning(
            f"[GW] 无法删除 {path}（owner 可能是 root）: {e}；"
            f"考虑 'sudo rm {path}' 或修 udev 规则让 handler 写文件后 chown"
        )
        return False


async def _start_admin_server(
    wifi_mgr: WiFiManager,
    machine_name: str,
) -> Optional[ProvisioningServer]:
    """启动常驻的管理后台 Web 服务器（mode=management）。

    端口策略：
    - root 启动（systemd User=root）→ 80 端口，用户访问 ``http://<gw_ip>``
    - 普通用户 → 8080 端口（80 需要 CAP_NET_BIND_SERVICE），用户访问 ``http://<gw_ip>:8080``

    启动失败不影响主流程：返回 None，主流程继续，用户可以 ssh 进去看日志排查。
    """
    is_root = (hasattr(os, "geteuid") and os.geteuid() == 0)
    admin_port = 80 if is_root else 8080

    server = ProvisioningServer(
        wifi_mgr,
        mode="management",
        port=admin_port,
        machine_name=machine_name,
    )
    try:
        await server.start()
    except Exception as e:
        logger.warning(
            f"[GW] 管理后台 Web 启动失败（不影响主流程）: {e}。"
            f"想改 AK/SK 仍可 ssh 进去 sudo nano /etc/unilab-gateway.env"
        )
        return None

    # 给 uvicorn 一点时间真起来再判定
    await asyncio.sleep(0.5)

    # 计算管理地址并打印（同时上报到日志，方便用户从 journalctl 找到 IP）
    try:
        from unilabos.gateway.provisioning.web_server import _get_lan_ip
        lan_ip = _get_lan_ip()
    except Exception:
        lan_ip = "unknown"
    suffix = f":{admin_port}" if admin_port != 80 else ""
    url = f"http://{lan_ip}{suffix}"
    logger.info("=" * 60)
    logger.info("[GW] 网关管理后台已启动 (mode=management)")
    logger.info(f"[GW]   管理地址: {url}")
    logger.info(f"[GW]   主机名:   {socket.gethostname()}")
    logger.info(f"[GW]   局域网 IP: {lan_ip}")
    logger.info("[GW] 同 WiFi 下浏览器打开即可修改 AK/SK / 重置 WiFi")
    logger.info("=" * 60)

    return server


async def _run_ap_provisioning_mode(wifi_mgr: WiFiManager) -> None:
    """
    进入 AP 配网模式（网页配网，兜底方案）。

    启动 AP 热点和 Web 服务器，等待用户配置 WiFi。配网成功后立即触发
    ``reboot_system`` 让系统重启——开机后 NM autoconnect 保存的 WiFi，
    systemd 重新拉起 unilab-gateway，整个过程 30~60 秒。

    为什么不在线切回 STA：unisoc sprdwl_ng 驱动从 AP 模式切回 STA 在 OPi Zero 2W
    上极度不稳定。试过 ``rmmod/modprobe sprdwl_ng``（手动 shell OK，进程里
    ``modprobe`` 后 ``/sys/class/net/wlan0`` 60s 都不出现）、``systemctl restart
    NetworkManager``、组合等多种方案，唯一 100% 可靠的就是整机 reboot。
    """
    logger.info("=" * 60)
    logger.info("[配网] 进入 AP 配网模式")
    logger.info(f"[配网] 请用手机连接 WiFi: {wifi_mgr.ap_ssid}")
    if wifi_mgr.ap_password:
        logger.info(f"[配网] WiFi 密码: {wifi_mgr.ap_password}")
    else:
        logger.warning("[配网] ⚠ 开放网络（无密码）- 配网完成后将自动关闭")
    logger.info(f"[配网] 连上后浏览器打开: http://{wifi_mgr.AP_GATEWAY_IP}")
    logger.info("=" * 60)

    if not wifi_mgr.start_ap():
        logger.error("[配网] 启动 AP 热点失败，无法进入配网模式")
        raise RuntimeError("无法启动 AP 热点")

    provisioning_done = asyncio.Event()

    def on_success(ssid: Optional[str] = None):
        logger.info(f"[配网] 收到配网成功信号 ssid={ssid}")
        provisioning_done.set()

    server = ProvisioningServer(wifi_mgr, on_success=on_success)
    await server.start()

    try:
        await provisioning_done.wait()
        logger.info("[配网] 等待 3 秒以便 Web 响应完成发送...")
        await asyncio.sleep(3)
    finally:
        # 先停 web，确保 200 已发完，再 reboot
        await server.stop()
        logger.info("[配网] 重启系统让新 WiFi 配置生效（约 30-60 秒后服务自动恢复）...")
        wifi_mgr.reboot_system()
        # reboot 启动后 systemd 会 SIGTERM 我们；等几秒别让函数立刻返回执行后续逻辑
        await asyncio.sleep(60)


# bring-up 阶段允许明文 Provision（0x00），方便用 nRF Connect 手测；
# APP 联调打通、生产发布前应改为 False（只接受 X25519+AES-GCM 加密路径）。
_BLE_ALLOW_PLAINTEXT = True


async def _run_ble_provisioning_mode(
    wifi_mgr: WiFiManager, machine_name: str
) -> bool:
    """进入蓝牙(BLE)配网模式（首选方案，在线试连、**不 reboot**）。

    与 AP 方案的本质区别：蓝牙走独立 BT 射频，全程不碰 wlan0 的 STA 状态，因此配网
    成功后可直接在本进程继续正常业务，无需整机重启（已在真机 5/5 验证纯 STA 在线
    切换稳定）。

    :return: True  = 蓝牙配网成功且已联网（调用方继续正常流程，不 reboot）；
             False = 蓝牙栈起不来（缺 bluez/cryptography / 无蓝牙硬件），需回退 AP。
    """
    logger.info("=" * 60)
    logger.info("[配网] 进入蓝牙(BLE)配网模式（首选，在线配网不 reboot）")
    logger.info("[配网] 请用 APP / nRF Connect 扫描并连接 UniLab-GW-*")
    logger.info("=" * 60)

    provisioning_done = asyncio.Event()

    def on_success(ssid: Optional[str] = None):
        logger.info(f"[配网][BLE] 收到配网成功信号 ssid={ssid}")
        provisioning_done.set()

    server = BLEProvisioningServer(
        wifi_mgr,
        on_success=on_success,
        machine_name=machine_name,
        allow_plaintext=_BLE_ALLOW_PLAINTEXT,
    )
    try:
        await server.start()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[配网][BLE] 蓝牙服务启动失败（缺 bluez-peripheral/cryptography 或无蓝牙？）: {e}"
        )
        return False

    try:
        await provisioning_done.wait()
        # 给 Status(step=10) 的最后一条 notify 一点发送时间，再收摊
        await asyncio.sleep(1)
        logger.info("[配网][BLE] 配网成功，已在线，继续启动业务（无需 reboot）")
        return True
    finally:
        await server.stop()


async def _run_provisioning_mode(
    wifi_mgr: WiFiManager, method: str, machine_name: str
) -> bool:
    """配网调度器：优先蓝牙，蓝牙不可用则回退 AP 网页。

    :param method: ``auto`` / ``ble`` / ``ap``。
    :return: True  = 已在线（BLE 成功，调用方继续，不 reboot）；
             False = 走了 AP 网页路径（该路径内部 reboot，正常不会返回；返回 False
                     表示 reboot 未生效需由 systemd 兜底重启）。
    """
    method = (method or "auto").lower()

    if method in ("auto", "ble"):
        try:
            if await _run_ble_provisioning_mode(wifi_mgr, machine_name):
                return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[配网] 蓝牙配网异常: {e}")
        if method == "ble":
            logger.warning("[配网] 指定了 BLE 但蓝牙不可用，为保证可用性仍回退 AP 网页")
        else:
            logger.info("[配网] 蓝牙不可用，回退 AP 网页配网")

    # AP 网页兜底：内部 reboot，正常不返回
    await _run_ap_provisioning_mode(wifi_mgr)
    return False


# 运行期断网多久就重启进程（重启后启动流程会重新做配网检查）
_NETWORK_LOSS_RESTART_GRACE = 20.0


async def _network_watchdog(
    client: GatewayClient,
    wifi_mgr: WiFiManager,
    grace_seconds: float = _NETWORK_LOSS_RESTART_GRACE,
    check_interval: float = 5.0,
) -> None:
    """运行期断网看门狗：真断网持续超过 ``grace_seconds`` 就重启进程。

    重启后 ``run_gateway`` 启动流程会重新做配网检查:连不上已保存的 WiFi 就重新
    进入配网(蓝牙/AP)流程。

    判定逻辑(避免"云端故障"误判为"断网"而反复重启):
    1. WS 还连着 → 一切正常,清零计时;
    2. WS 断了,但 ``wifi_mgr.is_connected()`` 显示本地仍能出公网 → 只是云端/WS
       问题,交给 WS 自己重连,不重启;
    3. WS 断了且本地也出不了公网 → 真断网,开始计时;持续超过 grace 秒 → 重启进程。

    只有在 WS 断开时才会去跑 nmcli 检查,正常联网期间零额外开销、不刷日志。
    """
    loop = asyncio.get_running_loop()
    down_since: Optional[float] = None
    while True:
        await asyncio.sleep(check_interval)

        if client.is_connected:
            if down_since is not None:
                logger.info("[GW] 网络已恢复，取消重启计划")
            down_since = None
            continue

        # WS 断了,进一步确认是不是真断网(区分本地断网 vs 云端故障)
        try:
            net_ok = await loop.run_in_executor(None, wifi_mgr.is_connected)
        except Exception:
            net_ok = False
        if net_ok:
            # 本地网络正常,只是连不上云端 → 交给 WS 内部重连,不重启
            if down_since is not None:
                logger.info("[GW] 本地网络正常(仅云端未连上)，取消重启计划")
            down_since = None
            continue

        now = loop.time()
        if down_since is None:
            down_since = now
            logger.warning(
                f"[GW] 检测到断网，{grace_seconds:.0f}s 内未恢复将重启进程重新进入配网流程"
            )
        elif now - down_since >= grace_seconds:
            logger.error(
                f"[GW] 断网已超过 {grace_seconds:.0f}s，重启进程 → 由 systemd 拉起后重新进入配网流程"
            )
            # 硬退出,保证一定重启(依赖 systemd 的 Restart=always/on-failure)
            os._exit(1)


async def run_gateway(
    devices_cfg: List[Dict[str, Any]],
    ws_url: str,
    machine_name: str,
    *,
    register: bool = False,
    http_url: Optional[str] = None,
    mount_uuid: str = "",
    skip_provisioning: bool = False,
    provision_method: str = "auto",
) -> None:
    # WiFiManager 既给配网检查用，也给常驻管理后台 (admin_server) 用，
    # 所以无论是否 skip_provisioning 都先建好。
    wifi_mgr = WiFiManager()

    # 配网检查（除非明确跳过）
    if not skip_provisioning:
        # 检查是否需要进入配网模式
        needs_provisioning = False

        if not wifi_mgr.has_saved_wifi():
            logger.info("[GW] 未发现已保存的 WiFi 配置，进入配网模式")
            needs_provisioning = True
        elif not wifi_mgr.is_connected():
            logger.info("[GW] 尝试连接已保存的 WiFi...")
            if not wifi_mgr.wait_for_connection(timeout=30):
                logger.warning("[GW] 无法连接到已保存的 WiFi，进入配网模式")
                needs_provisioning = True

        if needs_provisioning:
            online = await _run_provisioning_mode(
                wifi_mgr, provision_method, machine_name
            )
            if online:
                # 蓝牙在线配网成功，本进程直接继续正常业务，不 reboot
                logger.info("[GW] 配网成功且已联网，继续启动业务")
            else:
                # 走了 AP 网页路径，内部会 sudo reboot，正常这里不会执行到
                # （reboot 会 SIGTERM 我们）。走到这里说明 reboot 未生效，wlan0 处于
                # stop_ap 后的 unisoc 卡死态在线救不回，直接退出由 systemd 重启。
                logger.error("[GW] reboot 未生效，退出由 systemd 重新拉起本进程")
                sys.exit(1)

    # 常驻管理后台：联网正常之后启动一个 ProvisioningServer(mode="management")
    # 让用户在同 WiFi 下用浏览器修改 AK/SK / mount_uuid，省掉 ssh + sudo nano
    # /etc/unilab-gateway.env 的麻烦。即使 register/ws 后续连不上云端，本管理后台
    # 仍然在跑，用户可以改 AK/SK 救场。
    admin_server = await _start_admin_server(wifi_mgr, machine_name)

    if register:
        base_url = (http_url or HTTPConfig.remote_addr).rstrip("/")
        # 先上传注册表“类型模板”(设备/资源类型定义)，否则后端在节点注册时会因
        # 模板不存在返回 22020 (material resource template not exist)。
        # 纯 Python 构建 + 纯 HTTP 上报，不依赖 ROS。
        try:
            from unilabos.gateway.registry_upload import upload_registry_templates

            await upload_registry_templates(base_url)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[GW] 注册表模板上传失败（继续尝试节点注册）: {e}")

        ok = await register_async(base_url, machine_name, devices_cfg, mount_uuid=mount_uuid)
        if not ok:
            logger.warning(
                "[GW] 资源树注册失败，仍将尝试启动 WebSocket（前端可能看不到设备）"
            )

    workers: Dict[str, DeviceWorker] = {}

    def on_device_lost(device_id: str) -> None:
        logger.info(f"[GW] 设备 {device_id} 已丢失，从 workers 移除，等待热插拔重新识别")
        workers.pop(device_id, None)

    async def send_fn(msg: Dict[str, Any]) -> None:
        await client.send(msg)

    # 自建 OTA 客户端（对接 uni-lab-backend，见 ota/ota-design.md §13）。
    # 网关以"一台特殊 device"身份登记：product_key 固定，device_name = hostname 后缀。
    # 下发本期先走 HTTP 兜底拉取（不依赖 WS 连接类型）；WS ota_cmd 主动推送若能到也一并处理。
    ota_agent = SelfHostedOtaAgent(
        send_fn=send_fn,
        machine_name=machine_name,
        base_url=http_url,
    )

    async def on_ready() -> Dict[str, Any]:
        devices_payload = []
        for device_id, worker in workers.items():
            actions = worker.list_actions()
            meta: Dict[str, Any] = {
                "device_type": getattr(worker.driver, "device_type", "unknown"),
            }
            for k in ("manufacturer", "model", "serial", "protocol"):
                v = getattr(worker.driver, k, None)
                if v is not None:
                    meta[k] = v

            devices_payload.append(
                {
                    "device_id": device_id,
                    "namespace": "/devices",
                    "device_key": f"/devices/{device_id}",
                    "is_online": True,
                    "machine_name": machine_name,
                    "actions": actions,
                    "meta": meta,
                }
            )

        logger.info(f"[GW] host_node_ready: 上报 {len(devices_payload)} 个设备")
        return {
            "action": "host_node_ready",
            "data": {
                "status": "ready",
                "timestamp": time.time(),
                "machine_name": machine_name,
                "gateway_type": "iot_gateway",
                "devices": devices_payload,
            },
        }

    async def on_message(msg: Dict[str, Any]) -> None:
        action = msg.get("action")
        data = msg.get("data", {}) or {}

        if action == "job_start":
            await _handle_job_start(data, workers, client, machine_name)
        elif action == "query_action_state":
            await _handle_query_action_state(data, workers, client)
        elif action == "ota_cmd":
            await ota_agent.handle_ota_cmd(data)
        elif action == "ota_cancel":
            await ota_agent.handle_ota_cancel(data)
        elif action == "cancel_action" or action == "cancel_task":
            logger.info(f"[GW] 收到取消请求 action={action} data={data}（暂未实现）")
        elif action in ("add_material", "update_material", "remove_material"):
            logger.debug(f"[GW] 资源同步消息 action={action}（暂忽略）")
        elif action == "add_device" or action == "remove_device":
            logger.info(f"[GW] 设备热插拔消息 action={action}（暂未实现）")
        else:
            logger.debug(f"[GW] 未处理的下行消息 action={action} keys={list(data.keys())}")

    # WS 握手声明网关身份（ota-design.md §13.1）。ConnType=gateway 是与后端约定的
    # 专用类型：既保留主机连接语义（不影响真实设备的 job_start 路由，区别于 device 型），
    # 又让后端据 (ProductKey, DeviceName) 把本网关的 lab_id upsert 进 device 表，
    # 从而填上设备台账的"实验室"归属。pk/sn 与 OTA 拉取用的一致（见 ota_agent）。
    client = GatewayClient(
        url=ws_url,
        machine_name=machine_name,
        on_message=on_message,
        on_ready=on_ready,
        extra_headers={
            "ConnType": "gateway",
            "ProductKey": ota_agent.product_key,
            "DeviceName": ota_agent.device_name,
        },
    )

    workers = _build_workers(devices_cfg, send_fn=send_fn, machine_name=machine_name, on_device_lost=on_device_lost)
    for worker in workers.values():
        await worker.start()

    # 启动热插拔监听任务
    hotplug_task = asyncio.create_task(
        _hotplug_monitor(
            workers, send_fn, machine_name, client, on_device_lost,
            register=register,
            http_url=http_url,
            mount_uuid=mount_uuid,
        )
    )

    # 启动断网看门狗：运行期真断网超过 20s 就重启进程重新进入配网流程
    watchdog_task = asyncio.create_task(
        _network_watchdog(client, wifi_mgr), name="gw-net-watchdog"
    )

    # 启动自建 OTA 的 HTTP 兜底拉取任务（§13.8）；WS ota_cmd 推送经 on_message 处理。
    ota_poll_task = asyncio.create_task(
        ota_agent.http_poll_loop(), name="gw-ota-poll"
    )

    try:
        await client.run()
    finally:
        ota_agent.stop()
        ota_poll_task.cancel()
        watchdog_task.cancel()
        hotplug_task.cancel()
        for worker in workers.values():
            await worker.stop()
        if admin_server is not None:
            try:
                await admin_server.stop()
            except Exception as e:
                logger.debug(f"[GW] 关闭管理后台 Web 异常（忽略）: {e}")


async def _handle_job_start(
    data: Dict[str, Any],
    workers: Dict[str, DeviceWorker],
    client: GatewayClient,
    machine_name: str,
) -> None:
    device_id = data.get("device_id")
    action_name = data.get("action")
    action_args = data.get("action_args") or {}
    job_id = data.get("job_id")
    task_id = data.get("task_id")

    worker = workers.get(device_id)
    if worker is None:
        logger.warning(f"[GW] job_start 找不到设备 {device_id}, job={job_id}")
        await client.send(
            {
                "action": "job_status",
                "data": {
                    "job_id": job_id,
                    "task_id": task_id,
                    "device_id": device_id,
                    "action_name": action_name,
                    "status": "failed",
                    "return_info": {"error": f"unknown device {device_id}"},
                    "timestamp": time.time(),
                },
            }
        )
        return

    logger.info(
        f"[GW] job_start device={device_id} action={action_name} args={action_args} job={job_id}"
    )

    await client.send(
        {
            "action": "job_status",
            "data": {
                "job_id": job_id,
                "task_id": task_id,
                "device_id": device_id,
                "action_name": action_name,
                "status": "running",
                "return_info": {},
                "timestamp": time.time(),
            },
        }
    )

    result = await worker.execute_action(action_name, action_args)

    await client.send(
        {
            "action": "job_status",
            "data": {
                "job_id": job_id,
                "task_id": task_id,
                "device_id": device_id,
                "action_name": action_name,
                "status": result["status"],
                "return_info": result.get("return_info", {}),
                "timestamp": time.time(),
            },
        }
    )


async def _handle_query_action_state(
    data: Dict[str, Any],
    workers: Dict[str, DeviceWorker],
    client: GatewayClient,
) -> None:
    device_id = data.get("device_id")
    await client.send(
        {
            "action": "report_action_state",
            "data": {
                "type": "query_action_status",
                "device_id": device_id,
                "action_name": data.get("action_name"),
                "task_id": data.get("task_id"),
                "job_id": data.get("job_id"),
                "free": device_id in workers,
                "need_more": 0,
            },
        }
    )


async def _hotplug_monitor(
    workers: Dict[str, DeviceWorker],
    send_fn,
    machine_name: str,
    client: GatewayClient,
    on_device_lost=None,
    *,
    register: bool = False,
    http_url: Optional[str] = None,
    mount_uuid: str = "",
) -> None:
    """
    监听热插拔信号文件，自动加载新设备。

    udev 规则会在 USB 串口插入时调用 hotplug_handler，
    handler 探测成功后写入信号文件到 /tmp/unilab-gateway/hotplug/。
    本函数定期扫描该目录，发现新设备就加载并启动。
    """
    signal_dir = Path("/tmp/unilab-gateway/hotplug")
    signal_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[HOTPLUG] 监听目录: {signal_dir}")

    while True:
        try:
            await asyncio.sleep(2.0)  # 每 2 秒扫描一次

            signal_files = list(signal_dir.glob("*.json"))
            if not signal_files:
                continue

            for signal_file in signal_files:
                try:
                    with open(signal_file, "r", encoding="utf-8") as f:
                        import json
                        device_cfg = json.load(f)

                    device_id = device_cfg["device_id"]
                    new_port = (device_cfg.get("init") or {}).get("port")

                    # 如果同名设备已存在（旧 worker 还在重连），先停止旧的再加载新的
                    if device_id in workers:
                        logger.warning(
                            f"[HOTPLUG] 设备 {device_id} 已存在（可能正在重连），"
                            f"先停止旧 worker 再加载新设备"
                        )
                        old_worker = workers.pop(device_id)
                        try:
                            await old_worker.stop()
                        except Exception as e:
                            logger.debug(f"[HOTPLUG] 停止旧 worker 时出错: {e}")

                    # 按 port 去重：同一物理串口上不允许存在多个 worker，
                    # 否则会出现 RS-485 总线串扰、CRC 错乱、误识别等问题。
                    # 触发场景：udev 规则重复触发 / 设备热拔插 / 误识别。
                    if new_port:
                        conflicting = [
                            (did, w)
                            for did, w in workers.items()
                            if getattr(w, "port", None) == new_port and did != device_id
                        ]
                        for did, old_worker in conflicting:
                            logger.warning(
                                f"[HOTPLUG] 端口冲突: {new_port} 已被 {did} 占用，"
                                f"停止旧 worker 后再加载 {device_id}"
                            )
                            workers.pop(did, None)
                            try:
                                await old_worker.stop()
                            except Exception as e:
                                logger.debug(f"[HOTPLUG] 停止旧 worker {did} 出错: {e}")
                            # 通知云端旧设备下线
                            try:
                                await client.send(
                                    {
                                        "action": "remove_device",
                                        "data": {
                                            "device_id": did,
                                            "namespace": "/devices",
                                            "device_key": f"/devices/{did}",
                                            "machine_name": machine_name,
                                        },
                                    }
                                )
                            except Exception as e:
                                logger.debug(f"[HOTPLUG] 通知云端 {did} 下线失败: {e}")

                    logger.info(f"[HOTPLUG] 加载新设备: {device_id} (port={new_port})")

                    # 如果启用了注册，先注册到资源树
                    if register:
                        from unilabos.config.config import HTTPConfig
                        base_url = (http_url or HTTPConfig.remote_addr).rstrip("/")
                        logger.info(f"[HOTPLUG] 注册设备 {device_id} 到资源树")
                        ok = await register_async(
                            base_url, machine_name, [device_cfg], mount_uuid=mount_uuid
                        )
                        if not ok:
                            logger.warning(f"[HOTPLUG] 设备 {device_id} 注册失败，但仍会加载到网关")

                    # 构建 worker
                    new_workers = _build_workers([device_cfg], send_fn=send_fn, machine_name=machine_name, on_device_lost=on_device_lost)
                    worker = new_workers[device_id]
                    await worker.start()
                    workers[device_id] = worker

                    # 通知云端设备上线
                    actions = worker.list_actions()
                    meta: Dict[str, Any] = {
                        "device_type": getattr(worker.driver, "device_type", "unknown"),
                    }
                    for k in ("manufacturer", "model", "serial", "protocol"):
                        v = getattr(worker.driver, k, None)
                        if v is not None:
                            meta[k] = v

                    await client.send(
                        {
                            "action": "add_device",
                            "data": {
                                "device_id": device_id,
                                "namespace": "/devices",
                                "device_key": f"/devices/{device_id}",
                                "is_online": True,
                                "machine_name": machine_name,
                                "actions": actions,
                                "meta": meta,
                            },
                        }
                    )

                    logger.info(f"[HOTPLUG] ✓ 设备 {device_id} 已上线")

                    # 删除信号文件
                    _safe_unlink(signal_file)

                except Exception as e:
                    logger.error(f"[HOTPLUG] 处理信号文件 {signal_file} 失败: {e}")
                    _safe_unlink(signal_file)

        except asyncio.CancelledError:
            logger.info("[HOTPLUG] 监听任务已取消")
            break
        except Exception as e:
            logger.error(f"[HOTPLUG] 监听循环异常: {e}")
            await asyncio.sleep(5.0)


def _resolve_ak_sk(args: argparse.Namespace) -> None:
    """优先级：CLI 参数 > 环境变量 > 配置文件已设置的值。"""
    if args.ak:
        BasicConfig.ak = args.ak
    elif not BasicConfig.ak:
        BasicConfig.ak = os.environ.get("UNILABOS_BASICCONFIG_AK", "") or BasicConfig.ak
    if args.sk:
        BasicConfig.sk = args.sk
    elif not BasicConfig.sk:
        BasicConfig.sk = os.environ.get("UNILABOS_BASICCONFIG_SK", "") or BasicConfig.sk


def _resolve_ws_url(args_url: Optional[str]) -> str:
    if args_url:
        return args_url
    base = HTTPConfig.remote_addr.replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/ws/schedule"


def main() -> None:
    parser = argparse.ArgumentParser(description="Uni-Lab IoT 网关 (极简版)")
    parser.add_argument("--config", required=True, help="网关 YAML 配置文件")
    parser.add_argument("--ws-url", help="WebSocket URL (默认走 HTTPConfig.remote_addr)")
    parser.add_argument(
        "--http-url",
        help="HTTP API URL，用于资源树注册 (默认 HTTPConfig.remote_addr)",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="启动时通过 POST /edge/material 把设备挂到 lab 资源树 (幂等，可重复运行)",
    )
    parser.add_argument(
        "--mount-uuid",
        default="",
        help="资源树挂载点 UUID。填你的 lab UUID（从浏览器 URL /laboratory/<uuid>/ 复制）",
    )
    parser.add_argument("--machine-name", default=None, help="机器名 (默认 <hostname>)")
    parser.add_argument("--ak", help="AK，覆盖环境变量与配置文件")
    parser.add_argument("--sk", help="SK，覆盖环境变量与配置文件")
    parser.add_argument(
        "--log-level",
        default=os.environ.get("GATEWAY_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--auto-discover",
        action="store_true",
        help="启用串口自动发现（扫描所有串口并识别已知设备）",
    )
    parser.add_argument(
        "--skip-provisioning",
        action="store_true",
        help="跳过 WiFi 配网检查（已联网或调试时使用）",
    )
    parser.add_argument(
        "--provision-method",
        default=None,
        choices=["auto", "ble", "ap"],
        help="配网方式：auto=优先蓝牙失败回退AP网页(默认) / ble=仅蓝牙 / ap=仅AP网页",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # websockets 库的 DEBUG 太吵了（每 10s 心跳 PING/PONG 都打），
    # 即使主程序设 INFO，也强制把它压到 WARNING 起步
    if args.log_level != "DEBUG":
        logging.getLogger("websockets").setLevel(logging.WARNING)

    _resolve_ak_sk(args)
    if not BasicConfig.ak or not BasicConfig.sk:
        logger.error(
            "[GW] 缺少 ak/sk。请通过 --ak/--sk、UNILABOS_BASICCONFIG_AK/SK 环境变量、或配置文件提供"
        )
        sys.exit(2)

    ws_url = _resolve_ws_url(args.ws_url)

    machine_name = args.machine_name or socket.gethostname()
    BasicConfig.machine_name = machine_name

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"[GW] 配置文件不存在: {config_path}")
        sys.exit(2)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    devices_cfg = cfg.get("devices", [])

    # 自动发现设备（如果启用）
    if args.auto_discover:
        from .discovery import scan_all_ports
        discovered = scan_all_ports()
        if discovered:
            logger.info(f"[GW] 自动发现 {len(discovered)} 个设备，合并到配置")
            # 手动配置优先：如果 device_id 已存在，跳过自动发现的
            manual_ids = {d.get("device_id") for d in devices_cfg}
            for dev in discovered:
                if dev["device_id"] not in manual_ids:
                    devices_cfg.append(dev)
                else:
                    logger.info(f"[GW] 跳过自动发现的 {dev['device_id']}（手动配置已存在）")

    if not devices_cfg:
        logger.warning("[GW] 配置中没有 devices，网关会空跑（仅维持连接）")

    if cfg.get("machine_name"):
        machine_name = cfg["machine_name"]
        BasicConfig.machine_name = machine_name

    # 配网方式：命令行 > 配置文件 > 默认 auto
    provision_method = args.provision_method or cfg.get("provision_method") or "auto"

    logger.info(
        f"[GW] 启动: machine_name={machine_name} devices={len(devices_cfg)} "
        f"ws={ws_url} register={args.register} reconnect_interval={WSConfig.reconnect_interval}s"
    )

    try:
        asyncio.run(
            run_gateway(
                devices_cfg,
                ws_url,
                machine_name,
                register=args.register,
                http_url=args.http_url,
                mount_uuid=args.mount_uuid,
                skip_provisioning=args.skip_provisioning,
                provision_method=provision_method,
            )
        )
    except KeyboardInterrupt:
        logger.info("[GW] 用户中断，退出")


if __name__ == "__main__":
    main()

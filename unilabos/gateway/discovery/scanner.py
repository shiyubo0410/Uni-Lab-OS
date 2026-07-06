"""
串口扫描器 - 枚举所有串口并调用探针，返回发现的设备配置列表。

核心函数：
- scan_all_ports() -> List[dict]
  扫描系统所有串口，返回自动发现的设备配置列表（可直接合并到 gateway.yaml）
"""

import glob
import logging
from typing import Any, Dict, List

from .probe import load_fingerprints, probe_port

logger = logging.getLogger(__name__)


def _enumerate_serial_ports() -> List[str]:
    """
    枚举系统串口设备。

    pyserial 的 list_ports.comports() 在某些 Linux 环境下找不到设备，
    改用直接 glob /dev/tty* 的方式。

    只扫描 USB/ACM 类串口（真正的外设），跳过 ttyS*（CPU 内建串口，
    通常没接东西，探测会超时拖慢启动）。
    """
    patterns = [
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/cu.usbserial*",  # macOS
        "/dev/cu.usbmodem*",   # macOS
    ]
    ports = []
    for pattern in patterns:
        ports.extend(glob.glob(pattern))
    return sorted(set(ports))


def scan_all_ports() -> List[Dict[str, Any]]:
    """
    扫描系统所有串口，返回自动发现的设备配置列表。

    返回格式（与 gateway.yaml 的 devices 列表兼容）：
    [
        {
            "device_id": "pump-sy03b-auto-a3f2",
            "name": "SY-03B 注射泵 (auto)",
            "driver": "unilabos.devices.pump_and_valve.runze_backbone.RunzeSyringePump",
            "registry_class": "syringe_pump_with_valve.runze.SY03B-T06",
            "init": {"port": "/dev/ttyUSB0", "address": "1", "max_volume": 25.0},
            "properties": ["status", "position", "valve_position", "max_velocity"],
            "poll_interval": 1.5,
            "report_unchanged": false,
            "_auto_discovered": true  # 标记为自动发现
        }
    ]
    """
    fingerprints = load_fingerprints()
    if not fingerprints:
        logger.warning("[SCAN] 指纹库为空，跳过自动发现")
        return []

    ports = _enumerate_serial_ports()
    logger.info(f"[SCAN] 发现 {len(ports)} 个串口，开始探测...")

    discovered = []
    for port in ports:
        logger.debug(f"[SCAN] 探测 {port}")

        matched = probe_port(port, fingerprints)
        if matched:
            device_cfg = _fingerprint_to_device_config(matched)
            discovered.append(device_cfg)
            logger.info(
                f"[SCAN] ✓ {port} -> {device_cfg['device_id']} ({matched['name']})"
            )

    logger.info(f"[SCAN] 完成，发现 {len(discovered)} 个设备")
    return discovered


def _fingerprint_to_device_config(fp: Dict[str, Any]) -> Dict[str, Any]:
    """
    将匹配的指纹转换为设备配置字典（gateway.yaml 格式）。

    fp 必须包含 "port" 字段（由 probe_port 填充）。
    """
    port = fp["port"]
    driver = fp["driver"]
    name = fp.get("name", "unknown")
    fp_name = fp.get("name", driver.split(".")[-1].lower())

    # 生成 device_id：使用指纹名作为固定 ID，假设同时只有一个该类型设备
    # 这样同一物理设备拔出再插入（即使端口号变了）也保持同名，避免日志混乱
    device_id = f"{fp_name}-auto-1"

    # 合并 init_template + port
    init_params = dict(fp.get("init_template", {}))
    init_params["port"] = port

    return {
        "device_id": device_id,
        "name": f"{name} (auto)",
        "driver": driver,
        # 驱动包下载地址(可选)：本地缺驱动模块时由 _build_workers 自动下载解压
        "driver_url": fp.get("driver_url", ""),
        # 驱动期望版本(可选)：本地已装但版本不一致时触发重新下载更新
        "driver_version": fp.get("driver_version", ""),
        "registry_class": fp.get("registry_class", ""),
        "init": init_params,
        "properties": fp.get("properties", []),
        "poll_interval": fp.get("poll_interval", 1.0),
        "report_unchanged": fp.get("report_unchanged", False),
        "_auto_discovered": True,  # 标记为自动发现，便于调试
    }

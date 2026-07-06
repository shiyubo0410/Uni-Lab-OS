"""
USB 热插拔处理器 - 响应 udev 事件，触发设备重新扫描。

核心函数：
- handle_usb_add(port) -> None
  当 USB 串口插入时被 udev 规则调用，探测新设备并通知 gateway 加载
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from .probe import load_fingerprints, probe_port

logger = logging.getLogger(__name__)


def handle_usb_add(port: str) -> Optional[dict]:
    """
    处理 USB 串口插入事件。

    Args:
        port: 新插入的串口路径，如 /dev/ttyUSB0

    Returns:
        匹配的设备配置字典，未匹配返回 None
    """
    logger.info(f"[HOTPLUG] 检测到 USB 串口插入: {port}")

    fingerprints = load_fingerprints()
    if not fingerprints:
        logger.warning("[HOTPLUG] 指纹库为空，跳过探测")
        return None

    matched = probe_port(port, fingerprints)
    if matched:
        logger.info(f"[HOTPLUG] {port} 匹配指纹: {matched['name']}")
        return matched
    else:
        logger.info(f"[HOTPLUG] {port} 未匹配任何已知设备")
        return None


def notify_gateway(device_config: dict) -> bool:
    """
    通知 gateway 进程加载新设备。

    通过写入信号文件的方式通知（简单可靠，无需网络连接）。
    Gateway 会定期检查信号文件并加载新设备。

    Args:
        device_config: 设备配置字典（scanner._fingerprint_to_device_config 格式）

    Returns:
        成功返回 True
    """
    import json

    device_id = device_config["device_id"]

    signal_dir = Path("/tmp/unilab-gateway/hotplug")
    signal_dir.mkdir(parents=True, exist_ok=True)
    try:
        signal_dir.chmod(0o777)
    except Exception:
        pass

    signal_file = signal_dir / f"{device_id}.json"

    try:
        with open(signal_file, "w", encoding="utf-8") as f:
            json.dump(device_config, f, ensure_ascii=False, indent=2)
        try:
            signal_file.chmod(0o666)
        except Exception:
            pass
        logger.info(f"[HOTPLUG] 已写入信号文件: {signal_file}")
        return True
    except Exception as e:
        logger.error(f"[HOTPLUG] 写入信号文件失败: {e}")
        return False


def main():
    """
    命令行入口，供 udev 规则调用。

    用法：
        python -m unilabos.gateway.discovery.hotplug_handler /dev/ttyUSB0
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if len(sys.argv) < 2:
        logger.error("[HOTPLUG] 缺少串口参数")
        sys.exit(1)

    port = sys.argv[1]

    # 探测设备
    matched = handle_usb_add(port)
    if not matched:
        logger.info(f"[HOTPLUG] {port} 不是已知设备，忽略")
        sys.exit(0)

    # 转换为设备配置
    from .scanner import _fingerprint_to_device_config
    device_config = _fingerprint_to_device_config(matched)

    # 通知 gateway
    if notify_gateway(device_config):
        logger.info(f"[HOTPLUG] 成功通知 gateway 加载 {device_config['device_id']}")
        sys.exit(0)
    else:
        logger.error("[HOTPLUG] 通知 gateway 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()

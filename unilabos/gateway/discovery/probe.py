"""
探针引擎 - 对单个串口尝试所有指纹，返回匹配的设备类型。

核心函数：
- probe_port(port, fingerprints) -> Optional[dict]
  对指定串口依次尝试所有指纹，返回第一个匹配的指纹配置（含 port 信息）
"""

import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import serial
import yaml

logger = logging.getLogger(__name__)


def load_fingerprints() -> List[Dict[str, Any]]:
    """加载指纹库 YAML 文件。"""
    fp_path = Path(__file__).parent / "fingerprints.yaml"
    if not fp_path.exists():
        logger.warning(f"[PROBE] 指纹库文件不存在: {fp_path}")
        return []
    with open(fp_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if data else []


def probe_port(port: str, fingerprints: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """
    对指定串口依次尝试所有指纹，返回第一个匹配的指纹配置。

    Args:
        port: 串口路径，如 /dev/ttyUSB0
        fingerprints: 指纹列表（不传则自动加载）

    Returns:
        匹配的指纹配置字典（含 port 字段），未匹配返回 None
    """
    if fingerprints is None:
        fingerprints = load_fingerprints()

    for fp in fingerprints:
        if _try_fingerprint(port, fp):
            logger.info(f"[PROBE] {port} 匹配指纹: {fp['name']}")
            # 返回副本，避免污染原始指纹库
            matched = dict(fp)
            matched["port"] = port
            return matched

    logger.debug(f"[PROBE] {port} 未匹配任何指纹")
    return None


def _try_fingerprint(port: str, fp: Dict[str, Any]) -> bool:
    """
    尝试单个指纹。返回 True 表示匹配成功。

    指纹格式：
    {
        "name": "runze_sy03b",
        "probe": {
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "commands": [
                {"send": "/1Q\\r\\n", "expect_prefix": "\\xff/0`", "timeout": 1.0}
            ]
        }
    }
    """
    probe_cfg = fp.get("probe", {})
    baudrate = probe_cfg.get("baudrate", 9600)
    bytesize = probe_cfg.get("bytesize", 8)
    parity = probe_cfg.get("parity", "N")
    stopbits = probe_cfg.get("stopbits", 1)
    commands = probe_cfg.get("commands", [])

    if not commands:
        logger.warning(f"[PROBE] 指纹 {fp['name']} 无 probe.commands，跳过")
        return False

    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=1.0,
        )
    except Exception as e:
        logger.debug(f"[PROBE] {port} 打开失败 (baudrate={baudrate}): {e}")
        return False

    # FTDI/CH340 等 USB 串口芯片刚打开时 DTR/RTS 可能在跳变，等 0.5s 让它稳定
    time.sleep(0.5)

    try:
        # 依次执行所有探测命令，全部匹配才算成功
        for cmd in commands:
            if not _execute_probe_command(ser, cmd, fp["name"]):
                return False
        return True
    finally:
        ser.close()


def _str_to_bytes(s: str) -> bytes:
    """
    把 YAML 里的字符串转成字节串。

    YAML 双引号字符串会自动处理 \\r \\n \\xff 等转义，加载后已经是 Unicode 字符串，
    每个字符对应一个码位。用 latin1 编码把码位 0-255 映射为单字节（而非 UTF-8 多字节）。
    """
    return s.encode("latin1")


def _execute_probe_command(ser: serial.Serial, cmd: Dict[str, Any], fp_name: str) -> bool:
    """
    执行单条探测命令。

    cmd 格式：
    {
        "send": "/1Q\\r\\n",
        "expect_prefix": "\\xff/0`",  # 可选
        "expect_regex": "^[0-9]+",    # 可选，与 expect_prefix 二选一
        "timeout": 1.0
    }
    """
    send_str = cmd.get("send", "")
    expect_prefix = cmd.get("expect_prefix")
    expect_regex = cmd.get("expect_regex")
    timeout = cmd.get("timeout", 1.0)

    send_bytes = _str_to_bytes(send_str)

    ser.reset_input_buffer()
    ser.write(send_bytes)
    time.sleep(0.1)  # 给设备一点反应时间

    # 读取响应
    ser.timeout = timeout
    response = ser.read(128)

    if not response:
        logger.debug(f"[PROBE] {fp_name} 无响应: send={send_bytes!r}")
        return False

    # 匹配检查
    if expect_prefix:
        prefix_bytes = _str_to_bytes(expect_prefix)
        if not response.startswith(prefix_bytes):
            logger.debug(
                f"[PROBE] {fp_name} 前缀不匹配: expect={prefix_bytes!r} got={response!r}"
            )
            return False

    if expect_regex:
        pattern = re.compile(_str_to_bytes(expect_regex))
        if not pattern.match(response):
            logger.debug(
                f"[PROBE] {fp_name} 正则不匹配: pattern={expect_regex} got={response!r}"
            )
            return False

    logger.debug(f"[PROBE] {fp_name} 命令匹配: send={send_bytes!r} resp={response!r}")
    return True

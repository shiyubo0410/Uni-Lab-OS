#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试推杆控制命令
显示实际发送给串口的MODBUS-RTU命令
"""

import sys
from pathlib import Path

# 添加路径
UTILS_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(UTILS_DIR / 'skills' / 'jidianqi'))

from relay_utils import CRC16

def generate_modbus_command(device_address: int, channel: int, action: str) -> str:
    """
    生成MODBUS-RTU命令
    
    Args:
        device_address: 设备地址
        channel: 通道号 (1-16)
        action: 动作 ("on" 或 "off")
    
    Returns:
        str: 十六进制命令字符串
    """
    addr = (channel - 1) & 0xFFFF
    if action == "on":
        # 05功能码，写入单个线圈，值为1
        data = f"{device_address:02X}05{addr:04X}FF00"
    else:
        # 05功能码，写入单个线圈，值为0
        data = f"{device_address:02X}05{addr:04X}0000"
    
    # 计算CRC校验
    cmd_hex = CRC16.append_to_hex(data)
    return cmd_hex

def test_pushrod_commands(device_address: int = 1):
    """测试推杆控制命令"""
    print("=" * 60)
    print("推杆控制MODBUS-RTU命令测试")
    print("=" * 60)
    print(f"设备地址: {device_address}")
    print()
    
    # 上推杆控制
    print("【上推杆控制】")
    print("推出: 先关12，再开13")
    print(f"  关闭通道12: {generate_modbus_command(device_address, 12, 'off')}")
    print(f"  开启通道13: {generate_modbus_command(device_address, 13, 'on')}")
    print()
    print("收回: 先关13，再开12")
    print(f"  关闭通道13: {generate_modbus_command(device_address, 13, 'off')}")
    print(f"  开启通道12: {generate_modbus_command(device_address, 12, 'on')}")
    print()
    
    # 下推杆控制
    print("【下推杆控制】")
    print("推出: 先关10，再开11")
    print(f"  关闭通道10: {generate_modbus_command(device_address, 10, 'off')}")
    print(f"  开启通道11: {generate_modbus_command(device_address, 11, 'on')}")
    print()
    print("收回: 先关11，再开10")
    print(f"  关闭通道11: {generate_modbus_command(device_address, 11, 'off')}")
    print(f"  开启通道10: {generate_modbus_command(device_address, 10, 'on')}")
    print()
    
    # 旋涂仪推杆控制
    print("【旋涂仪推杆控制】")
    print("推出: 先关15，再开14")
    print(f"  关闭通道15: {generate_modbus_command(device_address, 15, 'off')}")
    print(f"  开启通道14: {generate_modbus_command(device_address, 14, 'on')}")
    print()
    print("收回: 先关14，再开15")
    print(f"  关闭通道14: {generate_modbus_command(device_address, 14, 'off')}")
    print(f"  开启通道15: {generate_modbus_command(device_address, 15, 'on')}")
    print()
    
    print("=" * 60)
    print("命令格式说明:")
    print("格式: 设备地址 + 功能码 + 寄存器地址 + 数据 + CRC校验")
    print("示例: 0105000BFF004C39")
    print("  - 01: 设备地址")
    print("  - 05: 功能码 (写入单个线圈)")
    print("  - 000B: 寄存器地址 (通道12，地址=11)")
    print("  - FF00: 数据 (FF00=开, 0000=关)")
    print("  - 4C39: CRC16校验码")
    print("=" * 60)

if __name__ == "__main__":
    test_pushrod_commands(device_address=1)
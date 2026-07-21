#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旋涂仪手动回原调试脚本
"""

import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.serial_utils import SerialClient
from skills.xuantu.xuantu_utils import SpinCoaterCommands

def test_manual_home():
    """测试手动回原功能"""
    print("=== 旋涂仪手动回原调试脚本 ===")
    
    # 串口参数
    port = "COM6"
    baudrate = 19200
    data_bits = 8
    stop_bits = 1
    parity = "EVEN"
    
    print(f"连接串口: {port} @ {baudrate} bps")
    
    # 创建串口客户端
    serial_client = SerialClient(
        port=port,
        baudrate=baudrate,
        data_bits=data_bits,
        stop_bits=stop_bits,
        parity=parity
    )
    
    # 连接串口（使用特殊流程）
    if not serial_client.connect(special_flow=True):
        print("❌ 串口连接失败")
        return
    
    try:
        print("\n🔧 测试手动回原...")
        
        # 手动回原命令
        on_command = SpinCoaterCommands.manual_home_on()
        off_command = SpinCoaterCommands.manual_home_off()
        
        print(f"置位命令: {on_command}")
        print(f"复位命令: {off_command}")
        
        # 测试不同地址
        test_addresses = ["00 13", "00 14", "00 15"]
        
        for addr in test_addresses:
            print(f"\n🔧 测试地址 {addr}...")
            
            # 生成置位和复位命令
            on_cmd = f"01 05 {addr} FF 00"
            off_cmd = f"01 05 {addr} 00 00"
            
            # 计算CRC
            from skills.xuantu.xuantu_utils import CRC16Modbus
            crc_on = CRC16Modbus.calculate_hex(on_cmd)
            crc_off = CRC16Modbus.calculate_hex(off_cmd)
            
            on_cmd_full = f"{on_cmd} {crc_on:04X}".upper()
            off_cmd_full = f"{off_cmd} {crc_off:04X}".upper()
            
            print(f"  置位命令: {on_cmd_full}")
            response1 = serial_client.send_command(on_cmd_full, wait_time=0.5)
            if response1:
                print(f"  响应: {response1}")
            else:
                print("  无响应")
            
            time.sleep(0.3)
            
            print(f"  复位命令: {off_cmd_full}")
            response2 = serial_client.send_command(off_cmd_full, wait_time=0.5)
            if response2:
                print(f"  响应: {response2}")
            else:
                print("  无响应")
            
            time.sleep(0.5)
        
        print("\n✓ 手动回原测试完成")
        
        # 测试其他命令（对比）
        print("\n=== 测试其他命令（对比）===")
        
        # 测试开启真空命令
        print("\n🔧 测试开启真空...")
        vacuum_on = SpinCoaterCommands.vacuum_on()
        vacuum_off = SpinCoaterCommands.vacuum_off()
        
        print(f"真空开启命令: {vacuum_on}")
        response_vac = serial_client.send_command(vacuum_on, wait_time=0.5)
        if response_vac:
            print(f"响应: {response_vac}")
        else:
            print("无响应 (设备可能不响应写命令)")
        
        time.sleep(0.5)
        print(f"真空关闭命令: {vacuum_off}")
        response_vac_off = serial_client.send_command(vacuum_off, wait_time=0.5)
        if response_vac_off:
            print(f"响应: {response_vac_off}")
        else:
            print("无响应 (设备可能不响应写命令)")
        
        # 测试读取当前页面号
        print("\n🔧 测试读取当前页面号...")
        # 读取命令：功能码03，地址0003，长度01
        read_page_command = "01 03 00 03 00 01 64 0B"
        print(f"读取页面命令: {read_page_command}")
        response_page = serial_client.send_command(read_page_command, wait_time=0.5)
        if response_page:
            print(f"响应: {response_page}")
            # 解析页面号
            parts = response_page.split()
            if len(parts) >= 5:
                page_value = int(parts[3], 16)
                print(f"当前页面号: {page_value} (0x{parts[3]})")
        else:
            print("无响应")
        
        # 测试读取不同M寄存器的状态
        test_registers = ["00 01", "00 02", "00 10", "00 14", "00 32"]
        for reg in test_registers:
            print(f"\n🔧 测试读取寄存器 {reg}...")
            # 读取命令：功能码01，地址reg，长度01
            cmd = f"01 01 {reg} 00 01"
            # 计算CRC
            from skills.xuantu.xuantu_utils import CRC16Modbus
            crc = CRC16Modbus.calculate_hex(cmd)
            cmd_full = f"{cmd} {crc:04X}".upper()
            print(f"读取命令: {cmd_full}")
            response = serial_client.send_command(cmd_full, wait_time=0.5)
            if response:
                print(f"响应: {response}")
            else:
                print("无响应")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
    finally:
        # 断开连接
        serial_client.disconnect()

if __name__ == "__main__":
    test_manual_home()

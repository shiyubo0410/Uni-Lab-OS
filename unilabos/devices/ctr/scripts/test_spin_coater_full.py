#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旋涂仪全流程测试脚本
测试流程：使能开启 -> 真空开启 -> 旋涂启动
"""

import sys
import time
from pathlib import Path

# 添加 scripts 和 utils 到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'utils'))

try:
    from spin_coater_controller import SpinCoaterController
    from spin_coater_utils import (
        SpinCoaterControl,
        enable_on,
        vacuum_on,
        spin_start
    )
except ImportError as e:
    print(f"❌ 无法导入模块 - {e}")
    sys.exit(1)


def test_full_workflow(port: str = "COM3", baudrate: int = 19200):
    """
    全流程测试
    
    Args:
        port: 串口号
        baudrate: 波特率
    """
    print("=" * 60)
    print("旋涂仪全流程测试")
    print("=" * 60)
    
    # 创建串口控制器
    print(f"\n📡 初始化串口控制器...")
    print(f"   串口: {port}")
    print(f"   波特率: {baudrate}")
    controller = SpinCoaterController(port=port, baudrate=baudrate)
    
    # 连接串口
    print(f"\n🔌 连接串口...")
    if not controller.connect():
        print("❌ 串口连接失败，请检查串口号和设备连接")
        return False
    print("✓ 串口连接成功")
    
    # 创建旋涂仪控制对象
    spin_control = SpinCoaterControl(controller)
    
    # 步骤1: 使能开启
    print("\n" + "-" * 60)
    print("步骤 1/3: 使能开启")
    print("-" * 60)
    if not enable_on(spin_control):
        print("❌ 使能开启失败")
        controller.disconnect()
        return False
    print("✓ 使能开启成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 步骤2: 真空开启
    print("\n" + "-" * 60)
    print("步骤 2/3: 真空开启")
    print("-" * 60)
    if not vacuum_on(spin_control):
        print("❌ 真空开启失败")
        controller.disconnect()
        return False
    print("✓ 真空开启成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 步骤3: 旋涂启动
    print("\n" + "-" * 60)
    print("步骤 3/3: 旋涂启动")
    print("-" * 60)
    if not spin_start(spin_control):
        print("❌ 旋涂启动失败")
        controller.disconnect()
        return False
    print("✓ 旋涂启动成功")
    
    # 完成
    print("\n" + "=" * 60)
    print("✓ 全流程测试完成")
    print("=" * 60)
    
    # 断开连接
    print(f"\n🔌 断开串口连接...")
    controller.disconnect()
    print("✓ 已断开连接")
    
    return True


def test_with_menu():
    """
    带菜单的测试
    """
    print("=" * 60)
    print("旋涂仪全流程测试")
    print("=" * 60)
    
    # 获取串口号
    port = input("\n请输入串口号 (默认: COM3): ").strip()
    if not port:
        port = "COM3"
    
    # 确认开始测试
    print(f"\n测试配置:")
    print(f"  串口: {port}")
    print(f"  波特率: 19200")
    print(f"\n测试流程:")
    print(f"  1. 使能开启")
    print(f"  2. 真空开启")
    print(f"  3. 旋涂启动")
    
    confirm = input("\n是否开始测试? (y/n): ").strip().lower()
    if confirm != 'y':
        print("测试已取消")
        return
    
    # 执行测试
    test_full_workflow(port=port)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='旋涂仪全流程测试')
    parser.add_argument('--port', type=str, default='COM3', help='串口号 (默认: COM3)')
    parser.add_argument('--baudrate', type=int, default=19200, help='波特率 (默认: 19200)')
    parser.add_argument('--interactive', action='store_true', help='交互式模式')
    
    args = parser.parse_args()
    
    if args.interactive:
        test_with_menu()
    else:
        test_full_workflow(port=args.port, baudrate=args.baudrate)

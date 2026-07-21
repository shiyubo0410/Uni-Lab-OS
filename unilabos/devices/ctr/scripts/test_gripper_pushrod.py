#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
夹爪和推杆功能测试脚本
测试夹爪开合、上推杆、下推杆、旋涂仪推杆的所有功能
"""

import sys
import time
from pathlib import Path

# 添加 scripts 和 utils 到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'utils'))

try:
    from gripper_pushrod_utils import (
        GripperControl,
        PushRodControl,
        gripper_open,
        gripper_close,
        gripper_toggle,
        upper_pushrod_extend,
        upper_pushrod_retract,
        upper_pushrod_toggle,
        lower_pushrod_extend,
        lower_pushrod_retract,
        lower_pushrod_toggle,
        spin_coater_pushrod_extend,
        spin_coater_pushrod_retract,
        spin_coater_pushrod_toggle
    )
except ImportError as e:
    print(f"❌ 无法导入模块 - {e}")
    sys.exit(1)


def test_gripper(gripper_port: str = "COM4", slave_id: int = 1):
    """
    测试夹爪功能
    
    Args:
        gripper_port: 夹爪串口号
        slave_id: 夹爪从站ID
    """
    print("=" * 60)
    print("夹爪功能测试")
    print("=" * 60)
    
    # 创建夹爪控制器
    print(f"\n📡 初始化夹爪控制器...")
    print(f"   串口: {gripper_port}")
    print(f"   ID: {slave_id}")
    gripper_control = GripperControl(port=gripper_port, slave_id=slave_id)
    
    # 连接夹爪
    print(f"\n🔌 连接夹爪...")
    if not gripper_control.connect():
        print("❌ 夹爪连接失败，请检查串口号和设备连接")
        return False
    print("✓ 夹爪连接成功")
    
    # 初始化夹爪
    print(f"\n🔧 初始化夹爪...")
    if not gripper_control.initialize():
        print("❌ 夹爪初始化失败")
        gripper_control.disconnect()
        return False
    print("✓ 夹爪初始化成功")
    
    # 测试1: 夹爪张开
    print("\n" + "-" * 60)
    print("测试 1/3: 夹爪张开")
    print("-" * 60)
    if not gripper_open(gripper_control, position=1000, speed=50):
        print("❌ 夹爪张开失败")
        gripper_control.disconnect()
        return False
    print("✓ 夹爪张开成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试2: 夹爪闭合
    print("\n" + "-" * 60)
    print("测试 2/3: 夹爪闭合")
    print("-" * 60)
    if not gripper_close(gripper_control, force=50, speed=30):
        print("❌ 夹爪闭合失败")
        gripper_control.disconnect()
        return False
    print("✓ 夹爪闭合成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试3: 夹爪切换
    print("\n" + "-" * 60)
    print("测试 3/3: 夹爪切换")
    print("-" * 60)
    if not gripper_toggle(gripper_control, position=1000, force=50, speed=50):
        print("❌ 夹爪切换失败")
        gripper_control.disconnect()
        return False
    print("✓ 夹爪切换成功")
    
    # 完成
    print("\n" + "=" * 60)
    print("✓ 夹爪功能测试完成")
    print("=" * 60)
    
    # 断开连接
    print(f"\n🔌 断开夹爪连接...")
    gripper_control.disconnect()
    print("✓ 已断开连接")
    
    return True


def test_pushrods(relay_ip: str = "192.168.1.100", relay_port: int = 50000):
    """
    测试推杆功能
    
    Args:
        relay_ip: 继电器IP地址
        relay_port: 继电器端口号
    """
    print("=" * 60)
    print("推杆功能测试")
    print("=" * 60)
    
    # 创建推杆控制器
    print(f"\n📡 初始化推杆控制器...")
    print(f"   IP: {relay_ip}")
    print(f"   端口: {relay_port}")
    pushrod_control = PushRodControl(relay_ip=relay_ip, relay_port=relay_port)
    
    # 测试1: 上推杆
    print("\n" + "-" * 60)
    print("测试 1/6: 上推杆推出")
    print("-" * 60)
    if not upper_pushrod_extend(pushrod_control):
        print("❌ 上推杆推出失败")
        return False
    print("✓ 上推杆推出成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试2: 上推杆收回
    print("\n" + "-" * 60)
    print("测试 2/6: 上推杆收回")
    print("-" * 60)
    if not upper_pushrod_retract(pushrod_control):
        print("❌ 上推杆收回失败")
        return False
    print("✓ 上推杆收回成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试3: 下推杆推出
    print("\n" + "-" * 60)
    print("测试 3/6: 下推杆推出")
    print("-" * 60)
    if not lower_pushrod_extend(pushrod_control):
        print("❌ 下推杆推出失败")
        return False
    print("✓ 下推杆推出成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试4: 下推杆收回
    print("\n" + "-" * 60)
    print("测试 4/6: 下推杆收回")
    print("-" * 60)
    if not lower_pushrod_retract(pushrod_control):
        print("❌ 下推杆收回失败")
        return False
    print("✓ 下推杆收回成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试5: 旋涂仪推杆推出
    print("\n" + "-" * 60)
    print("测试 5/6: 旋涂仪推杆推出")
    print("-" * 60)
    if not spin_coater_pushrod_extend(pushrod_control):
        print("❌ 旋涂仪推杆推出失败")
        return False
    print("✓ 旋涂仪推杆推出成功")
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试6: 旋涂仪推杆收回
    print("\n" + "-" * 60)
    print("测试 6/6: 旋涂仪推杆收回")
    print("-" * 60)
    if not spin_coater_pushrod_retract(pushrod_control):
        print("❌ 旋涂仪推杆收回失败")
        return False
    print("✓ 旋涂仪推杆收回成功")
    
    # 完成
    print("\n" + "=" * 60)
    print("✓ 推杆功能测试完成")
    print("=" * 60)
    
    return True


def test_all(gripper_port: str = "COM4", slave_id: int = 1,
            relay_ip: str = "192.168.1.100", relay_port: int = 50000):
    """
    测试所有功能
    
    Args:
        gripper_port: 夹爪串口号
        slave_id: 夹爪从站ID
        relay_ip: 继电器IP地址
        relay_port: 继电器端口号
    """
    print("=" * 60)
    print("夹爪和推杆全功能测试")
    print("=" * 60)
    
    # 测试夹爪
    if not test_gripper(gripper_port=gripper_port, slave_id=slave_id):
        print("❌ 夹爪测试失败")
        return False
    
    # 等待2秒
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)
    
    # 测试推杆
    if not test_pushrods(relay_ip=relay_ip, relay_port=relay_port):
        print("❌ 推杆测试失败")
        return False
    
    # 完成
    print("\n" + "=" * 60)
    print("✓ 全功能测试完成")
    print("=" * 60)
    
    return True


def test_with_menu():
    """
    带菜单的测试
    """
    print("=" * 60)
    print("夹爪和推杆功能测试")
    print("=" * 60)
    
    # 获取测试选项
    print("\n请选择测试类型:")
    print("  1 - 夹爪测试")
    print("  2 - 推杆测试")
    print("  3 - 全功能测试")
    
    choice = input("\n请输入选项 (1-3): ").strip()
    
    # 获取夹爪配置
    gripper_port = input("夹爪串口号 (默认: COM4): ").strip()
    if not gripper_port:
        gripper_port = "COM4"
    
    slave_id = input("夹爪从站ID (默认: 1): ").strip()
    if not slave_id:
        slave_id = 1
    else:
        slave_id = int(slave_id)
    
    # 获取继电器配置
    relay_ip = input("继电器IP地址 (默认: 192.168.1.100): ").strip()
    if not relay_ip:
        relay_ip = "192.168.1.100"
    
    relay_port = input("继电器端口号 (默认: 50000): ").strip()
    if not relay_port:
        relay_port = 50000
    else:
        relay_port = int(relay_port)
    
    # 确认开始测试
    print(f"\n测试配置:")
    print(f"  夹爪串口: {gripper_port}, ID: {slave_id}")
    print(f"  继电器: {relay_ip}:{relay_port}")
    
    confirm = input("\n是否开始测试? (y/n): ").strip().lower()
    if confirm != 'y':
        print("测试已取消")
        return
    
    # 执行测试
    if choice == '1':
        test_gripper(gripper_port=gripper_port, slave_id=slave_id)
    elif choice == '2':
        test_pushrods(relay_ip=relay_ip, relay_port=relay_port)
    elif choice == '3':
        test_all(gripper_port=gripper_port, slave_id=slave_id,
                 relay_ip=relay_ip, relay_port=relay_port)
    else:
        print("❌ 无效选项")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='夹爪和推杆功能测试')
    parser.add_argument('--gripper-port', type=str, default='COM4', help='夹爪串口号 (默认: COM4)')
    parser.add_argument('--slave-id', type=int, default=1, help='夹爪从站ID (默认: 1)')
    parser.add_argument('--relay-ip', type=str, default='192.168.1.100', help='继电器IP地址 (默认: 192.168.1.100)')
    parser.add_argument('--relay-port', type=int, default=50000, help='继电器端口号 (默认: 50000)')
    parser.add_argument('--test', type=str, choices=['gripper', 'pushrod', 'all'], 
                       default='all', help='测试类型: gripper, pushrod, all (默认: all)')
    parser.add_argument('--interactive', action='store_true', help='交互式模式')
    
    args = parser.parse_args()
    
    if args.interactive:
        test_with_menu()
    elif args.test == 'gripper':
        test_gripper(gripper_port=args.gripper_port, slave_id=args.slave_id)
    elif args.test == 'pushrod':
        test_pushrods(relay_ip=args.relay_ip, relay_port=args.relay_port)
    else:
        test_all(gripper_port=args.gripper_port, slave_id=args.slave_id,
                 relay_ip=args.relay_ip, relay_port=args.relay_port)

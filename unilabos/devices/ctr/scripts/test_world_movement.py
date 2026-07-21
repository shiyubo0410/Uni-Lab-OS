#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
世界坐标系移动和TCP姿态控制测试脚本
测试Z轴上下移动和末端垂直功能
"""

import sys
import os
import time
from pathlib import Path

# 添加路径
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'utils'))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'skills' / 'changguangxi'))

try:
    from robot_utils import CGXiRobot
    from robot_control_utils import create_robot_controller
except ImportError as e:
    print(f"❌ 无法导入模块 - {e}")
    sys.exit(1)


def test_world_z_movement(controller):
    """测试世界坐标系Z轴移动"""
    print("\n" + "=" * 70)
    print("📍 测试1: 世界坐标系Z轴移动（上下）")
    print("=" * 70)
    
    print("\n当前位置:")
    success, pose = controller.robot.get_tcp_pose()
    if success:
        print(f"  X={pose[0]:.2f}, Y={pose[1]:.2f}, Z={pose[2]:.2f}")
    
    # 向上移动50mm
    print("\n1️⃣ 向上移动50mm...")
    controller.move_world_z(50.0, speed=20.0, block=True)
    time.sleep(1)
    
    # 向下移动50mm（回到原位）
    print("\n2️⃣ 向下移动50mm（回到原位）...")
    controller.move_world_z(-50.0, speed=20.0, block=True)
    time.sleep(1)
    
    # 向上移动100mm
    print("\n3️⃣ 向上移动100mm...")
    controller.move_world_z(100.0, speed=30.0, block=True)
    
    print("\n✓ Z轴移动测试完成")
    return True


def test_world_relative_movement(controller):
    """测试世界坐标系相对移动"""
    print("\n" + "=" * 70)
    print("📍 测试2: 世界坐标系相对移动")
    print("=" * 70)
    
    print("\n当前位置:")
    success, pose = controller.robot.get_tcp_pose()
    if success:
        print(f"  X={pose[0]:.2f}, Y={pose[1]:.2f}, Z={pose[2]:.2f}")
    
    # X方向移动
    print("\n1️⃣ X轴正方向移动30mm...")
    controller.move_world_relative(dx=30.0, dy=0, dz=0, speed=20.0, block=True)
    time.sleep(1)
    
    # Y方向移动
    print("\n2️⃣ Y轴正方向移动30mm...")
    controller.move_world_relative(dx=0, dy=30.0, dz=0, speed=20.0, block=True)
    time.sleep(1)
    
    # XYZ同时移动（回到原位附近）
    print("\n3️⃣ XYZ同时移动...")
    controller.move_world_relative(dx=-30.0, dy=-30.0, dz=0, speed=20.0, block=True)
    
    print("\n✓ 相对移动测试完成")
    return True


def test_tcp_vertical(controller):
    """测试TCP末端垂直"""
    print("\n" + "=" * 70)
    print("📐 测试3: TCP末端垂直向下")
    print("=" * 70)
    
    print("\n当前姿态:")
    success, pose = controller.robot.get_tcp_pose()
    if success:
        print(f"  Rx={pose[3]:.2f}°, Ry={pose[4]:.2f}°, Rz={pose[5]:.2f}°")
    
    # 设置垂直向下
    print("\n1️⃣ 设置TCP末端垂直向下...")
    controller.set_tcp_vertical(speed=20.0, block=True)
    time.sleep(1)
    
    # 查看新姿态
    print("\n新姿态:")
    success, pose = controller.robot.get_tcp_pose()
    if success:
        print(f"  Rx={pose[3]:.2f}°, Ry={pose[4]:.2f}°, Rz={pose[5]:.2f}°")
    
    print("\n✓ TCP垂直设置完成")
    return True


def test_tcp_orientation(controller):
    """测试TCP任意姿态设置"""
    print("\n" + "=" * 70)
    print("📐 测试4: TCP任意姿态设置")
    print("=" * 70)
    
    print("\n当前姿态:")
    success, pose = controller.robot.get_tcp_pose()
    if success:
        print(f"  Rx={pose[3]:.2f}°, Ry={pose[4]:.2f}°, Rz={pose[5]:.2f}°")
    
    # 设置水平姿态
    print("\n1️⃣ 设置TCP水平（Rx=90°）...")
    controller.set_tcp_orientation(rx=90.0, ry=0.0, rz=0.0, speed=20.0, block=True)
    time.sleep(1)
    
    # 查看新姿态
    print("\n新姿态:")
    success, pose = controller.robot.get_tcp_pose()
    if success:
        print(f"  Rx={pose[3]:.2f}°, Ry={pose[4]:.2f}°, Rz={pose[5]:.2f}°")
    
    # 设置垂直向下
    print("\n2️⃣ 设置TCP垂直向下（Rx=180°）...")
    controller.set_tcp_orientation(rx=180.0, ry=0.0, rz=0.0, speed=20.0, block=True)
    
    print("\n✓ TCP姿态设置测试完成")
    return True


def demo_pick_place(controller):
    """
    演示取放动作
    使用Z轴移动和垂直姿态
    """
    print("\n" + "=" * 70)
    print("🎯 演示: 取放动作")
    print("=" * 70)
    
    print("\n📋 动作流程:")
    print("  1. 设置TCP垂直向下")
    print("  2. 下降到取料位置")
    print("  3. 夹取（模拟）")
    print("  4. 上升")
    print("  5. 移动到放料位置")
    print("  6. 下降")
    print("  7. 释放（模拟）")
    print("  8. 上升复位")
    
    # 1. 设置垂直
    print("\n1️⃣ 设置TCP垂直向下...")
    controller.set_tcp_vertical(speed=30.0, block=True)
    time.sleep(0.5)
    
    # 2. 下降
    print("\n2️⃣ 下降50mm到取料位置...")
    controller.move_world_z(-50.0, speed=20.0, block=True)
    time.sleep(0.5)
    
    # 3. 夹取（模拟）
    print("\n3️⃣ 夹取物料（模拟，等待1秒）...")
    time.sleep(1)
    
    # 4. 上升
    print("\n4️⃣ 上升50mm...")
    controller.move_world_z(50.0, speed=20.0, block=True)
    time.sleep(0.5)
    
    # 5. 移动（这里简化，实际应该移动到放料位置）
    print("\n5️⃣ 移动到放料位置（X+100mm）...")
    controller.move_world_relative(dx=100.0, dy=0, dz=0, speed=30.0, block=True)
    time.sleep(0.5)
    
    # 6. 下降
    print("\n6️⃣ 下降50mm到放料位置...")
    controller.move_world_z(-50.0, speed=20.0, block=True)
    time.sleep(0.5)
    
    # 7. 释放（模拟）
    print("\n7️⃣ 释放物料（模拟，等待1秒）...")
    time.sleep(1)
    
    # 8. 上升复位
    print("\n8️⃣ 上升复位...")
    controller.move_world_z(50.0, speed=20.0, block=True)
    
    print("\n✓ 取放动作演示完成")
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='世界坐标系移动和TCP姿态控制测试')
    parser.add_argument('--ip', type=str, default='192.168.6.6', help='机器人IP (默认: 192.168.6.6)')
    parser.add_argument('--port', type=int, default=2323, help='端口号 (默认: 2323)')
    parser.add_argument('--password', type=str, default='123', help='连接密码 (默认: 123)')
    parser.add_argument('--virtual', action='store_true', help='使用虚拟臂模式')
    parser.add_argument('--test', type=str, 
                       choices=['z', 'relative', 'vertical', 'orientation', 'demo', 'all'],
                       default='all', help='测试类型')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🤖 世界坐标系移动和TCP姿态控制测试")
    print("=" * 70)
    
    # 创建机器人实例
    if args.virtual:
        print("\n📡 使用虚拟臂模式")
        robot = CGXiRobot(virtual=True)
    else:
        print(f"\n📡 连接真实机器人: {args.ip}:{args.port}")
        robot = CGXiRobot(ip=args.ip, port=args.port, password=args.password)
    
    # 连接机器人
    print("\n🔌 连接机器人...")
    if not robot.connect():
        print("❌ 连接失败")
        print("\n💡 提示:")
        print("  - 确认机器人已开机并连接到网络")
        print("  - 检查IP地址和端口号是否正确")
        print("  - 使用 --virtual 参数测试虚拟臂模式")
        return 1
    
    print("✓ 连接成功")
    
    # 上电和使能
    print("\n⚡ 检查机器人状态...")
    success, mode = robot.get_robot_mode()
    if not success:
        print("❌ 无法获取机器人状态")
        robot.disconnect()
        return 1
    
    print(f"当前状态码: {mode}")
    
    if mode == 6:
        print("机器人未上电，开始上电...")
        if not robot.power_on():
            print("❌ 上电失败")
            robot.disconnect()
            return 1
        
        # 等待上电完成
        print("⏳ 等待上电完成...")
        for i in range(150):
            time.sleep(1)
            success, mode = robot.get_robot_mode()
            if success and mode == 8:
                print(f"✓ 上电完成 (耗时 {i+1} 秒)")
                break
            if (i + 1) % 10 == 0:
                print(f"  已等待 {i+1} 秒...")
    
    if mode == 8 or (success and mode != 103):
        print("\n🔓 机器人使能...")
        if not robot.enable():
            print("❌ 使能失败")
            robot.disconnect()
            return 1
        
        # 等待使能完成
        print("⏳ 等待使能完成...")
        for i in range(30):
            time.sleep(1)
            success, mode = robot.get_robot_mode()
            if success and mode == 103:
                print(f"✓ 使能完成 (耗时 {i+1} 秒)")
                break
    
    print("\n✓ 机器人准备就绪")
    
    # 创建控制器
    controller = create_robot_controller(robot)
    
    try:
        # 执行测试
        if args.test == 'z':
            test_world_z_movement(controller)
        elif args.test == 'relative':
            test_world_relative_movement(controller)
        elif args.test == 'vertical':
            test_tcp_vertical(controller)
        elif args.test == 'orientation':
            test_tcp_orientation(controller)
        elif args.test == 'demo':
            demo_pick_place(controller)
        elif args.test == 'all':
            test_world_z_movement(controller)
            test_world_relative_movement(controller)
            test_tcp_vertical(controller)
            test_tcp_orientation(controller)
            demo_pick_place(controller)
        
        print("\n" + "=" * 70)
        print("✓ 所有测试完成")
        print("=" * 70)
    
    except KeyboardInterrupt:
        print("\n\n👋 用户中断")
    
    finally:
        # 安全关闭
        print("\n🔒 安全关闭机器人...")
        try:
            robot.disable()
        except:
            pass
        time.sleep(0.5)
        robot.disconnect()
        print("✓ 测试完成")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

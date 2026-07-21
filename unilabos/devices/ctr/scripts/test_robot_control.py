#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人控制功能测试脚本
测试路点记录、路点间移动、键盘控制功能
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
    from robot_control_utils import (
        RobotController, 
        KeyboardController,
        create_robot_controller,
        create_keyboard_controller,
        Waypoint
    )
except ImportError as e:
    print(f"❌ 无法导入模块 - {e}")
    sys.exit(1)


def test_record_waypoint(robot: CGXiRobot):
    """测试路点记录功能"""
    print("\n" + "=" * 70)
    print("📍 测试1: 路点记录功能")
    print("=" * 70)
    
    controller = create_robot_controller(robot)
    
    # 记录当前路点
    print("\n记录当前路点...")
    wp = controller.record_current_waypoint("测试点1", "这是一个测试路点")
    
    if wp:
        print(f"✓ 路点记录成功")
        print(f"  名称: {wp.name}")
        print(f"  关节: {wp.joint_pos}")
        print(f"  TCP: {wp.tcp_pose}")
        return True
    else:
        print("❌ 路点记录失败")
        return False


def test_waypoint_management(robot: CGXiRobot):
    """测试路点管理功能"""
    print("\n" + "=" * 70)
    print("📋 测试2: 路点管理功能")
    print("=" * 70)
    
    controller = create_robot_controller(robot)
    
    # 记录多个路点
    print("\n记录多个路点...")
    controller.record_current_waypoint("起点", "起始位置")
    time.sleep(0.5)
    controller.record_current_waypoint("中间点", "中间位置")
    time.sleep(0.5)
    controller.record_current_waypoint("终点", "目标位置")
    
    # 列出所有路点
    print("\n列出所有路点:")
    controller.list_waypoints()
    
    # 保存路点
    save_path = SCRIPT_DIR / "test_waypoints.json"
    controller.save_waypoints(str(save_path))
    
    # 清空路点
    controller.clear_waypoints()
    print(f"\n路点数量: {len(controller.waypoints)}")
    
    # 加载路点
    controller.load_waypoints(str(save_path))
    print(f"路点数量: {len(controller.waypoints)}")
    
    # 清理测试文件
    if save_path.exists():
        save_path.unlink()
    
    return True


def test_move_between_waypoints(robot: CGXiRobot):
    """测试路点间移动功能"""
    print("\n" + "=" * 70)
    print("🚀 测试3: 路点间移动功能")
    print("=" * 70)
    
    controller = create_robot_controller(robot)
    
    # 记录两个路点（模拟）
    print("\n创建测试路点...")
    
    # 获取当前位置作为起点
    success, joint_pos = robot.get_joint_position()
    success2, tcp_pose = robot.get_tcp_pose()
    
    if not success or not success2:
        print("❌ 无法获取当前位置")
        return False
    
    # 创建起点路点
    wp1 = Waypoint("起点", joint_pos.copy(), tcp_pose.copy(), "起始位置")
    controller.waypoints.append(wp1)
    
    # 创建终点路点（偏移）
    joint_pos[0] += 10  # J1 +10度
    tcp_pose[0] += 50   # X +50mm
    wp2 = Waypoint("终点", joint_pos, tcp_pose, "目标位置")
    controller.waypoints.append(wp2)
    
    print(f"起点: J1={wp1.joint_pos[0]:.2f}°, X={wp1.tcp_pose[0]:.2f}mm")
    print(f"终点: J1={wp2.joint_pos[0]:.2f}°, X={wp2.tcp_pose[0]:.2f}mm")
    
    # 测试路点间移动（使用虚拟臂，不会真动）
    print("\n测试路点间移动 (MoveJ)...")
    # 注意：在虚拟模式下，运动命令会返回成功但不会实际移动
    result = controller.move_between_waypoints(0, 1, speed=30, use_joint_space=True, block=True)
    
    if result:
        print("✓ 路点间移动命令发送成功")
    else:
        print("❌ 路点间移动失败")
    
    return True


def test_keyboard_control(robot: CGXiRobot, controller: RobotController = None):
    """测试键盘控制功能"""
    print("\n" + "=" * 70)
    print("🎮 测试4: 键盘控制功能")
    print("=" * 70)
    
    kb = create_keyboard_controller(robot)
    
    # 设置路点记录回调
    if controller:
        def record_wp():
            name = input("路点名称 (默认自动命名): ").strip()
            desc = input("描述信息: ").strip()
            controller.record_current_waypoint(name or None, desc)
        kb.waypoint_callback = record_wp
    
    # 打印帮助信息
    kb.print_help()
    
    print("\n🚀 启动键盘控制循环...")
    print("  按 ? 查看帮助，按 Q/ESC 退出")
    
    # 启动实际控制
    kb.run()
    
    print("\n✓ 键盘控制功能测试完成")
    return True


def interactive_demo(robot: CGXiRobot):
    """交互式演示"""
    print("\n" + "=" * 70)
    print("🎯 交互式演示")
    print("=" * 70)
    
    controller = create_robot_controller(robot)
    
    print("\n请选择要测试的功能:")
    print("  1 - 记录当前路点")
    print("  2 - 列出所有路点")
    print("  3 - 移动到指定路点")
    print("  4 - 路点间移动")
    print("  5 - 启动键盘控制")
    print("  6 - 保存/加载路点")
    print("  7 - 世界坐标系Z轴移动（上下）")
    print("  8 - 世界坐标系相对移动")
    print("  9 - 设置TCP末端垂直向下")
    print("  10 - 设置TCP任意姿态")
    print("  0 - 退出")
    
    while True:
        choice = input("\n请输入选项 (0-6): ").strip()
        
        if choice == '0':
            print("退出演示")
            break
        
        elif choice == '1':
            name = input("路点名称 (默认自动命名): ").strip()
            desc = input("描述信息: ").strip()
            controller.record_current_waypoint(name or None, desc)
        
        elif choice == '2':
            controller.list_waypoints()
        
        elif choice == '3':
            if not controller.waypoints:
                print("❌ 没有记录的路点")
                continue
            controller.list_waypoints()
            idx = input("请输入路点索引: ").strip()
            try:
                idx = int(idx)
                use_joint = input("使用关节空间运动? (y/n, 默认y): ").strip().lower() != 'n'
                controller.move_to_waypoint(idx, use_joint_space=use_joint, block=True)
            except ValueError:
                print("❌ 无效的索引")
        
        elif choice == '4':
            if len(controller.waypoints) < 2:
                print("❌ 需要至少2个路点")
                continue
            controller.list_waypoints()
            start = input("起始路点索引: ").strip()
            end = input("目标路点索引: ").strip()
            try:
                start, end = int(start), int(end)
                use_joint = input("使用关节空间运动? (y/n, 默认y): ").strip().lower() != 'n'
                controller.move_between_waypoints(start, end, use_joint_space=use_joint, block=True)
            except ValueError:
                print("❌ 无效的索引")
        
        elif choice == '5':
            test_keyboard_control(robot, controller)
        
        elif choice == '6':
            print("\n  1 - 保存路点")
            print("  2 - 加载路点")
            print("  3 - 验证路点文件")
            print("  4 - 导出为CSV")
            print("  5 - 导出为TXT")
            sub_choice = input("请选择: ").strip()
            
            if sub_choice == '1':
                print("\n选择保存格式:")
                print("  1 - JSON (默认)")
                print("  2 - CSV")
                print("  3 - TXT")
                format_choice = input("请选择: ").strip()
                
                format_map = {'1': 'json', '2': 'csv', '3': 'txt'}
                fmt = format_map.get(format_choice, 'json')
                
                path = input(f"保存路径 (默认: waypoints.{fmt}): ").strip()
                path = path or f"waypoints.{fmt}"
                
                append = input("追加到现有文件? (y/n, 默认n): ").strip().lower() == 'y'
                backup = input("备份现有文件? (y/n, 默认y): ").strip().lower() != 'n'
                
                controller.save_waypoints(path, format=fmt, append=append, backup=backup)
            
            elif sub_choice == '2':
                print("\n选择加载格式:")
                print("  1 - 自动检测 (默认)")
                print("  2 - JSON")
                print("  3 - CSV")
                print("  4 - TXT")
                format_choice = input("请选择: ").strip()
                
                format_map = {'1': 'auto', '2': 'json', '3': 'csv', '4': 'txt'}
                fmt = format_map.get(format_choice, 'auto')
                
                path = input("加载路径: ").strip()
                if not path:
                    print("❌ 请输入文件路径")
                    continue
                
                # 先验证文件
                valid, msg = controller.validate_waypoints_file(path)
                if not valid:
                    print(f"❌ {msg}")
                    continue
                else:
                    print(f"✓ {msg}")
                
                append = input("追加到现有路点? (y/n, 默认n): ").strip().lower() == 'y'
                replace = input("替换现有路点? (y/n, 默认n): ").strip().lower() == 'y'
                
                controller.load_waypoints(path, format=fmt, append=append, replace=replace)
            
            elif sub_choice == '3':
                path = input("文件路径: ").strip()
                if path:
                    valid, msg = controller.validate_waypoints_file(path)
                    if valid:
                        print(f"✓ {msg}")
                    else:
                        print(f"❌ {msg}")
            
            elif sub_choice == '4':
                path = input("保存路径 (默认: waypoints.csv): ").strip()
                path = path or "waypoints.csv"
                controller.export_waypoints(path, format="csv")
                print(f"💡 提示: CSV文件可以用Excel打开编辑")
            
            elif sub_choice == '5':
                path = input("保存路径 (默认: waypoints.txt): ").strip()
                path = path or "waypoints.txt"
                controller.export_waypoints(path, format="txt")
                print(f"💡 提示: TXT文件是纯文本格式，易于阅读")
        
        elif choice == '7':
            print("\n📍 世界坐标系Z轴移动（上下）")
            distance = input("移动距离 (mm, 正值向上, 负值向下): ").strip()
            try:
                distance = float(distance)
                speed = input("速度 (默认30): ").strip()
                speed = float(speed) if speed else 30.0
                controller.move_world_z(distance, speed=speed, block=True)
            except ValueError:
                print("❌ 无效的输入")
        
        elif choice == '8':
            print("\n📍 世界坐标系相对移动")
            dx = input("X轴偏移 (mm, 默认0): ").strip()
            dy = input("Y轴偏移 (mm, 默认0): ").strip()
            dz = input("Z轴偏移 (mm, 默认0): ").strip()
            try:
                dx = float(dx) if dx else 0.0
                dy = float(dy) if dy else 0.0
                dz = float(dz) if dz else 0.0
                speed = input("速度 (默认30): ").strip()
                speed = float(speed) if speed else 30.0
                controller.move_world_relative(dx, dy, dz, speed=speed, block=True)
            except ValueError:
                print("❌ 无效的输入")
        
        elif choice == '9':
            print("\n📐 设置TCP末端垂直向下")
            speed = input("速度 (默认30): ").strip()
            speed = float(speed) if speed else 30.0
            controller.set_tcp_vertical(speed=speed, block=True)
        
        elif choice == '10':
            print("\n📐 设置TCP任意姿态")
            rx = input("绕X轴旋转角度 Rx (°): ").strip()
            ry = input("绕Y轴旋转角度 Ry (°): ").strip()
            rz = input("绕Z轴旋转角度 Rz (°): ").strip()
            try:
                rx = float(rx)
                ry = float(ry)
                rz = float(rz)
                speed = input("速度 (默认30): ").strip()
                speed = float(speed) if speed else 30.0
                controller.set_tcp_orientation(rx, ry, rz, speed=speed, block=True)
            except ValueError:
                print("❌ 无效的输入")
        
        else:
            print("❌ 无效选项")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='机器人控制功能测试')
    parser.add_argument('--ip', type=str, default='192.168.6.6', help='机器人IP (默认: 192.168.6.6 真实机械臂)')
    parser.add_argument('--port', type=int, default=2323, help='端口号 (默认: 2323)')
    parser.add_argument('--password', type=str, default='123', help='连接密码 (默认: 123)')
    parser.add_argument('--virtual', action='store_true', help='使用虚拟臂模式')
    parser.add_argument('--test', type=str, choices=['record', 'manage', 'move', 'keyboard', 'all', 'interactive'],
                       default='interactive', help='测试类型')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🤖 CGXi 机器人控制功能测试")
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
    
    # 状态码说明:
    # 6 = JointPowerOff (本体未上电)
    # 7 = JointPowerOn (上电过程)
    # 8 = JointIdle (上电完成，空闲)
    # 103 = ProgramStop (使能完成，程序停止)
    
    if mode == 6:
        print("机器人未上电，开始上电...")
        if not robot.power_on():
            print("❌ 上电失败，尝试故障复位...")
            robot.fault_reset()
            time.sleep(1)
            if not robot.power_on():
                print("❌ 上电仍然失败")
                robot.disconnect()
                return 1
    elif mode == 8:
        print("机器人已上电，跳过上电步骤")
    elif mode == 103:
        print("机器人已上电并使能，跳过上电和使能步骤")
    else:
        print(f"⚠️ 机器人状态异常 (mode={mode})，尝试故障复位...")
        robot.fault_reset()
        time.sleep(1)
        
        # 复位后重新检查状态
        success, mode = robot.get_robot_mode()
        if not success:
            print("❌ 无法获取机器人状态")
            robot.disconnect()
            return 1
        
        print(f"复位后状态码: {mode}")
        
        if mode == 6:
            if not robot.power_on():
                print("❌ 上电失败")
                robot.disconnect()
                return 1
        elif mode == 8:
            print("机器人已上电")
        elif mode == 103:
            print("机器人已上电并使能")
        else:
            print(f"❌ 机器人状态仍异常 (mode={mode})")
            robot.disconnect()
            return 1
    
    # 等待机器人上电完成（状态码变为8）
    power_on_wait = 150
    print(f"\n⏳ 等待机器人上电完成... (最多{power_on_wait}秒)")
    for i in range(power_on_wait):
        time.sleep(1)
        success, mode = robot.get_robot_mode()
        if success and mode == 8:
            print(f"✓ 上电完成 (耗时 {i + 1} 秒)")
            break
        elif success and mode == 103:
            print(f"✓ 机器人已上电并使能 (耗时 {i + 1} 秒)")
            print("\n✓ 机器人准备就绪")
            break
        elif (i + 1) % 10 == 0:
            print(f"  已等待 {i + 1}/{power_on_wait} 秒，当前状态码: {mode}")
    else:
        print(f"❌ 等待超时，当前状态码: {mode}")
        robot.disconnect()
        return 1
    
    # 如果状态是8，执行使能
    if mode == 8:
        print("\n🔓 机器人使能...")
        if not robot.enable():
            print("❌ 使能失败，尝试故障复位后重试...")
            robot.fault_reset()
            time.sleep(2)
            if not robot.enable():
                print("❌ 使能仍然失败")
                robot.power_off()
                robot.disconnect()
                return 1
        
        # 等待使能完成（状态码变为103）
        print("⏳ 等待使能完成...")
        enable_wait = 30
        for i in range(enable_wait):
            time.sleep(1)
            success, mode = robot.get_robot_mode()
            if success and mode == 103:
                print(f"✓ 使能完成 (耗时 {i + 1} 秒)")
                break
            elif (i + 1) % 5 == 0:
                print(f"  已等待 {i + 1}/{enable_wait} 秒，当前状态码: {mode}")
        else:
            print(f"❌ 使能超时，当前状态码: {mode}")
            robot.disconnect()
            return 1
    
    print("\n✓ 机器人准备就绪")
    
    try:
        # 执行测试
        if args.test == 'record':
            test_record_waypoint(robot)
        elif args.test == 'manage':
            test_waypoint_management(robot)
        elif args.test == 'move':
            test_move_between_waypoints(robot)
        elif args.test == 'keyboard':
            test_keyboard_control(robot)
        elif args.test == 'all':
            test_record_waypoint(robot)
            test_waypoint_management(robot)
            test_move_between_waypoints(robot)
            test_keyboard_control(robot)
        else:  # interactive
            interactive_demo(robot)
    
    except KeyboardInterrupt:
        print("\n\n👋 用户中断")
    
    finally:
        # 安全关闭
        print("\n" + "=" * 70)
        print("🔒 安全关闭机器人...")
        print("=" * 70)
        
        print("停止运动...")
        # 尝试停止运动
        try:
            robot.disable()
        except:
            pass
        
        time.sleep(0.5)
        
        print("断开连接...")
        robot.disconnect()
        print("✓ 测试完成")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGXi 协作机器人控制示例
"""

from robot_utils import CGXiRobot, RobotMode, ScriptStatus, MoveStatus
import time


def example_basic_connection():
    """基本连接示例"""
    print("=" * 60)
    print("基本连接示例")
    print("=" * 60)
    
    # 创建机器人实例（虚拟臂）
    robot = CGXiRobot(virtual=True)
    
    # 连接
    print("\n【连接机器人】")
    if robot.connect():
        print("连接成功")
        
        # 断开连接
        print("\n【断开连接】")
        robot.disconnect()
    else:
        print("连接失败")


def example_power_control():
    """电源与使能控制示例"""
    print("\n" + "=" * 60)
    print("电源与使能控制示例")
    print("=" * 60)
    
    robot = CGXiRobot(virtual=True)
    
    if robot.connect():
        print("\n【电源控制】")
        robot.power_on()
        time.sleep(2)
        
        print("\n【使能控制】")
        robot.enable()
        time.sleep(2)
        
        print("\n【去使能】")
        robot.disable()
        time.sleep(2)
        
        print("\n【断电】")
        robot.power_off()
        
        robot.disconnect()


def example_status_read():
    """状态读取示例"""
    print("\n" + "=" * 60)
    print("状态读取示例")
    print("=" * 60)
    
    robot = CGXiRobot(virtual=True)
    
    if robot.connect():
        print("\n【机器人状态】")
        success, mode = robot.get_robot_mode()
        if success:
            mode_name = RobotMode.__dict__.get(f"_{mode}", f"未知({mode})")
            print(f"  状态码: {mode}")
            print(f"  状态名称: {mode_name}")
        
        print("\n【关节角度】")
        success, joint_pos = robot.get_joint_position()
        if success:
            print(f"  J1: {joint_pos[0]:.2f}°")
            print(f"  J2: {joint_pos[1]:.2f}°")
            print(f"  J3: {joint_pos[2]:.2f}°")
            print(f"  J4: {joint_pos[3]:.2f}°")
            print(f"  J5: {joint_pos[4]:.2f}°")
            print(f"  J6: {joint_pos[5]:.2f}°")
        
        print("\n【TCP位姿】")
        success, tcp_pose = robot.get_tcp_pose()
        if success:
            print(f"  X: {tcp_pose[0]:.2f} mm")
            print(f"  Y: {tcp_pose[1]:.2f} mm")
            print(f"  Z: {tcp_pose[2]:.2f} mm")
            print(f"  Rx: {tcp_pose[3]:.2f}°")
            print(f"  Ry: {tcp_pose[4]:.2f}°")
            print(f"  Rz: {tcp_pose[5]:.2f}°")
        
        print("\n【运动状态】")
        success, move_status = robot.get_move_status()
        if success:
            status_name = "运动中" if move_status == 1 else "停止"
            print(f"  状态码: {move_status}")
            print(f"  状态名称: {status_name}")
        
        print("\n【速度百分比】")
        success, speed = robot.get_speed_percent()
        if success:
            print(f"  速度: {speed}%")
        
        robot.disconnect()


def example_movej():
    """MoveJ 运动示例"""
    print("\n" + "=" * 60)
    print("MoveJ 运动示例")
    print("=" * 60)
    
    robot = CGXiRobot(virtual=True)
    
    if robot.connect():
        print("\n【上电和使能】")
        robot.power_on()
        time.sleep(2)
        robot.enable()
        time.sleep(2)
        
        print("\n【MoveJ 运动到初始位置】")
        joint_pos = [0, 0, 90, 0, -90, 0]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【MoveJ 运动到位置1】")
        joint_pos = [10, 10, 80, 10, -80, 10]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【MoveJ 运动到位置2】")
        joint_pos = [-10, -10, 100, -10, -100, -10]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【去使能和断电】")
        robot.disable()
        time.sleep(2)
        robot.power_off()
        
        robot.disconnect()


def example_movel():
    """MoveL 运动示例"""
    print("\n" + "=" * 60)
    print("MoveL 运动示例")
    print("=" * 60)
    
    robot = CGXiRobot(virtual=True)
    
    if robot.connect():
        print("\n【上电和使能】")
        robot.power_on()
        time.sleep(2)
        robot.enable()
        time.sleep(2)
        
        print("\n【MoveL 运动到位置1】")
        pose = [300, 0, 400, 0, 180, 0]
        robot.movel(pose)
        time.sleep(3)
        
        print("\n【MoveL 运动到位置2】")
        pose = [400, 100, 400, 0, 180, 0]
        robot.movel(pose)
        time.sleep(3)
        
        print("\n【MoveL 运动到位置3】")
        pose = [400, 200, 400, 0, 180, 0]
        robot.movel(pose)
        time.sleep(3)
        
        print("\n【去使能和断电】")
        robot.disable()
        time.sleep(2)
        robot.power_off()
        
        robot.disconnect()


def example_speed_control():
    """速度控制示例"""
    print("\n" + "=" * 60)
    print("速度控制示例")
    print("=" * 60)
    
    robot = CGXiRobot(virtual=True)
    
    if robot.connect():
        print("\n【上电和使能】")
        robot.power_on()
        time.sleep(2)
        robot.enable()
        time.sleep(2)
        
        print("\n【设置速度为 50%】")
        robot.set_speed_percent(50)
        time.sleep(1)
        
        print("\n【MoveJ 运动】")
        joint_pos = [0, 0, 90, 0, -90, 0]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【设置速度为 30%】")
        robot.set_speed_percent(30)
        time.sleep(1)
        
        print("\n【MoveJ 运动】")
        joint_pos = [10, 10, 80, 10, -80, 10]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【设置速度为 100%】")
        robot.set_speed_percent(100)
        time.sleep(1)
        
        print("\n【MoveJ 运动】")
        joint_pos = [0, 0, 90, 0, -90, 0]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【去使能和断电】")
        robot.disable()
        time.sleep(2)
        robot.power_off()
        
        robot.disconnect()


def example_project_control():
    """工程控制示例"""
    print("\n" + "=" * 60)
    print("工程控制示例")
    print("=" * 60)
    
    robot = CGXiRobot(virtual=True)
    
    if robot.connect():
        print("\n【加载程序】")
        program = b"function main()\nmovej({0,0,90,0,-90,0})\nend"
        robot.download_program(program)
        
        print("\n【运行程序】")
        robot.play()
        time.sleep(2)
        
        print("\n【查询脚本状态】")
        success, status = robot.get_script_status()
        if success:
            status_name = ScriptStatus.__dict__.get(f"_{status}", f"未知({status})")
            print(f"  状态码: {status}")
            print(f"  状态名称: {status_name}")
        
        print("\n【暂停程序】")
        robot.pause()
        time.sleep(2)
        
        print("\n【恢复程序】")
        robot.resume()
        time.sleep(2)
        
        print("\n【停止程序】")
        robot.stop()
        
        robot.disconnect()


def example_context_manager():
    """上下文管理器示例"""
    print("\n" + "=" * 60)
    print("上下文管理器示例")
    print("=" * 60)
    
    print("\n【使用 with 语句自动管理连接】")
    with CGXiRobot(virtual=True) as robot:
        print("连接成功")
        
        # 执行操作
        print("\n【上电和使能】")
        robot.power_on()
        time.sleep(2)
        robot.enable()
        time.sleep(2)
        
        print("\n【MoveJ 运动】")
        joint_pos = [0, 0, 90, 0, -90, 0]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【去使能和断电】")
        robot.disable()
        time.sleep(2)
        robot.power_off()
    
    print("\n连接已自动断开")


def example_complete_workflow():
    """完整工作流程示例"""
    print("\n" + "=" * 60)
    print("完整工作流程示例")
    print("=" * 60)
    
    with CGXiRobot(virtual=True) as robot:
        print("\n【步骤1】上电")
        robot.power_on()
        time.sleep(2)
        
        print("\n【步骤2】使能")
        robot.enable()
        time.sleep(2)
        
        print("\n【步骤3】设置速度为 50%")
        robot.set_speed_percent(50)
        
        print("\n【步骤4】MoveJ 运动到初始位置")
        joint_pos = [0, 0, 90, 0, -90, 0]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【步骤5】MoveL 运动到工作位置1】")
        pose = [300, 0, 400, 0, 180, 0]
        robot.movel(pose)
        time.sleep(3)
        
        print("\n【步骤6】MoveL 运动到工作位置2】")
        pose = [400, 100, 400, 0, 180, 0]
        robot.movel(pose)
        time.sleep(3)
        
        print("\n【步骤7】MoveL 运动到工作位置3】")
        pose = [400, 200, 400, 0, 180, 0]
        robot.movel(pose)
        time.sleep(3)
        
        print("\n【步骤8】MoveJ 返回初始位置")
        joint_pos = [0, 0, 90, 0, -90, 0]
        robot.movej(joint_pos)
        time.sleep(3)
        
        print("\n【步骤9】去使能")
        robot.disable()
        time.sleep(2)
        
        print("\n【步骤10】断电")
        robot.power_off()


def example_error_handling():
    """错误处理示例"""
    print("\n" + "=" * 60)
    print("错误处理示例")
    print("=" * 60)
    
    print("\n【尝试连接不存在的机器人】")
    robot = CGXiRobot(ip="192.168.1.1", port=2323)
    
    if not robot.connect():
        print("连接失败，使用虚拟臂代替")
        robot = CGXiRobot(virtual=True)
        robot.connect()
    
    print("\n【执行操作】")
    robot.power_on()
    time.sleep(2)
    
    print("\n【故障复位】")
    robot.fault_reset()
    
    print("\n【断开连接】")
    robot.disconnect()


def example_real_robot():
    """实际机器人连接示例"""
    print("\n" + "=" * 60)
    print("实际机器人连接示例")
    print("=" * 60)
    
    print("\n【创建实际机器人实例】")
    print("注意: 请确保机器人已连接到网络")
    
    robot = CGXiRobot(ip="192.168.6.6", port=2323, password="123")
    
    if robot.connect():
        print("连接成功")
        
        print("\n【读取机器人状态】")
        success, mode = robot.get_robot_mode()
        if success:
            print(f"机器人状态: {mode}")
        
        print("\n【读取关节角度】")
        success, joint_pos = robot.get_joint_position()
        if success:
            print(f"关节角度: {joint_pos}")
        
        print("\n【读取TCP位姿】")
        success, tcp_pose = robot.get_tcp_pose()
        if success:
            print(f"TCP位姿: {tcp_pose}")
        
        robot.disconnect()
    else:
        print("连接失败，请检查网络连接和机器人状态")


if __name__ == '__main__':
    print("=" * 60)
    print("CGXi 协作机器人控制示例程序")
    print("=" * 60)
    
    # 运行所有示例
    example_basic_connection()
    example_power_control()
    example_status_read()
    example_movej()
    example_movel()
    example_speed_control()
    example_project_control()
    example_context_manager()
    example_complete_workflow()
    example_error_handling()
    
    print("\n" + "=" * 60)
    print("注意: 实际机器人连接示例需要真实的机器人")
    print("如需测试实际机器人，请取消注释以下代码:")
    print("  example_real_robot()")
    print("=" * 60)
    
    # 取消注释以下代码以测试实际机器人
    # example_real_robot()

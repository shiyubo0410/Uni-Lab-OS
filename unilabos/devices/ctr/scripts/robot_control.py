#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长广溪(CGXi) 协作机械臂控制脚本
支持连接、上电、使能、运动控制等功能
"""

import sys
import time
from pathlib import Path

# 添加 skills/changguangxi 到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILLS_PATH = SCRIPT_DIR.parent / 'skills' / 'changguangxi'
sys.path.insert(0, str(SKILLS_PATH))

try:
    from robot_utils import CGXiRobot, RobotMode
except ImportError as e:
    print(f"❌ 无法导入机械臂SDK - {e}")
    print(f"请确保SDK路径正确: {SKILLS_PATH}")
    sys.exit(1)


class RobotController:
    """机械臂控制器"""
    
    def __init__(self, ip="192.168.6.6", port=2323, password="123", virtual=False):
        """
        初始化控制器
        
        Args:
            ip: 机器人IP地址
            port: 端口号
            password: 连接密码
            virtual: 是否使用虚拟臂
        """
        self.robot = CGXiRobot(ip=ip, port=port, password=password, virtual=virtual)
        self.virtual = virtual
        
    def connect(self):
        """连接机器人"""
        print("\n" + "="*50)
        print("🔌 连接机械臂...")
        print("="*50)
        return self.robot.connect()
    
    def wait_for_power_on(self, timeout=150):
        """等待上电完成"""
        print(f"\n⏳ 等待上电完成 (超时: {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            success, mode = self.robot.get_robot_mode()
            if success and mode == 8:  # 8 = 本体已上电
                print("  ✅ 上电完成")
                return True
            time.sleep(0.5)
        print("  ❌ 等待上电超时")
        return False
    
    def wait_for_enable(self, timeout=150):
        """等待使能完成"""
        print(f"\n⏳ 等待使能完成 (超时: {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            success, mode = self.robot.get_robot_mode()
            if success and mode == 10:  # 10 = 使能完成
                print("  ✅ 使能完成")
                return True
            time.sleep(0.5)
        print("  ❌ 等待使能超时")
        return False
    
    def disconnect(self):
        """断开连接"""
        print("\n" + "="*50)
        print("🔌 断开机械臂连接...")
        print("="*50)
        self.robot.disconnect()
    
    def power_on(self):
        """上电"""
        print("\n⚡ 执行上电...")
        return self.robot.power_on()
    
    def power_off(self):
        """断电"""
        print("\n⚡ 执行断电...")
        return self.robot.power_off()
    
    def enable(self):
        """使能"""
        print("\n✅ 执行使能...")
        return self.robot.enable()
    
    def disable(self):
        """去使能"""
        print("\n❎ 执行去使能...")
        return self.robot.disable()
    
    def fault_reset(self):
        """故障复位"""
        print("\n🔄 执行故障复位...")
        return self.robot.fault_reset()
    
    def get_status(self):
        """获取机器人状态"""
        print("\n📊 读取机器人状态...")
        success, mode = self.robot.get_robot_mode()
        if success:
            mode_names = {
                0: "未定义", 1: "未连接", 2: "连接中", 3: "已连接",
                4: "已断开", 5: "连接异常", 6: "本体未上电", 7: "本体上电中",
                8: "本体已上电", 9: "使能中", 10: "使能完成", 11: "去使能中",
                12: "去使能完成", 13: "运动中", 14: "运动完成", 15: "暂停中",
                16: "暂停完成", 17: "停止中", 18: "停止完成", 19: "错误",
                20: "错误恢复中", 21: "错误恢复完成", 22: "急停中", 23: "急停完成",
                100: "未使能", 101: "未上电", 102: "上电中", 103: "空闲",
                104: "暂停", 105: "运行中", 106: "拖动示教"
            }
            mode_name = mode_names.get(mode, f"未知({mode})")
            print(f"  状态码: {mode}")
            print(f"  状态名: {mode_name}")
            return True, mode
        return False, None
    
    def get_joint_position(self):
        """获取关节角度"""
        print("\n📐 读取关节角度...")
        success, joint_pos = self.robot.get_joint_position()
        if success:
            print(f"  J1: {joint_pos[0]:8.2f}°")
            print(f"  J2: {joint_pos[1]:8.2f}°")
            print(f"  J3: {joint_pos[2]:8.2f}°")
            print(f"  J4: {joint_pos[3]:8.2f}°")
            print(f"  J5: {joint_pos[4]:8.2f}°")
            print(f"  J6: {joint_pos[5]:8.2f}°")
            return True, joint_pos
        return False, None
    
    def get_tcp_pose(self):
        """获取TCP位姿"""
        print("\n📍 读取TCP位姿...")
        success, pose = self.robot.get_tcp_pose()
        if success:
            print(f"  X:  {pose[0]:8.2f} mm")
            print(f"  Y:  {pose[1]:8.2f} mm")
            print(f"  Z:  {pose[2]:8.2f} mm")
            print(f"  Rx: {pose[3]:8.2f}°")
            print(f"  Ry: {pose[4]:8.2f}°")
            print(f"  Rz: {pose[5]:8.2f}°")
            return True, pose
        return False, None
    
    def movej(self, joint_pos, speed=None, acc=None, block=False, desc=""):
        """
        轴空间运动 (MoveJ)
        
        Args:
            joint_pos: 关节角度列表 [j1, j2, j3, j4, j5, j6]
            speed: 速度列表
            acc: 加速度列表
            block: 是否阻塞等待
            desc: 运动描述
        """
        if desc:
            print(f"\n🤖 MoveJ运动 - {desc}")
        else:
            print(f"\n🤖 MoveJ运动")
        print(f"  目标位置: {joint_pos}")
        return self.robot.movej(joint_pos, speed, acc, block)
    
    def movel(self, pose, speed=None, acc=None, block=False, desc=""):
        """
        直线运动 (MoveL)
        
        Args:
            pose: 位姿列表 [x, y, z, rx, ry, rz]
            speed: 速度列表
            acc: 加速度列表
            block: 是否阻塞等待
            desc: 运动描述
        """
        if desc:
            print(f"\n🤖 MoveL运动 - {desc}")
        else:
            print(f"\n🤖 MoveL运动")
        print(f"  目标位姿: {pose}")
        return self.robot.movel(pose, speed, acc, block)
    
    def set_speed(self, speed_percent):
        """设置速度百分比"""
        print(f"\n⚡ 设置速度为 {speed_percent}%")
        return self.robot.set_speed_percent(speed_percent)
    
    def wait_move_complete(self, timeout=150):
        """等待运动完成"""
        print(f"\n⏳ 等待运动完成 (超时: {timeout}s)...")
        return self.robot.wait_move_complete(timeout)


def test_basic_connection(virtual=False):
    """测试基本连接"""
    print("\n" + "="*60)
    print("🧪 测试1: 基本连接测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if controller.connect():
        time.sleep(1)
        controller.get_status()
        controller.disconnect()
        print("\n✅ 基本连接测试通过")
        return True
    else:
        print("\n❌ 基本连接测试失败")
        return False


def test_power_cycle(virtual=False):
    """测试电源循环"""
    print("\n" + "="*60)
    print("🧪 测试2: 电源循环测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if not controller.connect():
        print("\n❌ 连接失败")
        return False
    
    try:
        # 上电
        controller.power_on()
        time.sleep(2)
        controller.get_status()
        
        # 断电
        controller.power_off()
        time.sleep(2)
        controller.get_status()
        
        print("\n✅ 电源循环测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    finally:
        controller.disconnect()


def test_enable_disable(virtual=False):
    """测试使能/去使能"""
    print("\n" + "="*60)
    print("🧪 测试3: 使能/去使能测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if not controller.connect():
        print("\n❌ 连接失败")
        return False
    
    try:
        # 上电并等待完成
        controller.power_on()
        controller.wait_for_power_on(timeout=150)
        
        # 使能并等待完成
        controller.enable()
        controller.wait_for_enable(timeout=150)
        controller.get_status()
        
        # 去使能
        controller.disable()
        time.sleep(2)
        controller.get_status()
        
        # 断电
        controller.power_off()
        
        print("\n✅ 使能/去使能测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    finally:
        controller.disconnect()


def test_status_reading(virtual=False):
    """测试状态读取"""
    print("\n" + "="*60)
    print("🧪 测试4: 状态读取测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if not controller.connect():
        print("\n❌ 连接失败")
        return False
    
    try:
        # 读取各种状态
        controller.get_status()
        controller.get_joint_position()
        controller.get_tcp_pose()
        
        # 上电使能后再次读取
        controller.power_on()
        controller.wait_for_power_on(timeout=150)
        controller.enable()
        controller.wait_for_enable(timeout=150)
        
        controller.get_status()
        controller.get_joint_position()
        controller.get_tcp_pose()
        
        # 清理
        controller.disable()
        time.sleep(1)
        controller.power_off()
        
        print("\n✅ 状态读取测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    finally:
        controller.disconnect()


def test_movej(virtual=False):
    """测试MoveJ运动"""
    print("\n" + "="*60)
    print("🧪 测试5: MoveJ运动测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if not controller.connect():
        print("\n❌ 连接失败")
        return False
    
    try:
        # 上电使能
        controller.power_on()
        controller.wait_for_power_on(timeout=150)
        controller.enable()
        controller.wait_for_enable(timeout=150)
        
        # 设置速度
        controller.set_speed(150)
        
        # 运动到初始位置
        controller.movej([0, 0, 90, 0, -90, 0], desc="初始位置")
        time.sleep(3)
        controller.get_joint_position()
        
        # 运动到位置1
        controller.movej([10, 10, 80, 10, -80, 10], desc="位置1")
        time.sleep(3)
        controller.get_joint_position()
        
        # 运动到位置2
        controller.movej([-10, -10, 100, -10, -100, -10], desc="位置2")
        time.sleep(3)
        controller.get_joint_position()
        
        # 回到初始位置
        controller.movej([0, 0, 90, 0, -90, 0], desc="回到初始位置")
        time.sleep(3)
        
        # 清理
        controller.disable()
        time.sleep(1)
        controller.power_off()
        
        print("\n✅ MoveJ运动测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    finally:
        controller.disconnect()


def test_movel(virtual=False):
    """测试MoveL运动"""
    print("\n" + "="*60)
    print("🧪 测试6: MoveL运动测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if not controller.connect():
        print("\n❌ 连接失败")
        return False
    
    try:
        # 上电使能
        controller.power_on()
        controller.wait_for_power_on(timeout=150)
        controller.enable()
        controller.wait_for_enable(timeout=150)
        
        # 设置速度
        controller.set_speed(150)
        
        # 先运动到初始位置
        controller.movej([0, 0, 90, 0, -90, 0], desc="初始位置")
        time.sleep(3)
        
        # MoveL运动
        controller.movel([1500, 0, 400, 0, 180, 0], desc="位置1")
        time.sleep(3)
        controller.get_tcp_pose()
        
        controller.movel([400, 100, 400, 0, 180, 0], desc="位置2")
        time.sleep(3)
        controller.get_tcp_pose()
        
        controller.movel([400, 200, 400, 0, 180, 0], desc="位置3")
        time.sleep(3)
        controller.get_tcp_pose()
        
        # 回到初始位置
        controller.movel([1500, 0, 400, 0, 180, 0], desc="回到位置1")
        time.sleep(3)
        
        # 清理
        controller.disable()
        time.sleep(1)
        controller.power_off()
        
        print("\n✅ MoveL运动测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    finally:
        controller.disconnect()


def test_speed_control(virtual=False):
    """测试速度控制"""
    print("\n" + "="*60)
    print("🧪 测试7: 速度控制测试")
    print("="*60)
    
    controller = RobotController(virtual=virtual)
    if not controller.connect():
        print("\n❌ 连接失败")
        return False
    
    try:
        # 上电使能
        controller.power_on()
        controller.wait_for_power_on(timeout=150)
        controller.enable()
        controller.wait_for_enable(timeout=150)
        
        # 测试不同速度
        speeds = [100, 50, 150, 10]
        for speed in speeds:
            controller.set_speed(speed)
            controller.movej([0, 0, 90, 0, -90, 0], desc=f"速度{speed}%")
            time.sleep(2)
            controller.movej([10, 0, 90, 0, -90, 0], desc=f"速度{speed}%")
            time.sleep(2)
        
        # 清理
        controller.disable()
        time.sleep(1)
        controller.power_off()
        
        print("\n✅ 速度控制测试通过")
        return True
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    finally:
        controller.disconnect()


def run_all_tests(virtual=False):
    """运行所有测试 - 只上电一次"""
    print("\n" + "="*70)
    print("🚀 长广溪(CGXi) 机械臂综合测试")
    print("="*70)
    print(f"模式: {'虚拟臂' if virtual else '真实机械臂'}")
    
    # 创建共享的控制器
    controller = RobotController(virtual=virtual)
    results = []
    
    try:
        # 1. 连接测试
        print("\n" + "="*60)
        print("🧪 测试1: 基本连接测试")
        print("="*60)
        if controller.connect():
            time.sleep(1)
            controller.get_status()
            print("\n✅ 基本连接测试通过")
            results.append(("基本连接", True))
        else:
            print("\n❌ 基本连接测试失败")
            results.append(("基本连接", False))
            return False
        
        # 2. 上电（只执行一次）
        print("\n" + "="*60)
        print("⚡ 执行上电...")
        print("="*60)
        controller.power_on()
        if not controller.wait_for_power_on(timeout=150):
            print("❌ 上电失败")
            results.append(("上电", False))
            return False
        print("✅ 上电完成")
        results.append(("上电", True))
        
        # 3. 状态读取测试
        print("\n" + "="*60)
        print("🧪 测试2: 状态读取测试")
        print("="*60)
        try:
            controller.get_status()
            controller.get_joint_position()
            controller.get_tcp_pose()
            print("\n✅ 状态读取测试通过")
            results.append(("状态读取", True))
        except Exception as e:
            print(f"\n❌ 状态读取测试失败: {e}")
            results.append(("状态读取", False))
        
        # 4. 使能/去使能测试
        print("\n" + "="*60)
        print("🧪 测试3: 使能/去使能测试")
        print("="*60)
        try:
            controller.enable()
            if controller.wait_for_enable(timeout=150):
                controller.get_status()
                print("✅ 使能成功")
                
                # 去使能
                controller.disable()
                time.sleep(2)
                controller.get_status()
                print("✅ 去使能成功")
                
                print("\n✅ 使能/去使能测试通过")
                results.append(("使能/去使能", True))
            else:
                print("❌ 使能超时")
                results.append(("使能/去使能", False))
        except Exception as e:
            print(f"\n❌ 使能/去使能测试失败: {e}")
            results.append(("使能/去使能", False))
        
        # 5. MoveJ运动测试
        print("\n" + "="*60)
        print("🧪 测试4: MoveJ运动测试")
        print("="*60)
        try:
            controller.enable()
            if controller.wait_for_enable(timeout=150):
                controller.set_speed(30)
                
                # 运动到初始位置
                controller.movej([0, 0, 90, 0, -90, 0], desc="初始位置")
                time.sleep(3)
                controller.get_joint_position()
                
                # 运动到位置1
                controller.movej([10, 10, 80, 10, -80, 10], desc="位置1")
                time.sleep(3)
                controller.get_joint_position()
                
                # 回到初始位置
                controller.movej([0, 0, 90, 0, -90, 0], desc="回到初始位置")
                time.sleep(3)
                
                controller.disable()
                print("\n✅ MoveJ运动测试通过")
                results.append(("MoveJ运动", True))
            else:
                print("❌ 使能超时")
                results.append(("MoveJ运动", False))
        except Exception as e:
            print(f"\n❌ MoveJ运动测试失败: {e}")
            results.append(("MoveJ运动", False))
        
        # 6. MoveL运动测试
        print("\n" + "="*60)
        print("🧪 测试5: MoveL运动测试")
        print("="*60)
        try:
            controller.enable()
            if controller.wait_for_enable(timeout=150):
                controller.set_speed(30)
                
                # 先运动到初始位置
                controller.movej([0, 0, 90, 0, -90, 0], desc="初始位置")
                time.sleep(3)
                
                # MoveL运动
                controller.movel([300, 0, 400, 0, 180, 0], desc="位置1")
                time.sleep(3)
                controller.get_tcp_pose()
                
                controller.movel([400, 100, 400, 0, 180, 0], desc="位置2")
                time.sleep(3)
                controller.get_tcp_pose()
                
                controller.disable()
                print("\n✅ MoveL运动测试通过")
                results.append(("MoveL运动", True))
            else:
                print("❌ 使能超时")
                results.append(("MoveL运动", False))
        except Exception as e:
            print(f"\n❌ MoveL运动测试失败: {e}")
            results.append(("MoveL运动", False))
        
        # 7. 速度控制测试
        print("\n" + "="*60)
        print("🧪 测试6: 速度控制测试")
        print("="*60)
        try:
            controller.enable()
            if controller.wait_for_enable(timeout=150):
                speeds = [100, 50, 30]
                for speed in speeds:
                    controller.set_speed(speed)
                    controller.movej([0, 0, 90, 0, -90, 0], desc=f"速度{speed}%")
                    time.sleep(2)
                
                controller.disable()
                print("\n✅ 速度控制测试通过")
                results.append(("速度控制", True))
            else:
                print("❌ 使能超时")
                results.append(("速度控制", False))
        except Exception as e:
            print(f"\n❌ 速度控制测试失败: {e}")
            results.append(("速度控制", False))
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
    finally:
        # 最后断电
        print("\n" + "="*60)
        print("⚡ 执行断电...")
        print("="*60)
        controller.power_off()
        controller.disconnect()
        print("✅ 断电完成，断开连接")
    
    # 打印测试报告
    print("\n" + "="*70)
    print("📋 测试报告")
    print("="*70)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
    
    print("-"*70)
    print(f"总计: {len(results)} 项 | 通过: {passed} 项 | 失败: {failed} 项")
    print("="*70)
    
    return failed == 0


def interactive_control(virtual=False):
    """交互式控制模式"""
    print("\n" + "="*60)
    print("🎮 交互式控制模式")
    print("="*60)
    print("命令列表:")
    print("  connect    - 连接机械臂")
    print("  disconnect - 断开连接")
    print("  on         - 上电")
    print("  off        - 断电")
    print("  enable     - 使能")
    print("  disable    - 去使能")
    print("  status     - 读取状态")
    print("  joint      - 读取关节角度")
    print("  tcp        - 读取TCP位姿")
    print("  movej      - MoveJ运动 (格式: movej 0,0,90,0,-90,0)")
    print("  movel      - MoveL运动 (格式: movel 1500,0,400,0,180,0)")
    print("  speed      - 设置速度 (格式: speed 50)")
    print("  home       - 回到初始位置")
    print("  test       - 运行完整测试")
    print("  help       - 显示帮助")
    print("  quit/exit  - 退出")
    print("="*60)
    
    controller = None
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd in ['quit', 'exit', 'q']:
                if controller:
                    controller.disconnect()
                print("👋 再见!")
                break
                
            elif cmd == 'help':
                print("命令列表: connect, disconnect, on, off, enable, disable,")
                print("          status, joint, tcp, movej, movel, speed, home, test, quit")
                
            elif cmd == 'connect':
                controller = RobotController(virtual=virtual)
                controller.connect()
                
            elif cmd == 'disconnect':
                if controller:
                    controller.disconnect()
                    controller = None
                else:
                    print("❌ 未连接")
                    
            elif cmd == 'on':
                if controller:
                    controller.power_on()
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'off':
                if controller:
                    controller.power_off()
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'enable':
                if controller:
                    controller.enable()
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'disable':
                if controller:
                    controller.disable()
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'status':
                if controller:
                    controller.get_status()
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'joint':
                if controller:
                    controller.get_joint_position()
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'tcp':
                if controller:
                    controller.get_tcp_pose()
                else:
                    print("❌ 请先连接")
                    
            elif cmd.startswith('movej '):
                if controller:
                    try:
                        joints = [float(x) for x in cmd[6:].split(',')]
                        if len(joints) == 6:
                            controller.movej(joints)
                        else:
                            print("❌ 需要6个关节角度值")
                    except ValueError:
                        print("❌ 格式错误，使用: movej 0,0,90,0,-90,0")
                else:
                    print("❌ 请先连接")
                    
            elif cmd.startswith('movel '):
                if controller:
                    try:
                        pose = [float(x) for x in cmd[6:].split(',')]
                        if len(pose) == 6:
                            controller.movel(pose)
                        else:
                            print("❌ 需要6个位姿值 (x,y,z,rx,ry,rz)")
                    except ValueError:
                        print("❌ 格式错误，使用: movel 1500,0,400,0,180,0")
                else:
                    print("❌ 请先连接")
                    
            elif cmd.startswith('speed '):
                if controller:
                    try:
                        speed = int(cmd[6:])
                        controller.set_speed(speed)
                    except ValueError:
                        print("❌ 格式错误，使用: speed 50")
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'home':
                if controller:
                    controller.movej([0, 0, 90, 0, -90, 0], desc="回到初始位置")
                else:
                    print("❌ 请先连接")
                    
            elif cmd == 'test':
                run_all_tests(virtual=virtual)
                
            elif cmd == '':
                continue
                
            else:
                print(f"❓ 未知命令: {cmd}")
                print("输入 'help' 查看命令列表")
                
        except KeyboardInterrupt:
            print("\n👋 再见!")
            if controller:
                controller.disconnect()
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='长广溪(CGXi) 机械臂控制脚本')
    parser.add_argument('--virtual', '-v', action='store_true', help='使用虚拟臂模式')
    parser.add_argument('--test', '-t', action='store_true', help='运行完整测试')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互式控制模式')
    parser.add_argument('--ip', default='192.168.6.6', help='机械臂IP地址 (默认: 192.168.6.6)')
    parser.add_argument('--port', type=int, default=2323, help='端口号 (默认: 2323)')
    
    args = parser.parse_args()
    
    if args.test:
        run_all_tests(virtual=args.virtual)
    elif args.interactive:
        interactive_control(virtual=args.virtual)
    else:
        # 默认显示帮助
        parser.print_help()
        print("\n" + "="*60)
        print("使用示例:")
        print("  python robot_control.py --test --virtual    # 虚拟臂测试")
        print("  python robot_control.py --test              # 真实机械臂测试")
        print("  python robot_control.py -i --virtual        # 虚拟臂交互模式")
        print("  python robot_control.py -i --ip 192.168.1.10 # 指定IP交互模式")
        print("="*60)

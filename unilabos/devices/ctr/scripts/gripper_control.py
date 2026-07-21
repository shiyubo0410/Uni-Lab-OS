#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PGEA夹爪 - 命令行控制工具
支持夹爪的基本操作:初始化、夹持、释放、移动、状态查询等
"""

import sys
import time
from pathlib import Path

# 添加 skills/pgea_gripper_skill 到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILLS_PATH = SCRIPT_DIR.parent / 'skills' / 'pgea_gripper_skill'
sys.path.insert(0, str(SKILLS_PATH))

try:
    from gripper import PGEAGripper, GripperStatus
    from constants import (
        GRIP_STATUS_MOVING,
        GRIP_STATUS_IN_POSITION,
        GRIP_STATUS_GRIPPED,
        GRIP_STATUS_DROPPED,
        POSITION_MIN,
        POSITION_MAX,
        FORCE_MIN,
        FORCE_MAX,
        SPEED_MIN,
        SPEED_MAX,
    )
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保 pgea_gripper_skill 包已正确安装:")
    print("   cd f:\\ctr\\skills\\pgea_gripper_skill && pip install -e .")
    sys.exit(1)


class GripperController:
    """夹爪控制器"""
    
    def __init__(self, port: str, slave_id: int = 1):
        self.port = port
        self.slave_id = slave_id
        self.gripper = None
    
    def connect(self) -> bool:
        """连接夹爪"""
        try:
            print(f"\n{'='*50}")
            print(f"🔌 连接夹爪: {self.port} (ID: {self.slave_id})")
            print('='*50)
            
            self.gripper = PGEAGripper(port=self.port, slave_id=self.slave_id)
            result = self.gripper.connect()
            
            if result:
                print(f"✅ 连接成功")
                return True
            else:
                print(f"❌ 连接失败")
                return False
                
        except Exception as e:
            print(f"❌ 连接异常: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.gripper:
            self.gripper.disconnect()
            print(f"\n🔌 已断开连接")
    
    def initialize(self, full_calibration: bool = False) -> bool:
        """初始化夹爪"""
        try:
            print(f"\n{'='*50}")
            print(f"🔧 初始化夹爪 ({'完全标定' if full_calibration else '正常初始化'})")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            # 检查是否已初始化
            if self.gripper.is_initialized():
                print("✅ 夹爪已初始化")
                return True
            
            # 执行初始化
            print("⏳ 正在初始化...")
            result = self.gripper.initialize(
                full_calibration=full_calibration,
                wait=True,
                timeout=10.0
            )
            
            if result:
                print("✅ 初始化完成")
            else:
                print("❌ 初始化失败")
            
            return result
            
        except Exception as e:
            print(f"❌ 初始化异常: {e}")
            return False
    
    def grip(self, force: int = 50, speed: int = 30) -> bool:
        """夹持动作"""
        try:
            print(f"\n{'='*50}")
            print(f"✊ 夹持动作 (力值: {force}%, 速度: {speed}%)")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            if not self.gripper.is_initialized():
                print("❌ 夹爪未初始化")
                return False
            
            # 执行夹持
            print("⏳ 正在夹持...")
            result = self.gripper.grip(force=force, speed=speed, wait=True, timeout=10.0)
            
            if result:
                print("✅ 成功夹住物体")
            else:
                print("⚠️  未检测到物体或到位")
            
            return result
            
        except Exception as e:
            print(f"❌ 夹持异常: {e}")
            return False
    
    def release(self, position: int = 1000, speed: int = 50) -> bool:
        """释放动作"""
        try:
            print(f"\n{'='*50}")
            print(f"🖐️  释放动作 (位置: {position}‰, 速度: {speed}%)")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            if not self.gripper.is_initialized():
                print("❌ 夹爪未初始化")
                return False
            
            # 执行释放
            print("⏳ 正在释放...")
            result = self.gripper.release(position=position, speed=speed, wait=True, timeout=10.0)
            
            if result:
                print("✅ 释放完成")
            else:
                print("⚠️  释放未完成")
            
            return result
            
        except Exception as e:
            print(f"❌ 释放异常: {e}")
            return False
    
    def move(self, position: int, speed: int = 50) -> bool:
        """移动到指定位置"""
        try:
            print(f"\n{'='*50}")
            print(f"📍 移动到位置 {position}‰ (速度: {speed}%)")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            if not self.gripper.is_initialized():
                print("❌ 夹爪未初始化")
                return False
            
            # 设置速度并移动
            self.gripper.set_speed(speed)
            self.gripper.move_to(position)
            
            print("⏳ 正在移动...")
            status = self.gripper.wait_for_complete(timeout=10.0)
            
            # 获取当前位置
            current_pos = self.gripper.get_current_position()
            
            if status == GRIP_STATUS_MOVING:
                print("⚠️  移动超时")
            elif status == GRIP_STATUS_GRIPPED:
                print("✅ 移动完成 (夹住物体)")
            else:
                print(f"✅ 移动完成 (当前位置: {current_pos}‰)")
            
            return status != GRIP_STATUS_MOVING
            
        except Exception as e:
            print(f"❌ 移动异常: {e}")
            return False
    
    def set_force(self, force: int) -> bool:
        """设置力值"""
        try:
            print(f"\n{'='*50}")
            print(f"💪 设置力值: {force}%")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            result = self.gripper.set_force(force)
            
            if result:
                print(f"✅ 力值已设置为 {force}%")
            else:
                print("❌ 设置失败")
            
            return result
            
        except Exception as e:
            print(f"❌ 设置力值异常: {e}")
            return False
    
    def set_speed(self, speed: int) -> bool:
        """设置速度"""
        try:
            print(f"\n{'='*50}")
            print(f"⚡ 设置速度: {speed}%")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            result = self.gripper.set_speed(speed)
            
            if result:
                print(f"✅ 速度已设置为 {speed}%")
            else:
                print("❌ 设置失败")
            
            return result
            
        except Exception as e:
            print(f"❌ 设置速度异常: {e}")
            return False
    
    def get_status(self) -> bool:
        """获取夹爪状态"""
        try:
            print(f"\n{'='*50}")
            print(f"📊 夹爪状态")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            # 获取完整状态
            status = self.gripper.get_full_status()
            
            # 状态映射
            status_map = {
                GRIP_STATUS_MOVING: "运动中",
                GRIP_STATUS_IN_POSITION: "到位",
                GRIP_STATUS_GRIPPED: "已夹住物体",
                GRIP_STATUS_DROPPED: "物体掉落",
            }
            status_text = status_map.get(status.grip_status, f"未知状态({status.grip_status})")
            
            # 打印状态信息
            print(f"  初始化状态: {'✅ 已初始化' if status.initialized else '❌ 未初始化'}")
            print(f"  运动状态:   {status_text}")
            print(f"  当前位置:   {status.position}‰")
            print(f"  当前速度:   {status.speed}%")
            print(f"  当前电流:   {status.current}")
            print(f"  电机温度:   {status.motor_temp}°C")
            print(f"  错误码:     {status.error_code}")
            
            # 错误信息
            if status.has_error:
                print(f"  错误信息:   {status.get_error_description()}")
            
            # IO状态
            print(f"  IO输入状态: {status.io_input}")
            print(f"  IO输出状态: {status.io_output}")
            
            return True
            
        except Exception as e:
            print(f"❌ 获取状态异常: {e}")
            return False
    
    def pick_and_place(self, pick_pos: int, place_pos: int, 
                      force: int = 50, speed: int = 30) -> bool:
        """取放操作"""
        try:
            print(f"\n{'='*50}")
            print(f"🔄 取放操作")
            print(f"   取物位置: {pick_pos}‰")
            print(f"   放置位置: {place_pos}‰")
            print(f"   力值: {force}%, 速度: {speed}%")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            if not self.gripper.is_initialized():
                print("❌ 夹爪未初始化")
                return False
            
            # 取物
            print("\n📍 移动到取物位置...")
            self.gripper.set_speed(speed)
            self.gripper.move_to(pick_pos)
            self.gripper.wait_for_complete()
            
            print("✊ 夹持...")
            gripped = self.gripper.grip(force=force, speed=speed, wait=True)
            
            if not gripped:
                print("⚠️  取物失败")
                return False
            
            time.sleep(0.5)
            
            # 放物
            print("\n📍 移动到放置位置...")
            self.gripper.move_to(place_pos)
            self.gripper.wait_for_complete()
            
            print("🖐️  释放...")
            self.gripper.release(position=1000, speed=speed, wait=True)
            
            print("\n✅ 取放操作完成")
            return True
            
        except Exception as e:
            print(f"❌ 取放操作异常: {e}")
            return False
    
    def stop(self) -> bool:
        """停止运动"""
        try:
            print(f"\n{'='*50}")
            print(f"🛑 停止运动")
            print('='*50)
            
            if not self.gripper or not self.gripper.is_connected():
                print("❌ 夹爪未连接")
                return False
            
            result = self.gripper.stop()
            
            if result:
                print("✅ 已停止")
            else:
                print("❌ 停止失败")
            
            return result
            
        except Exception as e:
            print(f"❌ 停止异常: {e}")
            return False


def print_help():
    """打印帮助信息"""
    print("""
PGEA夹爪控制工具

用法: python gripper_control.py <命令> [参数] [端口]

命令:
  init                    初始化夹爪
  init-full               完全初始化(重新标定行程)
  grip [力值] [速度]      夹持动作 (默认: 50 30)
  release [位置] [速度]  释放动作 (默认: 1000 50)
  move <位置> [速度]      移动到指定位置 (默认速度: 50)
  force <力值>            设置力值 (20-100)
  speed <速度>            设置速度 (1-100)
  status                  查看夹爪状态
  pick <取物位> <放物位>  取放操作
  stop                    停止运动

参数:
  端口                    串口设备 (默认: COM4)
                          Windows: COM3, COM4...
                          Linux: /dev/ttyUSB0, /dev/ttyUSB1...

示例:
  python gripper_control.py init COM4
  python gripper_control.py grip 60 40 COM4
  python gripper_control.py release 800 50
  python gripper_control.py move 500 30 COM4
  python gripper_control.py force 70
  python gripper_control.py speed 40
  python gripper_control.py status COM4
  python gripper_control.py pick 200 600 50 30
  python gripper_control.py stop

注意:
  - 位置范围: 0-1000‰ (0=闭合, 1000=张开)
  - 力值范围: 20-100%
  - 速度范围: 1-100%
  - 首次使用必须先执行 init
    """)


def main():
    """主函数"""
    # 默认配置
    default_port = 'COM4'
    
    # 显示帮助
    if len(sys.argv) < 2 or sys.argv[1] in ['--help', '-h', 'help']:
        print_help()
        sys.exit(0)
    
    # 解析命令
    command = sys.argv[1].lower()
    
    # 解析端口 (最后一个参数可能是端口)
    port = default_port
    if len(sys.argv) > 1:
        last_arg = sys.argv[-1]
        if last_arg.startswith('COM') or last_arg.startswith('/dev/tty'):
            port = sys.argv.pop()
    
    # 创建控制器
    controller = GripperController(port=port)
    
    # 连接夹爪
    if not controller.connect():
        sys.exit(1)
    
    try:
        # 执行命令
        if command == 'init':
            controller.initialize(full_calibration=False)
        
        elif command == 'init-full':
            controller.initialize(full_calibration=True)
        
        elif command == 'grip':
            force = int(sys.argv[2]) if len(sys.argv) > 2 else 50
            speed = int(sys.argv[3]) if len(sys.argv) > 3 else 30
            controller.grip(force=force, speed=speed)
        
        elif command == 'release':
            position = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
            speed = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            controller.release(position=position, speed=speed)
        
        elif command == 'move':
            if len(sys.argv) < 3:
                print("❌ 缺少位置参数")
                sys.exit(1)
            position = int(sys.argv[2])
            speed = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            controller.move(position=position, speed=speed)
        
        elif command == 'force':
            if len(sys.argv) < 3:
                print("❌ 缺少力值参数")
                sys.exit(1)
            force = int(sys.argv[2])
            controller.set_force(force=force)
        
        elif command == 'speed':
            if len(sys.argv) < 3:
                print("❌ 缺少速度参数")
                sys.exit(1)
            speed = int(sys.argv[2])
            controller.set_speed(speed=speed)
        
        elif command == 'status':
            controller.get_status()
        
        elif command == 'pick':
            if len(sys.argv) < 4:
                print("❌ 缺少取物位置和放置位置参数")
                sys.exit(1)
            pick_pos = int(sys.argv[2])
            place_pos = int(sys.argv[3])
            force = int(sys.argv[4]) if len(sys.argv) > 4 else 50
            speed = int(sys.argv[5]) if len(sys.argv) > 5 else 30
            controller.pick_and_place(pick_pos=pick_pos, place_pos=place_pos, 
                                     force=force, speed=speed)
        
        elif command == 'stop':
            controller.stop()
        
        else:
            print(f"❌ 未知命令: {command}")
            print("使用 --help 查看帮助")
            sys.exit(1)
    
    finally:
        # 断开连接
        controller.disconnect()


if __name__ == '__main__':
    main()

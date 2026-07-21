#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人图形化编程界面 (Streamlit版本)
提供可视化编程环境，支持路点管理、运动指令编辑、程序运行等功能
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum
import streamlit as st

# 添加路径
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'utils'))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'skills' / 'changguangxi'))

try:
    from robot_utils import CGXiRobot
    from robot_control_utils import create_robot_controller, Waypoint
    from gripper_pushrod_utils import GripperControl, PushRodControl, gripper_open, gripper_close, upper_pushrod_extend, upper_pushrod_retract, lower_pushrod_extend, lower_pushrod_retract, spin_coater_pushrod_extend, spin_coater_pushrod_retract
    from spin_coater_utils import SpinCoaterControl, enable_on, enable_off, vacuum_on, vacuum_off, spin_start, spin_stop, multi_step_start, multi_step_stop, manual_home, wait_for_spin_completion
    from serial_utils import SerialClient
except ImportError as e:
    st.error(f"❌ 无法导入模块 - {e}")
    st.stop()


class InstructionType(Enum):
    """指令类型"""
    MOVE_TO_WAYPOINT = "移动到路点"
    MOVE_WORLD_Z = "Z轴移动"
    MOVE_WORLD_REL = "相对移动"
    SET_TCP_VERTICAL = "末端垂直"
    SET_TCP_ORIENTATION = "设置姿态"
    DELAY = "延时"
    GRIPPER_OPEN = "夹爪打开"
    GRIPPER_CLOSE = "夹爪关闭"
    UPPER_PUSHROD_EXTEND = "上推杆推出"
    UPPER_PUSHROD_RETRACT = "上推杆收回"
    LOWER_PUSHROD_EXTEND = "下推杆推出"
    LOWER_PUSHROD_RETRACT = "下推杆收回"
    SPIN_COATER_PUSHROD_EXTEND = "旋涂仪推杆推出"
    SPIN_COATER_PUSHROD_RETRACT = "旋涂仪推杆收回"
    SPIN_COATER_ENABLE_ON = "旋涂仪使能开启"
    SPIN_COATER_ENABLE_OFF = "旋涂仪使能关闭"
    SPIN_COATER_VACUUM_ON = "旋涂仪真空开启"
    SPIN_COATER_VACUUM_OFF = "旋涂仪真空关闭"
    SPIN_COATER_SPIN_START = "旋涂仪旋涂启动"
    SPIN_COATER_SPIN_STOP = "旋涂仪旋涂停止"
    SPIN_COATER_MULTI_STEP_START = "旋涂仪多步旋涂"
    SPIN_COATER_MANUAL_HOME = "旋涂仪手动回原"
    SPIN_COATER_WAIT_COMPLETION = "等待旋涂结束"


class Instruction:
    """指令类"""
    
    def __init__(self, instr_type: InstructionType, params: Dict = None, 
                 comment: str = ""):
        self.type = instr_type
        self.params = params or {}
        self.comment = comment
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "params": self.params,
            "comment": self.comment
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Instruction':
        instr_type = InstructionType(data["type"])
        return cls(instr_type, data.get("params", {}), data.get("comment", ""))
    
    def __str__(self) -> str:
        if self.comment:
            return f"{self.type.value} - {self.comment}"
        return self.type.value


class RobotProgram:
    """机器人程序类"""
    
    def __init__(self, name: str = "未命名程序"):
        self.name = name
        self.instructions: List[Instruction] = []
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.modified_at = self.created_at
    
    def add_instruction(self, instruction: Instruction, index: int = -1):
        """添加指令"""
        if index == -1 or index >= len(self.instructions):
            self.instructions.append(instruction)
        else:
            self.instructions.insert(index, instruction)
        self.modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def remove_instruction(self, index: int):
        """删除指令"""
        if 0 <= index < len(self.instructions):
            self.instructions.pop(index)
            self.modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def move_instruction(self, from_idx: int, to_idx: int):
        """移动指令"""
        if 0 <= from_idx < len(self.instructions) and 0 <= to_idx < len(self.instructions):
            instr = self.instructions.pop(from_idx)
            self.instructions.insert(to_idx, instr)
            self.modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def clear(self):
        """清空程序"""
        self.instructions.clear()
        self.modified_at = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "instructions": [instr.to_dict() for instr in self.instructions],
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RobotProgram':
        program = cls(data.get("name", "未命名程序"))
        program.instructions = [Instruction.from_dict(d) for d in data.get("instructions", [])]
        program.created_at = data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))
        program.modified_at = data.get("modified_at", program.created_at)
        return program


class RobotGUIStreamlit:
    """机器人图形化编程界面 (Streamlit版本)"""
    
    def __init__(self):
        # 初始化会话状态
        if 'robot' not in st.session_state:
            st.session_state.robot = None
        if 'controller' not in st.session_state:
            st.session_state.controller = None
        if 'connected' not in st.session_state:
            st.session_state.connected = False
        if 'waypoints' not in st.session_state:
            st.session_state.waypoints = []
        if 'current_program' not in st.session_state:
            st.session_state.current_program = RobotProgram()
        if 'gripper_control' not in st.session_state:
            st.session_state.gripper_control = GripperControl()
        if 'pushrod_control' not in st.session_state:
            st.session_state.pushrod_control = PushRodControl()
        if 'gripper_connected' not in st.session_state:
            st.session_state.gripper_connected = False
        if 'pushrod_connected' not in st.session_state:
            st.session_state.pushrod_connected = False
        if 'relay_ip' not in st.session_state:
            st.session_state.relay_ip = "192.168.1.100"
        if 'relay_port' not in st.session_state:
            st.session_state.relay_port = 50000
        if 'waypoints_file' not in st.session_state:
            st.session_state.waypoints_file = "waypoints.json"
        if 'spin_coater_control' not in st.session_state:
            st.session_state.spin_coater_control = SpinCoaterControl()
        if 'spin_coater_connected' not in st.session_state:
            st.session_state.spin_coater_connected = False
        if 'spin_coater_port' not in st.session_state:
            st.session_state.spin_coater_port = "COM6"
        if 'spin_coater_baudrate' not in st.session_state:
            st.session_state.spin_coater_baudrate = 19200
        if 'logs' not in st.session_state:
            st.session_state.logs = []
        if 'selected_waypoint' not in st.session_state:
            st.session_state.selected_waypoint = None
        if 'selected_instruction' not in st.session_state:
            st.session_state.selected_instruction = None
        
        # 创建目录
        self.programs_dir = Path("programs")
        self.programs_dir.mkdir(exist_ok=True)
        
        # 加载数据
        self.load_data()
    
    def log(self, message: str):
        """记录日志"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        st.session_state.logs.append(log_message)
        # 限制日志数量
        if len(st.session_state.logs) > 100:
            st.session_state.logs = st.session_state.logs[-100:]
    
    def load_data(self):
        """加载路点数据"""
        waypoints_file = Path(st.session_state.waypoints_file)
        if waypoints_file.exists():
            try:
                with open(waypoints_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 支持两种格式：直接列表或包含waypoints键的对象
                    if isinstance(data, dict) and "waypoints" in data:
                        waypoints_list = data["waypoints"]
                    elif isinstance(data, list):
                        waypoints_list = data
                    else:
                        waypoints_list = []
                    st.session_state.waypoints = [Waypoint.from_dict(wp) for wp in waypoints_list]
                    self.log(f"✓ 加载了 {len(st.session_state.waypoints)} 个路点")
            except Exception as e:
                self.log(f"❌ 加载路点失败: {e}")
    
    def save_waypoints_to_file(self):
        """保存路点到文件"""
        waypoints_file = Path(st.session_state.waypoints_file)
        try:
            with open(waypoints_file, 'w', encoding='utf-8') as f:
                # 保存为包含waypoints键的对象格式，与原始格式一致
                data = {"waypoints": [wp.to_dict() for wp in st.session_state.waypoints]}
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f"✓ 保存了 {len(st.session_state.waypoints)} 个路点")
        except Exception as e:
            self.log(f"❌ 保存路点失败: {e}")
    
    def save_program(self, program: RobotProgram, file_path: str):
        """保存程序到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(program.to_dict(), f, ensure_ascii=False, indent=2)
            self.log(f"✓ 保存程序: {program.name}")
        except Exception as e:
            self.log(f"❌ 保存程序失败: {e}")
    
    def load_program(self, file_path: str) -> Optional[RobotProgram]:
        """从文件加载程序"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                program = RobotProgram.from_dict(data)
                self.log(f"✓ 加载程序: {program.name}")
                return program
        except Exception as e:
            self.log(f"❌ 加载程序失败: {e}")
            return None
    
    def connect_robot(self, ip: str, port: str):
        """连接机器人"""
        try:
            st.session_state.controller = create_robot_controller(ip, int(port))
            if st.session_state.controller:
                st.session_state.robot = st.session_state.controller.robot
                st.session_state.connected = True
                self.log("✓ 机器人连接成功")
            else:
                self.log("❌ 机器人连接失败")
        except Exception as e:
            self.log(f"❌ 机器人连接异常: {e}")
    
    def disconnect_robot(self):
        """断开机器人连接"""
        try:
            if st.session_state.robot:
                st.session_state.robot.disable()
            st.session_state.robot = None
            st.session_state.controller = None
            st.session_state.connected = False
            self.log("✓ 机器人断开连接")
        except Exception as e:
            self.log(f"❌ 断开连接异常: {e}")
    
    def power_on(self):
        """机器人上电"""
        if st.session_state.robot:
            try:
                st.session_state.robot.power_on()
                self.log("✓ 机器人上电成功")
            except Exception as e:
                self.log(f"❌ 机器人上电失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def power_off(self):
        """机器人断电"""
        if st.session_state.robot:
            try:
                st.session_state.robot.power_off()
                self.log("✓ 机器人断电成功")
            except Exception as e:
                self.log(f"❌ 机器人断电失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def enable_robot(self):
        """机器人使能"""
        if st.session_state.robot:
            try:
                st.session_state.robot.enable()
                self.log("✓ 机器人使能成功")
            except Exception as e:
                self.log(f"❌ 机器人使能失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def disable_robot(self):
        """机器人去使能"""
        if st.session_state.robot:
            try:
                st.session_state.robot.disable()
                self.log("✓ 机器人去使能成功")
            except Exception as e:
                self.log(f"❌ 机器人去使能失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def fault_reset(self):
        """机器人故障复位"""
        if st.session_state.robot:
            try:
                st.session_state.robot.reset_error()
                self.log("✓ 机器人故障复位成功")
            except Exception as e:
                self.log(f"❌ 机器人故障复位失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def move_world_z(self, distance: float):
        """Z轴移动"""
        if st.session_state.controller:
            try:
                st.session_state.controller.move_world_z(distance, speed=30.0, block=True)
                self.log(f"✓ Z轴移动 {distance} mm 成功")
            except Exception as e:
                self.log(f"❌ Z轴移动失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def set_tcp_vertical(self):
        """末端垂直"""
        if st.session_state.controller:
            try:
                st.session_state.controller.set_tcp_vertical(speed=30.0, block=True)
                self.log("✓ 末端垂直设置成功")
            except Exception as e:
                self.log(f"❌ 末端垂直设置失败: {e}")
        else:
            self.log("❌ 请先连接机器人")
    
    def connect_gripper(self):
        """连接夹爪"""
        try:
            # 这里需要根据实际情况实现夹爪连接逻辑
            st.session_state.gripper_connected = True
            self.log("✓ 夹爪连接成功")
        except Exception as e:
            self.log(f"❌ 夹爪连接失败: {e}")
    
    def initialize_gripper(self):
        """初始化夹爪"""
        if st.session_state.gripper_connected:
            try:
                # 这里需要根据实际情况实现夹爪初始化逻辑
                self.log("✓ 夹爪初始化成功")
            except Exception as e:
                self.log(f"❌ 夹爪初始化失败: {e}")
        else:
            self.log("❌ 请先连接夹爪")
    
    def gripper_open(self):
        """夹爪打开"""
        if st.session_state.gripper_connected:
            try:
                result = gripper_open(st.session_state.gripper_control)
                if result:
                    self.log("✓ 夹爪打开成功")
                else:
                    self.log("❌ 夹爪打开失败")
            except Exception as e:
                self.log(f"❌ 夹爪打开异常: {e}")
        else:
            self.log("❌ 夹爪未连接")
    
    def gripper_close(self):
        """夹爪关闭"""
        if st.session_state.gripper_connected:
            try:
                result = gripper_close(st.session_state.gripper_control)
                if result:
                    self.log("✓ 夹爪关闭成功")
                else:
                    self.log("❌ 夹爪关闭失败")
            except Exception as e:
                self.log(f"❌ 夹爪关闭异常: {e}")
        else:
            self.log("❌ 夹爪未连接")
    
    def upper_pushrod_extend(self):
        """上推杆推出"""
        try:
            result = upper_pushrod_extend(st.session_state.pushrod_control)
            if result:
                self.log("✓ 上推杆推出成功")
            else:
                self.log("❌ 上推杆推出失败")
        except Exception as e:
            self.log(f"❌ 上推杆推出异常: {e}")
    
    def upper_pushrod_retract(self):
        """上推杆收回"""
        try:
            result = upper_pushrod_retract(st.session_state.pushrod_control)
            if result:
                self.log("✓ 上推杆收回成功")
            else:
                self.log("❌ 上推杆收回失败")
        except Exception as e:
            self.log(f"❌ 上推杆收回异常: {e}")
    
    def lower_pushrod_extend(self):
        """下推杆推出"""
        try:
            result = lower_pushrod_extend(st.session_state.pushrod_control)
            if result:
                self.log("✓ 下推杆推出成功")
            else:
                self.log("❌ 下推杆推出失败")
        except Exception as e:
            self.log(f"❌ 下推杆推出异常: {e}")
    
    def lower_pushrod_retract(self):
        """下推杆收回"""
        try:
            result = lower_pushrod_retract(st.session_state.pushrod_control)
            if result:
                self.log("✓ 下推杆收回成功")
            else:
                self.log("❌ 下推杆收回失败")
        except Exception as e:
            self.log(f"❌ 下推杆收回异常: {e}")
    
    def spin_coater_pushrod_extend(self):
        """旋涂仪推杆推出"""
        try:
            result = spin_coater_pushrod_extend(st.session_state.pushrod_control)
            if result:
                self.log("✓ 旋涂仪推杆推出成功")
            else:
                self.log("❌ 旋涂仪推杆推出失败")
        except Exception as e:
            self.log(f"❌ 旋涂仪推杆推出异常: {e}")
    
    def spin_coater_pushrod_retract(self):
        """旋涂仪推杆收回"""
        try:
            result = spin_coater_pushrod_retract(st.session_state.pushrod_control)
            if result:
                self.log("✓ 旋涂仪推杆收回成功")
            else:
                self.log("❌ 旋涂仪推杆收回失败")
        except Exception as e:
            self.log(f"❌ 旋涂仪推杆收回异常: {e}")
    
    def connect_spin_coater(self, port: str, baudrate: int):
        """连接旋涂仪"""
        try:
            # 这里需要根据实际情况实现旋涂仪连接逻辑
            st.session_state.spin_coater_connected = True
            self.log("✓ 旋涂仪连接成功")
        except Exception as e:
            self.log(f"❌ 旋涂仪连接失败: {e}")
    
    def spin_coater_enable_on(self):
        """旋涂仪使能开启"""
        if st.session_state.spin_coater_connected:
            try:
                result = enable_on(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪使能开启成功")
                else:
                    self.log("❌ 旋涂仪使能开启失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪使能开启异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_enable_off(self):
        """旋涂仪使能关闭"""
        if st.session_state.spin_coater_connected:
            try:
                result = enable_off(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪使能关闭成功")
                else:
                    self.log("❌ 旋涂仪使能关闭失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪使能关闭异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_vacuum_on(self):
        """旋涂仪真空开启"""
        if st.session_state.spin_coater_connected:
            try:
                result = vacuum_on(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪真空开启成功")
                else:
                    self.log("❌ 旋涂仪真空开启失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪真空开启异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_vacuum_off(self):
        """旋涂仪真空关闭"""
        if st.session_state.spin_coater_connected:
            try:
                result = vacuum_off(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪真空关闭成功")
                else:
                    self.log("❌ 旋涂仪真空关闭失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪真空关闭异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_spin_start(self):
        """旋涂仪旋涂启动"""
        if st.session_state.spin_coater_connected:
            try:
                result = spin_start(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪旋涂启动成功")
                else:
                    self.log("❌ 旋涂仪旋涂启动失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪旋涂启动异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_spin_stop(self):
        """旋涂仪旋涂停止"""
        if st.session_state.spin_coater_connected:
            try:
                result = spin_stop(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪旋涂停止成功")
                else:
                    self.log("❌ 旋涂仪旋涂停止失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪旋涂停止异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_multi_step_start(self):
        """旋涂仪多步旋涂"""
        if st.session_state.spin_coater_connected:
            try:
                result = multi_step_start(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪多步旋涂启动成功")
                else:
                    self.log("❌ 旋涂仪多步旋涂启动失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪多步旋涂异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def spin_coater_manual_home(self):
        """旋涂仪手动回原"""
        if st.session_state.spin_coater_connected:
            try:
                result = manual_home(st.session_state.spin_coater_control)
                if result:
                    self.log("✓ 旋涂仪手动回原成功")
                else:
                    self.log("❌ 旋涂仪手动回原失败")
            except Exception as e:
                self.log(f"❌ 旋涂仪手动回原异常: {e}")
        else:
            self.log("❌ 请先连接旋涂仪")
    
    def record_waypoint(self, name: str):
        """记录当前路点"""
        if not st.session_state.connected or not st.session_state.controller:
            self.log("❌ 请先连接机器人")
            return
        
        if not name:
            name = f"路点_{len(st.session_state.waypoints)+1}"
        
        try:
            wp = st.session_state.controller.record_current_waypoint(name)
            if wp:
                st.session_state.waypoints.append(wp)
                self.log(f"✓ 记录路点: {name}")
                self.save_waypoints_to_file()
            else:
                self.log("❌ 记录路点失败")
        except Exception as e:
            self.log(f"❌ 记录路点异常: {e}")
    
    def delete_waypoint(self, index: int):
        """删除选中路点"""
        if 0 <= index < len(st.session_state.waypoints):
            name = st.session_state.waypoints[index].name
            st.session_state.waypoints.pop(index)
            self.log(f"✓ 删除路点: {name}")
            self.save_waypoints_to_file()
        else:
            self.log("❌ 路点索引无效")
    
    def clear_waypoints(self):
        """清空所有路点"""
        if st.session_state.waypoints:
            count = len(st.session_state.waypoints)
            st.session_state.waypoints.clear()
            self.log(f"✓ 清空所有路点 ({count} 个)")
            self.save_waypoints_to_file()
        else:
            self.log("❌ 路点列表为空")
    
    def move_to_waypoint(self, index: int):
        """移动到选中路点"""
        if not st.session_state.connected or not st.session_state.controller:
            self.log("❌ 请先连接机器人")
            return
        
        if 0 <= index < len(st.session_state.waypoints):
            wp = st.session_state.waypoints[index]
            try:
                if st.session_state.controller.move_to_waypoint(index, block=True):
                    self.log(f"✓ 移动到路点: {wp.name}")
                else:
                    self.log(f"❌ 移动到路点失败: {wp.name}")
            except Exception as e:
                self.log(f"❌ 移动到路点异常: {e}")
        else:
            self.log("❌ 路点索引无效")
    
    def add_instruction(self, instr_type: InstructionType, params: Dict, comment: str):
        """添加指令"""
        instr = Instruction(instr_type, params, comment)
        st.session_state.current_program.add_instruction(instr)
        self.log(f"✓ 添加指令: {instr.type.value}")
    
    def delete_instruction(self, index: int):
        """删除选中指令"""
        if 0 <= index < len(st.session_state.current_program.instructions):
            instr = st.session_state.current_program.instructions[index]
            st.session_state.current_program.remove_instruction(index)
            self.log(f"✓ 删除指令: {instr.type.value}")
        else:
            self.log("❌ 指令索引无效")
    
    def clear_program(self):
        """清空程序"""
        if st.session_state.current_program.instructions:
            count = len(st.session_state.current_program.instructions)
            st.session_state.current_program.clear()
            self.log(f"✓ 清空程序 ({count} 条指令)")
        else:
            self.log("❌ 程序为空")
    
    def run_program(self):
        """运行程序"""
        if not st.session_state.current_program.instructions:
            self.log("❌ 程序为空")
            return
        
        if not st.session_state.connected or not st.session_state.controller:
            self.log("❌ 请先连接机器人")
            return
        
        self.log("=" * 50)
        self.log("开始运行程序")
        self.log("=" * 50)
        
        try:
            for i, instr in enumerate(st.session_state.current_program.instructions):
                self.log(f"\n[{i+1}/{len(st.session_state.current_program.instructions)}] 执行: {instr.type.value}")
                
                if not self.execute_instruction(instr):
                    self.log("❌ 程序执行失败，停止运行")
                    return
            
            self.log("\n" + "=" * 50)
            self.log("程序执行完成")
            self.log("=" * 50)
        except Exception as e:
            self.log(f"❌ 程序执行异常: {e}")
    
    def step_program(self, index: int):
        """单步运行"""
        if not st.session_state.connected or not st.session_state.controller:
            self.log("❌ 请先连接机器人")
            return
        
        if 0 <= index < len(st.session_state.current_program.instructions):
            instr = st.session_state.current_program.instructions[index]
            self.log(f"[单步] 执行: {instr.type.value}")
            
            self.execute_instruction(instr)
        else:
            self.log("❌ 指令索引无效")
    
    def execute_instruction(self, instr: Instruction) -> bool:
        """执行单条指令"""
        try:
            if instr.type == InstructionType.MOVE_TO_WAYPOINT:
                idx = instr.params.get("waypoint_index", 0)
                if not st.session_state.waypoints:
                    self.log("❌ 路点列表为空")
                    return False
                if idx < len(st.session_state.waypoints):
                    return st.session_state.controller.move_to_waypoint(idx, block=True)
                else:
                    self.log(f"❌ 路点索引 {idx} 无效")
                    return False
            
            elif instr.type == InstructionType.MOVE_WORLD_Z:
                distance = instr.params.get("distance", 0)
                speed = instr.params.get("speed", 30.0)
                return st.session_state.controller.move_world_z(distance, speed=speed, block=True)
            
            elif instr.type == InstructionType.MOVE_WORLD_REL:
                dx = instr.params.get("dx", 0)
                dy = instr.params.get("dy", 0)
                dz = instr.params.get("dz", 0)
                speed = instr.params.get("speed", 30.0)
                return st.session_state.controller.move_world_relative(dx, dy, dz, speed=speed, block=True)
            
            elif instr.type == InstructionType.SET_TCP_VERTICAL:
                speed = instr.params.get("speed", 30.0)
                return st.session_state.controller.set_tcp_vertical(speed=speed, block=True)
            
            elif instr.type == InstructionType.SET_TCP_ORIENTATION:
                rx = instr.params.get("rx", 0)
                ry = instr.params.get("ry", 0)
                rz = instr.params.get("rz", 0)
                speed = instr.params.get("speed", 30.0)
                return st.session_state.controller.set_tcp_orientation(rx, ry, rz, speed=speed, block=True)
            
            elif instr.type == InstructionType.DELAY:
                delay = instr.params.get("delay", 1.0)
                self.log(f"  延时 {delay} 秒...")
                time.sleep(delay)
                return True
            
            elif instr.type == InstructionType.GRIPPER_OPEN:
                self.log("  夹爪打开")
                if st.session_state.gripper_connected:
                    return gripper_open(st.session_state.gripper_control)
                else:
                    self.log("  夹爪未连接")
                    return False
            
            elif instr.type == InstructionType.GRIPPER_CLOSE:
                self.log("  夹爪关闭")
                if st.session_state.gripper_connected:
                    return gripper_close(st.session_state.gripper_control)
                else:
                    self.log("  夹爪未连接")
                    return False
            
            elif instr.type == InstructionType.UPPER_PUSHROD_EXTEND:
                self.log("  上推杆推出")
                return upper_pushrod_extend(st.session_state.pushrod_control)
            
            elif instr.type == InstructionType.UPPER_PUSHROD_RETRACT:
                self.log("  上推杆收回")
                return upper_pushrod_retract(st.session_state.pushrod_control)
            
            elif instr.type == InstructionType.LOWER_PUSHROD_EXTEND:
                self.log("  下推杆推出")
                return lower_pushrod_extend(st.session_state.pushrod_control)
            
            elif instr.type == InstructionType.LOWER_PUSHROD_RETRACT:
                self.log("  下推杆收回")
                return lower_pushrod_retract(st.session_state.pushrod_control)
            
            elif instr.type == InstructionType.SPIN_COATER_PUSHROD_EXTEND:
                self.log("  旋涂仪推杆推出")
                return spin_coater_pushrod_extend(st.session_state.pushrod_control)
            
            elif instr.type == InstructionType.SPIN_COATER_PUSHROD_RETRACT:
                self.log("  旋涂仪推杆收回")
                return spin_coater_pushrod_retract(st.session_state.pushrod_control)
            
            elif instr.type == InstructionType.SPIN_COATER_ENABLE_ON:
                self.log("  旋涂仪使能开启")
                return enable_on(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_ENABLE_OFF:
                self.log("  旋涂仪使能关闭")
                return enable_off(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_VACUUM_ON:
                self.log("  旋涂仪真空开启")
                return vacuum_on(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_VACUUM_OFF:
                self.log("  旋涂仪真空关闭")
                return vacuum_off(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_SPIN_START:
                self.log("  旋涂仪旋涂启动")
                return spin_start(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_SPIN_STOP:
                self.log("  旋涂仪旋涂停止")
                return spin_stop(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_MULTI_STEP_START:
                self.log("  旋涂仪多步旋涂")
                return multi_step_start(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_MANUAL_HOME:
                self.log("  旋涂仪手动回原")
                return manual_home(st.session_state.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_WAIT_COMPLETION:
                self.log("  等待旋涂结束")
                return wait_for_spin_completion(st.session_state.spin_coater_control)
            
            else:
                self.log(f"❌ 未知指令类型: {instr.type.value}")
                return False
        except Exception as e:
            self.log(f"❌ 执行指令异常: {e}")
            return False
    
    def render(self):
        """渲染界面"""
        st.title("机器人图形化编程系统")
        
        # 创建标签页
        tab1, tab2, tab3, tab4 = st.tabs(["路点管理", "程序编辑器", "机器人控制", "运行日志"])
        
        with tab1:
            st.header("路点管理")
            
            # 路点列表
            st.subheader("路点列表")
            if st.session_state.waypoints:
                waypoint_names = [f"[{i}] {wp.name}" for i, wp in enumerate(st.session_state.waypoints)]
                selected_waypoint = st.selectbox("选择路点", options=range(len(st.session_state.waypoints)), format_func=lambda i: waypoint_names[i], key="waypoint_selector")
                
                # 路点信息
                st.subheader("路点信息")
                wp = st.session_state.waypoints[selected_waypoint]
                info = f"名称: {wp.name}\n"
                info += f"描述: {wp.description}\n"
                info += f"时间: {wp.timestamp}\n\n"
                info += f"关节角度:\n"
                for i, j in enumerate(wp.joint_pos):
                    info += f"  J{i+1}: {j:.2f}°\n"
                info += f"\nTCP位姿:\n"
                info += f"  X: {wp.tcp_pose[0]:.2f} mm\n"
                info += f"  Y: {wp.tcp_pose[1]:.2f} mm\n"
                info += f"  Z: {wp.tcp_pose[2]:.2f} mm\n"
                info += f"  Rx: {wp.tcp_pose[3]:.2f}°\n"
                info += f"  Ry: {wp.tcp_pose[4]:.2f}°\n"
                info += f"  Rz: {wp.tcp_pose[5]:.2f}°\n"
                st.text(info)
                
                # 路点操作
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("移动到路点"):
                        self.move_to_waypoint(selected_waypoint)
                with col2:
                    if st.button("删除选中路点"):
                        self.delete_waypoint(selected_waypoint)
                with col3:
                    if st.button("清空所有路点"):
                        self.clear_waypoints()
            else:
                st.info("路点列表为空")
            
            # 记录路点
            st.subheader("记录路点")
            waypoint_name = st.text_input("路点名称", placeholder="输入路点名称")
            if st.button("记录当前路点"):
                self.record_waypoint(waypoint_name)
        
        with tab2:
            st.header("程序编辑器")
            
            # 程序信息
            program_name = st.text_input("程序名称", value=st.session_state.current_program.name)
            if program_name != st.session_state.current_program.name:
                st.session_state.current_program.name = program_name
            
            # 指令列表
            st.subheader("指令列表")
            if st.session_state.current_program.instructions:
                instruction_names = [f"{i+1}. {instr}" for i, instr in enumerate(st.session_state.current_program.instructions)]
                selected_instruction = st.selectbox("选择指令", options=range(len(st.session_state.current_program.instructions)), format_func=lambda i: instruction_names[i], key="instruction_selector")
                
                # 指令详情
                st.subheader("指令详情")
                instr = st.session_state.current_program.instructions[selected_instruction]
                info = f"类型: {instr.type.value}\n"
                info += f"注释: {instr.comment}\n\n"
                info += f"参数:\n"
                for key, value in instr.params.items():
                    info += f"  {key}: {value}\n"
                st.text(info)
                
                # 指令操作
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("删除选中指令"):
                        self.delete_instruction(selected_instruction)
                with col2:
                    if st.button("清空程序"):
                        self.clear_program()
            else:
                st.info("程序为空")
            
            # 添加指令
            st.subheader("添加指令")
            instr_type = st.selectbox("指令类型", options=[t.value for t in InstructionType])
            instr_type_enum = InstructionType(instr_type)
            
            params = {}
            comment = st.text_input("注释", placeholder="可选")
            
            # 根据指令类型显示不同的参数输入
            if instr_type_enum == InstructionType.MOVE_TO_WAYPOINT:
                if st.session_state.waypoints:
                    waypoint_options = {f"[{i}] {wp.name}": i for i, wp in enumerate(st.session_state.waypoints)}
                    selected_wp = st.selectbox("选择路点", options=list(waypoint_options.keys()))
                    params["waypoint_index"] = waypoint_options[selected_wp]
                else:
                    st.warning("路点列表为空，请先添加路点")
            elif instr_type_enum == InstructionType.MOVE_WORLD_Z:
                params["distance"] = st.number_input("移动距离 (mm)", value=0.0)
                params["speed"] = st.number_input("速度 (mm/s)", value=30.0)
            elif instr_type_enum == InstructionType.MOVE_WORLD_REL:
                params["dx"] = st.number_input("X轴距离 (mm)", value=0.0)
                params["dy"] = st.number_input("Y轴距离 (mm)", value=0.0)
                params["dz"] = st.number_input("Z轴距离 (mm)", value=0.0)
                params["speed"] = st.number_input("速度 (mm/s)", value=30.0)
            elif instr_type_enum == InstructionType.SET_TCP_VERTICAL:
                params["speed"] = st.number_input("速度 (mm/s)", value=30.0)
            elif instr_type_enum == InstructionType.SET_TCP_ORIENTATION:
                params["rx"] = st.number_input("Rx (度)", value=0.0)
                params["ry"] = st.number_input("Ry (度)", value=0.0)
                params["rz"] = st.number_input("Rz (度)", value=0.0)
                params["speed"] = st.number_input("速度 (mm/s)", value=30.0)
            elif instr_type_enum == InstructionType.DELAY:
                params["delay"] = st.number_input("延时时间 (秒)", value=1.0)
            
            if st.button("添加指令"):
                self.add_instruction(instr_type_enum, params, comment)
            
            # 程序运行控制
            st.subheader("程序运行")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("运行程序"):
                    self.run_program()
            with col2:
                if st.session_state.current_program.instructions:
                    step_index = st.number_input("单步运行索引", min_value=0, max_value=len(st.session_state.current_program.instructions)-1, value=0)
                    if st.button("单步运行"):
                        self.step_program(step_index)
            with col3:
                # 保存程序
                save_path = st.text_input("保存路径", value=f"programs/{st.session_state.current_program.name}.json")
                if st.button("保存程序"):
                    self.save_program(st.session_state.current_program, save_path)
                
                # 加载程序
                load_path = st.text_input("加载路径", value="programs/")
                if st.button("加载程序"):
                    program = self.load_program(load_path)
                    if program:
                        st.session_state.current_program = program
        
        with tab3:
            st.header("机器人控制")
            
            # 连接设置
            st.subheader("连接设置")
            ip = st.text_input("IP地址", value="192.168.6.6")
            port = st.text_input("端口", value="2323")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("连接机器人"):
                    self.connect_robot(ip, port)
            with col2:
                if st.button("断开连接"):
                    self.disconnect_robot()
            
            # 电源控制
            st.subheader("电源控制")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("上电"):
                    self.power_on()
            with col2:
                if st.button("断电"):
                    self.power_off()
            with col3:
                if st.button("使能"):
                    self.enable_robot()
            with col4:
                if st.button("去使能"):
                    self.disable_robot()
            if st.button("故障复位"):
                self.fault_reset()
            
            # 快捷移动
            st.subheader("快捷移动")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Z轴上升 50mm"):
                    self.move_world_z(50)
            with col2:
                if st.button("Z轴下降 50mm"):
                    self.move_world_z(-50)
            if st.button("末端垂直"):
                self.set_tcp_vertical()
            
            # 夹爪和推杆控制
            st.subheader("夹爪和推杆控制")
            
            # 继电器配置
            st.subheader("继电器配置")
            relay_ip = st.text_input("继电器IP地址", value=st.session_state.relay_ip)
            relay_port = st.number_input("继电器端口", value=st.session_state.relay_port)
            if st.button("应用继电器配置"):
                st.session_state.relay_ip = relay_ip
                st.session_state.relay_port = relay_port
                self.log(f"✓ 继电器配置已更新: {relay_ip}:{relay_port}")
            
            # 夹爪控制
            st.subheader("夹爪控制")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("连接夹爪"):
                    self.connect_gripper()
                if st.button("夹爪打开"):
                    self.gripper_open()
            with col2:
                if st.button("初始化夹爪"):
                    self.initialize_gripper()
                if st.button("夹爪关闭"):
                    self.gripper_close()
            
            # 上推杆控制
            st.subheader("上推杆控制")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("上推杆推出"):
                    self.upper_pushrod_extend()
            with col2:
                if st.button("上推杆收回"):
                    self.upper_pushrod_retract()
            
            # 下推杆控制
            st.subheader("下推杆控制")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("下推杆推出"):
                    self.lower_pushrod_extend()
            with col2:
                if st.button("下推杆收回"):
                    self.lower_pushrod_retract()
            
            # 旋涂仪推杆控制
            st.subheader("旋涂仪推杆控制")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("旋涂仪推杆推出"):
                    self.spin_coater_pushrod_extend()
            with col2:
                if st.button("旋涂仪推杆收回"):
                    self.spin_coater_pushrod_retract()
            
            # 旋涂仪串口配置
            st.subheader("旋涂仪串口配置")
            spin_coater_port = st.text_input("端口", value=st.session_state.spin_coater_port)
            spin_coater_baudrate = st.number_input("波特率", value=st.session_state.spin_coater_baudrate)
            if st.button("连接旋涂仪"):
                self.connect_spin_coater(spin_coater_port, spin_coater_baudrate)
            
            # 旋涂仪控制
            st.subheader("旋涂仪控制")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("使能开启"):
                    self.spin_coater_enable_on()
                if st.button("真空开启"):
                    self.spin_coater_vacuum_on()
                if st.button("旋涂启动"):
                    self.spin_coater_spin_start()
                if st.button("多步旋涂"):
                    self.spin_coater_multi_step_start()
            with col2:
                if st.button("使能关闭"):
                    self.spin_coater_enable_off()
                if st.button("真空关闭"):
                    self.spin_coater_vacuum_off()
                if st.button("旋涂停止"):
                    self.spin_coater_spin_stop()
                if st.button("手动回原"):
                    self.spin_coater_manual_home()
        
        with tab4:
            st.header("运行日志")
            if st.button("清空日志"):
                st.session_state.logs = []
            
            # 显示日志
            for log in st.session_state.logs:
                st.text(log)


if __name__ == '__main__':
    gui = RobotGUIStreamlit()
    gui.render()

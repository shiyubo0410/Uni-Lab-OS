#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人图形化编程界面
提供可视化编程环境，支持路点管理、运动指令编辑、程序运行等功能
"""

import sys
import os
import time
import json
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum

# 添加路径
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'utils'))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'skills' / 'changguangxi'))

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
    from robot_utils import CGXiRobot
    from robot_control_utils import create_robot_controller, Waypoint
    from gripper_pushrod_utils import GripperControl, PushRodControl, gripper_open, gripper_close, upper_pushrod_extend, upper_pushrod_retract, lower_pushrod_extend, lower_pushrod_retract, spin_coater_pushrod_extend, spin_coater_pushrod_retract
    from spin_coater_utils import SpinCoaterControl, enable_on, enable_off, vacuum_on, vacuum_off, spin_start, spin_stop, multi_step_start, multi_step_stop, manual_home, wait_for_spin_completion
    from serial_utils import SerialClient
except ImportError as e:
    print(f"❌ 无法导入模块 - {e}")
    sys.exit(1)


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


class RobotGUI:
    """机器人图形化编程界面"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("机器人图形化编程系统")
        self.root.geometry("1400x900")
        
        # 初始化变量
        self.robot = None
        self.controller = None
        self.connected = False
        self.waypoints: List[Waypoint] = []
        self.current_program = RobotProgram()
        self.programs: List[RobotProgram] = []
        self.current_file_path: Optional[str] = None  # 当前程序文件路径
        self.recent_files: List[str] = []  # 最近打开的文件列表
        self.max_recent_files = 5  # 最大最近文件数
        # 夹爪和推杆控制
        self.gripper_control = GripperControl()
        self.pushrod_control = PushRodControl()
        self.gripper_connected = False
        self.pushrod_connected = False
        # 推杆控制配置
        self.relay_ip = "192.168.1.100"
        self.relay_port = 50000
        # 路点自动保存配置
        self.waypoints_file = "waypoints.json"
        self.auto_save_waypoints = True
        # 程序自动保存配置
        self.programs_dir = Path("programs")
        self.programs_dir.mkdir(exist_ok=True)
        self.auto_save_program = True
        self.auto_save_program_file = self.programs_dir / "autosave.json"
        self.config_file = "gui_config.json"
        # 旋涂仪控制
        self.spin_coater_control = SpinCoaterControl()
        self.spin_coater_connected = False
        # 旋涂仪串口配置
        self.spin_coater_port = "COM6"
        self.spin_coater_baudrate = 19200
        self.spin_coater_connect_baudrate = 9600
        self.spin_coater_data_bits = 8
        self.spin_coater_stop_bits = 1
        self.spin_coater_parity = "EVEN"
        self.spin_coater_station = 1
        
        # 创建界面
        self.create_menu()
        self.create_layout()
        
        # 加载保存的数据
        self.load_config()
        self.load_data()
        self.load_auto_saved_program()
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        
        # 文件菜单
        self.file_menu = tk.Menu(menubar, tearoff=0)
        self.file_menu.add_command(label="新建程序 (Ctrl+N)", command=self.new_program, accelerator="Ctrl+N")
        self.file_menu.add_command(label="打开程序 (Ctrl+O)", command=self.open_program, accelerator="Ctrl+O")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="保存程序 (Ctrl+S)", command=self.save_program, accelerator="Ctrl+S")
        self.file_menu.add_command(label="另存为 (Ctrl+Shift+S)", command=self.save_program_as, accelerator="Ctrl+Shift+S")
        self.file_menu.add_separator()
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="最近打开", menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="导入路点", command=self.import_waypoints)
        self.file_menu.add_command(label="导出路点", command=self.export_waypoints)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=self.on_exit)
        menubar.add_cascade(label="文件", menu=self.file_menu)
        
        # 绑定快捷键
        self.root.bind('<Control-n>', lambda e: self.new_program())
        self.root.bind('<Control-o>', lambda e: self.open_program())
        self.root.bind('<Control-s>', lambda e: self.save_program())
        self.root.bind('<Control-Shift-S>', lambda e: self.save_program_as())
        
        # 编辑菜单
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="撤销", command=self.undo)
        edit_menu.add_command(label="重做", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="清空程序", command=self.clear_program)
        menubar.add_cascade(label="编辑", menu=edit_menu)
        
        # 运行菜单
        run_menu = tk.Menu(menubar, tearoff=0)
        run_menu.add_command(label="运行程序", command=self.run_program)
        run_menu.add_command(label="单步运行", command=self.step_program)
        run_menu.add_command(label="停止运行", command=self.stop_program)
        run_menu.add_command(label="手动控制", command=self.open_manual_control)
        menubar.add_cascade(label="运行", menu=run_menu)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def create_layout(self):
        """创建主布局"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # 左侧：路点管理
        self.create_waypoint_panel(main_frame)
        
        # 中间：程序编辑器
        self.create_program_panel(main_frame)
        
        # 右侧：机器人控制
        self.create_control_panel(main_frame)
        
        # 底部：状态栏
        self.create_status_bar(main_frame)
    
    def create_waypoint_panel(self, parent):
        """创建路点管理面板"""
        frame = ttk.LabelFrame(parent, text="路点管理", padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 路点列表
        self.waypoint_listbox = tk.Listbox(frame, height=20, selectmode=tk.SINGLE)
        self.waypoint_listbox.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.waypoint_listbox.bind('<<ListboxSelect>>', self.on_waypoint_select)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.waypoint_listbox.yview)
        scrollbar.grid(row=0, column=2, sticky=(tk.N, tk.S))
        self.waypoint_listbox.config(yscrollcommand=scrollbar.set)
        
        # 路点操作按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=3, pady=5)
        
        ttk.Button(btn_frame, text="记录当前路点", command=self.record_waypoint).grid(row=0, column=0, padx=2)
        ttk.Button(btn_frame, text="删除选中", command=self.delete_waypoint).grid(row=0, column=1, padx=2)
        ttk.Button(btn_frame, text="清空全部", command=self.clear_waypoints).grid(row=0, column=2, padx=2)
        
        ttk.Button(btn_frame, text="移动到路点", command=self.move_to_waypoint).grid(row=1, column=0, padx=2, pady=5)
        ttk.Button(btn_frame, text="导入路点", command=self.import_waypoints).grid(row=1, column=1, padx=2, pady=5)
        ttk.Button(btn_frame, text="导出路点", command=self.export_waypoints).grid(row=1, column=2, padx=2, pady=5)
        
        # 路点信息
        info_frame = ttk.LabelFrame(frame, text="路点信息", padding="5")
        info_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.waypoint_info = scrolledtext.ScrolledText(info_frame, height=8, width=35, state='disabled')
        self.waypoint_info.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def create_program_panel(self, parent):
        """创建程序编辑器面板"""
        frame = ttk.LabelFrame(parent, text="程序编辑器", padding="10")
        frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # 程序列表
        self.program_listbox = tk.Listbox(frame, height=25, selectmode=tk.SINGLE)
        self.program_listbox.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        self.program_listbox.bind('<<ListboxSelect>>', self.on_instruction_select)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.program_listbox.yview)
        scrollbar.grid(row=0, column=3, sticky=(tk.N, tk.S))
        self.program_listbox.config(yscrollcommand=scrollbar.set)
        
        # 指令操作按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=5)
        
        ttk.Button(btn_frame, text="添加指令", command=self.show_instruction_dialog).grid(row=0, column=0, padx=2)
        ttk.Button(btn_frame, text="编辑指令", command=self.edit_instruction).grid(row=0, column=1, padx=2)
        ttk.Button(btn_frame, text="删除指令", command=self.delete_instruction).grid(row=0, column=2, padx=2)
        ttk.Button(btn_frame, text="上移", command=self.move_instruction_up).grid(row=0, column=3, padx=2)
        ttk.Button(btn_frame, text="下移", command=self.move_instruction_down).grid(row=0, column=4, padx=2)
        ttk.Button(btn_frame, text="清空程序", command=self.clear_program).grid(row=0, column=5, padx=2)
        
        # 运行控制
        run_frame = ttk.Frame(frame)
        run_frame.grid(row=2, column=0, columnspan=4, pady=5)
        
        ttk.Button(run_frame, text="▶ 运行程序", command=self.run_program).grid(row=0, column=0, padx=5)
        ttk.Button(run_frame, text="⏭ 单步运行", command=self.step_program).grid(row=0, column=1, padx=5)
        ttk.Button(run_frame, text="⏹ 停止", command=self.stop_program).grid(row=0, column=2, padx=5)
        
        # 指令详情
        info_frame = ttk.LabelFrame(frame, text="指令详情", padding="5")
        info_frame.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.instruction_info = scrolledtext.ScrolledText(info_frame, height=8, width=50, state='disabled')
        self.instruction_info.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def create_control_panel(self, parent):
        """创建机器人控制面板"""
        # 创建外层框架
        outer_frame = ttk.LabelFrame(parent, text="机器人控制", padding="5")
        outer_frame.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        outer_frame.columnconfigure(0, weight=1)
        outer_frame.rowconfigure(0, weight=1)
        
        # 创建Canvas和滚动条
        canvas = tk.Canvas(outer_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        
        # 创建可滚动框架
        frame = ttk.Frame(canvas, padding="5")
        
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 将frame放入canvas
        canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw", width=outer_frame.winfo_width())
        
        # 绑定事件以更新滚动区域
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        
        # 启用鼠标滚轮滚动
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # 连接设置
        conn_frame = ttk.LabelFrame(frame, text="连接设置", padding="5")
        conn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(conn_frame, text="IP地址:").grid(row=0, column=0, sticky=tk.W)
        self.ip_entry = ttk.Entry(conn_frame, width=15)
        self.ip_entry.insert(0, "192.168.6.6")
        self.ip_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(conn_frame, text="端口:").grid(row=1, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(conn_frame, width=15)
        self.port_entry.insert(0, "2323")
        self.port_entry.grid(row=1, column=1, padx=5)
        
        ttk.Button(conn_frame, text="连接", command=self.connect_robot).grid(row=2, column=0, pady=5)
        ttk.Button(conn_frame, text="断开", command=self.disconnect_robot).grid(row=2, column=1, pady=5)
        
        # 电源控制
        power_frame = ttk.LabelFrame(frame, text="电源控制", padding="5")
        power_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Button(power_frame, text="上电", command=self.power_on).grid(row=0, column=0, padx=2)
        ttk.Button(power_frame, text="断电", command=self.power_off).grid(row=0, column=1, padx=2)
        ttk.Button(power_frame, text="使能", command=self.enable_robot).grid(row=1, column=0, padx=2)
        ttk.Button(power_frame, text="去使能", command=self.disable_robot).grid(row=1, column=1, padx=2)
        ttk.Button(power_frame, text="故障复位", command=self.fault_reset).grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=2)
        
        # 快捷移动
        move_frame = ttk.LabelFrame(frame, text="快捷移动", padding="5")
        move_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Button(move_frame, text="Z轴上升 50mm", command=lambda: self.move_world_z(50)).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(move_frame, text="Z轴下降 50mm", command=lambda: self.move_world_z(-50)).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(move_frame, text="末端垂直", command=self.set_tcp_vertical).grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=2, pady=2)
        
        # 夹爪和推杆控制
        actuator_frame = ttk.LabelFrame(frame, text="夹爪和推杆控制", padding="5")
        actuator_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 继电器配置
        ttk.Label(actuator_frame, text="继电器配置:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Label(actuator_frame, text="IP地址:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.relay_ip_entry = ttk.Entry(actuator_frame, width=15)
        self.relay_ip_entry.insert(0, self.relay_ip)
        self.relay_ip_entry.grid(row=1, column=1, padx=2, pady=2)
        ttk.Label(actuator_frame, text="端口:").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.relay_port_entry = ttk.Entry(actuator_frame, width=8)
        self.relay_port_entry.insert(0, str(self.relay_port))
        self.relay_port_entry.grid(row=1, column=3, padx=2, pady=2)
        ttk.Button(actuator_frame, text="应用配置", command=self.apply_relay_config).grid(row=2, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=2)
        
        # 夹爪控制
        ttk.Label(actuator_frame, text="夹爪:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Button(actuator_frame, text="连接", command=self.connect_gripper).grid(row=4, column=0, padx=2)
        ttk.Button(actuator_frame, text="初始化", command=self.initialize_gripper).grid(row=4, column=1, padx=2)
        ttk.Button(actuator_frame, text="打开", command=self.gripper_open).grid(row=5, column=0, padx=2, pady=2)
        ttk.Button(actuator_frame, text="关闭", command=self.gripper_close).grid(row=5, column=1, padx=2, pady=2)
        
        # 上推杆控制
        ttk.Label(actuator_frame, text="上推杆:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Button(actuator_frame, text="推出", command=self.upper_pushrod_extend).grid(row=7, column=0, padx=2)
        ttk.Button(actuator_frame, text="收回", command=self.upper_pushrod_retract).grid(row=7, column=1, padx=2)
        
        # 下推杆控制
        ttk.Label(actuator_frame, text="下推杆:", font=('Arial', 10, 'bold')).grid(row=8, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Button(actuator_frame, text="推出", command=self.lower_pushrod_extend).grid(row=9, column=0, padx=2)
        ttk.Button(actuator_frame, text="收回", command=self.lower_pushrod_retract).grid(row=9, column=1, padx=2)
        
        # 旋涂仪推杆控制
        ttk.Label(actuator_frame, text="旋涂仪推杆:", font=('Arial', 10, 'bold')).grid(row=10, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Button(actuator_frame, text="推出", command=self.spin_coater_pushrod_extend).grid(row=11, column=0, padx=2)
        ttk.Button(actuator_frame, text="收回", command=self.spin_coater_pushrod_retract).grid(row=11, column=1, padx=2)
        
        # 旋涂仪串口配置
        ttk.Label(actuator_frame, text="旋涂仪串口配置:", font=('Arial', 10, 'bold')).grid(row=12, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Label(actuator_frame, text="端口:").grid(row=13, column=0, sticky=tk.W, pady=1)
        self.spin_coater_port_entry = ttk.Entry(actuator_frame, width=10)
        self.spin_coater_port_entry.insert(0, self.spin_coater_port)
        self.spin_coater_port_entry.grid(row=13, column=1, padx=2, pady=1)
        ttk.Label(actuator_frame, text="波特率:").grid(row=14, column=0, sticky=tk.W, pady=1)
        self.spin_coater_baudrate_entry = ttk.Entry(actuator_frame, width=10)
        self.spin_coater_baudrate_entry.insert(0, str(self.spin_coater_baudrate))
        self.spin_coater_baudrate_entry.grid(row=14, column=1, padx=2, pady=1)
        ttk.Button(actuator_frame, text="连接旋涂仪", command=self.connect_spin_coater).grid(row=15, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2)
        
        # 旋涂仪控制
        ttk.Label(actuator_frame, text="旋涂仪控制:", font=('Arial', 10, 'bold')).grid(row=16, column=0, sticky=tk.W, pady=2, columnspan=3)
        ttk.Button(actuator_frame, text="使能开启", command=self.spin_coater_enable_on).grid(row=17, column=0, padx=2, pady=1)
        ttk.Button(actuator_frame, text="使能关闭", command=self.spin_coater_enable_off).grid(row=17, column=1, padx=2, pady=1)
        ttk.Button(actuator_frame, text="真空开启", command=self.spin_coater_vacuum_on).grid(row=18, column=0, padx=2, pady=1)
        ttk.Button(actuator_frame, text="真空关闭", command=self.spin_coater_vacuum_off).grid(row=18, column=1, padx=2, pady=1)
        ttk.Button(actuator_frame, text="旋涂启动", command=self.spin_coater_spin_start).grid(row=19, column=0, padx=2, pady=1)
        ttk.Button(actuator_frame, text="旋涂停止", command=self.spin_coater_spin_stop).grid(row=19, column=1, padx=2, pady=1)
        ttk.Button(actuator_frame, text="多步旋涂", command=self.spin_coater_multi_step_start).grid(row=20, column=0, padx=2, pady=1)
        ttk.Button(actuator_frame, text="手动回原", command=self.spin_coater_manual_home).grid(row=20, column=1, padx=2, pady=1)
        
        # 日志输出
        log_frame = ttk.LabelFrame(frame, text="运行日志", padding="5")
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=35, state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 清空日志按钮
        ttk.Button(log_frame, text="清空日志", command=self.clear_log).grid(row=1, column=0, pady=5)
    
    def create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.status_label = ttk.Label(status_frame, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.robot_status_label = ttk.Label(status_frame, text="未连接", relief=tk.SUNKEN, width=20)
        self.robot_status_label.grid(row=0, column=1, padx=5)
    
    # ==================== 路点管理 ====================
    
    def record_waypoint(self):
        """记录当前路点"""
        if not self.connected or not self.controller:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        name = simpledialog.askstring("路点名称", "请输入路点名称:", parent=self.root)
        if not name:
            name = f"路点_{len(self.waypoints)+1}"
        
        wp = self.controller.record_current_waypoint(name)
        if wp:
            self.waypoints.append(wp)
            self.update_waypoint_list()
            self.log(f"✓ 记录路点: {name}")
            self.save_waypoints_to_file()
    
    def delete_waypoint(self):
        """删除选中路点"""
        selection = self.waypoint_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        name = self.waypoints[idx].name
        if messagebox.askyesno("确认", f"确定删除路点 '{name}'?"):
            self.waypoints.pop(idx)
            self.update_waypoint_list()
            self.log(f"✓ 删除路点: {name}")
            self.save_waypoints_to_file()
    
    def clear_waypoints(self):
        """清空所有路点"""
        if not self.waypoints:
            return
        
        if messagebox.askyesno("确认", f"确定清空 {len(self.waypoints)} 个路点?"):
            self.waypoints.clear()
            self.update_waypoint_list()
            self.log(f"✓ 清空所有路点")
            self.save_waypoints_to_file()
    
    def move_to_waypoint(self):
        """移动到选中路点"""
        selection = self.waypoint_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个路点")
            return
        
        if not self.connected or not self.controller:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        idx = selection[0]
        wp = self.waypoints[idx]
        if self.controller.move_to_waypoint(idx, block=True):
            self.log(f"✓ 移动到路点: {wp.name}")
        else:
            self.log(f"❌ 移动到路点失败: {wp.name}")
    
    def update_waypoint_list(self):
        """更新路点列表"""
        self.waypoint_listbox.delete(0, tk.END)
        for i, wp in enumerate(self.waypoints):
            self.waypoint_listbox.insert(tk.END, f"[{i}] {wp.name}")
    
    def on_waypoint_select(self, event):
        """路点选择事件"""
        selection = self.waypoint_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        wp = self.waypoints[idx]
        
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
        
        self.waypoint_info.config(state='normal')
        self.waypoint_info.delete(1.0, tk.END)
        self.waypoint_info.insert(tk.END, info)
        self.waypoint_info.config(state='disabled')
    
    # ==================== 程序编辑 ====================
    
    def show_instruction_dialog(self):
        """显示添加指令对话框"""
        dialog = InstructionDialog(self.root, self.waypoints)
        dialog.dialog.wait_window()  # 等待对话框关闭
        if dialog.result:
            instr = dialog.result
            self.current_program.add_instruction(instr)
            self.update_program_list()
            self.log(f"✓ 添加指令: {instr.type.value}")
    
    def edit_instruction(self):
        """编辑选中指令"""
        selection = self.program_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一条指令")
            return
        
        idx = selection[0]
        instr = self.current_program.instructions[idx]
        
        dialog = InstructionDialog(self.root, self.waypoints, instr)
        dialog.dialog.wait_window()  # 等待对话框关闭
        if dialog.result:
            self.current_program.instructions[idx] = dialog.result
            self.update_program_list()
            self.log(f"✓ 编辑指令: {dialog.result.type.value}")
    
    def delete_instruction(self):
        """删除选中指令"""
        selection = self.program_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        instr = self.current_program.instructions[idx]
        if messagebox.askyesno("确认", f"确定删除指令 '{instr.type.value}'?"):
            self.current_program.remove_instruction(idx)
            self.update_program_list()
            self.log(f"✓ 删除指令: {instr.type.value}")
    
    def move_instruction_up(self):
        """上移指令"""
        selection = self.program_listbox.curselection()
        if not selection or selection[0] == 0:
            return
        
        idx = selection[0]
        self.current_program.move_instruction(idx, idx - 1)
        self.update_program_list()
        self.program_listbox.selection_set(idx - 1)
    
    def move_instruction_down(self):
        """下移指令"""
        selection = self.program_listbox.curselection()
        if not selection or selection[0] >= len(self.current_program.instructions) - 1:
            return
        
        idx = selection[0]
        self.current_program.move_instruction(idx, idx + 1)
        self.update_program_list()
        self.program_listbox.selection_set(idx + 1)
    
    def clear_program(self):
        """清空程序"""
        if not self.current_program.instructions:
            return
        
        if messagebox.askyesno("确认", f"确定清空 {len(self.current_program.instructions)} 条指令?"):
            self.current_program.clear()
            self.update_program_list()
            self.log(f"✓ 清空程序")
    
    def update_program_list(self):
        """更新程序列表"""
        self.program_listbox.delete(0, tk.END)
        for i, instr in enumerate(self.current_program.instructions):
            self.program_listbox.insert(tk.END, f"{i+1}. {instr}")
    
    def on_instruction_select(self, event):
        """指令选择事件"""
        selection = self.program_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        instr = self.current_program.instructions[idx]
        
        info = f"类型: {instr.type.value}\n"
        info += f"注释: {instr.comment}\n\n"
        info += f"参数:\n"
        for key, value in instr.params.items():
            info += f"  {key}: {value}\n"
        
        self.instruction_info.config(state='normal')
        self.instruction_info.delete(1.0, tk.END)
        self.instruction_info.insert(tk.END, info)
        self.instruction_info.config(state='disabled')
    
    # ==================== 程序运行 ====================
    
    def run_program(self):
        """运行程序"""
        if not self.current_program.instructions:
            messagebox.showwarning("提示", "程序为空")
            return
        
        if not self.connected or not self.controller:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        self.log("=" * 50)
        self.log("开始运行程序")
        self.log("=" * 50)
        
        try:
            for i, instr in enumerate(self.current_program.instructions):
                self.log(f"\n[{i+1}/{len(self.current_program.instructions)}] 执行: {instr.type.value}")
                self.highlight_instruction(i)
                self.root.update()
                
                if not self.execute_instruction(instr):
                    self.log(f"❌ 程序执行失败，停止运行")
                    return
            
            self.log("\n" + "=" * 50)
            self.log("程序执行完成")
            self.log("=" * 50)
            messagebox.showinfo("完成", "程序执行完成")
        
        except Exception as e:
            self.log(f"❌ 程序执行异常: {e}")
            messagebox.showerror("错误", f"程序执行异常: {e}")
    
    def step_program(self):
        """单步运行"""
        if not self.connected or not self.controller:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        # 获取当前选中的指令，如果没有则选择第一条
        selection = self.program_listbox.curselection()
        if selection:
            idx = selection[0]
        else:
            idx = 0
        
        if idx >= len(self.current_program.instructions):
            messagebox.showinfo("提示", "已到达程序末尾")
            return
        
        instr = self.current_program.instructions[idx]
        self.log(f"[单步] 执行: {instr.type.value}")
        self.highlight_instruction(idx)
        
        if self.execute_instruction(instr):
            # 自动选择下一条指令
            if idx < len(self.current_program.instructions) - 1:
                self.program_listbox.selection_set(idx + 1)
                self.on_instruction_select(None)
    
    def stop_program(self):
        """停止运行"""
        if self.controller and self.controller.robot:
            try:
                self.controller.robot.disable()
                self.log("⏹ 程序已停止")
            except:
                pass
    
    def execute_instruction(self, instr: Instruction) -> bool:
        """执行单条指令"""
        try:
            if instr.type == InstructionType.MOVE_TO_WAYPOINT:
                idx = instr.params.get("waypoint_index", 0)
                if not self.waypoints:
                    self.log("❌ 路点列表为空")
                    return False
                if idx < len(self.waypoints):
                    return self.controller.move_to_waypoint(idx, block=True)
                else:
                    self.log(f"❌ 路点索引 {idx} 无效")
                    return False
            
            elif instr.type == InstructionType.MOVE_WORLD_Z:
                distance = instr.params.get("distance", 0)
                speed = instr.params.get("speed", 30.0)
                return self.controller.move_world_z(distance, speed=speed, block=True)
            
            elif instr.type == InstructionType.MOVE_WORLD_REL:
                dx = instr.params.get("dx", 0)
                dy = instr.params.get("dy", 0)
                dz = instr.params.get("dz", 0)
                speed = instr.params.get("speed", 30.0)
                return self.controller.move_world_relative(dx, dy, dz, speed=speed, block=True)
            
            elif instr.type == InstructionType.SET_TCP_VERTICAL:
                speed = instr.params.get("speed", 30.0)
                return self.controller.set_tcp_vertical(speed=speed, block=True)
            
            elif instr.type == InstructionType.SET_TCP_ORIENTATION:
                rx = instr.params.get("rx", 0)
                ry = instr.params.get("ry", 0)
                rz = instr.params.get("rz", 0)
                speed = instr.params.get("speed", 30.0)
                return self.controller.set_tcp_orientation(rx, ry, rz, speed=speed, block=True)
            
            elif instr.type == InstructionType.DELAY:
                delay = instr.params.get("delay", 1.0)
                self.log(f"  延时 {delay} 秒...")
                time.sleep(delay)
                return True
            
            elif instr.type == InstructionType.GRIPPER_OPEN:
                self.log("  夹爪打开")
                if self.gripper_connected:
                    return gripper_open(self.gripper_control)
                else:
                    self.log("  夹爪未连接")
                    return False
            
            elif instr.type == InstructionType.GRIPPER_CLOSE:
                self.log("  夹爪关闭")
                if self.gripper_connected:
                    return gripper_close(self.gripper_control)
                else:
                    self.log("  夹爪未连接")
                    return False
            
            elif instr.type == InstructionType.UPPER_PUSHROD_EXTEND:
                self.log("  上推杆推出")
                return upper_pushrod_extend(self.pushrod_control)
            
            elif instr.type == InstructionType.UPPER_PUSHROD_RETRACT:
                self.log("  上推杆收回")
                return upper_pushrod_retract(self.pushrod_control)
            
            elif instr.type == InstructionType.LOWER_PUSHROD_EXTEND:
                self.log("  下推杆推出")
                return lower_pushrod_extend(self.pushrod_control)
            
            elif instr.type == InstructionType.LOWER_PUSHROD_RETRACT:
                self.log("  下推杆收回")
                return lower_pushrod_retract(self.pushrod_control)
            
            elif instr.type == InstructionType.SPIN_COATER_PUSHROD_EXTEND:
                self.log("  旋涂仪推杆推出")
                return spin_coater_pushrod_extend(self.pushrod_control)
            
            elif instr.type == InstructionType.SPIN_COATER_PUSHROD_RETRACT:
                self.log("  旋涂仪推杆收回")
                return spin_coater_pushrod_retract(self.pushrod_control)
            
            elif instr.type == InstructionType.SPIN_COATER_ENABLE_ON:
                self.log("  旋涂仪使能开启")
                return enable_on(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_ENABLE_OFF:
                self.log("  旋涂仪使能关闭")
                return enable_off(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_VACUUM_ON:
                self.log("  旋涂仪真空开启")
                return vacuum_on(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_VACUUM_OFF:
                self.log("  旋涂仪真空关闭")
                return vacuum_off(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_SPIN_START:
                self.log("  旋涂仪旋涂启动")
                return spin_start(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_SPIN_STOP:
                self.log("  旋涂仪旋涂停止")
                return spin_stop(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_MULTI_STEP_START:
                self.log("  旋涂仪多步旋涂")
                return multi_step_start(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_MANUAL_HOME:
                self.log("  旋涂仪手动回原")
                return manual_home(self.spin_coater_control)
            
            elif instr.type == InstructionType.SPIN_COATER_WAIT_COMPLETION:
                self.log("  等待旋涂结束...")
                timeout = instr.params.get("timeout", 60)
                return wait_for_spin_completion(self.spin_coater_control, timeout=timeout)
            
            return False
        
        except Exception as e:
            self.log(f"❌ 执行指令失败: {e}")
            return False
    
    def highlight_instruction(self, idx: int):
        """高亮显示指令"""
        self.program_listbox.selection_clear(0, tk.END)
        self.program_listbox.selection_set(idx)
        self.program_listbox.see(idx)
    
    # ==================== 机器人控制 ====================
    
    def connect_robot(self):
        """连接机器人"""
        try:
            ip = self.ip_entry.get()
            port = int(self.port_entry.get())
            
            self.robot = CGXiRobot(ip=ip, port=port)
            if self.robot.connect():
                self.controller = create_robot_controller(self.robot)
                # 同步路点到控制器
                if self.waypoints:
                    self.controller.waypoints = self.waypoints
                    self.log(f"✓ 同步路点到控制器: {len(self.waypoints)} 个路点")
                self.connected = True
                self.robot_status_label.config(text="已连接", foreground="green")
                self.log(f"✓ 连接成功: {ip}:{port}")
                messagebox.showinfo("成功", "机器人连接成功")
            else:
                self.log(f"❌ 连接失败")
                messagebox.showerror("错误", "机器人连接失败")
        
        except Exception as e:
            self.log(f"❌ 连接异常: {e}")
            messagebox.showerror("错误", f"连接异常: {e}")
    
    def disconnect_robot(self):
        """断开机器人"""
        if self.robot:
            self.robot.disconnect()
            self.connected = False
            self.controller = None
            self.robot_status_label.config(text="未连接", foreground="red")
            self.log("✓ 已断开连接")
    
    def power_on(self):
        """上电"""
        if not self.connected:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        if self.robot.power_on():
            self.log("✓ 上电成功")
        else:
            self.log("❌ 上电失败")
    
    def power_off(self):
        """断电"""
        if not self.connected:
            return
        
        if self.robot.power_off():
            self.log("✓ 断电成功")
        else:
            self.log("❌ 断电失败")
    
    def enable_robot(self):
        """使能"""
        if not self.connected:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        if self.robot.enable():
            self.log("✓ 使能成功")
        else:
            self.log("❌ 使能失败")
    
    def disable_robot(self):
        """去使能"""
        if not self.connected:
            return
        
        if self.robot.disable():
            self.log("✓ 去使能成功")
        else:
            self.log("❌ 去使能失败")
    
    def fault_reset(self):
        """故障复位"""
        if not self.connected:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        if self.robot.fault_reset():
            self.log("✓ 故障复位成功")
        else:
            self.log("❌ 故障复位失败")
    
    def move_world_z(self, distance: float):
        """Z轴移动"""
        if not self.connected:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        if self.controller.move_world_z(distance, block=True):
            self.log(f"✓ Z轴移动: {distance:+.2f}mm")
        else:
            self.log(f"❌ Z轴移动失败")
    
    def set_tcp_vertical(self):
        """设置TCP垂直"""
        if not self.connected:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        if self.controller.set_tcp_vertical(block=True):
            self.log("✓ TCP已设置为垂直")
        else:
            self.log("❌ TCP垂直设置失败")
    
    # ==================== 夹爪和推杆控制 ====================
    
    def connect_gripper(self):
        """连接夹爪"""
        if self.gripper_control.connect():
            self.gripper_connected = True
            self.log("✓ 夹爪连接成功")
        else:
            self.log("❌ 夹爪连接失败")
    
    def initialize_gripper(self):
        """初始化夹爪"""
        if not self.gripper_connected:
            messagebox.showerror("错误", "请先连接夹爪")
            return
        
        if self.gripper_control.initialize():
            self.log("✓ 夹爪初始化成功")
        else:
            self.log("❌ 夹爪初始化失败")
    
    def gripper_open(self):
        """打开夹爪"""
        if not self.gripper_connected:
            messagebox.showerror("错误", "请先连接夹爪")
            return
        
        if gripper_open(self.gripper_control):
            self.log("✓ 夹爪打开成功")
        else:
            self.log("❌ 夹爪打开失败")
    
    def gripper_close(self):
        """关闭夹爪"""
        if not self.gripper_connected:
            messagebox.showerror("错误", "请先连接夹爪")
            return
        
        if gripper_close(self.gripper_control):
            self.log("✓ 夹爪关闭成功")
        else:
            self.log("❌ 夹爪关闭失败")
    
    def upper_pushrod_extend(self):
        """上推杆推出"""
        if upper_pushrod_extend(self.pushrod_control):
            self.log("✓ 上推杆推出成功")
        else:
            self.log("❌ 上推杆推出失败")
    
    def upper_pushrod_retract(self):
        """上推杆收回"""
        if upper_pushrod_retract(self.pushrod_control):
            self.log("✓ 上推杆收回成功")
        else:
            self.log("❌ 上推杆收回失败")
    
    def lower_pushrod_extend(self):
        """下推杆推出"""
        if lower_pushrod_extend(self.pushrod_control):
            self.log("✓ 下推杆推出成功")
        else:
            self.log("❌ 下推杆推出失败")
    
    def lower_pushrod_retract(self):
        """下推杆收回"""
        if lower_pushrod_retract(self.pushrod_control):
            self.log("✓ 下推杆收回成功")
        else:
            self.log("❌ 下推杆收回失败")
    
    def spin_coater_pushrod_extend(self):
        """旋涂仪推杆推出"""
        if spin_coater_pushrod_extend(self.pushrod_control):
            self.log("✓ 旋涂仪推杆推出成功")
        else:
            self.log("❌ 旋涂仪推杆推出失败")
    
    def spin_coater_pushrod_retract(self):
        """旋涂仪推杆收回"""
        if spin_coater_pushrod_retract(self.pushrod_control):
            self.log("✓ 旋涂仪推杆收回成功")
        else:
            self.log("❌ 旋涂仪推杆收回失败")
    
    # ==================== 旋涂仪控制 ====================
    
    def spin_coater_enable_on(self):
        """旋涂仪使能开启"""
        if enable_on(self.spin_coater_control):
            self.log("✓ 旋涂仪使能开启成功")
        else:
            self.log("❌ 旋涂仪使能开启失败")
    
    def spin_coater_enable_off(self):
        """旋涂仪使能关闭"""
        if enable_off(self.spin_coater_control):
            self.log("✓ 旋涂仪使能关闭成功")
        else:
            self.log("❌ 旋涂仪使能关闭失败")
    
    def spin_coater_vacuum_on(self):
        """旋涂仪真空开启"""
        if vacuum_on(self.spin_coater_control):
            self.log("✓ 旋涂仪真空开启成功")
        else:
            self.log("❌ 旋涂仪真空开启失败")
    
    def spin_coater_vacuum_off(self):
        """旋涂仪真空关闭"""
        if vacuum_off(self.spin_coater_control):
            self.log("✓ 旋涂仪真空关闭成功")
        else:
            self.log("❌ 旋涂仪真空关闭失败")
    
    def spin_coater_spin_start(self):
        """旋涂仪旋涂启动"""
        if spin_start(self.spin_coater_control):
            self.log("✓ 旋涂仪旋涂启动成功")
        else:
            self.log("❌ 旋涂仪旋涂启动失败")
    
    def spin_coater_spin_stop(self):
        """旋涂仪旋涂停止"""
        if spin_stop(self.spin_coater_control):
            self.log("✓ 旋涂仪旋涂停止成功")
        else:
            self.log("❌ 旋涂仪旋涂停止失败")
    
    def spin_coater_multi_step_start(self):
        """旋涂仪多步旋涂启动"""
        if multi_step_start(self.spin_coater_control):
            self.log("✓ 旋涂仪多步旋涂启动成功")
        else:
            self.log("❌ 旋涂仪多步旋涂启动失败")
    
    def spin_coater_manual_home(self):
        """旋涂仪手动回原"""
        if manual_home(self.spin_coater_control):
            self.log("✓ 旋涂仪手动回原成功")
        else:
            self.log("❌ 旋涂仪手动回原失败")
    
    def connect_spin_coater(self):
        """连接旋涂仪"""
        try:
            # 获取串口配置
            port = self.spin_coater_port_entry.get()
            baudrate = int(self.spin_coater_baudrate_entry.get())
            
            # 创建串口客户端
            serial_client = SerialClient(
                port=port,
                baudrate=baudrate,
                data_bits=self.spin_coater_data_bits,
                stop_bits=self.spin_coater_stop_bits,
                parity=self.spin_coater_parity
            )
            
            # 连接串口（使用特殊流程：先9600，再切换到目标波特率）
            if serial_client.connect(special_flow=True):
                # 更新旋涂仪控制对象
                self.spin_coater_control.serial_client = serial_client
                self.spin_coater_connected = True
                self.log(f"✓ 旋涂仪连接成功 (端口: {port}, 波特率: {baudrate})")
            else:
                self.log(f"❌ 旋涂仪连接失败 (端口: {port})")
        except Exception as e:
            self.log(f"❌ 旋涂仪连接出错: {e}")
    
    def apply_relay_config(self):
        """应用继电器配置"""
        try:
            new_ip = self.relay_ip_entry.get().strip()
            new_port = int(self.relay_port_entry.get().strip())
            
            # 更新配置
            self.relay_ip = new_ip
            self.relay_port = new_port
            
            # 创建新的PushRodControl对象
            self.pushrod_control = PushRodControl(relay_ip=new_ip, relay_port=new_port)
            
            self.log(f"✓ 继电器配置已更新: {new_ip}:{new_port}")
            messagebox.showinfo("成功", f"继电器配置已更新:\nIP: {new_ip}\n端口: {new_port}")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的端口号")
        except Exception as e:
            messagebox.showerror("错误", f"配置更新失败: {e}")
    
    # ==================== 文件操作 ====================
    
    def new_program(self):
        """新建程序"""
        # 检查当前程序是否需要保存
        if self.current_program.instructions:
            if not messagebox.askyesno("确认", "当前程序未保存，确定要新建程序吗?"):
                return
        
        self.current_program = RobotProgram()
        self.current_file_path = None
        self.update_program_list()
        self.update_title()
        self.log("✓ 新建程序")
    
    def open_program(self, filepath: str = None):
        """打开程序"""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                title="打开程序",
                filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
                initialdir=str(self.programs_dir)
            )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.current_program = RobotProgram.from_dict(data)
            self.current_file_path = filepath
            self.update_program_list()
            self.update_title()
            self.add_recent_file(filepath)
            self.log(f"✓ 打开程序: {filepath}")
        
        except Exception as e:
            messagebox.showerror("错误", f"打开程序失败: {e}")
    
    def save_program(self):
        """保存程序"""
        if self.current_file_path:
            self._save_program_to_file(self.current_file_path)
        else:
            self.save_program_as()
    
    def save_program_as(self):
        """另存为"""
        filepath = filedialog.asksaveasfilename(
            title="保存程序",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            initialdir=str(self.programs_dir)
        )
        
        if not filepath:
            return
        
        self.current_program.name = Path(filepath).stem
        self.current_file_path = filepath
        self._save_program_to_file(filepath)
        self.update_title()
        self.add_recent_file(filepath)
    
    def _save_program_to_file(self, filepath: str):
        """保存程序到文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.current_program.to_dict(), f, indent=2, ensure_ascii=False)
            self.log(f"✓ 保存程序: {filepath}")
            messagebox.showinfo("成功", "程序保存成功")
            # 同时保存到自动保存文件
            if self.auto_save_program:
                self.auto_save_current_program()
        
        except Exception as e:
            messagebox.showerror("错误", f"保存程序失败: {e}")
    
    def import_waypoints(self):
        """导入路点"""
        filepath = filedialog.askopenfilename(
            title="导入路点",
            filetypes=[
                ("JSON文件", "*.json"),
                ("CSV文件", "*.csv"),
                ("TXT文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        if not self.connected or not self.controller:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        if self.controller.load_waypoints(filepath, format="auto"):
            self.waypoints = self.controller.waypoints
            self.update_waypoint_list()
            self.log(f"✓ 导入路点: {filepath}")
            self.save_waypoints_to_file()
    
    def export_waypoints(self):
        """导出路点"""
        if not self.waypoints:
            messagebox.showwarning("提示", "没有路点可导出")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="导出路点",
            defaultextension=".json",
            filetypes=[
                ("JSON文件", "*.json"),
                ("CSV文件", "*.csv"),
                ("TXT文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        if not self.connected or not self.controller:
            messagebox.showerror("错误", "请先连接机器人")
            return
        
        self.controller.waypoints = self.waypoints
        suffix = Path(filepath).suffix.lower()
        fmt = "json" if suffix == ".json" else ("csv" if suffix == ".csv" else "txt")
        
        if self.controller.save_waypoints(filepath, format=fmt):
            self.log(f"✓ 导出路点: {filepath}")
    
    # ==================== 其他功能 ====================
    
    def log(self, message: str):
        """添加日志"""
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')
        self.status_label.config(text=message)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
    
    def undo(self):
        """撤销"""
        pass
    
    def redo(self):
        """重做"""
        pass
    
    def show_help(self):
        """显示帮助"""
        help_text = """
机器人图形化编程系统 - 使用说明

1. 路点管理
   - 点击"记录当前路点"记录当前位置
   - 选中路点后可查看详情或移动到该路点
   - 支持导入/导出路点文件

2. 程序编辑
   - 点击"添加指令"选择要执行的指令
   - 可以上移/下移调整指令顺序
   - 支持编辑/删除指令

3. 程序运行
   - 点击"运行程序"执行完整程序
   - 点击"单步运行"逐条执行指令
   - 点击"停止"中断程序执行

4. 机器人控制
   - 设置IP和端口后点击"连接"
   - 上电/使能后才能执行运动
   - 支持快捷移动和末端垂直设置

5. 文件操作
   - 支持保存/打开程序文件
   - 程序文件格式为JSON
        """
        messagebox.showinfo("使用说明", help_text)
    
    def show_about(self):
        """显示关于"""
        about_text = """
机器人图形化编程系统
版本: 1.0

支持CGXi协作机器人的图形化编程
提供路点管理、程序编辑、运动控制等功能
        """
        messagebox.showinfo("关于", about_text)
    
    def load_data(self):
        """加载保存的数据"""
        try:
            # 自动加载路点文件
            import os
            if os.path.exists(self.waypoints_file):
                if self.connected and self.controller:
                    if self.controller.load_waypoints(self.waypoints_file, format="json"):
                        self.waypoints = self.controller.waypoints
                        self.update_waypoint_list()
                        self.log(f"✓ 自动加载路点: {len(self.waypoints)} 个路点")
                else:
                    # 先加载到内存，等连接机器人后再同步
                    import json
                    with open(self.waypoints_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    from robot_control_utils import Waypoint
                    self.waypoints = [Waypoint.from_dict(wp_data) for wp_data in data.get('waypoints', [])]
                    self.update_waypoint_list()
                    self.log(f"✓ 自动加载路点: {len(self.waypoints)} 个路点")
        except Exception as e:
            self.log(f"❌ 自动加载路点失败: {e}")
    
    def save_waypoints_to_file(self):
        """自动保存路点到文件"""
        if self.auto_save_waypoints and self.waypoints:
            try:
                import json
                data = {
                    "waypoints": [wp.to_dict() for wp in self.waypoints],
                    "count": len(self.waypoints),
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "version": "1.0"
                }
                with open(self.waypoints_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.log(f"✓ 自动保存路点: {len(self.waypoints)} 个路点")
            except Exception as e:
                self.log(f"❌ 自动保存路点失败: {e}")

    # ==================== 程序保存和配置管理 ====================

    def update_title(self):
        """更新窗口标题"""
        title = "机器人图形化编程系统"
        if self.current_program.name and self.current_program.name != "未命名程序":
            title += f" - {self.current_program.name}"
        if self.current_file_path:
            title += f" [{self.current_file_path}]"
        self.root.title(title)

    def add_recent_file(self, filepath: str):
        """添加文件到最近文件列表"""
        # 移除已存在的相同路径
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        # 添加到开头
        self.recent_files.insert(0, filepath)
        # 限制数量
        self.recent_files = self.recent_files[:self.max_recent_files]
        # 更新菜单
        self.update_recent_menu()
        # 保存配置
        self.save_config()

    def update_recent_menu(self):
        """更新最近文件菜单"""
        # 清空菜单
        self.recent_menu.delete(0, tk.END)
        
        if not self.recent_files:
            self.recent_menu.add_command(label="(无)", state=tk.DISABLED)
            return
        
        for filepath in self.recent_files:
            # 显示文件名和路径
            display_name = f"{Path(filepath).name}"
            self.recent_menu.add_command(
                label=display_name,
                command=lambda fp=filepath: self.open_program(fp)
            )
        
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="清除历史", command=self.clear_recent_files)

    def clear_recent_files(self):
        """清除最近文件列表"""
        self.recent_files.clear()
        self.update_recent_menu()
        self.save_config()
        self.log("✓ 清除最近文件列表")

    def save_config(self):
        """保存配置到文件"""
        try:
            config = {
                "recent_files": self.recent_files,
                "max_recent_files": self.max_recent_files,
                "auto_save_program": self.auto_save_program,
                "relay_ip": self.relay_ip,
                "relay_port": self.relay_port,
                "spin_coater_port": self.spin_coater_port,
                "spin_coater_baudrate": self.spin_coater_baudrate,
                "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"❌ 保存配置失败: {e}")

    def load_config(self):
        """从文件加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.recent_files = config.get("recent_files", [])
                self.max_recent_files = config.get("max_recent_files", 5)
                self.auto_save_program = config.get("auto_save_program", True)
                self.relay_ip = config.get("relay_ip", "192.168.1.100")
                self.relay_port = config.get("relay_port", 50000)
                self.spin_coater_port = config.get("spin_coater_port", "COM6")
                self.spin_coater_baudrate = config.get("spin_coater_baudrate", 19200)
                
                # 更新UI中的配置值
                self.update_config_ui()
                # 更新最近文件菜单
                self.update_recent_menu()
                self.log("✓ 加载配置成功")
        except Exception as e:
            self.log(f"❌ 加载配置失败: {e}")

    def update_config_ui(self):
        """更新配置相关的UI元素"""
        # 更新继电器配置输入框
        if hasattr(self, 'relay_ip_entry'):
            self.relay_ip_entry.delete(0, tk.END)
            self.relay_ip_entry.insert(0, self.relay_ip)
        if hasattr(self, 'relay_port_entry'):
            self.relay_port_entry.delete(0, tk.END)
            self.relay_port_entry.insert(0, str(self.relay_port))
        # 更新旋涂仪配置输入框
        if hasattr(self, 'spin_coater_port_entry'):
            self.spin_coater_port_entry.delete(0, tk.END)
            self.spin_coater_port_entry.insert(0, self.spin_coater_port)
        if hasattr(self, 'spin_coater_baudrate_entry'):
            self.spin_coater_baudrate_entry.delete(0, tk.END)
            self.spin_coater_baudrate_entry.insert(0, str(self.spin_coater_baudrate))

    def auto_save_current_program(self):
        """自动保存当前程序"""
        try:
            with open(self.auto_save_program_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_program.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"❌ 自动保存程序失败: {e}")

    def load_auto_saved_program(self):
        """加载自动保存的程序"""
        try:
            if os.path.exists(self.auto_save_program_file):
                with open(self.auto_save_program_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.current_program = RobotProgram.from_dict(data)
                self.update_program_list()
                self.update_title()
                self.log(f"✓ 自动加载程序: {self.current_program.name}")
        except Exception as e:
            self.log(f"❌ 自动加载程序失败: {e}")

    def open_manual_control(self):
        """打开手动控制窗口"""
        ManualControlWindow(self.root, self)

    def on_exit(self):
        """退出程序"""
        # 退出前保存路点和配置
        self.save_waypoints_to_file()
        self.save_config()
        
        # 自动保存当前程序
        if self.auto_save_program:
            self.auto_save_current_program()
        
        if self.connected:
            if messagebox.askyesno("确认", "机器人已连接，确定要退出吗?"):
                self.disconnect_robot()
                self.root.quit()
        else:
            self.root.quit()


class InstructionDialog:
    """指令对话框"""
    
    def __init__(self, parent, waypoints: List[Waypoint], instruction: Instruction = None):
        self.result = None
        self.waypoints = waypoints
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("添加指令")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 指令类型选择
        type_frame = ttk.LabelFrame(self.dialog, text="指令类型", padding="10")
        type_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.instr_type_var = tk.StringVar()
        if instruction:
            self.instr_type_var.set(instruction.type.value)
        else:
            self.instr_type_var.set(InstructionType.MOVE_TO_WAYPOINT.value)
        
        for instr_type in InstructionType:
            ttk.Radiobutton(
                type_frame, 
                text=instr_type.value, 
                value=instr_type.value, 
                variable=self.instr_type_var,
                command=self.on_type_change
            ).pack(anchor=tk.W)
        
        # 参数设置
        self.param_frame = ttk.LabelFrame(self.dialog, text="参数设置", padding="10")
        self.param_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 注释
        ttk.Label(self.param_frame, text="注释:").grid(row=0, column=0, sticky=tk.W)
        self.comment_entry = ttk.Entry(self.param_frame, width=40)
        self.comment_entry.grid(row=0, column=1, padx=5, pady=2)
        if instruction:
            self.comment_entry.insert(0, instruction.comment)
        
        # 创建参数输入框
        self.param_entries = {}
        self.create_param_inputs()
        
        # 按钮
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)
        
        # 初始化参数值
        if instruction:
            self.load_instruction_params(instruction)
    
    def create_param_inputs(self):
        """创建参数输入框"""
        # 清除旧的参数输入框
        for widget in self.param_frame.winfo_children():
            if widget not in [self.comment_entry]:
                widget.destroy()
        
        self.param_entries = {}
        instr_type = self.instr_type_var.get()
        
        if instr_type == InstructionType.MOVE_TO_WAYPOINT.value:
            ttk.Label(self.param_frame, text="路点:").grid(row=1, column=0, sticky=tk.W)
            wp_var = tk.StringVar()
            wp_combo = ttk.Combobox(self.param_frame, textvariable=wp_var, width=37)
            wp_combo['values'] = [f"[{i}] {wp.name}" for i, wp in enumerate(self.waypoints)]
            wp_combo.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['waypoint_index'] = (wp_var, wp_combo)
        
        elif instr_type == InstructionType.MOVE_WORLD_Z.value:
            ttk.Label(self.param_frame, text="距离 (mm):").grid(row=1, column=0, sticky=tk.W)
            dist_entry = ttk.Entry(self.param_frame, width=37)
            dist_entry.insert(0, "50")
            dist_entry.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['distance'] = dist_entry
            
            ttk.Label(self.param_frame, text="速度:").grid(row=2, column=0, sticky=tk.W)
            speed_entry = ttk.Entry(self.param_frame, width=37)
            speed_entry.insert(0, "30")
            speed_entry.grid(row=2, column=1, padx=5, pady=2)
            self.param_entries['speed'] = speed_entry
        
        elif instr_type == InstructionType.MOVE_WORLD_REL.value:
            ttk.Label(self.param_frame, text="X偏移 (mm):").grid(row=1, column=0, sticky=tk.W)
            dx_entry = ttk.Entry(self.param_frame, width=37)
            dx_entry.insert(0, "0")
            dx_entry.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['dx'] = dx_entry
            
            ttk.Label(self.param_frame, text="Y偏移 (mm):").grid(row=2, column=0, sticky=tk.W)
            dy_entry = ttk.Entry(self.param_frame, width=37)
            dy_entry.insert(0, "0")
            dy_entry.grid(row=2, column=1, padx=5, pady=2)
            self.param_entries['dy'] = dy_entry
            
            ttk.Label(self.param_frame, text="Z偏移 (mm):").grid(row=3, column=0, sticky=tk.W)
            dz_entry = ttk.Entry(self.param_frame, width=37)
            dz_entry.insert(0, "0")
            dz_entry.grid(row=3, column=1, padx=5, pady=2)
            self.param_entries['dz'] = dz_entry
            
            ttk.Label(self.param_frame, text="速度:").grid(row=4, column=0, sticky=tk.W)
            speed_entry = ttk.Entry(self.param_frame, width=37)
            speed_entry.insert(0, "30")
            speed_entry.grid(row=4, column=1, padx=5, pady=2)
            self.param_entries['speed'] = speed_entry
        
        elif instr_type == InstructionType.SET_TCP_VERTICAL.value:
            ttk.Label(self.param_frame, text="速度:").grid(row=1, column=0, sticky=tk.W)
            speed_entry = ttk.Entry(self.param_frame, width=37)
            speed_entry.insert(0, "30")
            speed_entry.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['speed'] = speed_entry
        
        elif instr_type == InstructionType.SET_TCP_ORIENTATION.value:
            ttk.Label(self.param_frame, text="Rx (度):").grid(row=1, column=0, sticky=tk.W)
            rx_entry = ttk.Entry(self.param_frame, width=37)
            rx_entry.insert(0, "0")
            rx_entry.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['rx'] = rx_entry
            
            ttk.Label(self.param_frame, text="Ry (度):").grid(row=2, column=0, sticky=tk.W)
            ry_entry = ttk.Entry(self.param_frame, width=37)
            ry_entry.insert(0, "0")
            ry_entry.grid(row=2, column=1, padx=5, pady=2)
            self.param_entries['ry'] = ry_entry
            
            ttk.Label(self.param_frame, text="Rz (度):").grid(row=3, column=0, sticky=tk.W)
            rz_entry = ttk.Entry(self.param_frame, width=37)
            rz_entry.insert(0, "0")
            rz_entry.grid(row=3, column=1, padx=5, pady=2)
            self.param_entries['rz'] = rz_entry
            
            ttk.Label(self.param_frame, text="速度:").grid(row=4, column=0, sticky=tk.W)
            speed_entry = ttk.Entry(self.param_frame, width=37)
            speed_entry.insert(0, "30")
            speed_entry.grid(row=4, column=1, padx=5, pady=2)
            self.param_entries['speed'] = speed_entry
        
        elif instr_type == InstructionType.DELAY.value:
            ttk.Label(self.param_frame, text="延时 (秒):").grid(row=1, column=0, sticky=tk.W)
            delay_entry = ttk.Entry(self.param_frame, width=37)
            delay_entry.insert(0, "1.0")
            delay_entry.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['delay'] = delay_entry
        
        elif instr_type == InstructionType.SPIN_COATER_WAIT_COMPLETION.value:
            ttk.Label(self.param_frame, text="超时时间 (秒):").grid(row=1, column=0, sticky=tk.W)
            timeout_entry = ttk.Entry(self.param_frame, width=37)
            timeout_entry.insert(0, "60")
            timeout_entry.grid(row=1, column=1, padx=5, pady=2)
            self.param_entries['timeout'] = timeout_entry
    
    def on_type_change(self):
        """指令类型改变事件"""
        self.create_param_inputs()
    
    def load_instruction_params(self, instruction: Instruction):
        """加载指令参数"""
        for key, value in instruction.params.items():
            if key in self.param_entries:
                entry = self.param_entries[key]
                if isinstance(entry, tuple):
                    var, combo = entry
                    var.set(f"[{value}] {self.waypoints[value].name}")
                else:
                    entry.delete(0, tk.END)
                    entry.insert(0, str(value))
    
    def on_ok(self):
        """确定按钮"""
        try:
            instr_type = InstructionType(self.instr_type_var.get())
            params = {}
            comment = self.comment_entry.get()
            
            for key, entry in self.param_entries.items():
                if isinstance(entry, tuple):
                    var, combo = entry
                    value_str = var.get()
                    if value_str:
                        idx = int(value_str[value_str.find('[')+1:value_str.find(']')])
                        params[key] = idx
                else:
                    value_str = entry.get()
                    if value_str:
                        if key in ['rx', 'ry', 'rz', 'distance', 'dx', 'dy', 'dz']:
                            params[key] = float(value_str)
                        elif key == 'speed':
                            params[key] = float(value_str)
                        elif key == 'delay':
                            params[key] = float(value_str)
                        elif key == 'timeout':
                            params[key] = float(value_str)
            
            self.result = Instruction(instr_type, params, comment)
            self.dialog.destroy()
        
        except Exception as e:
            messagebox.showerror("错误", f"参数错误: {e}")
    
    def on_cancel(self):
        """取消按钮"""
        self.dialog.destroy()


class ManualControlWindow:
    """手动控制窗口"""
    
    def __init__(self, parent, main_app):
        self.main_app = main_app
        self.window = tk.Toplevel(parent)
        self.window.title("手动控制")
        self.window.geometry("400x300")
        self.window.transient(parent)
        self.window.grab_set()
        
        # 速度设置
        self.speed = tk.DoubleVar(value=30.0)
        
        # 创建界面
        self.create_ui()
        
        # 绑定键盘事件
        self.window.bind('<Key>', self.on_key_press)
        self.window.bind('<KeyRelease>', self.on_key_release)
        
        # 当前移动状态
        self.moving = False
    
    def create_ui(self):
        """创建界面"""
        # 速度设置
        speed_frame = ttk.LabelFrame(self.window, text="速度设置", padding="10")
        speed_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(speed_frame, text="速度 (mm/s):").grid(row=0, column=0, sticky=tk.W)
        speed_scale = ttk.Scale(speed_frame, from_=10, to=100, orient=tk.HORIZONTAL, variable=self.speed, length=200)
        speed_scale.grid(row=0, column=1, padx=5)
        speed_entry = ttk.Entry(speed_frame, textvariable=self.speed, width=8)
        speed_entry.grid(row=0, column=2, padx=5)
        
        # 控制说明
        info_frame = ttk.LabelFrame(self.window, text="控制说明", padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_text = """
键盘控制:
W - Z轴上升
S - Z轴下降
A - Y轴左移
D - Y轴右移
C - X轴前移
Z - X轴后移

按任意键开始移动，释放键停止移动
        """
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
        info_label.pack(anchor=tk.W)
        
        # 状态显示
        self.status_var = tk.StringVar(value="就绪")
        status_frame = ttk.LabelFrame(self.window, text="状态", padding="10")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)
    
    def on_key_press(self, event):
        """键盘按下事件"""
        if self.moving:
            return
        
        if not self.main_app.connected or not self.main_app.controller:
            self.status_var.set("错误: 请先连接机器人")
            return
        
        key = event.keysym.lower()
        speed = self.speed.get()
        
        try:
            if key == 'w':
                # Z轴上升
                self.status_var.set(f"Z轴上升 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_z(10, speed=speed, block=False)
                self.moving = True
            elif key == 's':
                # Z轴下降
                self.status_var.set(f"Z轴下降 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_z(-10, speed=speed, block=False)
                self.moving = True
            elif key == 'a':
                # Y轴左移
                self.status_var.set(f"Y轴左移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(0, -10, 0, speed=speed, block=False)
                self.moving = True
            elif key == 'd':
                # Y轴右移
                self.status_var.set(f"Y轴右移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(0, 10, 0, speed=speed, block=False)
                self.moving = True
            elif key == 'c':
                # X轴前移
                self.status_var.set(f"X轴前移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(10, 0, 0, speed=speed, block=False)
                self.moving = True
            elif key == 'z':
                # X轴后移
                self.status_var.set(f"X轴后移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(-10, 0, 0, speed=speed, block=False)
                self.moving = True
        except Exception as e:
            self.status_var.set(f"错误: {e}")
    
    def on_key_release(self, event):
        """键盘释放事件"""
        if not self.moving:
            return
        
        key = event.keysym.lower()
        if key in ['w', 's', 'a', 'd', 'c', 'z']:
            self.status_var.set("就绪")
            self.moving = False


def main():
    """主函数"""
    root = tk.Tk()
    app = RobotGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

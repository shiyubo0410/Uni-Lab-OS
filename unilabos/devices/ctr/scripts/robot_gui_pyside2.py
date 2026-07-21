#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人图形化编程界面 (PySide2 重构版)
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
    from PySide2.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QGridLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QListWidget,
        QListWidgetItem, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
        QFrame, QSplitter, QMenuBar, QMenu, QAction, QMessageBox, QFileDialog,
        QInputDialog, QDialog, QRadioButton, QButtonGroup, QScrollArea,
        QSlider, QStatusBar, QToolBar, QTabWidget, QCheckBox, QTableWidget,
        QTableWidgetItem, QHeaderView, QAbstractItemView, QProgressBar,
        QSizePolicy, QSpacerItem, QStackedWidget
    )
    from PySide2.QtCore import Qt, QTimer, QThread, Signal, QSize
    from PySide2.QtGui import QKeyEvent, QFont, QIcon, QPalette, QColor
    
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
    SPIN_COATER_CHECK_ENABLE = "旋涂仪检查使能"
    SPIN_COATER_VACUUM_ON = "旋涂仪真空开启"
    SPIN_COATER_VACUUM_OFF = "旋涂仪真空关闭"
    SPIN_COATER_SPIN_START = "旋涂仪旋涂启动"
    SPIN_COATER_SPIN_STOP = "旋涂仪旋涂停止"
    SPIN_COATER_MULTI_STEP_START = "旋涂仪多步旋涂"
    SPIN_COATER_MANUAL_HOME = "旋涂仪手动回原"
    SPIN_COATER_WAIT_COMPLETION = "等待旋涂结束"
    LOOP_START = "循环开始"
    LOOP_END = "循环结束"
    LOOP_START_VAR = "循环开始(带变量)"


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


class RobotGUI(QMainWindow):
    """机器人图形化编程界面"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("机器人图形化编程系统")
        self.setGeometry(100, 100, 1400, 900)
        
        # 初始化变量
        self.robot = None
        self.controller = None
        self.connected = False
        self.waypoints: List[Waypoint] = []
        self.current_program = RobotProgram()
        self.programs: List[RobotProgram] = []
        self.current_file_path: Optional[str] = None
        self.recent_files: List[str] = []
        self.max_recent_files = 5
        
        # 程序运行控制
        self.program_running = False
        self.stop_requested = False
        
        # 推杆控制配置（串口）
        self.relay_port = "COM11"
        self.relay_baudrate = 9600
        self.relay_data_bits = 8
        self.relay_stop_bits = 1
        self.relay_parity = "NONE"
        self.relay_device_address = 1
        
        # 夹爪和推杆控制
        self.gripper_control = GripperControl()
        self.pushrod_control = PushRodControl(
            port=self.relay_port,
            baudrate=self.relay_baudrate,
            data_bits=self.relay_data_bits,
            stop_bits=self.relay_stop_bits,
            parity=self.relay_parity,
            device_address=self.relay_device_address
        )
        self.gripper_connected = False
        self.pushrod_connected = False
        
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
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        
        new_action = QAction("新建程序 (Ctrl+N)", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_program)
        file_menu.addAction(new_action)
        
        open_action = QAction("打开程序 (Ctrl+O)", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_program)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("保存程序 (Ctrl+S)", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_program)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("另存为 (Ctrl+Shift+S)", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_program_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        # 最近文件菜单
        self.recent_menu = QMenu("最近打开", self)
        file_menu.addMenu(self.recent_menu)
        
        file_menu.addSeparator()
        
        import_wp_action = QAction("导入路点", self)
        import_wp_action.triggered.connect(self.import_waypoints)
        file_menu.addAction(import_wp_action)
        
        export_wp_action = QAction("导出路点", self)
        export_wp_action.triggered.connect(self.export_waypoints)
        file_menu.addAction(export_wp_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.on_exit)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        
        undo_action = QAction("撤销", self)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("重做", self)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        clear_action = QAction("清空程序", self)
        clear_action.triggered.connect(self.clear_program)
        edit_menu.addAction(clear_action)
        
        # 运行菜单
        run_menu = menubar.addMenu("运行")
        
        run_action = QAction("运行程序", self)
        run_action.triggered.connect(self.run_program)
        run_menu.addAction(run_action)
        
        step_action = QAction("单步运行", self)
        step_action.triggered.connect(self.step_program)
        run_menu.addAction(step_action)
        
        stop_action = QAction("停止运行", self)
        stop_action.triggered.connect(self.stop_program)
        run_menu.addAction(stop_action)
        
        manual_action = QAction("手动控制", self)
        manual_action.triggered.connect(self.open_manual_control)
        run_menu.addAction(manual_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        help_action = QAction("使用说明", self)
        help_action.triggered.connect(self.show_help)
        help_menu.addAction(help_action)
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_layout(self):
        """创建主布局"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧：路点管理
        self.waypoint_panel = self.create_waypoint_panel()
        splitter.addWidget(self.waypoint_panel)
        
        # 中间：程序编辑器
        self.program_panel = self.create_program_panel()
        splitter.addWidget(self.program_panel)
        
        # 右侧：机器人控制
        self.control_panel = self.create_control_panel()
        splitter.addWidget(self.control_panel)
        
        # 设置分割器比例
        splitter.setSizes([350, 500, 400])
        
        # 底部：状态栏
        self.create_status_bar()
    
    def create_waypoint_panel(self):
        """创建路点管理面板"""
        group = QGroupBox("路点管理")
        layout = QVBoxLayout(group)
        
        # 路点列表
        self.waypoint_listbox = QListWidget()
        self.waypoint_listbox.setSelectionMode(QAbstractItemView.SingleSelection)
        self.waypoint_listbox.itemSelectionChanged.connect(self.on_waypoint_select)
        layout.addWidget(self.waypoint_listbox)
        
        # 路点操作按钮
        btn_layout = QGridLayout()
        
        self.btn_record_wp = QPushButton("记录当前路点")
        self.btn_record_wp.clicked.connect(self.record_waypoint)
        btn_layout.addWidget(self.btn_record_wp, 0, 0)
        
        self.btn_delete_wp = QPushButton("删除选中")
        self.btn_delete_wp.clicked.connect(self.delete_waypoint)
        btn_layout.addWidget(self.btn_delete_wp, 0, 1)
        
        self.btn_clear_wp = QPushButton("清空全部")
        self.btn_clear_wp.clicked.connect(self.clear_waypoints)
        btn_layout.addWidget(self.btn_clear_wp, 0, 2)
        
        self.btn_move_to_wp = QPushButton("移动到路点")
        self.btn_move_to_wp.clicked.connect(self.move_to_waypoint)
        btn_layout.addWidget(self.btn_move_to_wp, 1, 0)
        
        self.btn_import_wp = QPushButton("导入路点")
        self.btn_import_wp.clicked.connect(self.import_waypoints)
        btn_layout.addWidget(self.btn_import_wp, 1, 1)
        
        self.btn_export_wp = QPushButton("导出路点")
        self.btn_export_wp.clicked.connect(self.export_waypoints)
        btn_layout.addWidget(self.btn_export_wp, 1, 2)
        
        layout.addLayout(btn_layout)
        
        # 路点信息
        info_group = QGroupBox("路点信息")
        info_layout = QVBoxLayout(info_group)
        
        self.waypoint_info = QTextEdit()
        self.waypoint_info.setReadOnly(True)
        self.waypoint_info.setMaximumHeight(150)
        info_layout.addWidget(self.waypoint_info)
        
        layout.addWidget(info_group)
        
        return group
    
    def create_program_panel(self):
        """创建程序编辑器面板"""
        group = QGroupBox("程序编辑器")
        layout = QVBoxLayout(group)
        
        # 程序列表
        self.program_listbox = QListWidget()
        self.program_listbox.setSelectionMode(QAbstractItemView.SingleSelection)
        self.program_listbox.itemSelectionChanged.connect(self.on_instruction_select)
        layout.addWidget(self.program_listbox)
        
        # 指令操作按钮
        btn_layout = QHBoxLayout()
        
        self.btn_add_instr = QPushButton("添加指令")
        self.btn_add_instr.clicked.connect(self.show_instruction_dialog)
        btn_layout.addWidget(self.btn_add_instr)
        
        self.btn_edit_instr = QPushButton("编辑指令")
        self.btn_edit_instr.clicked.connect(self.edit_instruction)
        btn_layout.addWidget(self.btn_edit_instr)
        
        self.btn_delete_instr = QPushButton("删除指令")
        self.btn_delete_instr.clicked.connect(self.delete_instruction)
        btn_layout.addWidget(self.btn_delete_instr)
        
        self.btn_move_up = QPushButton("上移")
        self.btn_move_up.clicked.connect(self.move_instruction_up)
        btn_layout.addWidget(self.btn_move_up)
        
        self.btn_move_down = QPushButton("下移")
        self.btn_move_down.clicked.connect(self.move_instruction_down)
        btn_layout.addWidget(self.btn_move_down)
        
        self.btn_clear_prog = QPushButton("清空程序")
        self.btn_clear_prog.clicked.connect(self.clear_program)
        btn_layout.addWidget(self.btn_clear_prog)
        
        layout.addLayout(btn_layout)
        
        # 运行控制
        run_layout = QHBoxLayout()
        
        self.btn_run = QPushButton("▶ 运行程序")
        self.btn_run.clicked.connect(self.run_program)
        run_layout.addWidget(self.btn_run)
        
        self.btn_step = QPushButton("⏭ 单步运行")
        self.btn_step.clicked.connect(self.step_program)
        run_layout.addWidget(self.btn_step)
        
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.clicked.connect(self.stop_program)
        run_layout.addWidget(self.btn_stop)
        
        layout.addLayout(run_layout)
        
        # 指令详情
        info_group = QGroupBox("指令详情")
        info_layout = QVBoxLayout(info_group)
        
        self.instruction_info = QTextEdit()
        self.instruction_info.setReadOnly(True)
        self.instruction_info.setMaximumHeight(120)
        info_layout.addWidget(self.instruction_info)
        
        layout.addWidget(info_group)
        
        return group
    
    def create_control_panel(self):
        """创建机器人控制面板"""
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 创建容器部件
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        
        # 连接设置
        conn_group = QGroupBox("连接设置")
        conn_layout = QGridLayout(conn_group)
        
        conn_layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_entry = QLineEdit("192.168.6.6")
        conn_layout.addWidget(self.ip_entry, 0, 1)
        
        conn_layout.addWidget(QLabel("端口:"), 1, 0)
        self.port_entry = QLineEdit("2323")
        conn_layout.addWidget(self.port_entry, 1, 1)
        
        self.btn_connect = QPushButton("连接")
        self.btn_connect.clicked.connect(self.connect_robot)
        conn_layout.addWidget(self.btn_connect, 2, 0)
        
        self.btn_disconnect = QPushButton("断开")
        self.btn_disconnect.clicked.connect(self.disconnect_robot)
        conn_layout.addWidget(self.btn_disconnect, 2, 1)
        
        layout.addWidget(conn_group)
        
        # 电源控制
        power_group = QGroupBox("电源控制")
        power_layout = QGridLayout(power_group)
        
        self.btn_power_on = QPushButton("上电")
        self.btn_power_on.clicked.connect(self.power_on)
        power_layout.addWidget(self.btn_power_on, 0, 0)
        
        self.btn_power_off = QPushButton("断电")
        self.btn_power_off.clicked.connect(self.power_off)
        power_layout.addWidget(self.btn_power_off, 0, 1)
        
        self.btn_enable = QPushButton("使能")
        self.btn_enable.clicked.connect(self.enable_robot)
        power_layout.addWidget(self.btn_enable, 1, 0)
        
        self.btn_disable = QPushButton("去使能")
        self.btn_disable.clicked.connect(self.disable_robot)
        power_layout.addWidget(self.btn_disable, 1, 1)
        
        self.btn_fault_reset = QPushButton("故障复位")
        self.btn_fault_reset.clicked.connect(self.fault_reset)
        power_layout.addWidget(self.btn_fault_reset, 2, 0, 1, 2)
        
        layout.addWidget(power_group)
        
        # 快捷移动
        move_group = QGroupBox("快捷移动")
        move_layout = QGridLayout(move_group)
        
        self.btn_z_up = QPushButton("Z轴上升 50mm")
        self.btn_z_up.clicked.connect(lambda: self.move_world_z(50))
        move_layout.addWidget(self.btn_z_up, 0, 0)
        
        self.btn_z_down = QPushButton("Z轴下降 50mm")
        self.btn_z_down.clicked.connect(lambda: self.move_world_z(-50))
        move_layout.addWidget(self.btn_z_down, 0, 1)
        
        self.btn_tcp_vertical = QPushButton("末端垂直")
        self.btn_tcp_vertical.clicked.connect(self.set_tcp_vertical)
        move_layout.addWidget(self.btn_tcp_vertical, 1, 0, 1, 2)
        
        layout.addWidget(move_group)
        
        # 夹爪和推杆控制
        actuator_group = QGroupBox("夹爪和推杆控制")
        actuator_layout = QVBoxLayout(actuator_group)
        
        # 继电器配置（串口）
        relay_label = QLabel("推杆串口配置:")
        relay_label.setFont(QFont("Arial", 10, QFont.Bold))
        actuator_layout.addWidget(relay_label)
        
        relay_grid = QGridLayout()
        relay_grid.addWidget(QLabel("串口:"), 0, 0)
        self.relay_port_entry = QLineEdit(self.relay_port)
        relay_grid.addWidget(self.relay_port_entry, 0, 1)
        
        relay_grid.addWidget(QLabel("波特率:"), 0, 2)
        self.relay_baudrate_entry = QLineEdit(str(self.relay_baudrate))
        relay_grid.addWidget(self.relay_baudrate_entry, 0, 3)
        
        relay_grid.addWidget(QLabel("数据位:"), 1, 0)
        self.relay_data_bits_entry = QLineEdit(str(self.relay_data_bits))
        relay_grid.addWidget(self.relay_data_bits_entry, 1, 1)
        
        relay_grid.addWidget(QLabel("停止位:"), 1, 2)
        self.relay_stop_bits_entry = QLineEdit(str(self.relay_stop_bits))
        relay_grid.addWidget(self.relay_stop_bits_entry, 1, 3)
        
        relay_grid.addWidget(QLabel("校验位:"), 2, 0)
        self.relay_parity_entry = QLineEdit(self.relay_parity)
        relay_grid.addWidget(self.relay_parity_entry, 2, 1)
        
        relay_grid.addWidget(QLabel("设备地址:"), 3, 0)
        self.relay_device_address_entry = QLineEdit(str(self.relay_device_address))
        relay_grid.addWidget(self.relay_device_address_entry, 3, 1)
        
        actuator_layout.addLayout(relay_grid)
        
        self.btn_apply_relay = QPushButton("应用配置")
        self.btn_apply_relay.clicked.connect(self.apply_relay_config)
        actuator_layout.addWidget(self.btn_apply_relay)
        
        # 夹爪控制
        gripper_label = QLabel("夹爪控制:")
        gripper_label.setFont(QFont("Arial", 10, QFont.Bold))
        actuator_layout.addWidget(gripper_label)
        
        gripper_grid = QGridLayout()
        
        self.btn_connect_gripper = QPushButton("连接夹爪")
        self.btn_connect_gripper.clicked.connect(self.connect_gripper)
        gripper_grid.addWidget(self.btn_connect_gripper, 0, 0)
        
        self.btn_init_gripper = QPushButton("初始化")
        self.btn_init_gripper.clicked.connect(self.initialize_gripper)
        gripper_grid.addWidget(self.btn_init_gripper, 0, 1)
        
        self.btn_gripper_open = QPushButton("打开")
        self.btn_gripper_open.clicked.connect(self.gripper_open)
        gripper_grid.addWidget(self.btn_gripper_open, 1, 0)
        
        self.btn_gripper_close = QPushButton("关闭")
        self.btn_gripper_close.clicked.connect(self.gripper_close)
        gripper_grid.addWidget(self.btn_gripper_close, 1, 1)
        
        actuator_layout.addLayout(gripper_grid)
        
        # 推杆控制
        pushrod_label = QLabel("推杆控制:")
        pushrod_label.setFont(QFont("Arial", 10, QFont.Bold))
        actuator_layout.addWidget(pushrod_label)
        
        pushrod_grid = QGridLayout()
        
        self.btn_upper_extend = QPushButton("上推杆推出")
        self.btn_upper_extend.clicked.connect(self.upper_pushrod_extend)
        pushrod_grid.addWidget(self.btn_upper_extend, 0, 0)
        
        self.btn_upper_retract = QPushButton("上推杆收回")
        self.btn_upper_retract.clicked.connect(self.upper_pushrod_retract)
        pushrod_grid.addWidget(self.btn_upper_retract, 0, 1)
        
        self.btn_lower_extend = QPushButton("下推杆推出")
        self.btn_lower_extend.clicked.connect(self.lower_pushrod_extend)
        pushrod_grid.addWidget(self.btn_lower_extend, 1, 0)
        
        self.btn_lower_retract = QPushButton("下推杆收回")
        self.btn_lower_retract.clicked.connect(self.lower_pushrod_retract)
        pushrod_grid.addWidget(self.btn_lower_retract, 1, 1)
        
        self.btn_spin_extend = QPushButton("旋涂仪推杆推出")
        self.btn_spin_extend.clicked.connect(self.spin_coater_pushrod_extend)
        pushrod_grid.addWidget(self.btn_spin_extend, 2, 0)
        
        self.btn_spin_retract = QPushButton("旋涂仪推杆收回")
        self.btn_spin_retract.clicked.connect(self.spin_coater_pushrod_retract)
        pushrod_grid.addWidget(self.btn_spin_retract, 2, 1)
        
        actuator_layout.addLayout(pushrod_grid)
        
        layout.addWidget(actuator_group)
        
        # 旋涂仪控制
        spin_group = QGroupBox("旋涂仪控制")
        spin_layout = QVBoxLayout(spin_group)
        
        # 串口配置
        spin_config_grid = QGridLayout()
        
        spin_config_grid.addWidget(QLabel("串口:"), 0, 0)
        self.spin_coater_port_entry = QLineEdit(self.spin_coater_port)
        spin_config_grid.addWidget(self.spin_coater_port_entry, 0, 1)
        
        spin_config_grid.addWidget(QLabel("波特率:"), 1, 0)
        self.spin_coater_baudrate_entry = QLineEdit(str(self.spin_coater_baudrate))
        spin_config_grid.addWidget(self.spin_coater_baudrate_entry, 1, 1)
        
        spin_layout.addLayout(spin_config_grid)
        
        self.btn_connect_spin = QPushButton("连接旋涂仪")
        self.btn_connect_spin.clicked.connect(self.connect_spin_coater)
        spin_layout.addWidget(self.btn_connect_spin)
        
        # 旋涂仪控制按钮
        spin_btn_grid = QGridLayout()
        
        self.btn_spin_enable_on = QPushButton("使能开启")
        self.btn_spin_enable_on.clicked.connect(self.spin_coater_enable_on)
        spin_btn_grid.addWidget(self.btn_spin_enable_on, 0, 0)
        
        self.btn_spin_enable_off = QPushButton("使能关闭")
        self.btn_spin_enable_off.clicked.connect(self.spin_coater_enable_off)
        spin_btn_grid.addWidget(self.btn_spin_enable_off, 0, 1)
        
        self.btn_spin_vac_on = QPushButton("真空开启")
        self.btn_spin_vac_on.clicked.connect(self.spin_coater_vacuum_on)
        spin_btn_grid.addWidget(self.btn_spin_vac_on, 1, 0)
        
        self.btn_spin_vac_off = QPushButton("真空关闭")
        self.btn_spin_vac_off.clicked.connect(self.spin_coater_vacuum_off)
        spin_btn_grid.addWidget(self.btn_spin_vac_off, 1, 1)
        
        self.btn_spin_start = QPushButton("旋涂启动")
        self.btn_spin_start.clicked.connect(self.spin_coater_spin_start)
        spin_btn_grid.addWidget(self.btn_spin_start, 2, 0)
        
        self.btn_spin_stop = QPushButton("旋涂停止")
        self.btn_spin_stop.clicked.connect(self.spin_coater_spin_stop)
        spin_btn_grid.addWidget(self.btn_spin_stop, 2, 1)
        
        self.btn_spin_multi = QPushButton("多步旋涂")
        self.btn_spin_multi.clicked.connect(self.spin_coater_multi_step_start)
        spin_btn_grid.addWidget(self.btn_spin_multi, 3, 0)
        
        self.btn_spin_home = QPushButton("手动回原")
        self.btn_spin_home.clicked.connect(self.spin_coater_manual_home)
        spin_btn_grid.addWidget(self.btn_spin_home, 3, 1)
        
        spin_layout.addLayout(spin_btn_grid)
        
        layout.addWidget(spin_group)
        
        # 日志显示
        log_group = QGroupBox("系统日志")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.clicked.connect(self.clear_log)
        log_layout.addWidget(self.btn_clear_log)
        
        layout.addWidget(log_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        scroll.setWidget(container)
        return scroll
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        
        self.robot_status_label = QLabel("未连接")
        self.robot_status_label.setStyleSheet("color: red;")
        self.status_bar.addPermanentWidget(self.robot_status_label)
    
    # ==================== 路点管理 ====================
    
    def record_waypoint(self):
        """记录当前路点"""
        if not self.connected or not self.controller:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        name, ok = QInputDialog.getText(self, "路点名称", "请输入路点名称:", text=f"路点_{len(self.waypoints)+1}")
        if not ok:
            return
        
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
        current_row = self.waypoint_listbox.currentRow()
        if current_row < 0:
            return
        
        name = self.waypoints[current_row].name
        reply = QMessageBox.question(self, "确认", f"确定删除路点 '{name}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.waypoints.pop(current_row)
            self.update_waypoint_list()
            self.log(f"✓ 删除路点: {name}")
            self.save_waypoints_to_file()
    
    def clear_waypoints(self):
        """清空所有路点"""
        if not self.waypoints:
            return
        
        reply = QMessageBox.question(self, "确认", f"确定清空 {len(self.waypoints)} 个路点?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.waypoints.clear()
            self.update_waypoint_list()
            self.log("✓ 清空所有路点")
            self.save_waypoints_to_file()
    
    def move_to_waypoint(self):
        """移动到选中路点"""
        current_row = self.waypoint_listbox.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先选择一个路点")
            return
        
        if not self.connected or not self.controller:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        wp = self.waypoints[current_row]
        if self.controller.move_to_waypoint(current_row, block=True):
            self.log(f"✓ 移动到路点: {wp.name}")
        else:
            self.log(f"❌ 移动到路点失败: {wp.name}")
    
    def update_waypoint_list(self):
        """更新路点列表"""
        self.waypoint_listbox.clear()
        for i, wp in enumerate(self.waypoints):
            self.waypoint_listbox.addItem(f"[{i}] {wp.name}")
    
    def on_waypoint_select(self):
        """路点选择事件"""
        current_row = self.waypoint_listbox.currentRow()
        if current_row < 0 or current_row >= len(self.waypoints):
            return
        
        wp = self.waypoints[current_row]
        
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
        
        self.waypoint_info.setText(info)
    
    # ==================== 程序编辑 ====================
    
    def show_instruction_dialog(self):
        """显示添加指令对话框，在当前选中位置上方插入"""
        dialog = InstructionDialog(self, self.waypoints)
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            instr = dialog.result
            
            # 获取当前选中的行
            current_row = self.program_listbox.currentRow()
            
            if current_row < 0:
                # 没有选中任何项，添加到末尾
                self.current_program.add_instruction(instr)
                self.log(f"✓ 添加指令到末尾: {instr.type.value}")
            else:
                # 在当前选中位置上方插入
                self.current_program.add_instruction(instr, current_row)
                self.log(f"✓ 添加指令到位置 {current_row + 1}: {instr.type.value}")
            
            self.update_program_list()
            
            # 选中新添加的指令
            if current_row < 0:
                self.program_listbox.setCurrentRow(len(self.current_program.instructions) - 1)
            else:
                self.program_listbox.setCurrentRow(current_row)
    
    def edit_instruction(self):
        """编辑选中指令"""
        current_row = self.program_listbox.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "提示", "请先选择一条指令")
            return
        
        instr = self.current_program.instructions[current_row]
        
        dialog = InstructionDialog(self, self.waypoints, instr)
        if dialog.exec_() == QDialog.Accepted and dialog.result:
            self.current_program.instructions[current_row] = dialog.result
            self.update_program_list()
            self.log(f"✓ 编辑指令: {dialog.result.type.value}")
    
    def delete_instruction(self):
        """删除选中指令"""
        current_row = self.program_listbox.currentRow()
        if current_row < 0:
            return
        
        instr = self.current_program.instructions[current_row]
        reply = QMessageBox.question(self, "确认", f"确定删除指令 '{instr.type.value}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_program.remove_instruction(current_row)
            self.update_program_list()
            self.log(f"✓ 删除指令: {instr.type.value}")
    
    def move_instruction_up(self):
        """上移指令"""
        current_row = self.program_listbox.currentRow()
        if current_row <= 0:
            return
        
        self.current_program.move_instruction(current_row, current_row - 1)
        self.update_program_list()
        self.program_listbox.setCurrentRow(current_row - 1)
    
    def move_instruction_down(self):
        """下移指令"""
        current_row = self.program_listbox.currentRow()
        if current_row < 0 or current_row >= len(self.current_program.instructions) - 1:
            return
        
        self.current_program.move_instruction(current_row, current_row + 1)
        self.update_program_list()
        self.program_listbox.setCurrentRow(current_row + 1)
    
    def clear_program(self):
        """清空程序"""
        if not self.current_program.instructions:
            return
        
        reply = QMessageBox.question(self, "确认", f"确定清空 {len(self.current_program.instructions)} 条指令?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.current_program.clear()
            self.update_program_list()
            self.log("✓ 清空程序")
    
    def update_program_list(self):
        """更新程序列表，支持缩进显示循环结构"""
        self.program_listbox.clear()
        
        # 计算每个指令的缩进级别
        indent_level = 0
        indent_stack = []
        
        for i, instr in enumerate(self.current_program.instructions):
            # 检查是否需要减少缩进（遇到循环结束）
            if instr.type == InstructionType.LOOP_END:
                if indent_stack:
                    indent_level = indent_stack.pop()
                else:
                    indent_level = max(0, indent_level - 1)
            
            # 生成缩进字符串
            indent_str = "    " * indent_level
            
            # 添加指令到列表
            display_text = f"{i+1}. {indent_str}{instr}"
            item = QListWidgetItem(display_text)
            
            # 为循环指令设置特殊样式
            if instr.type == InstructionType.LOOP_START:
                item.setBackground(QColor(200, 230, 255))  # 浅蓝色背景
                item.setForeground(QColor(0, 0, 150))  # 深蓝色文字
                # 增加缩进级别
                indent_stack.append(indent_level)
                indent_level += 1
            elif instr.type == InstructionType.LOOP_END:
                item.setBackground(QColor(255, 230, 200))  # 浅橙色背景
                item.setForeground(QColor(150, 80, 0))  # 深橙色文字
            
            self.program_listbox.addItem(item)
    
    def on_instruction_select(self):
        """指令选择事件"""
        current_row = self.program_listbox.currentRow()
        if current_row < 0 or current_row >= len(self.current_program.instructions):
            return
        
        instr = self.current_program.instructions[current_row]
        
        info = f"类型: {instr.type.value}\n"
        info += f"注释: {instr.comment}\n\n"
        info += f"参数:\n"
        for key, value in instr.params.items():
            info += f"  {key}: {value}\n"
        
        self.instruction_info.setText(info)
    
    # ==================== 程序运行 ====================
    
    def run_program(self):
        """运行程序"""
        if not self.current_program.instructions:
            QMessageBox.warning(self, "提示", "程序为空")
            return
        
        if not self.connected or not self.controller:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        # 检查是否已经在运行
        if self.program_running:
            QMessageBox.warning(self, "提示", "程序正在运行中")
            return
        
        # 重置停止标志
        self.stop_requested = False
        self.program_running = True
        
        # 禁用运行按钮，启用停止按钮
        self.btn_run.setEnabled(False)
        self.btn_step.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        self.log("=" * 50)
        self.log("开始运行程序")
        self.log("=" * 50)
        
        try:
            # 使用带循环支持的执行引擎
            success = self._execute_program_with_loops()
            
            if success and not self.stop_requested:
                self.log("\n" + "=" * 50)
                self.log("程序执行完成")
                self.log("=" * 50)
                QMessageBox.information(self, "完成", "程序执行完成")
        
        except Exception as e:
            self.log(f"❌ 程序执行异常: {e}")
            QMessageBox.critical(self, "错误", f"程序执行异常: {e}")
        
        finally:
            # 恢复按钮状态
            self.program_running = False
            self.stop_requested = False
            self.btn_run.setEnabled(True)
            self.btn_step.setEnabled(True)
            self.btn_stop.setEnabled(True)
    
    def _execute_program_with_loops(self) -> bool:
        """
        执行程序，支持循环结构和变量
        返回 True 表示正常完成，False 表示执行失败
        """
        instructions = self.current_program.instructions
        pc = 0  # 程序计数器
        
        # 循环栈：存储 (loop_start_index, loop_count, current_iteration, var_name, var_scope)
        loop_stack = []
        
        # 变量字典：存储循环变量及其值
        variables = {}
        
        while pc < len(instructions):
            # 检查是否请求停止
            if self.stop_requested:
                self.log("⏹ 程序已被用户停止")
                return True
            
            instr = instructions[pc]
            
            self.log(f"\n[{pc+1}/{len(instructions)}] 执行: {instr.type.value}")
            self.highlight_instruction(pc)
            QApplication.processEvents()
            
            # 处理循环开始指令（普通循环）
            if instr.type == InstructionType.LOOP_START:
                loop_count = instr.params.get("loop_count", 1)
                if loop_count <= 0:
                    # 跳过整个循环体
                    pc = self._find_loop_end(pc)
                    if pc == -1:
                        self.log("❌ 找不到循环结束指令")
                        return False
                    pc += 1  # 跳到循环结束后的第一条指令
                else:
                    # 压入循环栈，开始第一次迭代
                    loop_stack.append({
                        'start_index': pc,
                        'loop_count': loop_count,
                        'current_iteration': 1,
                        'var_name': None,
                        'nest_level': len(loop_stack)
                    })
                    self.log(f"  开始循环，共 {loop_count} 次，当前第 1 次")
                    pc += 1
                continue
            
            # 处理带变量的循环开始指令
            if instr.type == InstructionType.LOOP_START_VAR:
                loop_count = instr.params.get("loop_count", 1)
                var_name = instr.params.get("var_name", "i")
                start_value = instr.params.get("start_value", 0)
                
                if loop_count <= 0:
                    # 跳过整个循环体
                    pc = self._find_loop_end(pc)
                    if pc == -1:
                        self.log("❌ 找不到循环结束指令")
                        return False
                    pc += 1
                else:
                    # 设置变量值（当前迭代值 + 起始偏移）
                    var_scope = f"{var_name}_{len(loop_stack)}"  # 作用域标识
                    variables[var_scope] = start_value
                    
                    loop_stack.append({
                        'start_index': pc,
                        'loop_count': loop_count,
                        'current_iteration': 1,
                        'var_name': var_name,
                        'var_scope': var_scope,
                        'start_value': start_value,
                        'nest_level': len(loop_stack)
                    })
                    self.log(f"  开始循环 {var_name}={start_value}，共 {loop_count} 次")
                    pc += 1
                continue
            
            # 处理循环结束指令
            if instr.type == InstructionType.LOOP_END:
                if not loop_stack:
                    self.log("❌ 循环结束指令没有匹配的循环开始")
                    return False
                
                current_loop = loop_stack[-1]
                current_loop['current_iteration'] += 1
                
                if current_loop['current_iteration'] <= current_loop['loop_count']:
                    # 继续下一次迭代
                    # 更新变量值
                    if current_loop.get('var_name'):
                        new_value = current_loop['start_value'] + current_loop['current_iteration'] - 1
                        variables[current_loop['var_scope']] = new_value
                        self.log(f"  循环第 {current_loop['current_iteration']}/{current_loop['loop_count']} 次，{current_loop['var_name']}={new_value}")
                    else:
                        self.log(f"  循环第 {current_loop['current_iteration']}/{current_loop['loop_count']} 次")
                    pc = current_loop['start_index'] + 1
                else:
                    # 循环结束，弹出栈并清理变量
                    if current_loop.get('var_scope'):
                        del variables[current_loop['var_scope']]
                    self.log(f"  循环完成，共执行 {current_loop['loop_count']} 次")
                    loop_stack.pop()
                    pc += 1
                continue
            
            # 执行普通指令（带变量替换）
            processed_instr = self._process_instruction_variables(instr, loop_stack, variables)
            if not self.execute_instruction(processed_instr):
                self.log(f"❌ 程序执行失败，停止运行")
                return False
            
            pc += 1
        
        # 检查是否有未闭合的循环
        if loop_stack:
            self.log("❌ 警告：存在未闭合的循环")
            return False
        
        return True
    
    def _process_instruction_variables(self, instr: Instruction, loop_stack: list, variables: dict) -> Instruction:
        """
        处理指令中的变量表达式
        将变量名替换为实际值
        """
        import copy
        import re
        
        # 深拷贝指令
        processed = copy.deepcopy(instr)
        
        # 如果没有循环栈，直接返回原指令
        if not loop_stack:
            return processed
        
        # 处理参数中的变量表达式
        for key, value in processed.params.items():
            if isinstance(value, str):
                # 替换变量表达式，如 "0.5*i" -> "0.5*2"
                new_value = self._eval_variable_expression(value, loop_stack, variables)
                if new_value != value:
                    processed.params[key] = new_value
            elif isinstance(value, (int, float)):
                # 数值类型不处理
                pass
        
        return processed
    
    def _eval_variable_expression(self, expr: str, loop_stack: list, variables: dict) -> str:
        """
        计算包含变量的表达式
        支持：i, j, k 等变量名
        返回计算后的字符串或原字符串
        """
        import re
        
        try:
            # 创建变量映射（从内层到外层）
            var_map = {}
            for loop_info in loop_stack:
                if loop_info.get('var_name'):
                    var_name = loop_info['var_name']
                    var_value = variables.get(loop_info['var_scope'], 0)
                    var_map[var_name] = var_value
            
            # 检查表达式是否包含变量
            contains_var = any(var in expr for var in var_map.keys())
            
            # 如果没有变量映射或表达式不包含变量，尝试直接转换为浮点数
            if not var_map or not contains_var:
                try:
                    float(expr)
                    return expr
                except:
                    # 无法转换，返回默认值 0
                    return "0"
            
            # 安全地计算表达式
            # 只允许数字、运算符、括号和已知变量
            allowed_chars = set('0123456789.+-*/() ')
            for var_name in var_map.keys():
                allowed_chars.update(var_name)
            
            if not all(c in allowed_chars for c in expr):
                # 尝试直接转换为浮点数
                try:
                    float(expr)
                    return expr
                except:
                    # 包含非法字符，返回默认值 0
                    return "0"
            
            # 计算表达式
            result = eval(expr, {"__builtins__": {}}, var_map)
            
            # 返回计算结果
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
            
        except Exception as e:
            # 计算失败，尝试直接转换为浮点数
            try:
                float(expr)
                return expr
            except:
                # 无法转换，返回原表达式
                return expr
    
    def _find_loop_end(self, start_index: int) -> int:
        """
        从指定位置查找对应的循环结束指令
        支持嵌套循环（包括带变量的循环）
        返回循环结束指令的索引，找不到返回 -1
        """
        instructions = self.current_program.instructions
        nest_level = 1
        
        for i in range(start_index + 1, len(instructions)):
            if instructions[i].type in (InstructionType.LOOP_START, InstructionType.LOOP_START_VAR):
                nest_level += 1
            elif instructions[i].type == InstructionType.LOOP_END:
                nest_level -= 1
                if nest_level == 0:
                    return i
        
        return -1
    
    def _move_to_waypoint_with_offset(self, idx: int, offset_x: float, offset_y: float) -> bool:
        """
        移动到带偏移的路点
        
        Args:
            idx: 路点索引
            offset_x: X轴偏移量（mm）
            offset_y: Y轴偏移量（mm）
        
        Returns:
            bool: 是否成功
        """
        if not self.connected or not self.controller:
            return False
        
        if idx >= len(self.waypoints):
            return False
        
        wp = self.waypoints[idx]
        
        # 创建偏移后的TCP位姿
        offset_pose = wp.tcp_pose.copy()
        offset_pose[0] += offset_x  # X轴偏移
        offset_pose[1] += offset_y  # Y轴偏移
        
        # 使用偏移后的位姿移动
        try:
            result = self.controller.robot.movel(offset_pose, speed=[30.0]*6, acc=[60.0]*6, block=True)
            if result:
                self.log(f"✓ 已到达偏移路点: {wp.name} (偏移: X={offset_x}, Y={offset_y})")
            else:
                self.log(f"❌ 移动到偏移路点失败: {wp.name}")
            return result
        except Exception as e:
            self.log(f"❌ 移动到偏移路点异常: {e}")
            return False
    
    def step_program(self):
        """单步运行"""
        if not self.connected or not self.controller:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        # 获取当前选中的指令，如果没有则选择第一条
        current_row = self.program_listbox.currentRow()
        if current_row < 0:
            current_row = 0
        
        if current_row >= len(self.current_program.instructions):
            QMessageBox.information(self, "提示", "已到达程序末尾")
            return
        
        instr = self.current_program.instructions[current_row]
        self.log(f"[单步] 执行: {instr.type.value}")
        self.highlight_instruction(current_row)
        
        # 处理变量表达式（单步运行时也需要处理）
        processed_instr = self._process_instruction_variables(instr, [], {})
        
        if self.execute_instruction(processed_instr):
            # 自动选择下一条指令
            if current_row < len(self.current_program.instructions) - 1:
                self.program_listbox.setCurrentRow(current_row + 1)
                self.on_instruction_select()
    
    def stop_program(self):
        """停止运行"""
        # 设置停止标志
        self.stop_requested = True
        self.log("⏹ 正在停止程序...")
        
        # 立即停止机器人运动
        if self.controller and self.controller.robot:
            try:
                # 发送停止命令
                self.controller.robot.disable()
                self.log("✓ 机器人已禁用")
            except Exception as e:
                self.log(f"❌ 停止机器人失败: {e}")
        
        # 如果程序正在运行，等待它结束
        if self.program_running:
            self.log("⏹ 等待当前指令完成...")
            # 强制处理事件以更新UI
            QApplication.processEvents()
    
    def execute_instruction(self, instr: Instruction) -> bool:
        """执行单条指令"""
        # 检查是否请求停止
        if self.stop_requested:
            self.log("  ⏹ 指令被跳过（停止请求）")
            return True  # 返回True以继续退出循环
        
        try:
            if instr.type == InstructionType.MOVE_TO_WAYPOINT:
                idx = instr.params.get("waypoint_index", 0)
                if not self.waypoints:
                    self.log("❌ 路点列表为空")
                    return False
                if idx < len(self.waypoints):
                    offset_x = float(instr.params.get("offset_x", 0))
                    offset_y = float(instr.params.get("offset_y", 0))
                    
                    if offset_x != 0 or offset_y != 0:
                        self.log(f"  路点偏移: X={offset_x}mm, Y={offset_y}mm")
                        return self._move_to_waypoint_with_offset(idx, offset_x, offset_y)
                    else:
                        return self.controller.move_to_waypoint(idx, block=True)
                else:
                    self.log(f"❌ 路点索引 {idx} 无效")
                    return False
            
            elif instr.type == InstructionType.MOVE_WORLD_Z:
                # 支持字符串表达式，转换为浮点数
                distance = float(instr.params.get("distance", 0))
                speed = float(instr.params.get("speed", 30.0))
                self.log(f"  Z轴移动: distance={distance}, speed={speed}")
                return self.controller.move_world_z(distance, speed=speed, block=True)

            elif instr.type == InstructionType.MOVE_WORLD_REL:
                # 支持字符串表达式，转换为浮点数
                try:
                    dx = float(instr.params.get("dx", 0))
                    dy = float(instr.params.get("dy", 0))
                    dz = float(instr.params.get("dz", 0))
                    speed = float(instr.params.get("speed", 30.0))
                    self.log(f"  相对移动: dx={dx}, dy={dy}, dz={dz}")
                    return self.controller.move_world_relative(dx, dy, dz, speed=speed, block=True)
                except ValueError as e:
                    self.log(f"  ❌ 相对移动参数错误: {e}")
                    return False

            elif instr.type == InstructionType.SET_TCP_VERTICAL:
                # 支持字符串表达式，转换为浮点数
                speed = float(instr.params.get("speed", 30.0))
                self.log(f"  设置末端垂直: speed={speed}")
                return self.controller.set_tcp_vertical(speed=speed, block=True)

            elif instr.type == InstructionType.SET_TCP_ORIENTATION:
                # 支持字符串表达式，转换为浮点数
                rx = float(instr.params.get("rx", 0))
                ry = float(instr.params.get("ry", 0))
                rz = float(instr.params.get("rz", 0))
                speed = float(instr.params.get("speed", 30.0))
                self.log(f"  设置姿态: rx={rx}, ry={ry}, rz={rz}")
                return self.controller.set_tcp_orientation(rx, ry, rz, speed=speed, block=True)

            elif instr.type == InstructionType.DELAY:
                # 支持字符串表达式，转换为浮点数
                delay = float(instr.params.get("delay", 1.0))
                self.log(f"  延时 {delay} 秒...")
                # 分段延时，以便能够响应停止请求
                elapsed = 0
                step = 0.1  # 100ms检查一次
                while elapsed < delay:
                    if self.stop_requested:
                        self.log("  ⏹ 延时被中断")
                        return True
                    time.sleep(step)
                    elapsed += step
                    QApplication.processEvents()
                return True
            
            elif instr.type == InstructionType.GRIPPER_OPEN:
                self.log("  夹爪打开")
                if self.gripper_connected:
                    return gripper_open(self.gripper_control)
                else:
                    self.log("  夹爪未连接")
                    return False
            
            elif instr.type == InstructionType.GRIPPER_CLOSE:
                # 支持夹持力参数
                force = float(instr.params.get("force", 100))
                # 限制力值范围在 20-100
                force = max(20, min(100, force))
                self.log(f"  夹爪关闭 (夹持力: {force}%)")
                if self.gripper_connected:
                    return gripper_close(self.gripper_control, int(force))
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
            
            elif instr.type == InstructionType.SPIN_COATER_CHECK_ENABLE:
                self.log("  检查旋涂仪使能状态")
                # 检查使能状态，如果关闭则打开
                if self.spin_coater_control.check_enable_status():
                    self.log("  使能已开启")
                    return True
                else:
                    self.log("  使能关闭，正在开启...")
                    return enable_on(self.spin_coater_control)
            
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
                timeout = float(instr.params.get("timeout", 180))
                max_retries = 3
                
                for attempt in range(max_retries):
                    if attempt > 0:
                        self.log(f"  🔄 第 {attempt + 1} 次尝试等待旋涂...")
                    
                    start_time = time.time()
                    check_interval = 0.5
                    
                    while time.time() - start_time < timeout:
                        if self.stop_requested:
                            self.log("  ⏹ 等待旋涂被中断")
                            return True
                        try:
                            if not self.spin_coater_control.is_spinning():
                                self.log("  ✓ 旋涂已完成")
                                return True
                        except Exception as e:
                            self.log(f"  ⚠ 检查旋涂状态时出错: {e}")
                        time.sleep(check_interval)
                        QApplication.processEvents()
                    
                    if attempt < max_retries - 1:
                        self.log(f"  ⚠ 第 {attempt + 1} 次等待超时，准备重试...")
                        time.sleep(1)
                
                self.log(f"  ⚠ 等待旋涂超时（已尝试 {max_retries} 次）")
                return True
            
            return False
        
        except Exception as e:
            self.log(f"❌ 执行指令失败: {e}")
            return False
    
    def highlight_instruction(self, idx: int):
        """高亮显示指令"""
        self.program_listbox.setCurrentRow(idx)
        self.program_listbox.scrollToItem(self.program_listbox.item(idx))
    
    # ==================== 机器人控制 ====================
    
    def connect_robot(self):
        """连接机器人"""
        try:
            ip = self.ip_entry.text()
            port = int(self.port_entry.text())
            
            self.robot = CGXiRobot(ip=ip, port=port)
            if self.robot.connect():
                self.controller = create_robot_controller(self.robot)
                # 同步路点到控制器
                if self.waypoints:
                    self.controller.waypoints = self.waypoints
                    self.log(f"✓ 同步路点到控制器: {len(self.waypoints)} 个路点")
                self.connected = True
                self.robot_status_label.setText("已连接")
                self.robot_status_label.setStyleSheet("color: green;")
                self.log(f"✓ 连接成功: {ip}:{port}")
                QMessageBox.information(self, "成功", "机器人连接成功")
            else:
                self.log(f"❌ 连接失败")
                QMessageBox.critical(self, "错误", "机器人连接失败")
        
        except Exception as e:
            self.log(f"❌ 连接异常: {e}")
            QMessageBox.critical(self, "错误", f"连接异常: {e}")
    
    def disconnect_robot(self):
        """断开机器人"""
        if self.robot:
            self.robot.disconnect()
            self.connected = False
            self.controller = None
            self.robot_status_label.setText("未连接")
            self.robot_status_label.setStyleSheet("color: red;")
            self.log("✓ 已断开连接")
    
    def power_on(self):
        """上电"""
        if not self.connected:
            QMessageBox.critical(self, "错误", "请先连接机器人")
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
            QMessageBox.critical(self, "错误", "请先连接机器人")
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
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        if self.robot.fault_reset():
            self.log("✓ 故障复位成功")
        else:
            self.log("❌ 故障复位失败")
    
    def move_world_z(self, distance: float):
        """Z轴移动"""
        if not self.connected:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        if self.controller.move_world_z(distance, block=True):
            self.log(f"✓ Z轴移动: {distance:+.2f}mm")
        else:
            self.log(f"❌ Z轴移动失败")
    
    def set_tcp_vertical(self):
        """设置TCP垂直"""
        if not self.connected:
            QMessageBox.critical(self, "错误", "请先连接机器人")
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
            QMessageBox.critical(self, "错误", "请先连接夹爪")
            return
        
        if self.gripper_control.initialize():
            self.log("✓ 夹爪初始化成功")
        else:
            self.log("❌ 夹爪初始化失败")
    
    def gripper_open(self):
        """打开夹爪"""
        if not self.gripper_connected:
            QMessageBox.critical(self, "错误", "请先连接夹爪")
            return
        
        if gripper_open(self.gripper_control):
            self.log("✓ 夹爪打开成功")
        else:
            self.log("❌ 夹爪打开失败")
    
    def gripper_close(self):
        """关闭夹爪"""
        if not self.gripper_connected:
            QMessageBox.critical(self, "错误", "请先连接夹爪")
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
            port = self.spin_coater_port_entry.text()
            baudrate = int(self.spin_coater_baudrate_entry.text())
            
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
        """应用推杆串口配置"""
        try:
            new_port = self.relay_port_entry.text().strip()
            new_baudrate = int(self.relay_baudrate_entry.text().strip())
            new_data_bits = int(self.relay_data_bits_entry.text().strip())
            new_stop_bits = int(self.relay_stop_bits_entry.text().strip())
            new_parity = self.relay_parity_entry.text().strip().upper()
            new_device_address = int(self.relay_device_address_entry.text().strip())
            
            # 更新配置
            self.relay_port = new_port
            self.relay_baudrate = new_baudrate
            self.relay_data_bits = new_data_bits
            self.relay_stop_bits = new_stop_bits
            self.relay_parity = new_parity
            self.relay_device_address = new_device_address
            
            # 创建新的PushRodControl对象
            self.pushrod_control = PushRodControl(
                port=new_port,
                baudrate=new_baudrate,
                data_bits=new_data_bits,
                stop_bits=new_stop_bits,
                parity=new_parity,
                device_address=new_device_address
            )
            
            self.log(f"✓ 推杆串口配置已更新: {new_port} @ {new_baudrate}bps")
            QMessageBox.information(self, "成功", f"推杆串口配置已更新:\n串口: {new_port}\n波特率: {new_baudrate}\n数据位: {new_data_bits}\n停止位: {new_stop_bits}\n校验位: {new_parity}\n设备地址: {new_device_address}")
        except ValueError:
            QMessageBox.critical(self, "错误", "请输入有效的数值参数")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"配置更新失败: {e}")
    
    # ==================== 文件操作 ====================
    
    def new_program(self):
        """新建程序"""
        # 检查当前程序是否需要保存
        if self.current_program.instructions:
            reply = QMessageBox.question(self, "确认", "当前程序未保存，确定要新建程序吗?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        self.current_program = RobotProgram()
        self.current_file_path = None
        self.update_program_list()
        self.update_title()
        self.log("✓ 新建程序")
    
    def open_program(self, filepath: str = None):
        """打开程序"""
        if filepath is None:
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "打开程序",
                str(self.programs_dir),
                "JSON文件 (*.json);;所有文件 (*.*)"
            )
        
        if not filepath:
            self.log("❌ 未选择文件")
            return
        
        self.log(f"📂 正在打开程序: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.log(f"📄 文件读取成功，正在解析...")
            
            # 验证数据格式
            if not isinstance(data, dict):
                raise ValueError("文件格式错误：根对象必须是字典")
            
            if 'instructions' not in data:
                raise ValueError("文件格式错误：缺少 instructions 字段")
            
            self.current_program = RobotProgram.from_dict(data)
            self.current_file_path = filepath
            
            self.log(f"✓ 解析成功，共 {len(self.current_program.instructions)} 条指令")
            
            self.update_program_list()
            self.update_title()
            self.add_recent_file(filepath)
            self.log(f"✓ 打开程序成功: {filepath}")
            
            QMessageBox.information(self, "成功", f"程序打开成功\n共 {len(self.current_program.instructions)} 条指令")
        
        except json.JSONDecodeError as e:
            self.log(f"❌ JSON解析错误: {e}")
            QMessageBox.critical(self, "错误", f"JSON解析失败: {e}\n请检查文件格式是否正确")
        
        except KeyError as e:
            self.log(f"❌ 数据格式错误: 缺少字段 {e}")
            QMessageBox.critical(self, "错误", f"文件格式错误: 缺少字段 {e}")
        
        except ValueError as e:
            self.log(f"❌ 数据错误: {e}")
            QMessageBox.critical(self, "错误", f"打开程序失败: {e}")
        
        except Exception as e:
            self.log(f"❌ 打开程序失败: {e}")
            QMessageBox.critical(self, "错误", f"打开程序失败: {e}")
    
    def save_program(self):
        """保存程序"""
        if self.current_file_path:
            self._save_program_to_file(self.current_file_path)
        else:
            self.save_program_as()
    
    def save_program_as(self):
        """另存为"""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "保存程序",
            str(self.programs_dir),
            "JSON文件 (*.json);;所有文件 (*.*)"
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
            QMessageBox.information(self, "成功", "程序保存成功")
            # 同时保存到自动保存文件
            if self.auto_save_program:
                self.auto_save_current_program()
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存程序失败: {e}")
    
    def import_waypoints(self):
        """导入路点"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "导入路点",
            "",
            "JSON文件 (*.json);;CSV文件 (*.csv);;TXT文件 (*.txt);;所有文件 (*.*)"
        )
        
        if not filepath:
            return
        
        if not self.connected or not self.controller:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        if self.controller.load_waypoints(filepath, format="auto"):
            self.waypoints = self.controller.waypoints
            self.update_waypoint_list()
            self.log(f"✓ 导入路点: {filepath}")
            self.save_waypoints_to_file()
    
    def export_waypoints(self):
        """导出路点"""
        if not self.waypoints:
            QMessageBox.warning(self, "提示", "没有路点可导出")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "导出路点",
            "",
            "JSON文件 (*.json);;CSV文件 (*.csv);;TXT文件 (*.txt);;所有文件 (*.*)"
        )
        
        if not filepath:
            return
        
        if not self.connected or not self.controller:
            QMessageBox.critical(self, "错误", "请先连接机器人")
            return
        
        self.controller.waypoints = self.waypoints
        suffix = Path(filepath).suffix.lower()
        fmt = "json" if suffix == ".json" else ("csv" if suffix == ".csv" else "txt")
        
        if self.controller.save_waypoints(filepath, format=fmt):
            self.log(f"✓ 导出路点: {filepath}")
    
    # ==================== 其他功能 ====================
    
    def log(self, message: str):
        """添加日志"""
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] {message}")
        self.status_label.setText(message)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
    
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
        QMessageBox.information(self, "使用说明", help_text)
    
    def show_about(self):
        """显示关于"""
        about_text = """
机器人图形化编程系统 (PySide2版)
版本: 1.0

支持CGXi协作机器人的图形化编程
提供路点管理、程序编辑、运动控制等功能
        """
        QMessageBox.information(self, "关于", about_text)
    
    def load_data(self):
        """加载保存的数据"""
        try:
            # 自动加载路点文件
            if os.path.exists(self.waypoints_file):
                if self.connected and self.controller:
                    if self.controller.load_waypoints(self.waypoints_file, format="json"):
                        self.waypoints = self.controller.waypoints
                        self.update_waypoint_list()
                        self.log(f"✓ 自动加载路点: {len(self.waypoints)} 个路点")
                else:
                    # 先加载到内存，等连接机器人后再同步
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
        self.setWindowTitle(title)

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
        self.recent_menu.clear()
        
        if not self.recent_files:
            action = QAction("(无)", self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)
            return
        
        for filepath in self.recent_files:
            # 显示文件名和路径
            display_name = f"{Path(filepath).name}"
            action = QAction(display_name, self)
            action.triggered.connect(lambda checked=False, fp=filepath: self.open_program(fp))
            self.recent_menu.addAction(action)
        
        self.recent_menu.addSeparator()
        clear_action = QAction("清除历史", self)
        clear_action.triggered.connect(self.clear_recent_files)
        self.recent_menu.addAction(clear_action)

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
                "relay_port": self.relay_port,
                "relay_baudrate": self.relay_baudrate,
                "relay_data_bits": self.relay_data_bits,
                "relay_stop_bits": self.relay_stop_bits,
                "relay_parity": self.relay_parity,
                "relay_device_address": self.relay_device_address,
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
                self.relay_port = config.get("relay_port", "COM11")
                self.relay_baudrate = config.get("relay_baudrate", 9600)
                self.relay_data_bits = config.get("relay_data_bits", 8)
                self.relay_stop_bits = config.get("relay_stop_bits", 1)
                self.relay_parity = config.get("relay_parity", "NONE")
                self.relay_device_address = config.get("relay_device_address", 1)
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
        # 更新推杆串口配置输入框
        if hasattr(self, 'relay_port_entry'):
            self.relay_port_entry.setText(self.relay_port)
        if hasattr(self, 'relay_baudrate_entry'):
            self.relay_baudrate_entry.setText(str(self.relay_baudrate))
        if hasattr(self, 'relay_data_bits_entry'):
            self.relay_data_bits_entry.setText(str(self.relay_data_bits))
        if hasattr(self, 'relay_stop_bits_entry'):
            self.relay_stop_bits_entry.setText(str(self.relay_stop_bits))
        if hasattr(self, 'relay_parity_entry'):
            self.relay_parity_entry.setText(self.relay_parity)
        if hasattr(self, 'relay_device_address_entry'):
            self.relay_device_address_entry.setText(str(self.relay_device_address))
        # 更新旋涂仪配置输入框
        if hasattr(self, 'spin_coater_port_entry'):
            self.spin_coater_port_entry.setText(self.spin_coater_port)
        if hasattr(self, 'spin_coater_baudrate_entry'):
            self.spin_coater_baudrate_entry.setText(str(self.spin_coater_baudrate))

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
                self.log(f"✓ 自动加载程序: {self.current_program.name}")
        except Exception as e:
            self.log(f"❌ 自动加载程序失败: {e}")

    def on_exit(self):
        """退出程序"""
        # 自动保存
        if self.auto_save_program:
            self.auto_save_current_program()
        self.save_config()
        self.close()

    def open_manual_control(self):
        """打开手动控制窗口"""
        dialog = ManualControlDialog(self, self)
        dialog.exec_()

    def closeEvent(self, event):
        """关闭事件"""
        if self.auto_save_program:
            self.auto_save_current_program()
        self.save_config()
        event.accept()


class InstructionDialog(QDialog):
    """指令对话框"""
    
    def __init__(self, parent, waypoints: List[Waypoint], instruction: Instruction = None):
        super().__init__(parent)
        self.result = None
        self.waypoints = waypoints
        self.current_instruction = instruction
        
        self.setWindowTitle("添加/编辑指令")
        self.setGeometry(200, 200, 700, 500)
        
        self.create_ui()
        
        if instruction:
            self.load_instruction_params(instruction)
    
    def create_ui(self):
        """创建界面 - 左右分栏布局"""
        # 主布局
        main_layout = QHBoxLayout(self)
        
        # 左侧：指令类型选择（带滚动）
        left_group = QGroupBox("指令类型")
        left_layout = QVBoxLayout(left_group)
        
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        left_scroll_content = QWidget()
        left_scroll_layout = QVBoxLayout(left_scroll_content)
        
        self.instr_type_group = QButtonGroup(self)
        for i, instr_type in enumerate(InstructionType):
            radio = QRadioButton(instr_type.value)
            self.instr_type_group.addButton(radio, i)
            left_scroll_layout.addWidget(radio)
            
            # 默认选中第一个或当前指令类型
            if self.current_instruction:
                if instr_type == self.current_instruction.type:
                    radio.setChecked(True)
            elif i == 0:
                radio.setChecked(True)
        
        self.instr_type_group.buttonClicked.connect(self.on_type_change)
        left_scroll_layout.addStretch()
        left_scroll.setWidget(left_scroll_content)
        left_layout.addWidget(left_scroll)
        
        main_layout.addWidget(left_group, 1)  # 左侧占1份
        
        # 右侧容器：参数设置 + 按钮
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        
        # 参数设置组
        self.param_group = QGroupBox("参数设置")
        self.param_layout = QGridLayout(self.param_group)
        
        # 注释
        self.param_layout.addWidget(QLabel("注释:"), 0, 0)
        self.comment_entry = QLineEdit()
        self.param_layout.addWidget(self.comment_entry, 0, 1)
        
        right_layout.addWidget(self.param_group)
        right_layout.addStretch()
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        
        self.btn_ok = QPushButton("确定")
        self.btn_ok.clicked.connect(self.on_ok)
        btn_layout.addWidget(self.btn_ok)
        
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        right_layout.addLayout(btn_layout)
        
        main_layout.addWidget(right_container, 1)  # 右侧占1份
        
        # 初始化参数输入框
        self.create_param_inputs()
    
    def create_param_inputs(self):
        """创建参数输入框"""
        # 清除旧的参数输入框（保留注释）
        while self.param_layout.count() > 2:
            item = self.param_layout.takeAt(2)
            if item.widget():
                item.widget().deleteLater()
        
        self.param_entries = {}
        
        # 获取当前选中的指令类型
        checked_button = self.instr_type_group.checkedButton()
        if not checked_button:
            return
        
        instr_type_value = checked_button.text()
        
        row = 1
        if instr_type_value == InstructionType.MOVE_TO_WAYPOINT.value:
            self.param_layout.addWidget(QLabel("路点:"), row, 0)
            self.wp_combo = QComboBox()
            for i, wp in enumerate(self.waypoints):
                self.wp_combo.addItem(f"[{i}] {wp.name}", i)
            self.param_layout.addWidget(self.wp_combo, row, 1)
            self.param_entries['waypoint_index'] = self.wp_combo
            
            row += 1
            self.param_layout.addWidget(QLabel("X偏移 (mm):"), row, 0)
            self.offset_x_entry = QLineEdit()
            self.offset_x_entry.setText("0")
            self.offset_x_entry.setPlaceholderText("数值或表达式，如: 40*i")
            self.param_layout.addWidget(self.offset_x_entry, row, 1)
            self.param_entries['offset_x'] = self.offset_x_entry
            
            row += 1
            self.param_layout.addWidget(QLabel("Y偏移 (mm):"), row, 0)
            self.offset_y_entry = QLineEdit()
            self.offset_y_entry.setText("0")
            self.offset_y_entry.setPlaceholderText("数值或表达式，如: 30*j")
            self.param_layout.addWidget(self.offset_y_entry, row, 1)
            self.param_entries['offset_y'] = self.offset_y_entry
        
        elif instr_type_value == InstructionType.MOVE_WORLD_Z.value:
            self.param_layout.addWidget(QLabel("距离 (mm):"), row, 0)
            self.distance_entry = QLineEdit()
            self.distance_entry.setText("50")
            self.distance_entry.setPlaceholderText("数值或表达式，如: 10*i")
            self.param_layout.addWidget(self.distance_entry, row, 1)
            self.param_entries['distance'] = self.distance_entry
            
            row += 1
            self.param_layout.addWidget(QLabel("速度:"), row, 0)
            self.speed_entry = QLineEdit()
            self.speed_entry.setText("30")
            self.speed_entry.setPlaceholderText("数值或表达式")
            self.param_layout.addWidget(self.speed_entry, row, 1)
            self.param_entries['speed'] = self.speed_entry
        
        elif instr_type_value == InstructionType.MOVE_WORLD_REL.value:
            self.param_layout.addWidget(QLabel("X偏移 (mm):"), row, 0)
            self.dx_entry = QLineEdit()
            self.dx_entry.setText("0")
            self.dx_entry.setPlaceholderText("数值或表达式，如: 0.5*i")
            self.param_layout.addWidget(self.dx_entry, row, 1)
            self.param_entries['dx'] = self.dx_entry
            
            row += 1
            self.param_layout.addWidget(QLabel("Y偏移 (mm):"), row, 0)
            self.dy_entry = QLineEdit()
            self.dy_entry.setText("0")
            self.dy_entry.setPlaceholderText("数值或表达式，如: 0.5*i")
            self.param_layout.addWidget(self.dy_entry, row, 1)
            self.param_entries['dy'] = self.dy_entry
            
            row += 1
            self.param_layout.addWidget(QLabel("Z偏移 (mm):"), row, 0)
            self.dz_entry = QLineEdit()
            self.dz_entry.setText("0")
            self.dz_entry.setPlaceholderText("数值或表达式，如: 0.5*i")
            self.param_layout.addWidget(self.dz_entry, row, 1)
            self.param_entries['dz'] = self.dz_entry
            
            row += 1
            self.param_layout.addWidget(QLabel("速度:"), row, 0)
            self.speed_spin2 = QDoubleSpinBox()
            self.speed_spin2.setRange(1, 100)
            self.speed_spin2.setValue(30)
            self.param_layout.addWidget(self.speed_spin2, row, 1)
            self.param_entries['speed'] = self.speed_spin2
        
        elif instr_type_value == InstructionType.SET_TCP_VERTICAL.value:
            self.param_layout.addWidget(QLabel("速度:"), row, 0)
            self.speed_entry3 = QLineEdit()
            self.speed_entry3.setText("30")
            self.speed_entry3.setPlaceholderText("数值或表达式")
            self.param_layout.addWidget(self.speed_entry3, row, 1)
            self.param_entries['speed'] = self.speed_entry3
        
        elif instr_type_value == InstructionType.SET_TCP_ORIENTATION.value:
            self.param_layout.addWidget(QLabel("Rx (度):"), row, 0)
            self.rx_entry = QLineEdit()
            self.rx_entry.setText("0")
            self.rx_entry.setPlaceholderText("数值或表达式")
            self.param_layout.addWidget(self.rx_entry, row, 1)
            self.param_entries['rx'] = self.rx_entry

            row += 1
            self.param_layout.addWidget(QLabel("Ry (度):"), row, 0)
            self.ry_entry = QLineEdit()
            self.ry_entry.setText("0")
            self.ry_entry.setPlaceholderText("数值或表达式")
            self.param_layout.addWidget(self.ry_entry, row, 1)
            self.param_entries['ry'] = self.ry_entry

            row += 1
            self.param_layout.addWidget(QLabel("Rz (度):"), row, 0)
            self.rz_entry = QLineEdit()
            self.rz_entry.setText("0")
            self.rz_entry.setPlaceholderText("数值或表达式")
            self.param_layout.addWidget(self.rz_entry, row, 1)
            self.param_entries['rz'] = self.rz_entry

            row += 1
            self.param_layout.addWidget(QLabel("速度:"), row, 0)
            self.speed_entry4 = QLineEdit()
            self.speed_entry4.setText("30")
            self.speed_entry4.setPlaceholderText("数值或表达式")
            self.param_layout.addWidget(self.speed_entry4, row, 1)
            self.param_entries['speed'] = self.speed_entry4
        
        elif instr_type_value == InstructionType.DELAY.value:
            self.param_layout.addWidget(QLabel("延时 (秒):"), row, 0)
            self.delay_entry = QLineEdit()
            self.delay_entry.setText("1.0")
            self.delay_entry.setPlaceholderText("数值或表达式，如: 0.5*i")
            self.param_layout.addWidget(self.delay_entry, row, 1)
            self.param_entries['delay'] = self.delay_entry
        
        elif instr_type_value == InstructionType.SPIN_COATER_WAIT_COMPLETION.value:
            self.param_layout.addWidget(QLabel("超时时间 (秒):"), row, 0)
            self.timeout_entry = QLineEdit()
            self.timeout_entry.setText("180")
            self.timeout_entry.setPlaceholderText("数值或表达式，如: 60, i*30")
            self.param_layout.addWidget(self.timeout_entry, row, 1)
            self.param_entries['timeout'] = self.timeout_entry
        
        elif instr_type_value == InstructionType.LOOP_START.value:
            self.param_layout.addWidget(QLabel("循环次数:"), row, 0)
            self.loop_count_spin = QSpinBox()
            self.loop_count_spin.setRange(1, 9999)
            self.loop_count_spin.setValue(2)
            self.param_layout.addWidget(self.loop_count_spin, row, 1)
            self.param_entries['loop_count'] = self.loop_count_spin
            
            row += 1
            info_label = QLabel("提示: 普通循环，需要配合'循环结束'使用")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            self.param_layout.addWidget(info_label, row, 0, 1, 2)
        
        elif instr_type_value == InstructionType.LOOP_START_VAR.value:
            self.param_layout.addWidget(QLabel("循环次数:"), row, 0)
            self.loop_count_spin = QSpinBox()
            self.loop_count_spin.setRange(1, 9999)
            self.loop_count_spin.setValue(5)
            self.param_layout.addWidget(self.loop_count_spin, row, 1)
            self.param_entries['loop_count'] = self.loop_count_spin
            
            row += 1
            self.param_layout.addWidget(QLabel("变量名:"), row, 0)
            self.var_name_entry = QLineEdit()
            self.var_name_entry.setText("i")
            self.var_name_entry.setPlaceholderText("如: i, j, k")
            self.param_layout.addWidget(self.var_name_entry, row, 1)
            self.param_entries['var_name'] = self.var_name_entry
            
            row += 1
            self.param_layout.addWidget(QLabel("起始值:"), row, 0)
            self.start_value_spin = QSpinBox()
            self.start_value_spin.setRange(0, 9999)
            self.start_value_spin.setValue(0)
            self.param_layout.addWidget(self.start_value_spin, row, 1)
            self.param_entries['start_value'] = self.start_value_spin
            
            row += 1
            info_label = QLabel("提示: 带变量的循环，变量可在参数中使用(如: 0.5*i)")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            self.param_layout.addWidget(info_label, row, 0, 1, 2)
            
            row += 1
            info_label2 = QLabel("嵌套示例: 外层用i，内层用j，参数写0.5*i+0.1*j")
            info_label2.setStyleSheet("color: blue; font-size: 10px;")
            self.param_layout.addWidget(info_label2, row, 0, 1, 2)
        
        elif instr_type_value == InstructionType.LOOP_END.value:
            info_label = QLabel("提示: 循环结束标记，与'循环开始'或'循环开始(带变量)'配对使用")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            self.param_layout.addWidget(info_label, row, 0, 1, 2)

        elif instr_type_value == InstructionType.GRIPPER_CLOSE.value:
            self.param_layout.addWidget(QLabel("夹持力 (%):"), row, 0)
            self.force_entry = QLineEdit()
            self.force_entry.setText("100")
            self.force_entry.setPlaceholderText("0-100，支持表达式如: 50+10*i")
            self.param_layout.addWidget(self.force_entry, row, 1)
            self.param_entries['force'] = self.force_entry

            row += 1
            info_label = QLabel("提示: 0=最小力，100=最大力")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            self.param_layout.addWidget(info_label, row, 0, 1, 2)

        elif instr_type_value == InstructionType.GRIPPER_OPEN.value:
            info_label = QLabel("提示: 夹爪完全打开")
            info_label.setStyleSheet("color: gray; font-size: 10px;")
            self.param_layout.addWidget(info_label, row, 0, 1, 2)

    def on_type_change(self):
        """指令类型改变事件"""
        self.create_param_inputs()
    
    def load_instruction_params(self, instruction: Instruction):
        """加载指令参数"""
        self.comment_entry.setText(instruction.comment)
        
        for key, value in instruction.params.items():
            if key in self.param_entries:
                widget = self.param_entries[key]
                if isinstance(widget, QComboBox):
                    widget.setCurrentIndex(value)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, QSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
    
    def on_ok(self):
        """确定按钮"""
        try:
            # 获取选中的指令类型
            checked_button = self.instr_type_group.checkedButton()
            instr_type = InstructionType(checked_button.text())
            
            params = {}
            comment = self.comment_entry.text()
            
            for key, widget in self.param_entries.items():
                if isinstance(widget, QComboBox):
                    params[key] = widget.currentData()
                elif isinstance(widget, QDoubleSpinBox):
                    params[key] = widget.value()
                elif isinstance(widget, QSpinBox):
                    params[key] = widget.value()
                elif isinstance(widget, QLineEdit):
                    params[key] = widget.text()
            
            self.result = Instruction(instr_type, params, comment)
            self.accept()
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"参数错误: {e}")


class ManualControlDialog(QDialog):
    """手动控制对话框"""
    
    def __init__(self, parent, main_app):
        super().__init__(parent)
        self.main_app = main_app
        self.moving = False
        
        self.setWindowTitle("手动控制")
        self.setGeometry(300, 300, 400, 350)
        
        self.create_ui()
        
        # 安装事件过滤器以捕获键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
    
    def create_ui(self):
        """创建界面"""
        layout = QVBoxLayout(self)
        
        # 速度设置
        speed_group = QGroupBox("速度设置")
        speed_layout = QHBoxLayout(speed_group)
        
        speed_layout.addWidget(QLabel("速度 (mm/s):"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(10, 100)
        self.speed_slider.setValue(30)
        speed_layout.addWidget(self.speed_slider)
        
        self.speed_label = QLabel("30")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(str(v)))
        speed_layout.addWidget(self.speed_label)
        
        layout.addWidget(speed_group)
        
        # 控制说明
        info_group = QGroupBox("控制说明")
        info_layout = QVBoxLayout(info_group)
        
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
        info_label = QLabel(info_text)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_group)
        
        # 状态显示
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout(status_group)
        
        self.status_var = QLabel("就绪")
        status_layout.addWidget(self.status_var)
        
        layout.addWidget(status_group)
        
        # 关闭按钮
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        layout.addWidget(self.btn_close)
    
    def keyPressEvent(self, event: QKeyEvent):
        """键盘按下事件"""
        if self.moving:
            return
        
        if not self.main_app.connected or not self.main_app.controller:
            self.status_var.setText("错误: 请先连接机器人")
            return
        
        key = event.key()
        speed = self.speed_slider.value()
        
        try:
            if key == Qt.Key_W:
                self.status_var.setText(f"Z轴上升 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_z(10, speed=speed, block=False)
                self.moving = True
            elif key == Qt.Key_S:
                self.status_var.setText(f"Z轴下降 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_z(-10, speed=speed, block=False)
                self.moving = True
            elif key == Qt.Key_A:
                self.status_var.setText(f"Y轴左移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(0, -10, 0, speed=speed, block=False)
                self.moving = True
            elif key == Qt.Key_D:
                self.status_var.setText(f"Y轴右移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(0, 10, 0, speed=speed, block=False)
                self.moving = True
            elif key == Qt.Key_C:
                self.status_var.setText(f"X轴前移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(10, 0, 0, speed=speed, block=False)
                self.moving = True
            elif key == Qt.Key_Z:
                self.status_var.setText(f"X轴后移 (速度: {speed} mm/s)")
                self.main_app.controller.move_world_relative(-10, 0, 0, speed=speed, block=False)
                self.moving = True
        except Exception as e:
            self.status_var.setText(f"错误: {e}")
    
    def keyReleaseEvent(self, event: QKeyEvent):
        """键盘释放事件"""
        if not self.moving:
            return
        
        key = event.key()
        if key in [Qt.Key_W, Qt.Key_S, Qt.Key_A, Qt.Key_D, Qt.Key_C, Qt.Key_Z]:
            self.status_var.setText("就绪")
            self.moving = False


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 设置字体
    font = QFont("Microsoft YaHei", 9)
    app.setFont(font)
    
    window = RobotGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

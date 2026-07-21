"""
PGEA系列驱控一体式工业平行电爪 - Python控制库

基于Modbus-RTU协议的大寰(DH-Robotics) PGEA系列夹爪控制库。

主要功能:
- 夹爪初始化与标定
- 力/位/速三闭环控制
- 夹持状态实时反馈
- IO模式配置
- 参数保存与恢复

快速开始:
    from pgea_gripper_skill import PGEAGripper, GripperStatus
    
    # 连接夹爪
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    gripper.connect()
    
    # 初始化
    gripper.initialize()
    
    # 设置参数并运动
    gripper.set_force(50)
    gripper.set_speed(30)
    gripper.move_to(500)
    
    # 等待完成
    gripper.wait_for_complete()
    
    # 获取状态
    status = gripper.get_full_status()
    print(status)
    
    # 断开连接
    gripper.disconnect()

版本: 1.0.0
作者: AI Assistant
协议: Modbus-RTU over RS485
"""

__version__ = "1.0.0"
__author__ = "AI Assistant"

# 主控制类
from .gripper import PGEAGripper, GripperStatus

# Modbus客户端
from .modbus_client import ModbusRTUClient, CRC16

# 常量定义
from .constants import (
    # 寄存器地址
    REG_INIT_GRIPPER,
    REG_FORCE,
    REG_POSITION,
    REG_SPEED,
    REG_JOG,
    REG_INIT_STATUS,
    REG_GRIP_STATUS,
    REG_POSITION_FEEDBACK,
    REG_CURRENT_FEEDBACK,
    REG_ERROR_FEEDBACK,
    
    # 状态值
    INIT_STATUS_NOT_INIT,
    INIT_STATUS_SUCCESS,
    INIT_STATUS_IN_PROGRESS,
    GRIP_STATUS_MOVING,
    GRIP_STATUS_IN_POSITION,
    GRIP_STATUS_GRIPPED,
    GRIP_STATUS_DROPPED,
    
    # 错误码
    ERROR_NONE,
    ERROR_UNDERVOLTAGE,
    ERROR_OVERVOLTAGE,
    ERROR_OVERCURRENT,
    ERROR_OVERTEMP,
    ERROR_ENCODER,
    ERROR_DESCRIPTIONS,
    
    # 初始化命令
    INIT_COMMAND_NORMAL,
    INIT_COMMAND_FULL,
    
    # 点动控制
    JOG_BACKWARD,
    JOG_STOP,
    JOG_FORWARD,
    
    # 数值范围
    FORCE_MIN,
    FORCE_MAX,
    POSITION_MIN,
    POSITION_MAX,
    SPEED_MIN,
    SPEED_MAX,
    
    # 默认配置
    DEFAULT_BAUDRATE,
    DEFAULT_SLAVE_ID,
)

__all__ = [
    # 主类
    'PGEAGripper',
    'GripperStatus',
    'ModbusRTUClient',
    'CRC16',
    
    # 寄存器地址
    'REG_INIT_GRIPPER',
    'REG_FORCE',
    'REG_POSITION',
    'REG_SPEED',
    'REG_JOG',
    'REG_INIT_STATUS',
    'REG_GRIP_STATUS',
    'REG_POSITION_FEEDBACK',
    'REG_CURRENT_FEEDBACK',
    'REG_ERROR_FEEDBACK',
    
    # 状态值
    'INIT_STATUS_NOT_INIT',
    'INIT_STATUS_SUCCESS',
    'INIT_STATUS_IN_PROGRESS',
    'GRIP_STATUS_MOVING',
    'GRIP_STATUS_IN_POSITION',
    'GRIP_STATUS_GRIPPED',
    'GRIP_STATUS_DROPPED',
    
    # 错误码
    'ERROR_NONE',
    'ERROR_UNDERVOLTAGE',
    'ERROR_OVERVOLTAGE',
    'ERROR_OVERCURRENT',
    'ERROR_OVERTEMP',
    'ERROR_ENCODER',
    'ERROR_DESCRIPTIONS',
    
    # 命令
    'INIT_COMMAND_NORMAL',
    'INIT_COMMAND_FULL',
    'JOG_BACKWARD',
    'JOG_STOP',
    'JOG_FORWARD',
    
    # 范围
    'FORCE_MIN',
    'FORCE_MAX',
    'POSITION_MIN',
    'POSITION_MAX',
    'SPEED_MIN',
    'SPEED_MAX',
    
    # 默认配置
    'DEFAULT_BAUDRATE',
    'DEFAULT_SLAVE_ID',
]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
夹爪和推杆控制工具函数
提供夹爪开合、上推杆、下推杆、旋涂仪推杆的控制功能
"""

import sys
import time
from pathlib import Path

# 添加 skills 路径
UTILS_DIR = Path(__file__).parent.resolve()
SKILLS_PATH = UTILS_DIR.parent / 'skills'
sys.path.insert(0, str(SKILLS_PATH / 'pgea_gripper_skill'))
sys.path.insert(0, str(SKILLS_PATH / 'jidianqi'))

try:
    from gripper import PGEAGripper
    from relay_utils import StringProtocol, ModbusRTU
except ImportError as e:
    print(f"无法导入模块 - {e}")
    sys.exit(1)


class GripperControl:
    """夹爪控制类"""
    
    def __init__(self, port: str = "COM4", slave_id: int = 1):
        """
        初始化夹爪控制器
        
        Args:
            port: 串口号
            slave_id: 从站ID
        """
        self.port = port
        self.slave_id = slave_id
        self.gripper = None
    
    def connect(self) -> bool:
        """连接夹爪"""
        try:
            self.gripper = PGEAGripper(port=self.port, slave_id=self.slave_id)
            result = self.gripper.connect()
            return result
        except Exception as e:
            print(f"夹爪连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.gripper:
            self.gripper.disconnect()
    
    def initialize(self, full_calibration: bool = False) -> bool:
        """初始化夹爪"""
        if not self.gripper or not self.gripper.is_connected():
            print("夹爪未连接")
            return False
        
        try:
            if self.gripper.is_initialized():
                print("夹爪已初始化")
                return True
            
            result = self.gripper.initialize(
                full_calibration=full_calibration,
                wait=True,
                timeout=10.0
            )
            return result
        except Exception as e:
            print(f"夹爪初始化失败: {e}")
            return False


class PushRodControl:
    """推杆控制类（基于串口）"""
    
    def __init__(self, port: str = "COM11", baudrate: int = 9600, data_bits: int = 8, stop_bits: int = 1, parity: str = "NONE", device_address: int = 1):
        """
        初始化推杆控制器
        
        Args:
            port: 串口端口，如 "COM11"
            baudrate: 波特率，默认9600
            data_bits: 数据位，默认8
            stop_bits: 停止位，默认1
            parity: 校验位，默认"NONE"
            device_address: 设备地址，默认1
        """
        self.port = port
        self.baudrate = baudrate
        self.data_bits = data_bits
        self.stop_bits = stop_bits
        self.parity = parity
        self.device_address = device_address
        self.ser = None
        # 推杆状态记录 (False=收回, True=推出, None=未知)
        self.upper_state = None
        self.lower_state = None
        self.spin_coater_state = None
    
    def _control_relay(self, channel: int, action: str) -> bool:
        """
        控制单个继电器通道（通过串口）
        
        Args:
            channel: 通道号
            action: 动作 ("on" 或 "off")
        
        Returns:
            bool: 是否成功
        """
        try:
            # 创建串口连接
            import serial
            
            # 映射校验位
            parity_map = {
                "NONE": serial.PARITY_NONE,
                "EVEN": serial.PARITY_EVEN,
                "ODD": serial.PARITY_ODD
            }
            
            # 映射数据位
            data_bits_map = {
                5: serial.FIVEBITS,
                6: serial.SIXBITS,
                7: serial.SEVENBITS,
                8: serial.EIGHTBITS
            }
            
            # 映射停止位
            stop_bits_map = {
                1: serial.STOPBITS_ONE,
                1.5: serial.STOPBITS_ONE_POINT_FIVE,
                2: serial.STOPBITS_TWO
            }
            
            # 创建串口对象
            ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=data_bits_map.get(self.data_bits, serial.EIGHTBITS),
                parity=parity_map.get(self.parity, serial.PARITY_NONE),
                stopbits=stop_bits_map.get(self.stop_bits, serial.STOPBITS_ONE),
                timeout=1
            )
            
            if not ser.is_open:
                print(f"  串口 {self.port} 打开失败")
                return False
            
            # 构建MODBUS-RTU指令
            addr = (channel - 1) & 0xFFFF
            if action == "on":
                # 05功能码，写入单个线圈，值为1
                data = f"{self.device_address:02X}05{addr:04X}FF00"
            else:
                # 05功能码，写入单个线圈，值为0
                data = f"{self.device_address:02X}05{addr:04X}0000"
            
            # 计算CRC校验
            from relay_utils import CRC16
            cmd_hex = CRC16.append_to_hex(data)
            
            # 将十六进制字符串转换为字节
            data_bytes = bytes.fromhex(cmd_hex.replace(' ', ''))
            ser.write(data_bytes)
            ser.flush()
            
            # 尝试接收响应
            try:
                response = ser.read(1024)
            except:
                pass  # 超时是正常的
            
            # 关闭连接
            ser.close()
            return True
            
        except Exception as e:
            print(f"  通道 {channel} {action} 失败: {e}")
            return False
    
    def _control_relay_pair(self, channel_on: int, channel_off: int) -> bool:
        """
        控制继电器对（一个开，一个关）
        
        Args:
            channel_on: 要开启的通道号
            channel_off: 要关闭的通道号
        
        Returns:
            bool: 是否成功
        """
        try:
            # 先关闭要关闭的通道
            if channel_off > 0:
                if not self._control_relay(channel_off, "off"):
                    return False
                time.sleep(0.1)
            
            # 再开启要开启的通道
            if channel_on > 0:
                if not self._control_relay(channel_on, "on"):
                    return False
                time.sleep(0.1)
            
            return True
        except Exception as e:
            print(f"发送继电器对命令失败: {e}")
            return False


def gripper_open(control: GripperControl, position: int = 1000, speed: int = 50) -> bool:
    """
    夹爪张开
    
    Args:
        control: 夹爪控制对象
        position: 张开位置 (0-1000‰, 默认1000)
        speed: 速度 (1-100%, 默认50)
    
    Returns:
        bool: 是否成功
    """
    print("🖐️  夹爪张开...")
    
    if not control.gripper or not control.gripper.is_connected():
        print("✗ 夹爪未连接")
        return False
    
    try:
        if not control.gripper.is_initialized():
            print("✗ 夹爪未初始化")
            return False
        
        control.gripper.set_speed(speed)
        control.gripper.move_to(position)
        control.gripper.wait_for_complete(timeout=10.0)
        print(f"✓ 夹爪张开到位置 {position}‰")
        return True
    except Exception as e:
        print(f"✗ 夹爪张开失败: {e}")
        return False


def gripper_close(control: GripperControl, force: int = 50, speed: int = 30) -> bool:
    """
    夹爪闭合
    
    Args:
        control: 夹爪控制对象
        force: 夹持力值 (20-100%, 默认50)
        speed: 速度 (1-100%, 默认30)
    
    Returns:
        bool: 是否成功
    """
    print("✊ 夹爪闭合...")
    
    if not control.gripper or not control.gripper.is_connected():
        print("✗ 夹爪未连接")
        return False
    
    try:
        if not control.gripper.is_initialized():
            print("✗ 夹爪未初始化")
            return False
        
        result = control.gripper.grip(force=force, speed=speed, wait=True, timeout=10.0)
        if result:
            print(f"✓ 夹爪闭合 (力值: {force}%)")
        else:
            print("⚠ 夹爪闭合但未检测到物体 (正常，无物体时闭合)")
        return True
    except Exception as e:
        print(f"✗ 夹爪闭合失败: {e}")
        return False


def gripper_toggle(control: GripperControl, position: int = 1000, 
                   force: int = 50, speed: int = 50) -> bool:
    """
    夹爪切换（张开/闭合）
    
    Args:
        control: 夹爪控制对象
        position: 张开位置 (0-1000‰, 默认1000)
        force: 夹持力值 (20-100%, 默认50)
        speed: 速度 (1-100%, 默认50)
    
    Returns:
        bool: 是否成功
    """
    print("🔄 夹爪切换...")
    
    if not control.gripper or not control.gripper.is_connected():
        print("✗ 夹爪未连接")
        return False
    
    if not control.gripper.is_initialized():
        print("✗ 夹爪未初始化")
        return False
    
    try:
        # 获取当前位置
        current_pos = control.gripper.get_current_position()
        
        # 如果当前位置接近张开位置，则闭合；否则张开
        if current_pos > position / 2:
            return gripper_close(control, force, speed)
        else:
            return gripper_open(control, position, speed)
    except Exception as e:
        print(f"✗ 夹爪切换失败: {e}")
        return False


def upper_pushrod_extend(control: PushRodControl) -> bool:
    """
    上推杆推出
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔼 上推杆推出...")
    # 12g/13k = 12关/13开 = 推出
    result = control._control_relay_pair(channel_on=13, channel_off=12)
    if result:
        control.upper_state = True
    print(f"{'✓' if result else '✗'} 上推杆推出{'成功' if result else '失败'}")
    return result


def upper_pushrod_retract(control: PushRodControl) -> bool:
    """
    上推杆收回
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔽 上推杆收回...")
    # 12k/13g = 12开/13关 = 收回
    result = control._control_relay_pair(channel_on=12, channel_off=13)
    if result:
        control.upper_state = False
    print(f"{'✓' if result else '✗'} 上推杆收回{'成功' if result else '失败'}")
    return result


def upper_pushrod_toggle(control: PushRodControl) -> bool:
    """
    上推杆切换（推出/收回）
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔄 上推杆切换...")
    
    # 根据当前状态决定动作
    if control.upper_state is None:
        # 状态未知，默认推出
        print("  状态未知，默认执行推出")
        return upper_pushrod_extend(control)
    elif control.upper_state:
        # 当前推出，执行收回
        print("  当前已推出，执行收回")
        return upper_pushrod_retract(control)
    else:
        # 当前收回，执行推出
        print("  当前已收回，执行推出")
        return upper_pushrod_extend(control)


def lower_pushrod_extend(control: PushRodControl) -> bool:
    """
    下推杆推出
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔼 下推杆推出...")
    # 10g/11k = 10关/11开 = 推出
    result = control._control_relay_pair(channel_on=11, channel_off=10)
    if result:
        control.lower_state = True
    print(f"{'✓' if result else '✗'} 下推杆推出{'成功' if result else '失败'}")
    return result


def lower_pushrod_retract(control: PushRodControl) -> bool:
    """
    下推杆收回
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔽 下推杆收回...")
    # 10k/11g = 10开/11关 = 收回
    result = control._control_relay_pair(channel_on=10, channel_off=11)
    if result:
        control.lower_state = False
    print(f"{'✓' if result else '✗'} 下推杆收回{'成功' if result else '失败'}")
    return result


def lower_pushrod_toggle(control: PushRodControl) -> bool:
    """
    下推杆切换（推出/收回）
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔄 下推杆切换...")
    
    # 根据当前状态决定动作
    if control.lower_state is None:
        # 状态未知，默认推出
        print("  状态未知，默认执行推出")
        return lower_pushrod_extend(control)
    elif control.lower_state:
        # 当前推出，执行收回
        print("  当前已推出，执行收回")
        return lower_pushrod_retract(control)
    else:
        # 当前收回，执行推出
        print("  当前已收回，执行推出")
        return lower_pushrod_extend(control)


def spin_coater_pushrod_extend(control: PushRodControl) -> bool:
    """
    旋涂仪推杆推出
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔼 旋涂仪推杆推出...")
    # 14开/15关 = 推出
    result = control._control_relay_pair(channel_on=14, channel_off=15)
    if result:
        control.spin_coater_state = True
    print(f"{'✓' if result else '✗'} 旋涂仪推杆推出{'成功' if result else '失败'}")
    return result


def spin_coater_pushrod_retract(control: PushRodControl) -> bool:
    """
    旋涂仪推杆收回
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔽 旋涂仪推杆收回...")
    # 15开/14关 = 收回
    result = control._control_relay_pair(channel_on=15, channel_off=14)
    if result:
        control.spin_coater_state = False
    print(f"{'✓' if result else '✗'} 旋涂仪推杆收回{'成功' if result else '失败'}")
    return result


def spin_coater_pushrod_toggle(control: PushRodControl) -> bool:
    """
    旋涂仪推杆切换（推出/收回）
    
    Args:
        control: 推杆控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔄 旋涂仪推杆切换...")
    
    # 根据当前状态决定动作
    if control.spin_coater_state is None:
        # 状态未知，默认推出
        print("  状态未知，默认执行推出")
        return spin_coater_pushrod_extend(control)
    elif control.spin_coater_state:
        # 当前推出，执行收回
        print("  当前已推出，执行收回")
        return spin_coater_pushrod_retract(control)
    else:
        # 当前收回，执行推出
        print("  当前已收回，执行推出")
        return spin_coater_pushrod_extend(control)


if __name__ == '__main__':
    print("=" * 60)
    print("夹爪和推杆控制工具函数测试")
    print("=" * 60)
    
    print("\n【夹爪控制功能】")
    print("✓ gripper_open()      - 夹爪张开")
    print("✓ gripper_close()     - 夹爪闭合")
    print("✓ gripper_toggle()   - 夹爪切换")
    
    print("\n【上推杆控制功能】")
    print("✓ upper_pushrod_extend()   - 上推杆推出")
    print("✓ upper_pushrod_retract()  - 上推杆收回")
    print("✓ upper_pushrod_toggle()   - 上推杆切换")
    print("  控制通道: 12开/13关 = 推出, 13开/12关 = 收回")
    
    print("\n【下推杆控制功能】")
    print("✓ lower_pushrod_extend()   - 下推杆推出")
    print("✓ lower_pushrod_retract()  - 下推杆收回")
    print("✓ lower_pushrod_toggle()   - 下推杆切换")
    print("  控制通道: 10开/11关 = 推出, 11开/10关 = 收回")
    
    print("\n【旋涂仪推杆控制功能】")
    print("✓ spin_coater_pushrod_extend()   - 旋涂仪推杆推出")
    print("✓ spin_coater_pushrod_retract()  - 旋涂仪推杆收回")
    print("✓ spin_coater_pushrod_toggle()   - 旋涂仪推杆切换")
    print("  控制通道: 14开/15关 = 推出, 15开/14关 = 收回")
    
    print("\n【继电器指令示例】")
    print(f"通道12开启: {StringProtocol.relay_on(12)}")
    print(f"通道13关闭: {StringProtocol.relay_off(13)}")
    print(f"通道10开启: {StringProtocol.relay_on(10)}")
    print(f"通道11关闭: {StringProtocol.relay_off(11)}")
    print(f"通道14开启: {StringProtocol.relay_on(14)}")
    print(f"通道15关闭: {StringProtocol.relay_off(15)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

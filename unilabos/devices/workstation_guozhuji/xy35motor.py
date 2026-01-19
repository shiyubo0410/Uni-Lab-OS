"""
XY35 步进电机 RS485 驱动
通讯协议：Modbus RTU
波特率：115200
数据位：8
停止位：1
奇偶校验：无
"""

from serial import Serial
import struct
import time
from enum import Enum
from typing import Optional
from serial.serialutil import SerialException
import serial.tools.list_ports
from dataclasses import dataclass
from threading import Lock


class XY35MotorConnectionError(Exception):
    """XY35电机连接异常"""
    pass


class MotorStatus(Enum):
    """电机状态"""
    STANDBY = 0x0000      # 待机中或到达位置
    RUNNING = 0x0001      # 正在运行
    COLLISION_STOP = 0x0002  # 碰撞停
    FORWARD_PHOTO_STOP = 0x0003  # 正光电停
    REVERSE_PHOTO_STOP = 0x0004  # 反光电停


class XY35Motor:
    """XY35步进电机驱动"""
    
    # Modbus寄存器地址
    REG_STATUS = 0x00           # 电机状态
    REG_ACTUAL_STEP_HIGH = 0x01 # 实际步数高位
    REG_ACTUAL_STEP_LOW = 0x02  # 实际步数低位
    REG_ACTUAL_SPEED = 0x03     # 实际速度(rpm)
    REG_EMERGENCY_STOP = 0x04   # 急停指令
    REG_CURRENT = 0x05          # 电流(mA)
    REG_ENABLE = 0x06           # 失能控制(1=使能, 0=失能)
    REG_OUTPUT = 0x07           # 输出指令(PWM占空比 0-1000)
    REG_ZERO_SINGLE_CIRCLE = 0x0E  # 单圈绝对值归零
    REG_ZERO = 0x0F             # 归零指令
    
    # 位置模式寄存器
    REG_TARGET_STEP_HIGH = 0x10 # 目标步数高位
    REG_TARGET_STEP_LOW = 0x11  # 目标步数低位
    REG_RESERVED = 0x12         # 保留
    REG_SPEED = 0x13            # 速度(rpm)
    REG_ACCELERATION = 0x14     # 加速度(0-60000 rpm/s)
    REG_PRECISION = 0x15        # 精度(步数)
    
    # Modbus功能码
    FUNC_READ = 0x03            # 读保持寄存器
    FUNC_WRITE_SINGLE = 0x06    # 写单个寄存器
    FUNC_WRITE_MULTIPLE = 0x10  # 写多个寄存器
    
    def __init__(self, address: int = 1, port: str = None, baudrate: int = 9600):
        """初始化XY35电机驱动"""
        self.address = address
        self.port = port
        self.baudrate = baudrate
        
        # 🔧 初始化锁
        from threading import Lock
        self._serial_lock = Lock()
        
        # 🔧 串口对象（延迟初始化）
        # 如果 port 是字符串（如 "serial_pump"），表示通过工作站的通信设备提供
        # 如果 port 是 None，则 hardware_interface 稍后由工作站注入
        if isinstance(port, str) and not port.startswith("COM"):
            # port 是设备ID（如 "serial_pump"），设置为属性供工作站识别
            self.hardware_interface = port  # 字符串，工作站会替换为实际串口对象
        else:
            self.hardware_interface = None
    
    @staticmethod
    def _calculate_crc16(data: bytes) -> bytes:
        """
        计算Modbus RTU CRC16校验码
        
        Args:
            data (bytes): 需要校验的数据
            
        Returns:
            bytes: CRC16校验码（低位在前）
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        
        # 返回小端格式（Modbus RTU标准）
        return struct.pack('<H', crc)
    
    def _build_read_command(self, register_addr: int, count: int = 1) -> bytes:
        """
        构建Modbus读寄存器命令(功能码 0x03)
        
        Args:
            register_addr (int): 寄存器起始地址
            count (int): 读取寄存器数量
            
        Returns:
            bytes: 完整的Modbus RTU命令
        """
        command = bytes([self.address, self.FUNC_READ]) + \
                  struct.pack('>H', register_addr) + \
                  struct.pack('>H', count)
        crc = self._calculate_crc16(command)
        return command + crc
    
    def _build_write_single_command(self, register_addr: int, value: int) -> bytes:
        """
        构建Modbus写单个寄存器命令(功能码 0x06)
        
        Args:
            register_addr (int): 寄存器地址
            value (int): 要写入的值(16位)
            
        Returns:
            bytes: 完整的Modbus RTU命令
        """
        command = bytes([self.address, self.FUNC_WRITE_SINGLE]) + \
                  struct.pack('>H', register_addr) + \
                  struct.pack('>H', value)
        crc = self._calculate_crc16(command)
        return command + crc
    
    def _build_write_multiple_command(self, register_addr: int, values: list) -> bytes:
        """
        构建Modbus写多个寄存器命令(功能码 0x10)
        
        Args:
            register_addr (int): 寄存器起始地址
            values (list): 要写入的值列表(每个值16位)
            
        Returns:
            bytes: 完整的Modbus RTU命令
        """
        count = len(values)
        byte_count = count * 2
        command = bytes([self.address, self.FUNC_WRITE_MULTIPLE]) + \
                  struct.pack('>H', register_addr) + \
                  struct.pack('>H', count) + \
                  bytes([byte_count])
        
        for value in values:
            command += struct.pack('>H', value)
        
        crc = self._calculate_crc16(command)
        return command + crc
    
    def send_command(self, command: bytes, response_length: int = 8) -> Optional[bytes]:
        """
        发送命令并接收响应（线程安全）
        
        Args:
            command (bytes): 要发送的命令
            response_length (int): 期望响应长度
            
        Returns:
            Optional[bytes]: 响应数据，失败返回None
        """
        # 检查 hardware_interface 是否是 Serial 对象
        if not hasattr(self.hardware_interface, "write"):
            raise XY35MotorConnectionError(
                f"hardware_interface未注入串口对象，当前类型: {type(self.hardware_interface)}"
            )
        
        # 使用类级别锁，确保同一时间只有一个设备在串口通信
        with self._serial_lock:
            # 清空接收缓冲区
            if hasattr(self.hardware_interface, 'reset_input_buffer'):
                self.hardware_interface.reset_input_buffer()
            
            # 发送命令
            self.hardware_interface.write(command)
            time.sleep(0.05)  # 等待设备响应
            
            # 读取响应
            response = self.hardware_interface.read(response_length)
            
            if not response:
                print(f"[地址{self.address}] ✗ 无响应")
                return None
            
            # 验证CRC
            if len(response) >= 2:
                received_crc = response[-2:]
                calculated_crc = self._calculate_crc16(response[:-2])
                if received_crc != calculated_crc:
                    print(f"[地址{self.address}] ⚠ CRC校验失败")
                    print(f"  收到: {response.hex().upper()}")
                    return None
            
            return response
    
    # ============ 1. 状态读取 ============
    
    def read_status(self) -> Optional[MotorStatus]:
        """
        读取电机状态
        
        Returns:
            MotorStatus: 电机状态枚举，失败返回None
        """
        command = self._build_read_command(self.REG_STATUS, 1)
        response = self.send_command(command, 7)
        
        if response and len(response) >= 7:
            # 响应格式: [地址][功能码][字节数][数据高位][数据低位][CRC低][CRC高]
            status_value = struct.unpack('>H', response[3:5])[0]
            try:
                status = MotorStatus(status_value)
                self._status = status
                return status
            except ValueError:
                print(f"未知状态值: {status_value}")
                return None
        
        return None
    
    def read_actual_steps(self) -> Optional[int]:
        """
        读取实际步数（32位有符号整数）
        
        Returns:
            int: 实际步数，失败返回None
        """
        command = self._build_read_command(self.REG_ACTUAL_STEP_HIGH, 2)
        response = self.send_command(command, 9)
        
        if response and len(response) >= 9:
            # 读取高16位和低16位
            high = struct.unpack('>H', response[3:5])[0]
            low = struct.unpack('>H', response[5:7])[0]
            
            # 组合成32位有符号整数
            steps = (high << 16) | low
            # 转换为有符号数
            if steps >= 0x80000000:
                steps -= 0x100000000
            
            return steps
        
        return None
    
    def read_actual_speed(self) -> Optional[int]:
        """
        读取实际速度
        
        Returns:
            int: 实际速度(rpm)，失败返回None
        """
        command = self._build_read_command(self.REG_ACTUAL_SPEED, 1)
        response = self.send_command(command, 7)
        
        if response and len(response) >= 7:
            speed = struct.unpack('>H', response[3:5])[0]
            return speed
        
        return None
    
    def read_current(self) -> Optional[int]:
        """
        读取电流
        
        Returns:
            int: 电流(mA)，失败返回None
        """
        command = self._build_read_command(self.REG_CURRENT, 1)
        response = self.send_command(command, 7)
        
        if response and len(response) >= 7:
            current = struct.unpack('>H', response[3:5])[0]
            return current
        
        return None
    
    def get_status_info(self) -> dict:
        """
        获取电机完整状态信息
        
        Returns:
            dict: 状态信息字典
        """
        info = {
            'status': None,
            'actual_steps': None,
            'actual_speed': None,
            'current': None
        }
        
        status = self.read_status()
        if status:
            info['status'] = status.name
        
        steps = self.read_actual_steps()
        if steps is not None:
            info['actual_steps'] = steps
        
        speed = self.read_actual_speed()
        if speed is not None:
            info['actual_speed'] = speed
        
        current = self.read_current()
        if current is not None:
            info['current'] = current
        
        return info
    
    # ============ 2. 基本控制 ============
    
    def enable(self) -> bool:
        """
        使能电机（电机保持力矩）
        
        Returns:
            bool: 是否成功
        """
        command = self._build_write_single_command(self.REG_ENABLE, 1)
        response = self.send_command(command)
        
        if response and response == command:
            print(f"✓ [地址{self.address}] 电机使能成功")
            return True
        
        print(f"✗ [地址{self.address}] 电机使能失败")
        return False
    
    def disable(self) -> bool:
        """
        失能电机（释放电机力矩）
        
        Returns:
            bool: 是否成功
        """
        command = self._build_write_single_command(self.REG_ENABLE, 0)
        response = self.send_command(command)
        
        if response and response == command:
            print(f"✓ [地址{self.address}] 电机失能成功")
            return True
        
        print(f"✗ [地址{self.address}] 电机失能失败")
        return False
    
    def emergency_stop(self) -> bool:
        """
        急停
        
        Returns:
            bool: 是否成功
        """
        command = self._build_write_single_command(self.REG_EMERGENCY_STOP, 1)
        response = self.send_command(command)
        
        if response:
            print("✓ 急停指令已发送")
            return True
        
        print("✗ 急停指令发送失败")
        return False
    
    def zero(self, speed: int = -200) -> bool:
        """
        归零指令（定点模式写入的值是归零速度）
        
        Args:
            speed (int): 归零速度(rpm)，正数=正向，负数=反向
                
        Returns:
            bool: 是否成功
        """
        # 确保电机已使能
        print("确保电机使能...")
        self.enable()
        time.sleep(0.3)
        
        # 将速度转换为16位值（处理负数）
        if speed < 0:
            # 负数：转换为补码
            speed_value = (speed + 0x10000) & 0xFFFF
        else:
            speed_value = speed & 0xFFFF
        
        # 使用写多个寄存器功能码 (0x10)
        command = self._build_write_multiple_command(self.REG_ZERO, [speed_value])
        response = self.send_command(command)
        
        if response:
            print(f"✓ [地址{self.address}] 归零指令已发送（速度: {speed} rpm）")
            return True
        
        print(f"✗ [地址{self.address}] 归零指令发送失败")
        return False
    
    # ============ 3. 位置模式控制 ============
    
    def move_to_position(self, steps: int, speed: int, acceleration: int = 5000, 
                        precision: int = 100) -> bool:
        """
        移动到指定位置（一次写入所有参数）
        
        Args:
            steps (int): 目标步数
            speed (int): 速度(rpm)
            acceleration (int): 加速度(rpm/s)，默认5000
            precision (int): 精度（步数），默认100
            
        Returns:
            bool: 是否设置成功
        """
        # 确保电机已使能
        current_status = self.read_status()
        if current_status != MotorStatus.RUNNING:
            print("确保电机使能...")
            self.enable()
            time.sleep(0.3)
        
        # 转换步数为32位
        if steps < 0:
            steps_u32 = steps + 0x100000000
        else:
            steps_u32 = steps
        
        # 分解为高16位和低16位
        high = (steps_u32 >> 16) & 0xFFFF
        low = steps_u32 & 0xFFFF
        
        print(f"移动到位置: {steps} 步 (速度: {speed} rpm)")
        
        # 一次性写入6个寄存器：目标步数高位、目标步数低位、保留、速度、加速度、精度
        command = self._build_write_multiple_command(
            self.REG_TARGET_STEP_HIGH, 
            [high, low, 0x0000, speed, acceleration, precision]
        )
        response = self.send_command(command)
        
        if response:
            print("✓ 运动指令已发送")
            return True
        
        print("✗ 运动指令发送失败")
        return False
    
    def move_distance(self, distance_mm: float, speed_mm_per_sec: float, 
                     acceleration: int = 5000, precision: int = 100,
                     lead: float = 4.0, steps_per_rev: int = 16384) -> bool:
        """
        根据距离移动电机（自动换算步数和速度）
        
        Args:
            distance_mm (float): 移动距离(mm)，正数=正向，负数=反向
            speed_mm_per_sec (float): 速度(mm/s)
            acceleration (int): 加速度(rpm/s)，默认5000
            precision (int): 精度（步数），默认100
            lead (float): 导程(mm/圈)，默认4.0
            steps_per_rev (int): 每圈步数，默认16384
            
        Returns:
            bool: 是否设置成功
        """
        # 确保电机已使能
        print("确保电机使能...")
        self.enable()
        time.sleep(0.3)
        
        # 计算目标步数
        steps = int((distance_mm / lead) * steps_per_rev)
        
        # 计算转速(rpm)
        rpm = int((abs(speed_mm_per_sec) / lead) * 60)
        
        # 限制最小速度
        if rpm < 1:
            rpm = 1
        
        print(f"\n========== 距离运动 ==========")
        print(f"移动距离: {distance_mm:.2f} mm")
        print(f"速度: {speed_mm_per_sec:.2f} mm/s ({rpm} rpm)")
        print(f"步数: {steps}")
        print(f"加速度: {acceleration} rpm/s")
        
        return self.move_to_position(steps, rpm, acceleration, precision)
    
    # ============ 4. 高级功能 ============
    
    def wait_until_stopped(self, timeout: float = 60.0, check_interval: float = 0.5) -> bool:
        """
        等待电机停止
        
        Args:
            timeout (float): 超时时间(秒)
            check_interval (float): 检查间隔(秒)
            
        Returns:
            bool: 是否正常停止（True）或超时（False）
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.read_status()
            
            if status == MotorStatus.STANDBY:
                print("✓ 电机已到达目标位置")
                return True
            elif status in [MotorStatus.COLLISION_STOP, 
                          MotorStatus.FORWARD_PHOTO_STOP, 
                          MotorStatus.REVERSE_PHOTO_STOP]:
                print(f"⚠ 电机异常停止: {status.name}")
                return False
            
            time.sleep(check_interval)
        
        print("✗ 等待超时")
        return False
    
    # ============ 5. 设备管理 ============
    
    def initialize(self) -> bool:
        """
        初始化电机（完整流程：检查连接 -> 使能 -> 回零）
        
        Returns:
            bool: 是否成功
        """
        print(f"\n{'='*60}")
        print(f"初始化XY35电机 (地址: {self.address})")
        print(f"{'='*60}")
        print(f"端口: {self.port}, 波特率: {self.baudrate}")
        
        # 检查硬件接口
        if not hasattr(self.hardware_interface, "write"):
            print("✗ 硬件接口未注入")
            return False
        
        if not self.hardware_interface.is_open:
            print("✗ 串口未打开")
            return False
        
        print("✓ 硬件接口连接正常")
        
        # 读取初始状态
        print("\n[1/3] 读取电机状态...")
        status = self.read_status()
        if status:
            print(f"✓ 电机状态: {status.name}")
        else:
            print("✗ 无法读取电机状态")
            return False
        
        # 使能电机
        print("\n[2/3] 使能电机...")
        if not self.enable():
            print("✗ 电机使能失败")
            return False
        time.sleep(0.5)
        
        # 执行回零
        print("\n[3/3] 执行回零操作...")
        if not self.zero(speed=-200):
            print("✗ 归零指令发送失败")
            return False
        
        print("等待归零完成...")
        if not self.wait_until_stopped(timeout=60):
            print("✗ 归零超时或失败")
            return False
        
        # 读取归零后位置
        steps = self.read_actual_steps()
        print(f"✓ 归零完成! 当前位置: {steps} 步")
        
        print(f"\n{'='*60}")
        print(f"✓ 电机初始化完成")
        print(f"{'='*60}\n")
        
        return True

    def close(self):
        """关闭串口连接"""
        # 检查是否拥有硬件接口的所有权
        if hasattr(self.hardware_interface, 'is_open') and self.hardware_interface.is_open:
            # 如果是共享串口，不要关闭
            print(f"[地址{self.address}] 硬件接口由工作站管理，不关闭")
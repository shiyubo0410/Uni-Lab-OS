from serial import Serial
import struct
import time
from enum import Enum
from typing import Optional
from serial.serialutil import SerialException
import serial.tools.list_ports
from dataclasses import dataclass
from threading import Lock

from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode


class PeristalticPumpConnectionError(Exception):
    pass


class MotorDirection(Enum):
    """电机转向"""
    FORWARD = 0x0003   # 正转（出液）
    REVERSE = 0x0004   # 反转


class PeristalticPump:
    """
    蠕动泵RS485控制类
    
    通讯协议：Modbus RTU
    波特率：9600
    数据位：8
    停止位：1
    奇偶校验：无
    """
    
    # 类级别的串口锁（所有实例共享）
    _serial_lock = Lock()

    
    def __init__(self, port: str, address: int = 1, baudrate: int = 9600,
                 hardware_interface: Optional[Serial] = None, **kwargs):
        """
        初始化蠕动泵

        Args:
            port (str): 串口号，默认 COM7
            address (int): 从机地址，默认 1
            baudrate (int): 波特率，默认 9600
        """
        self.port = port
        self.address = address
        self.baudrate = baudrate
        self._status = "Idle"
        self._direction = MotorDirection.FORWARD  # 默认正转（出液）
        self._current_speed = 0  # 当前速度

        timeout = kwargs.get("timeout", 0.2)
        if hardware_interface is not None:
            self.hardware_interface = hardware_interface
        else:
            try:
                # 真实串口直连
                self.hardware_interface = Serial(baudrate=baudrate, port=port, timeout=timeout)
            except (OSError, SerialException):
                # 端口名是通信代理设备（如 serial_pump），保留字符串供工作站代理替换
                self.hardware_interface = port
    
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
    
    def _build_command(self, function_code: int, register_addr: int, data: bytes) -> bytes:
        """
        构建Modbus RTU命令
        
        Args:
            function_code (int): 功能码（06 = 写单个寄存器）
            register_addr (int): 寄存器地址
            data (bytes): 要写入的数据
            
        Returns:
            bytes: 完整的Modbus RTU命令
        """
        # 构建命令体：地址 + 功能码 + 寄存器地址(2字节) + 数据(2字节)
        command = bytes([self.address, function_code]) + struct.pack('>H', register_addr) + data
        
        # 计算并附加CRC校验码
        crc = self._calculate_crc16(command)
        return command + crc
    
    def send_command(self, command: bytes) -> Optional[bytes]:
        """发送命令并接收响应（线程安全 + 完整验证）"""
        if not hasattr(self.hardware_interface, "write"):
            raise PeristalticPumpConnectionError(
                f"hardware_interface未注入串口对象，当前类型: {type(self.hardware_interface)}"
            )
        
        # 🔐 使用类级别锁，确保同一时间只有一个设备在串口通信
        with self._serial_lock:
            # 1. 清空接收缓冲区（避免旧数据干扰）
            if hasattr(self.hardware_interface, 'reset_input_buffer'):
                self.hardware_interface.reset_input_buffer()
            
            # 2. 发送命令
            self.hardware_interface.write(command)
            time.sleep(0.15)  # 等待设备响应
            
            # 3. 读取响应
            response = self.hardware_interface.read(8)
            
            # 4. 完整验证响应
            if not response:
                print(f"[地址{self.address}] ✗ 无响应")
                return None
            
            # 验证：Modbus写命令的响应必须与发送的命令完全一致（echo）
            if response != command:
                print(f"[地址{self.address}] ⚠ 响应不匹配")
                print(f"  发送: {command.hex().upper()}")
                print(f"  收到: {response.hex().upper()}")
                return None
            
            return response
    
    def _send_and_check(self, command: bytes, operation_name: str) -> bool:
        """
        发送命令并检查响应
        
        Args:
            command (bytes): 要发送的命令
            operation_name (str): 操作名称（用于日志）
            
        Returns:
            bool: 是否操作成功
        """
        print(f"发送命令：{operation_name}")
        print(f"命令字节：{command.hex().upper()}")
        
        response = self.send_command(command)
        
        if response:
            print(f"收到响应：{response.hex().upper()}")
            # 只要有响应就算成功
            print(f"✓ {operation_name}成功")
            return True
        else:
            print(f"✗ 未收到设备响应，请检查连接")
            return False
    
    # ============ 1. 方向控制 ============
    
    def set_direction(self, direction: MotorDirection) -> bool:
        """
        设置电机转向
        
        Args:
            direction (MotorDirection): 转向（FORWARD 正转/出液 / REVERSE 反转）
            
        Returns:
            bool: 是否设置成功
            
        Example:
            >>> pump.set_direction(MotorDirection.FORWARD)   # 正转（出液）
            >>> pump.set_direction(MotorDirection.REVERSE)   # 反转
        """
        data = struct.pack('>H', direction.value)
        command = self._build_command(0x06, 0x0001, data)
        
        direction_name = "正转（出液）" if direction == MotorDirection.FORWARD else "反转"
        success = self._send_and_check(command, f"设置转向为{direction_name}")
        
        if success:
            self._direction = direction
        
        return success
    
    def forward(self) -> bool:
        """设置电机正转（出液）"""
        return self.set_direction(MotorDirection.FORWARD)
    
    def reverse(self) -> bool:
        """设置电机反转"""
        return self.set_direction(MotorDirection.REVERSE)
    
    # ============ 2. 运行/停止控制 ============
    
    def start(self, rpm: Optional[float] = None, duration_seconds: Optional[float] = None, 
              direction: Optional[str] = "FORWARD") -> bool:
        """
        启动电机运行（支持定时运行和方向选择）
        
        Args:
            rpm (float, optional): 运行速度，单位：圈/分钟。如果为None则使用当前速度
            duration_seconds (float, optional): 运行时间，单位：秒。如果为None则持续运行
            direction (str, optional): 转向，默认为 "FORWARD"（正转/出液），可选 "REVERSE"（反转）
            
        Returns:
            bool: 是否启动成功
            
        Example:
            >>> pump.start()                                              # 以当前速度正转（出液）持续运行
            >>> pump.start(rpm=120, duration_seconds=60)                 # 以120 RPM正转（出液）运行60秒
            >>> pump.start(rpm=120, direction="REVERSE")                 # 以120 RPM反转持续运行
            >>> pump.start(duration_seconds=30, direction="REVERSE")     # 反转30秒
        """
        if rpm is not None:
            rpm = float(rpm)
        if duration_seconds is not None:
            duration_seconds = float(duration_seconds)
        
        # 解析direction参数（支持字符串或MotorDirection枚举）
        if isinstance(direction, str):
            direction = direction.upper()
            if direction == "REVERSE":
                motor_direction = MotorDirection.REVERSE
            else:
                motor_direction = MotorDirection.FORWARD
        elif isinstance(direction, MotorDirection):
            motor_direction = direction
        else:
            motor_direction = MotorDirection.FORWARD
        
        # 1. 设置方向
        direction_name = "正转（出液）" if motor_direction == MotorDirection.FORWARD else "反转"
        if not self.set_direction(motor_direction):
            print(f"✗ 设置方向失败：{direction_name}")
            return False
        
        # 2. 设置速度（如果提供了rpm参数）
        if rpm is not None:
            if not self.set_speed(rpm):
                print("✗ 设置速度失败")
                return False
            self._current_speed = rpm
        elif self._current_speed == 0:
            print("✗ 警告：当前速度为0，请先设置速度或提供rpm参数")
            return False
        
        # 3. 如果提供了运行时间，计算需要的圈数
        if duration_seconds is not None:
            # 计算圈数：圈数 = (rpm / 60) * duration_seconds
            # 即：每分钟rpm圈，转换为每秒rpm/60圈，乘以运行秒数
            rounds = (self._current_speed / 60.0) * duration_seconds
            
            print(f"定时运行模式：方向={direction_name}, 速度={self._current_speed} RPM, 时间={duration_seconds} 秒")
            print(f"计算圈数：({self._current_speed} / 60) × {duration_seconds} = {rounds:.2f} 圈")
            
            # 设置圈数（四舍五入到整数）
            rounds_int = round(rounds)
            if rounds_int < 1:
                rounds_int = 1  # 至少运行1圈
            
            if not self.set_rotation_count(rounds_int):
                print("✗ 设置圈数失败")
                return False
        else:
            print(f"持续运行模式：方向={direction_name}, 速度={self._current_speed} RPM")
        
        # 4. 启动电机
        data = struct.pack('>H', 0x0001)
        command = self._build_command(0x06, 0x0002, data)
        
        if duration_seconds is not None:
            return self._send_and_check(command, f"启动运行（{direction_name}，{duration_seconds}秒，约{rounds_int}圈）")
        else:
            return self._send_and_check(command, f"启动持续运行（{direction_name}）")
    
    def pause(self) -> bool:
        """
        暂停运行（保持当前位置）
        
        Returns:
            bool: 是否暂停成功
        """
        data = struct.pack('>H', 0x0001)
        command = self._build_command(0x06, 0x0002, data)
        return self._send_and_check(command, "暂停（保持当前位置）")
    
    def stop(self) -> bool:
        """
        停止运行（清零圈数/角度/脉冲）
        
        Returns:
            bool: 是否停止成功
        """
        data = struct.pack('>H', 0x0000)
        command = self._build_command(0x06, 0x0002, data)
        success = self._send_and_check(command, "停止运行")
        if success:
            self._status = "Idle"
        return success
    
    # ============ 3. 参数设置类命令 ============
    
    def set_speed(self, rpm: float) -> bool:
        """
        设置电机运行速度（RPM）
        
        Args:
            rpm (float): 速度，单位：圈/分钟（如120表示120圈每分钟）
            
        Returns:
            bool: 是否设置成功
            
        Example:
            >>> pump.set_speed(120)   # 设置120圈每分钟
            True
        """
        rpm = float(rpm)
        speed_value = int(rpm)
        speed_bytes = struct.pack('>H', speed_value)
        command = self._build_command(0x06, 0x0004, speed_bytes)
        
        print(f"发送命令设置速度为 {rpm} 圈/分钟")
        print(f"命令字节：{command.hex().upper()}")
        
        response = self.send_command(command)
        
        if response:
            print(f"收到响应：{response.hex().upper()}")
            if response == command:
                print(f"✓ 速度设置成功：{rpm} 圈/分钟")
                self._current_speed = rpm
                return True
            else:
                print(f"✗ 设备返回异常响应")
                return False
        else:
            print("✗ 未收到设备响应，请检查连接")
            return False
    
    def set_pulse_count(self, pulse_count: int) -> bool:
        """
        设置脉冲数（定量运行）
        
        Args:
            pulse_count (int): 脉冲数（如1600表示1600脉冲）
            
        Returns:
            bool: 是否设置成功
            
        Example:
            >>> pump.set_pulse_count(1600)  # 设置1600脉冲
            True
        """
        pulse_count = int(pulse_count)
        pulse_bytes = struct.pack('>H', pulse_count)
        command = self._build_command(0x06, 0x0005, pulse_bytes)
        return self._send_and_check(command, f"设置脉冲数为 {pulse_count}")
    
    def set_rotation_count(self, rounds: int) -> bool:
        """
        设置圈数
        
        Args:
            rounds (int): 圈数（如5表示5圈）
            
        Returns:
            bool: 是否设置成功
            
        Example:
            >>> pump.set_rotation_count(5)  # 设置5圈
            True
        """
        rounds = int(rounds)
        rounds_bytes = struct.pack('>H', rounds)
        command = self._build_command(0x06, 0x0006, rounds_bytes)
        return self._send_and_check(command, f"设置圈数为 {rounds} 圈")
    
    def set_angle(self, degrees: float) -> bool:
        """
        设置旋转角度
        
        Args:
            degrees (float): 旋转角度，单位：度（如360表示360°）
            
        Returns:
            bool: 是否设置成功
            
        Example:
            >>> pump.set_angle(360)  # 设置360°
            True
        """
        degrees = float(degrees)
        angle_value = int(degrees)
        angle_bytes = struct.pack('>H', angle_value)
        command = self._build_command(0x06, 0x0007, angle_bytes)
        return self._send_and_check(command, f"设置角度为 {degrees}°")
    
    # ============ 4. 脱机使能 ============
    
    def enable_offline_mode(self) -> bool:
        """
        打开脱机使能（释放电机，电机不保持力矩）
        
        Returns:
            bool: 是否设置成功
        """
        data = struct.pack('>H', 0x0001)
        command = self._build_command(0x06, 0x0009, data)
        return self._send_and_check(command, "打开脱机使能（释放电机）")
    
    def disable_offline_mode(self) -> bool:
        """
        关闭脱机使能（电机保持力矩）
        
        Returns:
            bool: 是否设置成功
        """
        data = struct.pack('>H', 0x0000)
        command = self._build_command(0x06, 0x0009, data)
        return self._send_and_check(command, "关闭脱机使能（电机保持力矩）")
    
    # ============ 5. 高级功能 ============
    
    def run_with_volume(self, rpm: float, volume_ml: float, ml_per_rotation: float,
                       direction: Optional[str] = "FORWARD") -> bool:
        """
        根据流量运行（适用于蠕动泵）
        
        Args:
            rpm (float): 运行速度，单位：圈/分钟
            volume_ml (float): 需要泵送的体积，单位：毫升(mL)
            ml_per_rotation (float): 每圈泵送的体积，单位：毫升/圈（根据泵管规格确定）
            direction (str, optional): 转向，默认为 "FORWARD"（正转/出液），可选 "REVERSE"（反转）
            
        Returns:
            bool: 是否启动成功
            
        Example:
            >>> # 假设泵管每圈泵送2.5mL，需要泵送50mL液体，速度120 RPM，正转出液
            >>> pump.run_with_volume(rpm=120, volume_ml=50, ml_per_rotation=2.5)
            >>> # 反转吸液
            >>> pump.run_with_volume(rpm=120, volume_ml=50, ml_per_rotation=2.5, direction="REVERSE")
        """
        rpm = float(rpm)
        volume_ml = float(volume_ml)
        ml_per_rotation = float(ml_per_rotation)
        
        # 解析direction参数（支持字符串或MotorDirection枚举）
        if isinstance(direction, str):
            direction = direction.upper()
            if direction == "REVERSE":
                motor_direction = MotorDirection.REVERSE
            else:
                motor_direction = MotorDirection.FORWARD
        elif isinstance(direction, MotorDirection):
            motor_direction = direction
        else:
            motor_direction = MotorDirection.FORWARD
        
        # 计算需要的圈数
        rounds = volume_ml / ml_per_rotation
        rounds_int = round(rounds)
        
        if rounds_int < 1:
            rounds_int = 1
        
        direction_name = "正转（出液）" if motor_direction == MotorDirection.FORWARD else "反转"
        
        print(f"体积运行模式：")
        print(f"  目标体积：{volume_ml} mL")
        print(f"  每圈体积：{ml_per_rotation} mL/圈")
        print(f"  计算圈数：{volume_ml} / {ml_per_rotation} = {rounds:.2f} ≈ {rounds_int} 圈")
        print(f"  运行速度：{rpm} RPM")
        print(f"  运行方向：{direction_name}")
        
        # 设置方向
        if not self.set_direction(motor_direction):
            return False
        
        # 设置速度
        if not self.set_speed(rpm):
            return False
        
        # 设置圈数
        if not self.set_rotation_count(rounds_int):
            return False
        
        # 启动
        data = struct.pack('>H', 0x0001)
        command = self._build_command(0x06, 0x0002, data)
        return self._send_and_check(command, f"启动运行（{direction_name}，泵送{volume_ml}mL，{rounds_int}圈）")
    
    # ============ 设备管理 ============
    
    def initialize(self):
        """初始化蠕动泵"""
        if hasattr(self.hardware_interface, "is_open"):
            if not self.hardware_interface.is_open:
                self.hardware_interface.open()
            print(f"正在初始化蠕动泵...")
            print(f"端口: {self.port}, 地址: {self.address}, 波特率: {self.baudrate}")
            if self.hardware_interface.is_open:
                print("连接成功！")
                return True
            else:
                print("连接失败！")
                return False
        else:
            print("当前未注入串口对象")
            return False
    
    def close(self):
        """关闭串口连接"""
        if self.hardware_interface.is_open:
            self.hardware_interface.close()
            print("连接已关闭")
    
    @staticmethod
    def list():
        for item in serial.tools.list_ports.comports():
            yield PeristalticPumpInfo(port=item.device)


@dataclass(frozen=True, kw_only=True)
class PeristalticPumpInfo:
    port: str
    address: int = 1
    baudrate: int = 9600

    def create(self):
        return PeristalticPump(self.port, self.address, self.baudrate)


if __name__ == "__main__":
    try:
        pump = PeristalticPump(port="COM7", address=2, baudrate=9600)
        pump.initialize()

        print("\n========== 用户输入速度、时间和方向 ==========")
        rpm = float(input("请输入运行速度 (RPM)："))
        duration = float(input("请输入运行时间 (秒)："))
        direction_input = input("请输入方向 (forward/正转/出液 或 reverse/反转，默认为正转)：").strip().lower()
        
        # 解析方向输入
        if direction_input in ['reverse', '反转']:
            direction = MotorDirection.REVERSE
        else:
            direction = MotorDirection.FORWARD  # 默认正转（出液）

        direction_name = "正转（出液）" if direction == MotorDirection.FORWARD else "反转"
        print(f"\n启动蠕动泵：方向={direction_name}，速度={rpm} RPM，时间={duration} 秒")
        success = pump.start(rpm=rpm, duration_seconds=duration, direction=direction)
        if success:
            print("✓ 启动成功，正在运行...")
            time.sleep(duration + 2)  # 等待运行完成（多等2秒确保设备响应）
            pump.stop()
            print("✓ 已停止运行")
        else:
            print("✗ 启动失败，请检查设备连接和参数")

        pump.close()
    except PeristalticPumpConnectionError as e:
        print(f"错误: {e}")
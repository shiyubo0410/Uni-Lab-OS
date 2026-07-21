#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旋涂仪 Modbus RTU 指令生成工具
支持设备控制、单步/多步旋涂控制、对中控制、摆动控制
"""


class CRC16Modbus:
    """CRC16-Modbus 校验计算"""
    
    @staticmethod
    def calculate(data: bytes) -> int:
        """
        计算 Modbus CRC16 校验码
        
        Args:
            data: 字节数据
        
        Returns:
            CRC16 值（16位整数）
        """
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    @staticmethod
    def calculate_hex(hex_string: str) -> int:
        """
        从16进制字符串计算CRC16
        
        Args:
            hex_string: 16进制字符串，如 "01 03 00 10 00 01"
        
        Returns:
            CRC16 值
        """
        data = bytes.fromhex(hex_string.replace(' ', ''))
        return CRC16Modbus.calculate(data)
    
    @staticmethod
    def append_to_hex(hex_string: str) -> str:
        """
        计算CRC并附加到16进制字符串
        
        Args:
            hex_string: 原始命令，如 "01 03 00 10 00 01"
        
        Returns:
            带CRC的完整命令，如 "01 03 00 10 00 01 85 C0"
        """
        crc = CRC16Modbus.calculate_hex(hex_string)
        crc_low = crc & 0xFF
        crc_high = (crc >> 8) & 0xFF
        return f"{hex_string} {crc_low:02X} {crc_high:02X}"


class SpinCoaterCommands:
    """旋涂仪指令生成器"""
    
    # 站号
    STATION = 0x01
    
    # ==================== 设备控制命令 ====================
    
    @classmethod
    def enable_on(cls) -> str:
        """使能开启 - 置位命令"""
        return "01 05 00 10 FF 00 8D FF"
    
    @classmethod
    def enable_off(cls) -> str:
        """使能开启 - 复位命令"""
        return "01 05 00 10 00 00 CC 0F"
    
    @classmethod
    def enable_status(cls) -> str:
        """使能状态查询"""
        return "01 01 00 1F 00 01 CC 0C"
    
    @classmethod
    def vacuum_on(cls) -> str:
        """开启真空 - 置位命令"""
        return "01 05 00 32 FF 00 2D F5"
    
    @classmethod
    def vacuum_off(cls) -> str:
        """开启真空 - 复位命令"""
        return "01 05 00 32 00 00 6C 05"
    
    @classmethod
    def vacuum_status(cls) -> str:
        """真空状态查询"""
        return "01 01 60 00 00 01 E3 CA"
    
    @classmethod
    def vacuum_display(cls) -> str:
        """真空显示值读取"""
        return "01 03 00 DC 00 01 45 F0"
    
    @classmethod
    def manual_home_on(cls) -> str:
        """手动回原 - 置位命令"""
        return "01 05 00 14 FF 00 CC 3E"
    
    @classmethod
    def manual_home_off(cls) -> str:
        """手动回原 - 复位命令"""
        return "01 05 00 14 00 00 8D CE"
    
    # ==================== 单步运行命令 ====================
    
    @classmethod
    def single_step_on(cls) -> str:
        """单步启停 - 置位命令"""
        return "01 05 00 07 FF 00 3D FB"
    
    @classmethod
    def single_step_off(cls) -> str:
        """单步启停 - 复位命令"""
        return "01 05 00 07 00 00 7C 0B"
    
    @classmethod
    def single_step_status(cls) -> str:
        """单步运行状态查询"""
        return "01 01 00 01 00 01 AC 0A"
    
    @classmethod
    def read_single_step_speed(cls) -> str:
        """读取单步速度"""
        return "01 03 A0 DA 00 01 87 F1"
    
    @classmethod
    def write_single_step_speed(cls, speed: int) -> str:
        """
        设置单步速度
        
        Args:
            speed: 速度值 (10-10000)
        
        Returns:
            完整命令字符串
        """
        if not (10 <= speed <= 10000):
            raise ValueError(f"速度必须在10-10000之间，当前值: {speed}")
        
        hex_str = f"01 06 A0 DA {(speed >> 8) & 0xFF:02X} {speed & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def read_single_step_time(cls) -> str:
        """读取单步时间"""
        return "01 03 A0 DB 00 01 D6 31"
    
    @classmethod
    def write_single_step_time(cls, time_ms: int) -> str:
        """
        设置单步时间
        
        Args:
            time_ms: 时间值 (0-3000ms)
        
        Returns:
            完整命令字符串
        """
        if not (0 <= time_ms <= 3000):
            raise ValueError(f"时间必须在0-3000之间，当前值: {time_ms}")
        
        hex_str = f"01 06 A0 DB {(time_ms >> 8) & 0xFF:02X} {time_ms & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def read_single_step_acceleration(cls) -> str:
        """读取单步加速度"""
        return "01 03 A0 DC 00 01 67 F0"
    
    @classmethod
    def write_single_step_acceleration(cls, acceleration: int) -> str:
        """
        设置单步加速度
        
        Args:
            acceleration: 加速度值 (200-30000)
        
        Returns:
            完整命令字符串
        """
        if not (200 <= acceleration <= 30000):
            raise ValueError(f"加速度必须在200-30000之间，当前值: {acceleration}")
        
        hex_str = f"01 06 A0 DC {(acceleration >> 8) & 0xFF:02X} {acceleration & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def read_run_speed(cls) -> str:
        """读取运行速度"""
        return "01 03 00 7A 00 01 A5 D3"
    
    @classmethod
    def read_run_time(cls) -> str:
        """读取运行时间"""
        return "01 03 00 46 00 01 65 DF"
    
    # ==================== 多步运行命令 ====================
    
    @classmethod
    def multi_step_on(cls) -> str:
        """多步启停 - 置位命令"""
        return "01 05 00 07 FF 00 3D FB"
    
    @classmethod
    def multi_step_off(cls) -> str:
        """多步启停 - 复位命令"""
        return "01 05 00 07 00 00 7C 0B"
    
    @classmethod
    def multi_step_status(cls) -> str:
        """多步运行状态查询"""
        return "01 01 00 02 00 01 5C 0A"
    
    @classmethod
    def read_multi_step_total_time(cls) -> str:
        """读取多步总运行时间"""
        return "01 03 00 48 00 01 04 1C"
    
    @classmethod
    def read_multi_step_current_step(cls) -> str:
        """读取多步运行步骤"""
        return "01 03 00 5C 00 01 44 18"
    
    @classmethod
    def _calculate_multi_step_address(cls, step_num: int, base_address: int) -> int:
        """
        计算多步参数地址
        
        Args:
            step_num: 步骤号 (1-100)
            base_address: 基础地址
        
        Returns:
            计算后的地址
        """
        if not (1 <= step_num <= 100):
            raise ValueError(f"步骤号必须在1-100之间，当前值: {step_num}")
        return base_address + (step_num - 1) * 3
    
    @classmethod
    def write_multi_step_speed(cls, step_num: int, speed: int) -> str:
        """
        设置多步速度
        
        Args:
            step_num: 步骤号 (1-100)
            speed: 速度值 (0-10000)
        
        Returns:
            完整命令字符串
        """
        if not (0 <= speed <= 10000):
            raise ValueError(f"速度必须在0-10000之间，当前值: {speed}")
        
        address = cls._calculate_multi_step_address(step_num, 0xA0E4)
        hex_str = f"01 06 {address:04X} {(speed >> 8) & 0xFF:02X} {speed & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def write_multi_step_time(cls, step_num: int, time_ms: int) -> str:
        """
        设置多步时间
        
        Args:
            step_num: 步骤号 (1-100)
            time_ms: 时间值 (0-3000ms)
        
        Returns:
            完整命令字符串
        """
        if not (0 <= time_ms <= 3000):
            raise ValueError(f"时间必须在0-3000之间，当前值: {time_ms}")
        
        address = cls._calculate_multi_step_address(step_num, 0xA0E5)
        hex_str = f"01 06 {address:04X} {(time_ms >> 8) & 0xFF:02X} {time_ms & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def write_multi_step_acceleration(cls, step_num: int, acceleration: int) -> str:
        """
        设置多步加速度
        
        Args:
            step_num: 步骤号 (1-100)
            acceleration: 加速度值 (200-30000)
        
        Returns:
            完整命令字符串
        """
        if not (200 <= acceleration <= 30000):
            raise ValueError(f"加速度必须在200-30000之间，当前值: {acceleration}")
        
        address = cls._calculate_multi_step_address(step_num, 0xA0E6)
        hex_str = f"01 06 {address:04X} {(acceleration >> 8) & 0xFF:02X} {acceleration & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    # ==================== 对中控制命令 ====================
    
    @classmethod
    def alignment_check(cls) -> str:
        """对中检查"""
        return "01 01 00 3A 00 01 DD C7"
    
    @classmethod
    def write_alignment_speed(cls, speed: int) -> str:
        """
        设置对中速度
        
        Args:
            speed: 速度值 (100-500)
        
        Returns:
            完整命令字符串
        """
        if not (100 <= speed <= 500):
            raise ValueError(f"对中速度必须在100-500之间，当前值: {speed}")
        
        hex_str = f"01 06 A0 A0 {(speed >> 8) & 0xFF:02X} {speed & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def write_alignment_time(cls, time_ms: int) -> str:
        """
        设置对中时间
        
        Args:
            time_ms: 时间值 (1-100ms)
        
        Returns:
            完整命令字符串
        """
        if not (1 <= time_ms <= 100):
            raise ValueError(f"对中时间必须在1-100之间，当前值: {time_ms}")
        
        hex_str = f"01 06 A0 A2 {(time_ms >> 8) & 0xFF:02X} {time_ms & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    # ==================== 摆动控制命令 ====================
    
    @classmethod
    def oscillation_start(cls) -> str:
        """摆动启动"""
        return "01 01 00 37 00 01 4C 04"
    
    @classmethod
    def write_oscillation_speed(cls, speed: int) -> str:
        """
        设置摆动速度
        
        Args:
            speed: 速度值 (10-800)
        
        Returns:
            完整命令字符串
        """
        if not (10 <= speed <= 800):
            raise ValueError(f"摆动速度必须在10-800之间，当前值: {speed}")
        
        hex_str = f"01 06 A0 A4 {(speed >> 8) & 0xFF:02X} {speed & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def write_oscillation_acceleration(cls, acceleration: int) -> str:
        """
        设置摆动加速度
        
        Args:
            acceleration: 加速度值 (10-2000)
        
        Returns:
            完整命令字符串
        """
        if not (10 <= acceleration <= 2000):
            raise ValueError(f"摆动加速度必须在10-2000之间，当前值: {acceleration}")
        
        hex_str = f"01 06 A0 A6 {(acceleration >> 8) & 0xFF:02X} {acceleration & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def write_oscillation_time(cls, time_ms: int) -> str:
        """
        设置摆动时间
        
        Args:
            time_ms: 时间值 (1-100ms)
        
        Returns:
            完整命令字符串
        """
        if not (1 <= time_ms <= 100):
            raise ValueError(f"摆动时间必须在1-100之间，当前值: {time_ms}")
        
        hex_str = f"01 06 A0 A8 {(time_ms >> 8) & 0xFF:02X} {time_ms & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)
    
    @classmethod
    def write_oscillation_count(cls, count: int) -> str:
        """
        设置摆动次数
        
        Args:
            count: 次数 (1-20)
        
        Returns:
            完整命令字符串
        """
        if not (1 <= count <= 20):
            raise ValueError(f"摆动次数必须在1-20之间，当前值: {count}")
        
        hex_str = f"01 06 A0 AA {(count >> 8) & 0xFF:02X} {count & 0xFF:02X}"
        return CRC16Modbus.append_to_hex(hex_str)


if __name__ == '__main__':
    # 测试示例
    print("=" * 60)
    print("旋涂仪指令生成测试")
    print("=" * 60)
    
    print("\n【设备控制命令】")
    print(f"使能开启置位: {SpinCoaterCommands.enable_on()}")
    print(f"使能开启复位: {SpinCoaterCommands.enable_off()}")
    print(f"真空开启置位: {SpinCoaterCommands.vacuum_on()}")
    print(f"真空开启复位: {SpinCoaterCommands.vacuum_off()}")
    
    print("\n【单步运行命令】")
    print(f"单步启停置位: {SpinCoaterCommands.single_step_on()}")
    print(f"单步启停复位: {SpinCoaterCommands.single_step_off()}")
    print(f"设置单步速度5000: {SpinCoaterCommands.write_single_step_speed(5000)}")
    print(f"设置单步时间2000: {SpinCoaterCommands.write_single_step_time(2000)}")
    
    print("\n【多步运行命令】")
    print(f"设置第1步速度3000: {SpinCoaterCommands.write_multi_step_speed(1, 3000)}")
    print(f"设置第2步时间1500: {SpinCoaterCommands.write_multi_step_time(2, 1500)}")
    print(f"设置第5步加速度4000: {SpinCoaterCommands.write_multi_step_acceleration(5, 4000)}")
    
    print("\n【对中控制命令】")
    print(f"设置对中速度300: {SpinCoaterCommands.write_alignment_speed(300)}")
    print(f"设置对中时间50: {SpinCoaterCommands.write_alignment_time(50)}")
    
    print("\n【摆动控制命令】")
    print(f"设置摆动速度400: {SpinCoaterCommands.write_oscillation_speed(400)}")
    print(f"设置摆动加速度500: {SpinCoaterCommands.write_oscillation_acceleration(500)}")
    print(f"设置摆动时间30: {SpinCoaterCommands.write_oscillation_time(30)}")
    print(f"设置摆动次数5: {SpinCoaterCommands.write_oscillation_count(5)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器指令生成工具
支持MODBUS-RTU、MODBUS-TCP、科星私有协议
"""

import struct


class CRC16:
    """CRC16校验计算"""
    
    # CRC16查表法高位表
    CRC16_HI = [
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
        0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
        0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
        0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
        0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
        0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
        0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
        0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
        0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
        0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
        0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
        0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
        0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
        0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
        0x80, 0x41, 0x00, 0xC1, 0x81, 0x40
    ]
    
    # CRC16查表法低位表
    CRC16_LO = [
        0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06,
        0x07, 0xC7, 0x05, 0xC5, 0xC4, 0x04, 0xCC, 0x0C, 0x0D, 0xCD,
        0x0F, 0xCF, 0xCE, 0x0E, 0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09,
        0x08, 0xC8, 0xD8, 0x18, 0x19, 0xD9, 0x1B, 0xDB, 0xDA, 0x1A,
        0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC, 0x14, 0xD4,
        0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6, 0xD2, 0x12, 0x13, 0xD3,
        0x11, 0xD1, 0xD0, 0x10, 0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3,
        0xF2, 0x32, 0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4,
        0x3C, 0xFC, 0xFD, 0x3D, 0xFF, 0x3F, 0x3E, 0xFE, 0xFA, 0x3A,
        0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38, 0x28, 0xE8, 0xE9, 0x29,
        0xEB, 0x2B, 0x2A, 0xEA, 0xEE, 0x2E, 0x2F, 0xEF, 0x2D, 0xED,
        0xEC, 0x2C, 0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
        0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0, 0xA0, 0x60,
        0x61, 0xA1, 0x63, 0xA3, 0xA2, 0x62, 0x66, 0xA6, 0xA7, 0x67,
        0xA5, 0x65, 0x64, 0xA4, 0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F,
        0x6E, 0xAE, 0xAA, 0x6A, 0x6B, 0xAB, 0x69, 0xA9, 0xA8, 0x68,
        0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA, 0xBE, 0x7E,
        0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C, 0xB4, 0x74, 0x75, 0xB5,
        0x77, 0xB7, 0xB6, 0x76, 0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71,
        0x70, 0xB0, 0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92,
        0x96, 0x56, 0x57, 0x97, 0x55, 0x95, 0x94, 0x54, 0x9C, 0x5C,
        0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E, 0x5A, 0x9A, 0x9B, 0x5B,
        0x99, 0x59, 0x58, 0x98, 0x88, 0x48, 0x49, 0x89, 0x4B, 0x8B,
        0x8A, 0x4A, 0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
        0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86, 0x82, 0x42,
        0x43, 0x83, 0x41, 0x81, 0x80, 0x40
    ]
    
    @classmethod
    def calculate(cls, data: bytes) -> int:
        """计算CRC16校验值"""
        crc_hi = 0xFF
        crc_lo = 0xFF
        for byte in data:
            index = crc_lo ^ byte
            crc_lo = crc_hi ^ cls.CRC16_HI[index]
            crc_hi = cls.CRC16_LO[index]
        return (crc_hi << 8) | crc_lo
    
    @classmethod
    def calculate_hex(cls, hex_string: str) -> int:
        """从16进制字符串计算CRC16"""
        data = bytes.fromhex(hex_string.replace(' ', ''))
        return cls.calculate(data)
    
    @classmethod
    def append_to_hex(cls, hex_string: str) -> str:
        """计算CRC并附加到16进制字符串"""
        crc = cls.calculate_hex(hex_string)
        return hex_string + f"{crc:04X}"


class ModbusRTU:
    """MODBUS-RTU指令生成"""
    
    DEVICE_ADDRESS = 0x01
    
    @classmethod
    def relay_on(cls, channel: int) -> str:
        """生成继电器开启指令 (05功能码)"""
        addr = (channel - 1) & 0xFFFF
        data = f"{cls.DEVICE_ADDRESS:02X}05{addr:04X}FF00"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def relay_off(cls, channel: int) -> str:
        """生成继电器关闭指令 (05功能码)"""
        addr = (channel - 1) & 0xFFFF
        data = f"{cls.DEVICE_ADDRESS:02X}05{addr:04X}0000"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def relay_pulse_fixed(cls, channel: int) -> str:
        """生成固定2S脉冲指令 (05功能码)"""
        addr = 0x3000 + (channel - 1)
        data = f"{cls.DEVICE_ADDRESS:02X}05{addr:04X}FF00"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def relay_toggle(cls, channel: int) -> str:
        """生成继电器反转指令 (05功能码)"""
        addr = 0x5000 + (channel - 1)
        data = f"{cls.DEVICE_ADDRESS:02X}05{addr:04X}FF00"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def relay_on_06(cls, channel: int) -> str:
        """生成继电器开启指令 (06功能码)"""
        addr = 0x1000 + (channel - 1)
        data = f"{cls.DEVICE_ADDRESS:02X}06{addr:04X}0001"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def relay_off_06(cls, channel: int) -> str:
        """生成继电器关闭指令 (06功能码)"""
        addr = 0x1000 + (channel - 1)
        data = f"{cls.DEVICE_ADDRESS:02X}06{addr:04X}0000"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def relay_pulse_variable(cls, channel: int, time_ms: int) -> str:
        """生成可变时间脉冲指令 (06功能码)"""
        addr = (channel - 1) & 0xFFFF
        time_val = time_ms & 0xFFFF
        data = f"{cls.DEVICE_ADDRESS:02X}06{addr:04X}{time_val:04X}"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def read_relay_status(cls, count: int = 8) -> str:
        """读取继电器状态 (01功能码)"""
        data = f"{cls.DEVICE_ADDRESS:02X}010000{count:04X}"
        return CRC16.append_to_hex(data)
    
    @classmethod
    def read_switch_status(cls, count: int = 8) -> str:
        """读取开关量状态 (02功能码)"""
        data = f"{cls.DEVICE_ADDRESS:02X}020000{count:04X}"
        return CRC16.append_to_hex(data)


class ModbusTCP:
    """MODBUS-TCP指令生成"""
    
    DEVICE_ADDRESS = 0x01
    HEADER = "000000000006"
    
    @classmethod
    def relay_on(cls, channel: int) -> str:
        """生成继电器开启指令"""
        addr = (channel - 1) & 0xFFFF
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}05{addr:04X}FF00"
    
    @classmethod
    def relay_off(cls, channel: int) -> str:
        """生成继电器关闭指令"""
        addr = (channel - 1) & 0xFFFF
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}05{addr:04X}0000"
    
    @classmethod
    def relay_pulse_fixed(cls, channel: int) -> str:
        """生成固定2S脉冲指令"""
        addr = 0x3000 + (channel - 1)
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}05{addr:04X}FF00"
    
    @classmethod
    def relay_toggle(cls, channel: int) -> str:
        """生成继电器反转指令"""
        addr = 0x5000 + (channel - 1)
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}05{addr:04X}FF00"
    
    @classmethod
    def relay_on_06(cls, channel: int) -> str:
        """生成继电器开启指令 (06功能码)"""
        addr = 0x1000 + (channel - 1)
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}06{addr:04X}0001"
    
    @classmethod
    def relay_off_06(cls, channel: int) -> str:
        """生成继电器关闭指令 (06功能码)"""
        addr = 0x1000 + (channel - 1)
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}06{addr:04X}0000"
    
    @classmethod
    def relay_pulse_variable(cls, channel: int, time_ms: int) -> str:
        """生成可变时间脉冲指令"""
        addr = (channel - 1) & 0xFFFF
        time_val = time_ms & 0xFFFF
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}06{addr:04X}{time_val:04X}"
    
    @classmethod
    def read_relay_status(cls, count: int = 8) -> str:
        """读取继电器状态"""
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}010000{count:04X}"
    
    @classmethod
    def read_switch_status(cls, count: int = 8) -> str:
        """读取开关量状态"""
        return f"{cls.HEADER}{cls.DEVICE_ADDRESS:02X}020000{count:04X}"


class KexingProtocol:
    """科星私有协议指令生成"""
    
    FRAME_HEAD = "CCDD"
    FRAME_END = "DDCC"
    DEVICE_ADDRESS = "01"
    
    # 固定指令
    READ_RELAY_STATUS = "CCDD B301 0000 0DBE7C"
    READ_SWITCH_STATUS = "CCDD C301 0000 0DCE9C"
    READ_ENHANCED_STATUS = "CCDD B201 0000 0DC080"
    READ_ANALOG = "CCDD D001 0000 0DCCDD"
    
    @classmethod
    def _calculate_checksum(cls, data: str) -> str:
        """计算科星协议校验码"""
        # 移除空格
        data = data.replace(' ', '')
        # 计算所有字节的和
        total = 0
        for i in range(0, len(data), 2):
            total += int(data[i:i+2], 16)
        # 取低8位
        ch = total & 0xFF
        cl = (ch + ch) & 0xFF
        return f"{ch:02X}{cl:02X}"
    
    @classmethod
    def relay_control(cls, channels_on: list, channels_off: list, channels_keep: list = None) -> str:
        """
        生成继电器控制指令 (A3功能码)
        
        Args:
            channels_on: 要导通的通道列表 [1, 2, 3]
            channels_off: 要断开的通道列表 [4, 5]
            channels_keep: 保持不变的通道列表 [6, 7]
        """
        # 初始化控制位和使能位 (6字节 = 48路)
        control = [0] * 6
        enable = [0] * 6
        
        # 设置导通通道
        for ch in channels_on:
            byte_idx = (ch - 1) // 8
            bit_idx = (ch - 1) % 8
            control[byte_idx] |= (1 << bit_idx)
            enable[byte_idx] |= (1 << bit_idx)
        
        # 设置断开通道
        for ch in channels_off:
            byte_idx = (ch - 1) // 8
            bit_idx = (ch - 1) % 8
            control[byte_idx] &= ~(1 << bit_idx)
            enable[byte_idx] |= (1 << bit_idx)
        
        # 设置保持不变通道
        if channels_keep:
            for ch in channels_keep:
                byte_idx = (ch - 1) // 8
                bit_idx = (ch - 1) % 8
                enable[byte_idx] &= ~(1 << bit_idx)
        
        # 构建指令
        ctrl_str = ''.join([f"{c:02X}" for c in reversed(control)])
        enbl_str = ''.join([f"{e:02X}" for e in reversed(enable)])
        
        data = f"A3{cls.DEVICE_ADDRESS}{ctrl_str}{enbl_str}0000"
        checksum = cls._calculate_checksum(data)
        
        return f"{cls.FRAME_HEAD}{data}{checksum}{cls.FRAME_END}"
    
    @classmethod
    def relay_on(cls, channel: int) -> str:
        """单路继电器开启"""
        return cls.relay_control([channel], [])
    
    @classmethod
    def relay_off(cls, channel: int) -> str:
        """单路继电器关闭"""
        return cls.relay_control([], [channel])


class StringProtocol:
    """字符串协议指令生成"""
    
    @staticmethod
    def relay_control(channel: int, action: str, delay: int = 0, res: str = "123") -> str:
        """
        生成继电器控制指令
        
        Args:
            channel: 通道号 (1-99)
            action: 动作类型 ("on"/"off"/"pulse"/"delay")
            delay: 延迟/脉冲时间(秒)
            res: 自定义返回标识
        """
        subtype_map = {
            "on": "1",
            "off": "1",
            "pulse": "2",
            "delay": "3"
        }
        
        state_map = {
            "on": "1",
            "off": "0",
            "pulse": "1",
            "delay": "1"
        }
        
        subtype = subtype_map.get(action, "1")
        state = state_map.get(action, "0")
        delay_str = f"{delay:04d}"
        
        return f'{{"A{channel:02d}":{subtype}{state}{delay_str},"res":"{res}"}}'
    
    @staticmethod
    def relay_on(channel: int, res: str = "123") -> str:
        """继电器开启"""
        return StringProtocol.relay_control(channel, "on", 0, res)
    
    @staticmethod
    def relay_off(channel: int, res: str = "123") -> str:
        """继电器关闭"""
        return StringProtocol.relay_control(channel, "off", 0, res)
    
    @staticmethod
    def relay_pulse(channel: int, seconds: int, res: str = "123") -> str:
        """继电器脉冲输出"""
        return StringProtocol.relay_control(channel, "pulse", seconds, res)
    
    @staticmethod
    def read_status(res: str = "12345") -> str:
        """读取状态"""
        return f'{{"readall","res":"{res}"}}'
    
    @staticmethod
    def rs485_forward_string(port: int, data: str) -> str:
        """RS485字符串转发"""
        return f'{{"rs485{port}s":"{data}"}}'
    
    @staticmethod
    def rs485_forward_hex(port: int, hex_data: str) -> str:
        """RS485十六进制转发"""
        return f'{{"rs485{port}h":"{hex_data}"}}'


def print_all_commands(channel: int = 1):
    """打印某通道的所有控制指令"""
    print(f"=== 第{channel}路继电器控制指令 ===\n")
    
    print("【MODBUS-RTU】")
    print(f"  开(05):  {ModbusRTU.relay_on(channel)}")
    print(f"  关(05):  {ModbusRTU.relay_off(channel)}")
    print(f"  点动2S:  {ModbusRTU.relay_pulse_fixed(channel)}")
    print(f"  反转:    {ModbusRTU.relay_toggle(channel)}")
    print(f"  开(06):  {ModbusRTU.relay_on_06(channel)}")
    print(f"  关(06):  {ModbusRTU.relay_off_06(channel)}")
    print(f"  脉冲1S:  {ModbusRTU.relay_pulse_variable(channel, 1000)}")
    
    print("\n【MODBUS-TCP】")
    print(f"  开(05):  {ModbusTCP.relay_on(channel)}")
    print(f"  关(05):  {ModbusTCP.relay_off(channel)}")
    print(f"  点动2S:  {ModbusTCP.relay_pulse_fixed(channel)}")
    print(f"  反转:    {ModbusTCP.relay_toggle(channel)}")
    
    print("\n【科星私有协议】")
    print(f"  开:      {KexingProtocol.relay_on(channel)}")
    print(f"  关:      {KexingProtocol.relay_off(channel)}")
    
    print("\n【字符串协议】")
    print(f"  开:      {StringProtocol.relay_on(channel)}")
    print(f"  关:      {StringProtocol.relay_off(channel)}")
    print(f"  脉冲2S:  {StringProtocol.relay_pulse(channel, 2)}")


if __name__ == "__main__":
    # 示例: 打印第1路的所有控制指令
    print_all_commands(1)
    
    print("\n" + "="*50)
    print("\n【读取状态指令】")
    print(f"MODBUS-RTU 读继电器: {ModbusRTU.read_relay_status(8)}")
    print(f"MODBUS-RTU 读开关量: {ModbusRTU.read_switch_status(8)}")
    print(f"科星协议 读继电器:   {KexingProtocol.READ_RELAY_STATUS}")
    print(f"科星协议 读开关量:   {KexingProtocol.READ_SWITCH_STATUS}")
    print(f"字符串协议 读状态:   {StringProtocol.read_status()}")
    
    print("\n【CRC校验示例】")
    test_data = "01050000FF00"
    crc = CRC16.calculate_hex(test_data)
    print(f"数据: {test_data}")
    print(f"CRC:  {crc:04X}")
    print(f"完整: {CRC16.append_to_hex(test_data)}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器控制示例
"""

from relay_utils import ModbusRTU, ModbusTCP, KexingProtocol, StringProtocol, CRC16


def example_modbus_rtu():
    """MODBUS-RTU协议示例"""
    print("=" * 50)
    print("MODBUS-RTU 协议示例")
    print("=" * 50)
    
    # 控制第1路继电器
    print("\n【控制第1路继电器】")
    print(f"开启:  {ModbusRTU.relay_on(1)}")
    print(f"关闭:  {ModbusRTU.relay_off(1)}")
    print(f"点动:  {ModbusRTU.relay_pulse_fixed(1)}")
    print(f"反转:  {ModbusRTU.relay_toggle(1)}")
    
    # 控制第8路继电器
    print("\n【控制第8路继电器】")
    print(f"开启:  {ModbusRTU.relay_on(8)}")
    print(f"关闭:  {ModbusRTU.relay_off(8)}")
    
    # 脉冲控制（自定义时间）
    print("\n【脉冲控制（自定义时间）】")
    print(f"第3路脉冲500ms:  {ModbusRTU.relay_pulse_variable(3, 500)}")
    print(f"第5路脉冲5000ms: {ModbusRTU.relay_pulse_variable(5, 5000)}")
    
    # 读取状态
    print("\n【读取状态】")
    print(f"读取8路继电器:  {ModbusRTU.read_relay_status(8)}")
    print(f"读取16路开关量: {ModbusRTU.read_switch_status(16)}")


def example_modbus_tcp():
    """MODBUS-TCP协议示例"""
    print("\n" + "=" * 50)
    print("MODBUS-TCP 协议示例")
    print("=" * 50)
    
    # 控制第1路继电器
    print("\n【控制第1路继电器】")
    print(f"开启:  {ModbusTCP.relay_on(1)}")
    print(f"关闭:  {ModbusTCP.relay_off(1)}")
    print(f"点动:  {ModbusTCP.relay_pulse_fixed(1)}")
    
    # 控制多路
    print("\n【控制多路继电器】")
    for i in range(1, 5):
        print(f"第{i}路开: {ModbusTCP.relay_on(i)}")


def example_kexing():
    """科星私有协议示例"""
    print("\n" + "=" * 50)
    print("科星私有协议示例")
    print("=" * 50)
    
    # 单路控制
    print("\n【单路控制】")
    print(f"第1路开: {KexingProtocol.relay_on(1)}")
    print(f"第1路关: {KexingProtocol.relay_off(1)}")
    print(f"第8路开: {KexingProtocol.relay_on(8)}")
    
    # 多路控制
    print("\n【多路控制】")
    print(f"1-4路开, 5-8路关: {KexingProtocol.relay_control([1,2,3,4], [5,6,7,8])}")
    print(f"仅第1路开(其他不变): {KexingProtocol.relay_control([1], [], [2,3,4,5,6,7,8])}")
    
    # 固定指令
    print("\n【固定读取指令】")
    print(f"读取继电器状态:  {KexingProtocol.READ_RELAY_STATUS}")
    print(f"读取开关量状态:  {KexingProtocol.READ_SWITCH_STATUS}")
    print(f"读取增强状态:    {KexingProtocol.READ_ENHANCED_STATUS}")
    print(f"读取模拟量:      {KexingProtocol.READ_ANALOG}")


def example_string():
    """字符串协议示例"""
    print("\n" + "=" * 50)
    print("字符串协议示例")
    print("=" * 50)
    
    # 继电器控制
    print("\n【继电器控制】")
    print(f"第1路开:     {StringProtocol.relay_on(1)}")
    print(f"第1路关:     {StringProtocol.relay_off(1)}")
    print(f"第2路脉冲5S: {StringProtocol.relay_pulse(2, 5)}")
    print(f"第3路延迟10S:{StringProtocol.relay_control(3, 'delay', 10)}")
    
    # 读取状态
    print("\n【读取状态】")
    print(f"读取所有: {StringProtocol.read_status()}")
    print(f"自定义res: {StringProtocol.read_status('myid123')}")
    
    # RS485转发
    print("\n【RS485转发】")
    print(f"字符串转发: {StringProtocol.rs485_forward_string(1, 'Hello')}")
    print(f"16进制转发: {StringProtocol.rs485_forward_hex(1, '010300000001C658')}")


def example_crc():
    """CRC校验示例"""
    print("\n" + "=" * 50)
    print("CRC校验示例")
    print("=" * 50)
    
    # 计算CRC
    test_data = [
        "01050000FF00",  # 第1路开
        "010500000000",  # 第1路关
        "01050001FF00",  # 第2路开
        "010100000008",  # 读取继电器状态
    ]
    
    print("\n【CRC计算】")
    for data in test_data:
        crc = CRC16.calculate_hex(data)
        full = CRC16.append_to_hex(data)
        print(f"数据: {data} -> CRC: {crc:04X} -> 完整: {full}")


def example_batch_control():
    """批量控制示例"""
    print("\n" + "=" * 50)
    print("批量控制示例")
    print("=" * 50)
    
    print("\n【批量生成1-8路控制指令】")
    print("\nMODBUS-RTU:")
    for i in range(1, 9):
        print(f"  第{i}路开: {ModbusRTU.relay_on(i)}")
    
    print("\n科星协议:")
    for i in range(1, 9):
        print(f"  第{i}路开: {KexingProtocol.relay_on(i)}")


if __name__ == "__main__":
    # 运行所有示例
    example_modbus_rtu()
    example_modbus_tcp()
    example_kexing()
    example_string()
    example_crc()
    example_batch_control()
    
    print("\n" + "=" * 50)
    print("示例运行完成!")
    print("=" * 50)

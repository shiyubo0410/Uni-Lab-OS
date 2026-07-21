#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旋涂仪控制示例
"""

from xuantu_utils import SpinCoaterCommands, CRC16Modbus


def example_device_control():
    """设备控制示例"""
    print("=" * 60)
    print("设备控制示例")
    print("=" * 60)
    
    # 使能控制
    print("\n【使能控制】")
    print(f"使能开启置位: {SpinCoaterCommands.enable_on()}")
    print(f"使能开启复位: {SpinCoaterCommands.enable_off()}")
    print(f"使能状态查询: {SpinCoaterCommands.enable_status()}")
    
    # 真空控制
    print("\n【真空控制】")
    print(f"开启真空置位: {SpinCoaterCommands.vacuum_on()}")
    print(f"开启真空复位: {SpinCoaterCommands.vacuum_off()}")
    print(f"真空状态查询: {SpinCoaterCommands.vacuum_status()}")
    print(f"真空显示值:   {SpinCoaterCommands.vacuum_display()}")
    
    # 手动回原
    print("\n【手动回原】")
    print(f"手动回原置位: {SpinCoaterCommands.manual_home_on()}")
    print(f"手动回原复位: {SpinCoaterCommands.manual_home_off()}")


def example_single_step():
    """单步运行示例"""
    print("\n" + "=" * 60)
    print("单步运行示例")
    print("=" * 60)
    
    # 单步启停
    print("\n【单步启停】")
    print(f"单步启停置位: {SpinCoaterCommands.single_step_on()}")
    print(f"单步启停复位: {SpinCoaterCommands.single_step_off()}")
    print(f"单步运行状态: {SpinCoaterCommands.single_step_status()}")
    
    # 参数设置
    print("\n【单步参数设置】")
    print(f"读取单步速度: {SpinCoaterCommands.read_single_step_speed()}")
    print(f"设置单步速度5000: {SpinCoaterCommands.write_single_step_speed(5000)}")
    print(f"设置单步速度3000: {SpinCoaterCommands.write_single_step_speed(3000)}")
    
    print(f"读取单步时间: {SpinCoaterCommands.read_single_step_time()}")
    print(f"设置单步时间2000: {SpinCoaterCommands.write_single_step_time(2000)}")
    print(f"设置单步时间1500: {SpinCoaterCommands.write_single_step_time(1500)}")
    
    print(f"读取单步加速度: {SpinCoaterCommands.read_single_step_acceleration()}")
    print(f"设置单步加速度5000: {SpinCoaterCommands.write_single_step_acceleration(5000)}")
    print(f"设置单步加速度4000: {SpinCoaterCommands.write_single_step_acceleration(4000)}")
    
    # 运行状态
    print("\n【运行状态读取】")
    print(f"读取运行速度: {SpinCoaterCommands.read_run_speed()}")
    print(f"读取运行时间: {SpinCoaterCommands.read_run_time()}")


def example_multi_step():
    """多步运行示例"""
    print("\n" + "=" * 60)
    print("多步运行示例")
    print("=" * 60)
    
    # 多步启停
    print("\n【多步启停】")
    print(f"多步启停置位: {SpinCoaterCommands.multi_step_on()}")
    print(f"多步启停复位: {SpinCoaterCommands.multi_step_off()}")
    print(f"多步运行状态: {SpinCoaterCommands.multi_step_status()}")
    print(f"多步总运行时间: {SpinCoaterCommands.read_multi_step_total_time()}")
    print(f"多步运行步骤: {SpinCoaterCommands.read_multi_step_current_step()}")
    
    # 多步参数设置
    print("\n【多步参数设置】")
    print("第1步参数:")
    print(f"  速度3000: {SpinCoaterCommands.write_multi_step_speed(1, 3000)}")
    print(f"  时间1500: {SpinCoaterCommands.write_multi_step_time(1, 1500)}")
    print(f"  加速度4000: {SpinCoaterCommands.write_multi_step_acceleration(1, 4000)}")
    
    print("第2步参数:")
    print(f"  速度5000: {SpinCoaterCommands.write_multi_step_speed(2, 5000)}")
    print(f"  时间1000: {SpinCoaterCommands.write_multi_step_time(2, 1000)}")
    print(f"  加速度6000: {SpinCoaterCommands.write_multi_step_acceleration(2, 6000)}")
    
    print("第5步参数:")
    print(f"  速度4000: {SpinCoaterCommands.write_multi_step_speed(5, 4000)}")
    print(f"  时间2000: {SpinCoaterCommands.write_multi_step_time(5, 2000)}")


def example_alignment():
    """对中控制示例"""
    print("\n" + "=" * 60)
    print("对中控制示例")
    print("=" * 60)
    
    print("\n【对中控制】")
    print(f"对中检查: {SpinCoaterCommands.alignment_check()}")
    print(f"设置对中速度300: {SpinCoaterCommands.write_alignment_speed(300)}")
    print(f"设置对中速度200: {SpinCoaterCommands.write_alignment_speed(200)}")
    print(f"设置对中时间50: {SpinCoaterCommands.write_alignment_time(50)}")
    print(f"设置对中时间80: {SpinCoaterCommands.write_alignment_time(80)}")


def example_oscillation():
    """摆动控制示例"""
    print("\n" + "=" * 60)
    print("摆动控制示例")
    print("=" * 60)
    
    print("\n【摆动控制】")
    print(f"摆动启动: {SpinCoaterCommands.oscillation_start()}")
    print(f"设置摆动速度400: {SpinCoaterCommands.write_oscillation_speed(400)}")
    print(f"设置摆动速度600: {SpinCoaterCommands.write_oscillation_speed(600)}")
    print(f"设置摆动加速度500: {SpinCoaterCommands.write_oscillation_acceleration(500)}")
    print(f"设置摆动加速度1000: {SpinCoaterCommands.write_oscillation_acceleration(1000)}")
    print(f"设置摆动时间30: {SpinCoaterCommands.write_oscillation_time(30)}")
    print(f"设置摆动时间50: {SpinCoaterCommands.write_oscillation_time(50)}")
    print(f"设置摆动次数5: {SpinCoaterCommands.write_oscillation_count(5)}")
    print(f"设置摆动次数10: {SpinCoaterCommands.write_oscillation_count(10)}")


def example_single_step_process():
    """单步旋涂完整流程示例"""
    print("\n" + "=" * 60)
    print("单步旋涂完整流程示例")
    print("=" * 60)
    
    print("\n【步骤1】连接设备（9600→19200）")
    print("  - 使用9600波特率打开串口")
    print("  - 确认连接成功后切换到19200波特率")
    
    print("\n【步骤2】使能设备")
    print(f"  发送: {SpinCoaterCommands.enable_on()}")
    print(f"  等待200ms")
    print(f"  发送: {SpinCoaterCommands.enable_off()}")
    
    print("\n【步骤3】开启真空")
    print(f"  发送: {SpinCoaterCommands.vacuum_on()}")
    print(f"  等待200ms")
    print(f"  发送: {SpinCoaterCommands.vacuum_off()}")
    
    print("\n【步骤4】设置旋涂参数")
    print(f"  速度5000: {SpinCoaterCommands.write_single_step_speed(5000)}")
    print(f"  时间3000ms: {SpinCoaterCommands.write_single_step_time(3000)}")
    print(f"  加速度5000: {SpinCoaterCommands.write_single_step_acceleration(5000)}")
    
    print("\n【步骤5】启动旋涂")
    print(f"  发送: {SpinCoaterCommands.single_step_on()}")
    print(f"  等待200ms")
    print(f"  发送: {SpinCoaterCommands.single_step_off()}")
    
    print("\n【步骤6】监控运行状态")
    print(f"  查询状态: {SpinCoaterCommands.single_step_status()}")
    print(f"  读取速度: {SpinCoaterCommands.read_run_speed()}")
    print(f"  读取时间: {SpinCoaterCommands.read_run_time()}")
    
    print("\n【步骤7】等待完成")
    print("  循环查询运行状态直到停止")


def example_multi_step_process():
    """多步旋涂完整流程示例"""
    print("\n" + "=" * 60)
    print("多步旋涂完整流程示例")
    print("=" * 60)
    
    print("\n【步骤1】连接设备")
    print("  - 使用9600波特率打开串口")
    print("  - 确认连接成功后切换到19200波特率")
    
    print("\n【步骤2】使能设备")
    print(f"  发送: {SpinCoaterCommands.enable_on()} → {SpinCoaterCommands.enable_off()}")
    
    print("\n【步骤3】开启真空")
    print(f"  发送: {SpinCoaterCommands.vacuum_on()} → {SpinCoaterCommands.vacuum_off()}")
    
    print("\n【步骤4】设置多步参数（设置3步）")
    print("  第1步:")
    print(f"    速度3000: {SpinCoaterCommands.write_multi_step_speed(1, 3000)}")
    print(f"    时间2000: {SpinCoaterCommands.write_multi_step_time(1, 2000)}")
    print(f"    加速度4000: {SpinCoaterCommands.write_multi_step_acceleration(1, 4000)}")
    
    print("  第2步:")
    print(f"    速度5000: {SpinCoaterCommands.write_multi_step_speed(2, 5000)}")
    print(f"    时间1500: {SpinCoaterCommands.write_multi_step_time(2, 1500)}")
    print(f"    加速度6000: {SpinCoaterCommands.write_multi_step_acceleration(2, 6000)}")
    
    print("  第3步:")
    print(f"    速度4000: {SpinCoaterCommands.write_multi_step_speed(3, 4000)}")
    print(f"    时间1000: {SpinCoaterCommands.write_multi_step_time(3, 1000)}")
    print(f"    加速度5000: {SpinCoaterCommands.write_multi_step_acceleration(3, 5000)}")
    
    print("\n【步骤5】启动多步旋涂")
    print(f"  发送: {SpinCoaterCommands.multi_step_on()} → {SpinCoaterCommands.multi_step_off()}")
    
    print("\n【步骤6】监控运行")
    print(f"  查询状态: {SpinCoaterCommands.multi_step_status()}")
    print(f"  查询步骤: {SpinCoaterCommands.read_multi_step_current_step()}")
    print(f"  查询时间: {SpinCoaterCommands.read_multi_step_total_time()}")


def example_crc_calculation():
    """CRC校验计算示例"""
    print("\n" + "=" * 60)
    print("CRC校验计算示例")
    print("=" * 60)
    
    # 计算CRC
    print("\n【CRC计算】")
    hex_str = "01 06 A0 DA 13 88"
    crc = CRC16Modbus.calculate_hex(hex_str)
    crc_low = crc & 0xFF
    crc_high = (crc >> 8) & 0xFF
    print(f"原始数据: {hex_str}")
    print(f"CRC值: {crc:04X} (低字节: {crc_low:02X}, 高字节: {crc_high:02X})")
    print(f"完整命令: {CRC16Modbus.append_to_hex(hex_str)}")
    
    # 更多示例
    print("\n【更多CRC示例】")
    examples = [
        "01 06 A0 DB 07 D0",
        "01 06 A0 DC 13 88",
        "01 06 A0 A0 01 2C"
    ]
    for ex in examples:
        print(f"{ex} → {CRC16Modbus.append_to_hex(ex)}")


if __name__ == '__main__':
    print("=" * 60)
    print("旋涂仪控制示例程序")
    print("=" * 60)
    
    # 运行所有示例
    example_device_control()
    example_single_step()
    example_multi_step()
    example_alignment()
    example_oscillation()
    example_single_step_process()
    example_multi_step_process()
    example_crc_calculation()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)

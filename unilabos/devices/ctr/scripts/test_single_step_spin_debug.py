import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spin_coater_controller import SpinCoaterController
import time

def test_single_step_spin_debug():
    """
    测试单步旋涂操作（带详细调试信息）
    步骤：使能开 -> 真空开 -> 旋涂开
    """
    
    print("=" * 60)
    print("单步旋涂测试程序 - 调试模式")
    print("=" * 60)
    
    # 创建控制器实例
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    # 连接设备
    print("\n[步骤 1/4] 连接设备...")
    print(f"  串口: COM6")
    print(f"  波特率: 19200")
    print(f"  站号: 1")
    print(f"  数据位: 8, 校验: EVEN, 停止位: 1")
    
    if not controller.connect():
        print("❌ 无法连接到旋涂仪")
        print("  请检查:")
        print("    - 串口线是否连接正确")
        print("    - 串口号是否正确（当前使用 COM1）")
        print("    - 设备电源是否开启")
        print("    - 是否有其他程序占用串口")
        return False
    
    print("✓ 设备连接成功")
    print(f"  串口状态: {controller.ser.is_open}")
    
    try:
        # 步骤1：使能开
        print("\n[步骤 2/4] 开启使能...")
        print("  发送命令: 01 05 00 10 FF 00 8D FF -> 01 05 00 10 00 00 CC 0F")
        
        controller.enable()
        time.sleep(0.5)
        
        print("  查询使能状态...")
        print("  发送命令: 01 01 00 1F 00 01 CC 0C")
        
        enable_status = controller.enable_status()
        
        if enable_status:
            print(f"✓ 使能已开启 (状态: {enable_status})")
        else:
            print(f"⚠ 使能状态查询失败 (返回值: {enable_status})")
            print("  可能原因:")
            print("    - 设备未响应")
            print("    - 响应数据格式错误")
            print("    - 但使能命令已发送")
        
        # 步骤2：真空开
        print("\n[步骤 3/4] 开启真空...")
        print("  发送命令: 01 05 00 32 FF 00 2D F5 -> 01 05 00 32 00 00 6C 05")
        
        controller.vacuum_on()
        time.sleep(0.5)
        
        print("  查询真空状态...")
        print("  发送命令: 01 01 60 00 00 01 E3 CA")
        
        vacuum_status = controller.vacuum_status()
        
        if vacuum_status:
            print(f"✓ 真空已开启 (状态: {vacuum_status})")
        else:
            print(f"⚠ 真空状态查询失败 (返回值: {vacuum_status})")
        
        print("  读取真空显示值...")
        print("  发送命令: 01 03 00 DC 00 01 45 F0")
        
        vacuum_display = controller.vacuum_display()
        
        if vacuum_display is not None:
            print(f"  真空显示值: {vacuum_display}")
        else:
            print(f"  真空显示值读取失败 (返回值: {vacuum_display})")
        
        # 步骤3：旋涂开
        print("\n[步骤 4/4] 启动单步旋涂...")
        print("  发送命令: 01 05 00 07 FF 00 3D FB -> 01 05 00 07 00 00 7C 0B")
        
        controller.single_step_start_stop()
        time.sleep(0.5)
        
        print("  查询旋涂运行状态...")
        print("  发送命令: 01 01 00 01 00 01 AC 0A")
        
        running_status = controller.single_step_running_status()
        
        if running_status:
            print(f"✓ 单步旋涂已启动 (状态: {running_status})")
            print("  旋涂正在运行中...")
            
            # 持续监控运行状态
            print("\n监控运行状态:")
            print("-" * 60)
            start_time = time.time()
            check_count = 0
            
            while running_status:
                elapsed_time = int(time.time() - start_time)
                check_count += 1
                print(f"  [{check_count}] 运行时间: {elapsed_time}秒 | 状态: 运行中")
                
                # 每秒检查一次状态
                time.sleep(1)
                running_status = controller.single_step_running_status()
            
            total_time = int(time.time() - start_time)
            print("-" * 60)
            print(f"✓ 旋涂完成！总运行时间: {total_time}秒")
        else:
            print(f"⚠ 旋涂状态查询失败 (返回值: {running_status})")
            print("  可能原因:")
            print("    - 设备未响应状态查询")
            print("    - 旋涂命令已发送，但无法确认是否启动")
        
        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 断开连接
        print("\n断开设备连接...")
        controller.disconnect()
        print("✓ 已断开连接")

def test_raw_commands():
    """
    直接发送原始命令进行测试
    """
    print("=" * 60)
    print("原始命令测试模式")
    print("=" * 60)
    
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    print("\n[连接设备...]")
    print("  串口: COM6")
    if not controller.connect():
        print("❌ 连接失败")
        return
    
    print("✓ 已连接")
    
    try:
        # 测试使能命令
        print("\n[测试使能命令]")
        print("  发送: 01 05 00 10 FF 00 8D FF")
        response1 = controller.send_command("01 05 00 10 FF 00 8D FF")
        print(f"  响应: {response1.hex() if response1 else '无响应'}")
        
        time.sleep(0.1)
        
        print("  发送: 01 05 00 10 00 00 CC 0F")
        response2 = controller.send_command("01 05 00 10 00 00 CC 0F")
        print(f"  响应: {response2.hex() if response2 else '无响应'}")
        
        # 测试真空命令
        print("\n[测试真空命令]")
        print("  发送: 01 05 00 32 FF 00 2D F5")
        response3 = controller.send_command("01 05 00 32 FF 00 2D F5")
        print(f"  响应: {response3.hex() if response3 else '无响应'}")
        
        time.sleep(0.1)
        
        print("  发送: 01 05 00 32 00 00 6C 05")
        response4 = controller.send_command("01 05 00 32 00 00 6C 05")
        print(f"  响应: {response4.hex() if response4 else '无响应'}")
        
        # 测试旋涂命令
        print("\n[测试旋涂命令]")
        print("  发送: 01 05 00 07 FF 00 3D FB")
        response5 = controller.send_command("01 05 00 07 FF 00 3D FB")
        print(f"  响应: {response5.hex() if response5 else '无响应'}")
        
        time.sleep(0.1)
        
        print("  发送: 01 05 00 07 00 00 7C 0B")
        response6 = controller.send_command("01 05 00 07 00 00 7C 0B")
        print(f"  响应: {response6.hex() if response6 else '无响应'}")
        
        print("\n✓ 所有命令已发送")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        controller.disconnect()
        print("\n✓ 已断开连接")

if __name__ == '__main__':
    print("选择测试模式:")
    print("1. 详细调试模式（显示每个命令和响应）")
    print("2. 原始命令测试（直接发送命令查看响应）")
    
    choice = input("\n请输入选择 (1/2): ").strip()
    
    if choice == '1':
        test_single_step_spin_debug()
    elif choice == '2':
        test_raw_commands()
    else:
        print("❌ 无效选择")

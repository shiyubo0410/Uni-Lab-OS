import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spin_coater_controller import SpinCoaterController
import time

def test_single_step_spin():
    """
    测试单步旋涂操作
    步骤：使能开 -> 真空开 -> 旋涂开
    """
    
    print("=" * 50)
    print("单步旋涂测试程序")
    print("=" * 50)
    
    # 创建控制器实例
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    # 连接设备
    print("\n[1/4] 连接设备...")
    if not controller.connect():
        print("❌ 无法连接到旋涂仪，请检查串口设置")
        return False
    
    print("✓ 设备连接成功")
    
    try:
        # 步骤1：使能开
        print("\n[2/4] 开启使能...")
        controller.enable()
        time.sleep(0.5)
        
        enable_status = controller.enable_status()
        if enable_status:
            print("✓ 使能已开启")
        else:
            print("⚠ 使能状态查询失败，但命令已发送")
        
        # 步骤2：真空开
        print("\n[3/4] 开启真空...")
        controller.vacuum_on()
        time.sleep(0.5)
        
        vacuum_status = controller.vacuum_status()
        vacuum_display = controller.vacuum_display()
        
        if vacuum_status:
            print(f"✓ 真空已开启")
            if vacuum_display is not None:
                print(f"  真空显示值: {vacuum_display}")
        else:
            print("⚠ 真空状态查询失败，但命令已发送")
        
        # 步骤3：旋涂开
        print("\n[4/4] 启动单步旋涂...")
        controller.single_step_start_stop()
        time.sleep(0.5)
        
        running_status = controller.single_step_running_status()
        if running_status:
            print("✓ 单步旋涂已启动")
            print("  旋涂正在运行中...")
            
            # 持续监控运行状态
            print("\n监控运行状态:")
            print("-" * 50)
            start_time = time.time()
            
            while running_status:
                elapsed_time = int(time.time() - start_time)
                print(f"  运行时间: {elapsed_time}秒 | 状态: 运行中")
                
                # 每秒检查一次状态
                time.sleep(1)
                running_status = controller.single_step_running_status()
            
            total_time = int(time.time() - start_time)
            print("-" * 50)
            print(f"✓ 旋涂完成！总运行时间: {total_time}秒")
        else:
            print("⚠ 旋涂状态查询失败，但命令已发送")
        
        print("\n" + "=" * 50)
        print("测试完成！")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False
    
    finally:
        # 断开连接
        print("\n断开设备连接...")
        controller.disconnect()
        print("✓ 已断开连接")

def test_with_parameters(speed=5000, spin_time=2000, acceleration=5000):
    """
    测试单步旋涂操作（带参数设置）
    
    Args:
        speed: 旋涂速度 (10-10000)
        spin_time: 旋涂时间 (0-3000ms)
        acceleration: 加速度 (200-30000)
    """
    
    print("=" * 50)
    print("单步旋涂测试程序（带参数）")
    print("=" * 50)
    print(f"参数设置:")
    print(f"  速度: {speed}")
    print(f"  时间: {spin_time}ms")
    print(f"  加速度: {acceleration}")
    print("=" * 50)
    
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    print("\n[1/5] 连接设备...")
    if not controller.connect():
        print("❌ 无法连接到旋涂仪")
        return False
    
    print("✓ 设备连接成功")
    
    try:
        # 步骤1：使能开
        print("\n[2/5] 开启使能...")
        controller.enable()
        time.sleep(0.5)
        print("✓ 使能已开启")
        
        # 步骤2：真空开
        print("\n[3/5] 开启真空...")
        controller.vacuum_on()
        time.sleep(0.5)
        print("✓ 真空已开启")
        
        # 步骤3：设置参数
        print("\n[4/5] 设置旋涂参数...")
        success = True
        success &= controller.set_single_step_speed(speed)
        success &= controller.set_single_step_time(spin_time)
        success &= controller.set_single_step_acceleration(acceleration)
        
        if success:
            print("✓ 参数设置成功")
        else:
            print("⚠ 部分参数设置失败")
        
        # 步骤4：旋涂开
        print("\n[5/5] 启动单步旋涂...")
        controller.single_step_start_stop()
        time.sleep(0.5)
        
        running_status = controller.single_step_running_status()
        if running_status:
            print("✓ 单步旋涂已启动")
            print("\n监控运行状态:")
            print("-" * 50)
            
            start_time = time.time()
            while running_status:
                elapsed_time = int(time.time() - start_time)
                print(f"  运行时间: {elapsed_time}秒 | 状态: 运行中")
                time.sleep(1)
                running_status = controller.single_step_running_status()
            
            total_time = int(time.time() - start_time)
            print("-" * 50)
            print(f"✓ 旋涂完成！总运行时间: {total_time}秒")
        else:
            print("⚠ 旋涂启动失败")
        
        print("\n" + "=" * 50)
        print("测试完成！")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        return False
    
    finally:
        controller.disconnect()
        print("\n✓ 已断开连接")

if __name__ == '__main__':
    print("选择测试模式:")
    print("1. 基础测试（使能开 -> 真空开 -> 旋涂开）")
    print("2. 带参数测试（可设置速度、时间、加速度）")
    
    choice = input("\n请输入选择 (1/2): ").strip()
    
    if choice == '1':
        test_single_step_spin()
    elif choice == '2':
        print("\n请输入参数（使用默认值直接回车）:")
        
        speed_input = input(f"旋涂速度 (10-10000, 默认5000): ").strip()
        speed = int(speed_input) if speed_input else 5000
        
        time_input = input(f"旋涂时间 (0-3000ms, 默认2000): ").strip()
        spin_time = int(time_input) if time_input else 2000
        
        acc_input = input(f"加速度 (200-30000, 默认5000): ").strip()
        acceleration = int(acc_input) if acc_input else 5000
        
        test_with_parameters(speed, spin_time, acceleration)
    else:
        print("❌ 无效选择")

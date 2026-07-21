import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spin_coater_controller import SpinCoaterController
import time

def example_usage():
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    if not controller.connect():
        print("无法连接到旋涂仪")
        return
    
    print("已连接到旋涂仪")
    
    try:
        print("\n=== 使能控制 ===")
        controller.enable()
        time.sleep(0.5)
        status = controller.enable_status()
        print(f"使能状态: {'开启' if status else '关闭'}")
        
        print("\n=== 真空控制 ===")
        controller.vacuum_on()
        time.sleep(0.5)
        vacuum_status = controller.vacuum_status()
        print(f"真空状态: {'开启' if vacuum_status else '关闭'}")
        
        vacuum_display = controller.vacuum_display()
        print(f"真空显示值: {vacuum_display}")
        
        print("\n=== 设置单步参数 ===")
        controller.set_single_step_speed(5000)
        controller.set_single_step_time(2000)
        controller.set_single_step_acceleration(5000)
        print("单步参数已设置: 速度=5000, 时间=2000ms, 加速度=5000")
        
        print("\n=== 执行单步运行 ===")
        controller.single_step_start_stop()
        time.sleep(1)
        running = controller.single_step_running_status()
        print(f"单步运行状态: {'运行中' if running else '停止'}")
        
        print("\n=== 设置多步参数 ===")
        controller.set_multi_step_speed(1, 3000)
        controller.set_multi_step_time(1, 1500)
        controller.set_multi_step_acceleration(1, 4000)
        print("多步第1步参数已设置: 速度=3000, 时间=1500ms, 加速度=4000")
        
        controller.set_multi_step_speed(2, 5000)
        controller.set_multi_step_time(2, 1000)
        controller.set_multi_step_acceleration(2, 6000)
        print("多步第2步参数已设置: 速度=5000, 时间=1000ms, 加速度=6000")
        
        print("\n=== 执行多步运行 ===")
        controller.multi_step_start_stop()
        time.sleep(1)
        running = controller.multi_step_running_status()
        print(f"多步运行状态: {'运行中' if running else '停止'}")
        
        current_step = controller.get_multi_step_current_step()
        print(f"当前运行步骤: {current_step}")
        
        print("\n=== 设置对中参数 ===")
        controller.set_alignment_speed(300)
        controller.set_alignment_time(50)
        print("对中参数已设置: 速度=300, 时间=50ms")
        
        print("\n=== 设置摆动参数 ===")
        controller.set_oscillation_speed(400)
        controller.set_oscillation_acceleration(500)
        controller.set_oscillation_time(30)
        controller.set_oscillation_count(5)
        print("摆动参数已设置: 速度=400, 加速度=500, 时间=30ms, 次数=5")
        
        print("\n=== 读取运行信息 ===")
        run_speed = controller.get_run_speed()
        run_time = controller.get_run_time()
        multi_total_time = controller.get_multi_step_total_time()
        print(f"运行速度: {run_speed}")
        print(f"运行时间: {run_time}")
        print(f"多步总运行时间: {multi_total_time}")
        
        print("\n=== 手动回原 ===")
        controller.manual_home()
        print("已发送手动回原命令")
        
        print("\n=== 页面控制 ===")
        controller.set_page(0x0003)
        print("已切换到单步运行画面")
        
        current_page = controller.get_current_page()
        print(f"当前页面: {hex(current_page) if current_page else '未知'}")
        
    except Exception as e:
        print(f"发生错误: {e}")
    
    finally:
        controller.disconnect()
        print("\n已断开连接")

def simple_vacuum_control():
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    if not controller.connect():
        print("无法连接到旋涂仪")
        return
    
    print("已连接到旋涂仪")
    
    try:
        print("\n开启真空...")
        controller.vacuum_on()
        
        time.sleep(1)
        
        status = controller.vacuum_status()
        display = controller.vacuum_display()
        
        print(f"真空状态: {'开启' if status else '关闭'}")
        print(f"真空显示值: {display}")
        
    finally:
        controller.disconnect()

def custom_spin_process():
    controller = SpinCoaterController(port='COM6', baudrate=19200, station=1)
    
    if not controller.connect():
        print("无法连接到旋涂仪")
        return
    
    print("已连接到旋涂仪")
    
    try:
        print("\n=== 自定义旋涂流程 ===")
        
        print("1. 使能设备...")
        controller.enable()
        time.sleep(0.5)
        
        print("2. 开启真空...")
        controller.vacuum_on()
        time.sleep(0.5)
        
        print("3. 设置旋涂参数...")
        controller.set_single_step_speed(3000)
        controller.set_single_step_time(3000)
        controller.set_single_step_acceleration(5000)
        
        print("4. 开始旋涂...")
        controller.single_step_start_stop()
        
        print("5. 等待旋涂完成...")
        time.sleep(5)
        
        running = controller.single_step_running_status()
        while running:
            print("旋涂中...")
            time.sleep(1)
            running = controller.single_step_running_status()
        
        print("旋涂完成!")
        
    except Exception as e:
        print(f"发生错误: {e}")
    
    finally:
        controller.disconnect()
        print("已断开连接")

if __name__ == '__main__':
    print("选择示例:")
    print("1. 完整功能演示")
    print("2. 简单真空控制")
    print("3. 自定义旋涂流程")
    
    choice = input("请输入选择 (1/2/3): ")
    
    if choice == '1':
        example_usage()
    elif choice == '2':
        simple_vacuum_control()
    elif choice == '3':
        custom_spin_process()
    else:
        print("无效选择")

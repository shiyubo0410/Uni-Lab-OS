"""
PGEA系列夹爪 - 使用示例

本文件包含各种使用场景的示例代码，供参考学习。
"""

import time
from pgea_gripper_skill import (
    PGEAGripper,
    GripperStatus,
    GRIP_STATUS_GRIPPED,
    GRIP_STATUS_IN_POSITION,
    POSITION_MIN,
    POSITION_MAX,
)


def example_basic_connection():
    """示例1: 基本连接与初始化"""
    print("=" * 50)
    print("示例1: 基本连接与初始化")
    print("=" * 50)
    
    # 创建夹爪实例
    gripper = PGEAGripper(port='/dev/ttyUSB0', slave_id=1)
    
    try:
        # 连接夹爪
        gripper.connect()
        print(f"连接状态: {gripper.is_connected()}")
        
        # 检查初始化状态
        if not gripper.is_initialized():
            print("夹爪未初始化，开始初始化...")
            gripper.initialize(full_calibration=False)
        else:
            print("夹爪已初始化")
            
    finally:
        # 断开连接
        gripper.disconnect()
        print("已断开连接")


def example_basic_control():
    """示例2: 基本运动控制"""
    print("=" * 50)
    print("示例2: 基本运动控制")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        # 确保已初始化
        if not gripper.is_initialized():
            gripper.initialize()
        
        # 设置参数
        print("设置力值50%，速度30%")
        gripper.set_force(50)
        gripper.set_speed(30)
        
        # 运动到50%位置
        print("运动到50%位置...")
        gripper.move_to(500)
        
        # 等待到位
        status = gripper.wait_for_complete(timeout=5.0)
        print(f"运动完成，状态: {status}")
        
        # 获取当前位置
        pos = gripper.get_current_position()
        print(f"当前位置: {pos}‰")
        
    finally:
        gripper.disconnect()


def example_grip_and_release():
    """示例3: 夹持与释放"""
    print("=" * 50)
    print("示例3: 夹持与释放")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        if not gripper.is_initialized():
            gripper.initialize()
        
        # 张开
        print("张开夹爪...")
        gripper.release(position=1000, speed=50)
        time.sleep(1)
        
        # 夹持
        print("夹持物体...")
        gripped = gripper.grip(force=60, speed=30, wait=True)
        
        if gripped:
            print("成功夹住物体!")
            time.sleep(2)
            
            # 检查是否掉落
            status = gripper.get_grip_status()
            if status == GRIP_STATUS_GRIPPED:
                print("物体仍然被夹住")
            else:
                print("物体已掉落")
        else:
            print("未检测到物体")
        
        # 释放
        print("释放物体...")
        gripper.release(position=800, speed=50)
        
    finally:
        gripper.disconnect()


def example_pick_and_place():
    """示例4: 取放操作"""
    print("=" * 50)
    print("示例4: 取放操作")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        if not gripper.is_initialized():
            gripper.initialize()
        
        # 取物
        print("执行取物...")
        success = gripper.pick(
            pick_position=200,    # 取物位置
            force=50,             # 夹持力
            speed=30,             # 速度
            lift_position=500,    # 提升位置
            wait_grip=True,
            timeout=10.0
        )
        
        if success:
            print("取物成功!")
            
            # 移动到放置位置
            time.sleep(1)
            
            # 放物
            print("执行放物...")
            gripper.place(
                place_position=300,   # 放置位置
                speed=30,
                release_position=800, # 释放后位置
                wait=True
            )
            print("放物完成")
        else:
            print("取物失败")
            
    finally:
        gripper.disconnect()


def example_status_monitoring():
    """示例5: 状态监控"""
    print("=" * 50)
    print("示例5: 状态监控")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        if not gripper.is_initialized():
            gripper.initialize()
        
        # 获取完整状态
        print("获取完整状态:")
        status = gripper.get_full_status()
        print(f"  初始化状态: {'已初始化' if status.initialized else '未初始化'}")
        print(f"  夹持状态: {status.grip_status}")
        print(f"  当前位置: {status.position}‰")
        print(f"  当前速度: {status.speed}")
        print(f"  当前电流: {status.current}")
        print(f"  电机温度: {status.motor_temp}°C")
        print(f"  错误码: {status.error_code}")
        print(f"  IO输入: {status.io_input}")
        print(f"  IO输出: {status.io_output}")
        
        # 检查错误
        if status.has_error:
            print(f"错误: {status.get_error_description()}")
        else:
            print("无错误")
        
        # 运动过程中监控
        print("\n运动监控:")
        gripper.set_speed(50)
        gripper.move_to(700)
        
        for _ in range(20):
            pos = gripper.get_current_position()
            current = gripper.get_current()
            grip_status = gripper.get_grip_status()
            print(f"  位置: {pos}‰, 电流: {current}, 状态: {grip_status}")
            time.sleep(0.1)
            
    finally:
        gripper.disconnect()


def example_error_handling():
    """示例6: 错误处理"""
    print("=" * 50)
    print("示例6: 错误处理")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        # 检查错误
        error = gripper.check_error()
        if error:
            print(f"检测到错误: {error}")
            print("尝试清除错误...")
            gripper.clear_error()
            time.sleep(0.5)
            
            # 再次检查
            error = gripper.check_error()
            if error:
                print(f"错误未清除: {error}")
            else:
                print("错误已清除")
        else:
            print("无错误")
            
    finally:
        gripper.disconnect()


def example_io_mode():
    """示例7: IO模式配置"""
    print("=" * 50)
    print("示例7: IO模式配置")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        if not gripper.is_initialized():
            gripper.initialize()
        
        # 配置4组IO参数
        print("配置IO参数组...")
        
        # 第1组: 张开
        gripper.set_io_parameters(
            group=1,
            position=1000,
            force=50,
            speed=50
        )
        
        # 第2组: 半闭合
        gripper.set_io_parameters(
            group=2,
            position=500,
            force=60,
            speed=30
        )
        
        # 第3组: 夹持
        gripper.set_io_parameters(
            group=3,
            position=0,
            force=80,
            speed=20
        )
        
        # 第4组: 微张
        gripper.set_io_parameters(
            group=4,
            position=200,
            force=40,
            speed=40
        )
        
        print("IO参数配置完成")
        
        # 测试第2组参数
        print("测试第2组IO参数...")
        gripper.test_io_group(2)
        time.sleep(2)
        
        # 保存参数
        print("保存参数到Flash...")
        gripper.save_parameters()
        
    finally:
        gripper.disconnect()


def example_parameter_config():
    """示例8: 参数配置"""
    print("=" * 50)
    print("示例8: 参数配置")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        # 设置初始化方向
        print("设置初始化方向为张开...")
        gripper.set_init_direction(0)  # 0=张开, 1=闭合
        
        # 设置自动初始化
        print("启用上电自动初始化...")
        gripper.set_auto_init(enable=True, full=False)
        
        # 保存参数
        print("保存参数...")
        gripper.save_parameters()
        print("参数已保存，重启后生效")
        
    finally:
        gripper.disconnect()


def example_context_manager():
    """示例9: 使用上下文管理器"""
    print("=" * 50)
    print("示例9: 使用上下文管理器")
    print("=" * 50)
    
    # 使用with语句自动管理连接
    with PGEAGripper(port='/dev/ttyUSB0') as gripper:
        print("已自动连接")
        
        if not gripper.is_initialized():
            gripper.initialize()
        
        gripper.set_force(50)
        gripper.set_speed(40)
        gripper.move_to(600)
        gripper.wait_for_complete()
        
        print("运动完成")
    
    print("已自动断开连接")


def example_continuous_operation():
    """示例10: 连续操作"""
    print("=" * 50)
    print("示例10: 连续操作")
    print("=" * 50)
    
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    
    try:
        gripper.connect()
        
        if not gripper.is_initialized():
            gripper.initialize()
        
        # 连续夹持和释放
        gripper.set_force(40)
        gripper.set_speed(50)
        
        for i in range(3):
            print(f"\n第 {i+1} 次循环:")
            
            # 张开
            print("  张开...")
            gripper.move_to(800)
            gripper.wait_for_complete()
            time.sleep(0.5)
            
            # 夹持
            print("  夹持...")
            gripper.move_to(100)
            gripper.wait_for_gripped(timeout=5.0)
            time.sleep(1)
            
    finally:
        gripper.disconnect()


# 运行所有示例
if __name__ == "__main__":
    print("PGEA夹爪控制库使用示例")
    print("=" * 50)
    print()
    
    # 选择要运行的示例
    examples = [
        example_basic_connection,
        example_basic_control,
        example_grip_and_release,
        example_pick_and_place,
        example_status_monitoring,
        example_error_handling,
        example_io_mode,
        example_parameter_config,
        example_context_manager,
        example_continuous_operation,
    ]
    
    # 提示用户修改串口路径
    print("注意: 请根据实际硬件连接修改串口路径 (如 '/dev/ttyUSB0' 或 'COM3')")
    print()
    
    # 运行示例
    for i, example in enumerate(examples, 1):
        try:
            example()
        except Exception as e:
            print(f"示例执行出错: {e}")
        print()

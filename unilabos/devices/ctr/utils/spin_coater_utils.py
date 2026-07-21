#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旋涂仪控制工具函数
提供使能启停、真空启停、旋涂启停等控制功能
"""

import sys
from pathlib import Path

# 添加 skills/xuantu 到路径
UTILS_DIR = Path(__file__).parent.resolve()
SKILLS_PATH = UTILS_DIR.parent / 'skills' / 'xuantu'
sys.path.insert(0, str(SKILLS_PATH))

try:
    from xuantu_utils import SpinCoaterCommands, CRC16Modbus
except ImportError as e:
    print(f"无法导入旋涂仪指令工具 - {e}")
    print(f"请确保路径正确: {SKILLS_PATH}")
    sys.exit(1)


class SpinCoaterControl:
    """旋涂仪控制类"""
    
    def __init__(self, serial_client=None):
        """
        初始化旋涂仪控制器
        
        Args:
            serial_client: 串口客户端对象，需实现 send_command 方法
        """
        self.serial_client = serial_client
    
    def set_serial_client(self, serial_client):
        """
        设置串口客户端
        
        Args:
            serial_client: 串口客户端对象
        """
        self.serial_client = serial_client
    
    def _send_command(self, command: str) -> bool:
        """
        发送命令到旋涂仪
        
        Args:
            command: 16进制命令字符串
        
        Returns:
            bool: 是否发送成功
        """
        if self.serial_client is None:
            print("错误: 串口客户端未设置")
            return False
        
        try:
            response = self.serial_client.send_command(command)
            return response is not None
        except Exception as e:
            print(f"发送命令失败: {e}")
            return False
    
    def _send_command_pair(self, command_pair: str) -> bool:
        """
        发送命令对（置位+复位）
        
        Args:
            command_pair: 命令对，格式为 "命令1 -> 命令2"
        
        Returns:
            bool: 是否发送成功
        """
        if self.serial_client is None:
            print("错误: 串口客户端未设置")
            return False
        
        try:
            parts = command_pair.split(' -> ')
            if len(parts) != 2:
                print("错误: 命令对格式不正确")
                return False
            
            response1 = self.serial_client.send_command(parts[0])
            if response1 is None:
                return False
            
            import time
            time.sleep(0.2)
            
            response2 = self.serial_client.send_command(parts[1])
            return response2 is not None
        except Exception as e:
            print(f"发送命令对失败: {e}")
            return False
    
    def check_spin_status(self) -> bool:
        """
        检查旋涂是否结束
        
        Returns:
            bool: True 表示旋涂已结束，False 表示旋涂仍在进行
        """
        if self.serial_client is None:
            print("错误: 串口客户端未设置")
            return False
        
        try:
            # 读取单步运行状态
            response = self.serial_client.send_command(SpinCoaterCommands.single_step_status())
            if response:
                # 解析响应
                # 假设响应格式为: 01 01 01 00 XX XX
                # 其中第4字节表示状态
                parts = response.split()
                if len(parts) >= 4:
                    status_byte = int(parts[3], 16)
                    # 如果状态为0，表示旋涂已结束
                    return status_byte == 0
            return True  # 如果无法获取状态，默认返回结束
        except Exception as e:
            print(f"检查旋涂状态失败: {e}")
            return True  # 出错时默认返回结束

    def is_spinning(self) -> bool:
        """
        检查是否正在旋涂
        
        Returns:
            bool: True 表示正在旋涂，False 表示旋涂已结束
        """
        return not self.check_spin_status()

    def check_enable_status(self) -> bool:
        """
        检查使能状态
        
        Returns:
            bool: True 表示使能已开启，False 表示使能关闭
        """
        if self.serial_client is None:
            print("错误: 串口客户端未设置")
            return False
        
        try:
            # 读取使能状态
            response = self.serial_client.send_command(SpinCoaterCommands.enable_status())
            if response:
                # 解析响应
                # 假设响应格式为: 01 01 01 00 XX XX 或 01 01 01 01 XX XX
                # 其中第4字节表示状态
                parts = response.split()
                if len(parts) >= 4:
                    status_byte = int(parts[3], 16)
                    # 如果状态为1，表示使能已开启
                    return status_byte == 1
            return False  # 如果无法获取状态，默认返回关闭
        except Exception as e:
            print(f"检查使能状态失败: {e}")
            return False  # 出错时默认返回关闭


def enable_on(control: SpinCoaterControl) -> bool:
    """
    使能开启
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.enable_on()} -> {SpinCoaterCommands.enable_off()}"
    print("🔧 使能开启...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 使能开启{'成功' if result else '失败'}")
    return result


def enable_off(control: SpinCoaterControl) -> bool:
    """
    使能关闭
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    # 使能关闭和使能开启使用相同的命令
    command = f"{SpinCoaterCommands.enable_on()} -> {SpinCoaterCommands.enable_off()}"
    print("🔧 使能关闭...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 使能关闭{'成功' if result else '失败'}")
    return result


def enable_toggle(control: SpinCoaterControl) -> bool:
    """
    使能启停（切换）
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.enable_on()} -> {SpinCoaterCommands.enable_off()}"
    print("🔄 使能启停...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 使能启停{'成功' if result else '失败'}")
    return result


def vacuum_on(control: SpinCoaterControl) -> bool:
    """
    真空开启
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.vacuum_on()} -> {SpinCoaterCommands.vacuum_off()}"
    print("🔧 真空开启...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 真空开启{'成功' if result else '失败'}")
    return result


def vacuum_off(control: SpinCoaterControl) -> bool:
    """
    真空关闭
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    # 真空关闭和真空开启使用相同的命令
    command = f"{SpinCoaterCommands.vacuum_on()} -> {SpinCoaterCommands.vacuum_off()}"
    print("🔧 真空关闭...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 真空关闭{'成功' if result else '失败'}")
    return result


def vacuum_toggle(control: SpinCoaterControl) -> bool:
    """
    真空启停（切换）
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.vacuum_on()} -> {SpinCoaterCommands.vacuum_off()}"
    print("🔄 真空启停...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 真空启停{'成功' if result else '失败'}")
    return result


def spin_start(control: SpinCoaterControl) -> bool:
    """
    旋涂启动（单步运行）
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.single_step_on()} -> {SpinCoaterCommands.single_step_off()}"
    print("🔧 旋涂启动...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 旋涂启动{'成功' if result else '失败'}")
    return result


def spin_stop(control: SpinCoaterControl) -> bool:
    """
    旋涂停止
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔧 旋涂停止...")
    print("注意: 旋涂停止通常通过发送复位命令实现")
    command = SpinCoaterCommands.single_step_off()
    result = control._send_command(command)
    print(f"{'✓' if result else '✗'} 旋涂停止{'成功' if result else '失败'}")
    return result


def spin_toggle(control: SpinCoaterControl) -> bool:
    """
    旋涂启停（切换）
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.single_step_on()} -> {SpinCoaterCommands.single_step_off()}"
    print("🔄 旋涂启停...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 旋涂启停{'成功' if result else '失败'}")
    return result


def multi_step_start(control: SpinCoaterControl) -> bool:
    """
    多步旋涂启动
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.multi_step_on()} -> {SpinCoaterCommands.multi_step_off()}"
    print("🔧 多步旋涂启动...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 多步旋涂启动{'成功' if result else '失败'}")
    return result


def multi_step_stop(control: SpinCoaterControl) -> bool:
    """
    多步旋涂停止
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    print("🔧 多步旋涂停止...")
    print("注意: 多步旋涂停止通常通过发送复位命令实现")
    command = SpinCoaterCommands.multi_step_off()
    result = control._send_command(command)
    print(f"{'✓' if result else '✗'} 多步旋涂停止{'成功' if result else '失败'}")
    return result


def multi_step_toggle(control: SpinCoaterControl) -> bool:
    """
    多步旋涂启停（切换）
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    command = f"{SpinCoaterCommands.multi_step_on()} -> {SpinCoaterCommands.multi_step_off()}"
    print("🔄 多步旋涂启停...")
    result = control._send_command_pair(command)
    print(f"{'✓' if result else '✗'} 多步旋涂启停{'成功' if result else '失败'}")
    return result


def manual_home(control: SpinCoaterControl) -> bool:
    """
    手动回原 - 上升沿触发
    
    协议: 读01/写05, M20 (H0014), HFF00/H0000
    先发送置位命令(FF00)，保持一段时间，再发送复位命令(0000)
    
    Args:
        control: 旋涂仪控制对象
    
    Returns:
        bool: 是否成功
    """
    if control.serial_client is None:
        print("错误: 串口客户端未设置")
        return False
    
    try:
        print("🔧 手动回原...")
        
        # 使用与其他命令相同的方式：命令对（置位+复位）
        command_pair = f"{SpinCoaterCommands.manual_home_on()} -> {SpinCoaterCommands.manual_home_off()}"
        print(f"  发送命令对: {command_pair}")
        
        # 直接使用_serial_client发送命令，忽略响应（设备可能不响应写命令）
        on_command = SpinCoaterCommands.manual_home_on()
        off_command = SpinCoaterCommands.manual_home_off()
        
        # 1. 发送置位命令
        print(f"  发送置位命令: {on_command}")
        control.serial_client.send_command(on_command, wait_time=0.3)
        
        # 2. 保持一段时间（上升沿触发）
        import time
        time.sleep(0.5)  # 保持500ms确保上升沿被检测到
        
        # 3. 发送复位命令
        print(f"  发送复位命令: {off_command}")
        control.serial_client.send_command(off_command, wait_time=0.3)
        
        print("✓ 手动回原完成 - 脉冲上升沿触发")
        return True
        
    except Exception as e:
        print(f"✗ 手动回原失败: {e}")
        return False


def wait_for_spin_completion(control: SpinCoaterControl, timeout: int = 60) -> bool:
    """
    等待旋涂结束
    
    Args:
        control: 旋涂仪控制对象
        timeout: 超时时间（秒）
    
    Returns:
        bool: 是否在超时前完成
    """
    import time
    start_time = time.time()
    print("⏳ 等待旋涂结束...")
    
    while time.time() - start_time < timeout:
        if control.check_spin_status():
            print("✓ 旋涂已结束")
            return True
        time.sleep(1)
    
    print("❌ 等待旋涂结束超时")
    return False


if __name__ == '__main__':
    print("=" * 60)
    print("旋涂仪控制工具函数测试")
    print("=" * 60)
    
    print("\n【命令生成测试】")
    print(f"使能开启置位: {SpinCoaterCommands.enable_on()}")
    print(f"使能开启复位: {SpinCoaterCommands.enable_off()}")
    print(f"真空开启置位: {SpinCoaterCommands.vacuum_on()}")
    print(f"真空开启复位: {SpinCoaterCommands.vacuum_off()}")
    print(f"单步启停置位: {SpinCoaterCommands.single_step_on()}")
    print(f"单步启停复位: {SpinCoaterCommands.single_step_off()}")
    print(f"多步启停置位: {SpinCoaterCommands.multi_step_on()}")
    print(f"多步启停复位: {SpinCoaterCommands.multi_step_off()}")
    print(f"手动回原置位: {SpinCoaterCommands.manual_home_on()}")
    print(f"手动回原复位: {SpinCoaterCommands.manual_home_off()}")
    
    print("\n【功能列表】")
    print("✓ enable_on()      - 使能开启")
    print("✓ enable_off()     - 使能关闭")
    print("✓ enable_toggle()  - 使能启停")
    print("✓ vacuum_on()      - 真空开启")
    print("✓ vacuum_off()     - 真空关闭")
    print("✓ vacuum_toggle()  - 真空启停")
    print("✓ spin_start()     - 旋涂启动（单步）")
    print("✓ spin_stop()      - 旋涂停止（单步）")
    print("✓ spin_toggle()    - 旋涂启停（单步）")
    print("✓ multi_step_start()  - 多步旋涂启动")
    print("✓ multi_step_stop()   - 多步旋涂停止")
    print("✓ multi_step_toggle() - 多步旋涂启停")
    print("✓ manual_home()    - 手动回原")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

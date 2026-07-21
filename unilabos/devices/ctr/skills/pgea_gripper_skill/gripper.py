"""
PGEA系列驱控一体式工业平行电爪 - 主控制类

提供高级API用于控制PGEA系列夹爪，包括:
- 初始化控制
- 力/位/速控制
- 状态读取
- 参数配置
- 错误处理

使用示例:
    from pgea_gripper_skill import PGEAGripper
    
    # 创建夹爪实例并连接
    gripper = PGEAGripper(port='/dev/ttyUSB0')
    gripper.connect()
    
    # 初始化夹爪
    gripper.initialize()
    
    # 设置参数并运动
    gripper.set_force(50)      # 设置50%力值
    gripper.set_speed(30)      # 设置30%速度
    gripper.move_to(500)       # 运动到50%位置
    
    # 等待到位并检查状态
    gripper.wait_for_complete()
    status = gripper.get_grip_status()
    
    # 断开连接
    gripper.disconnect()
"""

import time
import logging
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

try:
    from .modbus_client import ModbusRTUClient
    from .constants import *
except ImportError:
    from modbus_client import ModbusRTUClient
    from constants import *

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GripperStatus:
    """夹爪状态数据类"""
    initialized: bool          # 是否已初始化
    grip_status: int           # 夹持状态
    position: int              # 当前位置 (0-1000)
    speed: int                 # 当前速度
    current: int               # 当前电流
    error_code: int            # 错误码
    io_input: int              # IO输入状态
    io_output: int             # IO输出状态
    motor_temp: int            # 电机温度
    
    @property
    def is_moving(self) -> bool:
        """是否正在运动"""
        return self.grip_status == GRIP_STATUS_MOVING
    
    @property
    def is_gripped(self) -> bool:
        """是否已夹住物体"""
        return self.grip_status == GRIP_STATUS_GRIPPED
    
    @property
    def is_dropped(self) -> bool:
        """物体是否掉落"""
        return self.grip_status == GRIP_STATUS_DROPPED
    
    @property
    def in_position(self) -> bool:
        """是否已到位"""
        return self.grip_status == GRIP_STATUS_IN_POSITION
    
    @property
    def has_error(self) -> bool:
        """是否有错误"""
        return self.error_code != ERROR_NONE
    
    def get_error_description(self) -> str:
        """获取错误描述"""
        return ERROR_DESCRIPTIONS.get(self.error_code, f"未知错误码: {self.error_code}")
    
    def __str__(self) -> str:
        status_str = {
            GRIP_STATUS_MOVING: "运动中",
            GRIP_STATUS_IN_POSITION: "到位",
            GRIP_STATUS_GRIPPED: "已夹住物体",
            GRIP_STATUS_DROPPED: "物体掉落",
        }.get(self.grip_status, f"未知状态({self.grip_status})")
        
        return (
            f"夹爪状态: {'已初始化' if self.initialized else '未初始化'} | "
            f"运动状态: {status_str} | "
            f"位置: {self.position}‰ | "
            f"电流: {self.current} | "
            f"温度: {self.motor_temp}°C"
        )


class PGEAGripper:
    """PGEA系列夹爪控制器"""
    
    def __init__(
        self,
        port: str,
        slave_id: int = DEFAULT_SLAVE_ID,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 1.0,
        auto_connect: bool = False,
    ):
        """
        初始化PGEA夹爪控制器
        
        Args:
            port: 串口设备路径 (如 '/dev/ttyUSB0' 或 'COM3')
            slave_id: 从站ID (默认1)
            baudrate: 波特率 (默认115200)
            timeout: 通信超时时间(秒)
            auto_connect: 是否自动连接
        """
        self.port = port
        self.slave_id = slave_id
        self.baudrate = baudrate
        self.timeout = timeout
        
        self.client = ModbusRTUClient(
            port=port,
            slave_id=slave_id,
            baudrate=baudrate,
            timeout=timeout,
        )
        
        self._initialized = False
        self._current_force = 100
        self._current_speed = 50
        self._current_position = 0
        
        if auto_connect:
            self.connect()
    
    # ==================== 连接管理 ====================
    
    def connect(self) -> bool:
        """
        连接夹爪
        
        Returns:
            连接是否成功
        """
        try:
            result = self.client.connect()
            if result:
                logger.info(f"成功连接到夹爪 (端口: {self.port}, ID: {self.slave_id})")
            return result
        except Exception as e:
            logger.error(f"连接夹爪失败: {e}")
            raise
    
    def disconnect(self) -> None:
        """断开与夹爪的连接"""
        self.client.disconnect()
        logger.info("已断开与夹爪的连接")
    
    def is_connected(self) -> bool:
        """
        检查是否已连接
        
        Returns:
            是否已连接
        """
        return self.client.is_connected()
    
    # ==================== 初始化控制 ====================
    
    def initialize(
        self, 
        full_calibration: bool = False, 
        wait: bool = True,
        timeout: float = 10.0
    ) -> bool:
        """
        初始化夹爪
        
        初始化用于标定零点，必须在首次使用或更换指尖后执行。
        
        Args:
            full_calibration: 是否进行完全初始化(重新标定行程)
            wait: 是否等待初始化完成
            timeout: 等待超时时间(秒)
            
        Returns:
            初始化是否成功
        """
        init_value = INIT_COMMAND_FULL if full_calibration else INIT_COMMAND_NORMAL
        
        logger.info(f"开始{'完全' if full_calibration else '正常'}初始化...")
        
        try:
            self.client.write_single_register(REG_INIT_GRIPPER, init_value)
            
            if wait:
                start_time = time.time()
                while time.time() - start_time < timeout:
                    time.sleep(0.1)
                    status = self.get_init_status()
                    
                    if status == INIT_STATUS_SUCCESS:
                        self._initialized = True
                        logger.info("初始化完成")
                        return True
                    elif status == INIT_STATUS_STROKE_ERROR:
                        raise RuntimeError("行程标定异常，请检查是否有物体阻挡")
                
                raise TimeoutError("初始化超时")
            
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise
    
    def get_init_status(self) -> int:
        """
        获取初始化状态
        
        Returns:
            初始化状态码
            0: 未初始化
            1: 初始化成功
            2: 初始化中
            0xFFFF: 行程标定异常
        """
        values = self.client.read_holding_registers(REG_INIT_STATUS, 1)
        return values[0] if values else INIT_STATUS_NOT_INIT
    
    def is_initialized(self) -> bool:
        """
        检查夹爪是否已初始化
        
        Returns:
            是否已初始化
        """
        return self.get_init_status() == INIT_STATUS_SUCCESS
    
    # ==================== 运动控制 ====================
    
    def set_force(self, force: int) -> bool:
        """
        设置夹持力值
        
        Args:
            force: 力值百分比 (20-100)
            
        Returns:
            设置是否成功
        """
        force = max(FORCE_MIN, min(FORCE_MAX, force))
        
        try:
            result = self.client.write_single_register(REG_FORCE, force)
            if result:
                self._current_force = force
                logger.debug(f"力值设置为: {force}%")
            return result
        except Exception as e:
            logger.error(f"设置力值失败: {e}")
            raise
    
    def get_force(self) -> int:
        """
        获取当前设定的力值
        
        Returns:
            当前力值百分比
        """
        values = self.client.read_holding_registers(REG_FORCE, 1)
        return values[0] if values else 0
    
    def set_speed(self, speed: int) -> bool:
        """
        设置运行速度
        
        Args:
            speed: 速度百分比 (1-100)
            
        Returns:
            设置是否成功
        """
        speed = max(SPEED_MIN, min(SPEED_MAX, speed))
        
        try:
            result = self.client.write_single_register(REG_SPEED, speed)
            if result:
                self._current_speed = speed
                logger.debug(f"速度设置为: {speed}%")
            return result
        except Exception as e:
            logger.error(f"设置速度失败: {e}")
            raise
    
    def get_speed(self) -> int:
        """
        获取当前设定的速度
        
        Returns:
            当前速度百分比
        """
        values = self.client.read_holding_registers(REG_SPEED, 1)
        return values[0] if values else 0
    
    def move_to(self, position: int) -> bool:
        """
        运动到指定位置
        
        Args:
            position: 目标位置 (0-1000，千分比)
            
        Returns:
            命令是否发送成功
        """
        position = max(POSITION_MIN, min(POSITION_MAX, position))
        
        try:
            result = self.client.write_single_register(REG_POSITION, position)
            if result:
                self._current_position = position
                logger.debug(f"运动到位置: {position}‰")
            return result
        except Exception as e:
            logger.error(f"运动命令失败: {e}")
            raise
    
    def get_target_position(self) -> int:
        """
        获取当前目标位置
        
        Returns:
            目标位置 (0-1000)
        """
        values = self.client.read_holding_registers(REG_POSITION, 1)
        return values[0] if values else 0
    
    def get_current_position(self) -> int:
        """
        获取当前实际位置
        
        Returns:
            当前位置 (0-1000)
        """
        values = self.client.read_holding_registers(REG_POSITION_FEEDBACK, 1)
        return values[0] if values else 0
    
    def jog(self, direction: int) -> bool:
        """
        点动控制
        
        Args:
            direction: 方向 (-1:反向, 0:停止, 1:正向)
            
        Returns:
            命令是否发送成功
        """
        # 将方向值转换为16位有符号整数
        if direction < 0:
            value = 0xFFFF  # -1的补码表示
        else:
            value = direction
        
        try:
            return self.client.write_single_register(REG_JOG, value)
        except Exception as e:
            logger.error(f"点动控制失败: {e}")
            raise
    
    def stop(self) -> bool:
        """
        停止运动
        
        Returns:
            命令是否发送成功
        """
        return self.jog(JOG_STOP)
    
    # ==================== 状态读取 ====================
    
    def get_grip_status(self) -> int:
        """
        获取夹持状态
        
        Returns:
            夹持状态码
            0: 运动中
            1: 到达位置(未夹到物体)
            2: 夹住物体
            3: 物体掉落
            0xFFFF: 初始化未完成
        """
        values = self.client.read_holding_registers(REG_GRIP_STATUS, 1)
        return values[0] if values else GRIP_STATUS_NOT_INIT
    
    def get_current(self) -> int:
        """
        获取当前电流值
        
        Returns:
            电流值 (内部电机电流，非电源电流)
        """
        values = self.client.read_holding_registers(REG_CURRENT_FEEDBACK, 1)
        return values[0] if values else 0
    
    def get_speed_feedback(self) -> int:
        """
        获取当前速度反馈
        
        Returns:
            当前速度
        """
        values = self.client.read_holding_registers(REG_SPEED_FEEDBACK, 1)
        return values[0] if values else 0
    
    def get_error_code(self) -> int:
        """
        获取错误码
        
        Returns:
            错误码 (0表示无错误)
        """
        values = self.client.read_holding_registers(REG_ERROR_FEEDBACK, 1)
        return values[0] if values else 0
    
    def get_motor_temperature(self) -> int:
        """
        获取电机温度
        
        Returns:
            电机温度(摄氏度)
        """
        values = self.client.read_holding_registers(REG_MOTOR_TEMP, 1)
        # 温度值可能是有符号数
        temp = values[0] if values else 0
        if temp > 32767:
            temp -= 65536
        return temp
    
    def get_io_input_state(self) -> int:
        """
        获取IO输入状态
        
        Returns:
            IO输入状态
            0: Input1无, Input2无
            1: Input1有, Input2无
            2: Input1无, Input2有
            3: Input1有, Input2有
        """
        values = self.client.read_holding_registers(REG_IO_INPUT_STATE, 1)
        return values[0] if values else 0
    
    def get_io_output_state(self) -> int:
        """
        获取IO输出状态
        
        Returns:
            IO输出状态
            0: 运动中
            1: 到位
            2: 夹住物体
            3: 物体掉落
        """
        values = self.client.read_holding_registers(REG_IO_OUTPUT_STATE, 1)
        return values[0] if values else 0
    
    def get_full_status(self) -> GripperStatus:
        """
        获取完整状态
        
        Returns:
            GripperStatus对象
        """
        # 批量读取状态寄存器 (0x0200-0x0206)
        status_values = self.client.read_holding_registers(REG_INIT_STATUS, 7)
        
        # 读取IO状态
        io_values = self.client.read_holding_registers(REG_IO_INPUT_STATE, 2)
        
        # 读取电机温度
        temp_values = self.client.read_holding_registers(REG_MOTOR_TEMP, 1)
        
        return GripperStatus(
            initialized=(status_values[0] == INIT_STATUS_SUCCESS) if len(status_values) > 0 else False,
            grip_status=status_values[1] if len(status_values) > 1 else GRIP_STATUS_NOT_INIT,
            position=status_values[2] if len(status_values) > 2 else 0,
            speed=status_values[3] if len(status_values) > 3 else 0,
            current=status_values[4] if len(status_values) > 4 else 0,
            error_code=status_values[5] if len(status_values) > 5 else ERROR_NONE,
            io_input=io_values[0] if len(io_values) > 0 else 0,
            io_output=io_values[1] if len(io_values) > 1 else 0,
            motor_temp=temp_values[0] if len(temp_values) > 0 else 0,
        )
    
    # ==================== 等待功能 ====================
    
    def wait_for_complete(
        self, 
        timeout: float = 10.0, 
        poll_interval: float = 0.05
    ) -> int:
        """
        等待运动完成
        
        Args:
            timeout: 超时时间(秒)
            poll_interval: 轮询间隔(秒)
            
        Returns:
            最终夹持状态
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_grip_status()
            
            if status != GRIP_STATUS_MOVING:
                logger.debug(f"运动完成，状态: {status}")
                return status
            
            time.sleep(poll_interval)
        
        logger.warning("等待运动完成超时")
        return GRIP_STATUS_MOVING
    
    def wait_for_gripped(
        self, 
        timeout: float = 10.0, 
        poll_interval: float = 0.05
    ) -> bool:
        """
        等待夹住物体
        
        Args:
            timeout: 超时时间(秒)
            poll_interval: 轮询间隔(秒)
            
        Returns:
            是否成功夹住物体
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_grip_status()
            
            if status == GRIP_STATUS_GRIPPED:
                logger.info("成功夹住物体")
                return True
            elif status == GRIP_STATUS_DROPPED:
                logger.warning("物体掉落")
                return False
            elif status == GRIP_STATUS_IN_POSITION:
                logger.info("到位但未检测到物体")
                return False
            
            time.sleep(poll_interval)
        
        logger.warning("等待夹住物体超时")
        return False
    
    # ==================== 高级运动控制 ====================
    
    def grip(
        self, 
        force: Optional[int] = None, 
        speed: Optional[int] = None,
        wait: bool = True,
        timeout: float = 10.0
    ) -> bool:
        """
        夹持动作 (运动到闭合位置)
        
        Args:
            force: 夹持力 (默认使用当前设置)
            speed: 速度 (默认使用当前设置)
            wait: 是否等待完成
            timeout: 等待超时时间
            
        Returns:
            是否成功夹住物体
        """
        if force is not None:
            self.set_force(force)
        if speed is not None:
            self.set_speed(speed)
        
        # 运动到最小位置(闭合)
        self.move_to(POSITION_MIN)
        
        if wait:
            status = self.wait_for_complete(timeout)
            return status == GRIP_STATUS_GRIPPED
        
        return True
    
    def release(
        self, 
        position: int = POSITION_MAX,
        speed: Optional[int] = None,
        wait: bool = True,
        timeout: float = 10.0
    ) -> bool:
        """
        释放动作 (运动到张开位置)
        
        Args:
            position: 张开位置 (默认最大行程)
            speed: 速度 (默认使用当前设置)
            wait: 是否等待完成
            timeout: 等待超时时间
            
        Returns:
            是否成功到位
        """
        if speed is not None:
            self.set_speed(speed)
        
        self.move_to(position)
        
        if wait:
            status = self.wait_for_complete(timeout)
            return status == GRIP_STATUS_IN_POSITION
        
        return True
    
    def pick(
        self,
        pick_position: int,
        force: int = 50,
        speed: int = 30,
        lift_position: Optional[int] = None,
        wait_grip: bool = True,
        timeout: float = 10.0
    ) -> bool:
        """
        执行取物动作
        
        Args:
            pick_position: 取物位置
            force: 夹持力
            speed: 运动速度
            lift_position: 提升位置 (None表示不提升)
            wait_grip: 是否等待夹住物体
            timeout: 超时时间
            
        Returns:
            是否成功取物
        """
        # 设置参数
        self.set_force(force)
        self.set_speed(speed)
        
        # 运动到取物位置
        self.move_to(pick_position)
        self.wait_for_complete(timeout)
        
        # 夹持
        success = self.grip(force=force, speed=speed, wait=wait_grip, timeout=timeout)
        
        if success and lift_position is not None:
            # 提升
            self.move_to(lift_position)
            self.wait_for_complete(timeout)
        
        return success
    
    def place(
        self,
        place_position: int,
        speed: int = 30,
        release_position: int = POSITION_MAX,
        wait: bool = True,
        timeout: float = 10.0
    ) -> bool:
        """
        执行放物动作
        
        Args:
            place_position: 放置位置
            speed: 运动速度
            release_position: 释放后的位置
            wait: 是否等待完成
            timeout: 超时时间
            
        Returns:
            是否成功放物
        """
        self.set_speed(speed)
        
        # 运动到放置位置
        self.move_to(place_position)
        self.wait_for_complete(timeout)
        
        # 释放
        return self.release(position=release_position, wait=wait, timeout=timeout)
    
    # ==================== 错误处理 ====================
    
    def clear_error(self) -> bool:
        """
        清除错误
        
        Returns:
            清除是否成功
        """
        try:
            result = self.client.write_single_register(REG_CLEAR_ERROR, 1)
            if result:
                logger.info("错误已清除")
            return result
        except Exception as e:
            logger.error(f"清除错误失败: {e}")
            raise
    
    def check_error(self) -> Optional[str]:
        """
        检查是否有错误
        
        Returns:
            错误描述，无错误返回None
        """
        error_code = self.get_error_code()
        if error_code != ERROR_NONE:
            return ERROR_DESCRIPTIONS.get(error_code, f"未知错误码: {error_code}")
        return None
    
    # ==================== 参数配置 ====================
    
    def save_parameters(self) -> bool:
        """
        保存参数到Flash
        
        注意: 此操作会持续1-2秒，期间不响应其他命令
        
        Returns:
            保存是否成功
        """
        try:
            logger.info("正在保存参数到Flash...")
            result = self.client.write_single_register(REG_SAVE_FLASH, 1)
            if result:
                time.sleep(2)  # 等待保存完成
                logger.info("参数已保存")
            return result
        except Exception as e:
            logger.error(f"保存参数失败: {e}")
            raise
    
    def set_init_direction(self, direction: int) -> bool:
        """
        设置初始化方向
        
        Args:
            direction: 0-张开方向归零, 1-闭合方向归零
            
        Returns:
            设置是否成功
        """
        return self.client.write_single_register(REG_INIT_DIRECTION, direction)
    
    def set_device_id(self, device_id: int) -> bool:
        """
        设置设备ID
        
        Args:
            device_id: 设备ID (1-247)
            
        Returns:
            设置是否成功
        """
        device_id = max(DEVICE_ID_MIN, min(DEVICE_ID_MAX, device_id))
        return self.client.write_single_register(REG_DEVICE_ID, device_id)
    
    def set_auto_init(self, enable: bool, full: bool = False) -> bool:
        """
        设置上电自动初始化
        
        Args:
            enable: 是否启用
            full: 是否使用完全初始化
            
        Returns:
            设置是否成功
        """
        if enable:
            value = AUTO_INIT_FULL if full else AUTO_INIT_NORMAL
        else:
            value = AUTO_INIT_OFF
        
        return self.client.write_single_register(REG_AUTO_INIT, value)
    
    # ==================== IO控制 ====================
    
    def set_io_mode(self, enable: bool) -> bool:
        """
        设置IO模式开关
        
        Args:
            enable: 是否开启IO模式
            
        Returns:
            设置是否成功
        """
        return self.client.write_single_register(REG_IO_MODE_SWITCH, 1 if enable else 0)
    
    def set_io_parameters(
        self, 
        group: int, 
        position: int, 
        force: int, 
        speed: int
    ) -> bool:
        """
        设置IO参数组
        
        Args:
            group: 参数组 (1-4)
            position: 位置 (0-1000)
            force: 力值 (20-100)
            speed: 速度 (1-100)
            
        Returns:
            设置是否成功
        """
        if group < 1 or group > 4:
            raise ValueError("参数组必须在1-4之间")
        
        position = max(POSITION_MIN, min(POSITION_MAX, position))
        force = max(FORCE_MIN, min(FORCE_MAX, force))
        speed = max(SPEED_MIN, min(SPEED_MAX, speed))
        
        # 计算寄存器地址
        base_addr = REG_IO_GROUP1_POS + (group - 1) * 3
        
        # 批量写入
        values = [position, force, speed]
        return self.client.write_multiple_registers(base_addr, values)
    
    def test_io_group(self, group: int) -> bool:
        """
        测试IO参数组
        
        Args:
            group: 参数组 (1-4)
            
        Returns:
            命令是否发送成功
        """
        if group < 1 or group > 4:
            raise ValueError("参数组必须在1-4之间")
        
        return self.client.write_single_register(REG_IO_TEST, group)
    
    # ==================== 工具方法 ====================
    
    def __enter__(self):
        """上下文管理器入口"""
        if not self.is_connected():
            self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"PGEAGripper(port={self.port}, id={self.slave_id}, connected={self.is_connected()})"

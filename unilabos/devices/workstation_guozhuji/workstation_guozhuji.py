"""
工作站自动液体收集系统
集成: 京飞光谱仪 + XY35电机(X/Y轴) + 润泽注射泵
"""

import time
import numpy as np
from collections import deque
from typing import Optional, Tuple, Dict, List, Union
from dataclasses import dataclass

# 🔧 继承WorkstationBase以获得工作站能力
from unilabos.devices.workstation.workstation_base import WorkstationBase
from unilabos.devices.jingfei.Jingfei import JingfeiSpectrometer
from unilabos.devices.workstation_guozhuji.xy35motor import XY35Motor
from unilabos.devices.workstation_guozhuji.runze import RunzeSyringePump
from unilabos.ros.nodes.presets.workstation import ROS2WorkstationNode
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode


@dataclass
class CollectionConfig:
    """液体收集配置参数"""
    # 光谱监测参数
    monitor_wavelength: int = 280  # 监测波长(nm)
    monitor_interval: float = 0.5  # 监测间隔(秒)
    slope_threshold: float = 0.1  # 斜率阈值(吸光度/秒)
    slope_window_size: int = 5  # 计算斜率的数据窗口大小
    
    # 电机移动参数
    x_move_distance: float = 100.0  # X轴移动距离(mm)
    y_move_distance: float = 50.0   # Y轴移动距离(mm)
    motor_speed: float = 10.0       # 电机速度(mm/s)
    motor_acceleration: int = 5000  # 电机加速度(rpm/s)
    
    # 泵参数
    pump_air_inlet_valve: str = "I"   # 进气阀门位置
    pump_air_outlet_valve: str = "O"  # 出气阀门位置
    pump_blow_volume: float = 10.0    # 吹干体积(mL)
    pump_blow_cycles: int = 3         # 吹干循环次数
    pump_aspirate_velocity: float = 5.0   # 吸气速度(mL/s)
    pump_dispense_velocity: float = 8.0   # 吹气速度(mL/s)


# 🔧 继承WorkstationBase获得工作站能力
class AutoLiquidCollectionWorkstation(WorkstationBase):
    """自动液体收集工作站 - 协调多个设备的联动操作"""

    # 🔧 支持两种节点类型
    _ros_node: Union[ROS2WorkstationNode, BaseROS2DeviceNode]
    _parent_station: Optional[ROS2WorkstationNode] = None
    
    def __init__(
        self,
        deck=None,
        config: Optional[Union[CollectionConfig, Dict]] = None,
        **kwargs
    ):
        """初始化工作站"""
        # 🔧 先调用父类初始化（WorkstationBase会处理deck、children等参数）
        super().__init__(deck=deck, **kwargs)
        
        # 🔧 导入dataclasses的fields函数
        from dataclasses import fields
        
        # 🔧 获取CollectionConfig的所有字段名
        collection_config_fields = {f.name for f in fields(CollectionConfig)}
        
        # 🔧 只保留CollectionConfig认可的参数（过滤掉protocol_type、children等）
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in collection_config_fields}
        
        # 配置初始化
        if config is None and filtered_kwargs:
            self.config = CollectionConfig(**filtered_kwargs)
        elif config is None and not filtered_kwargs:
            self.config = CollectionConfig()
        elif isinstance(config, dict):
            filtered_dict = {k: v for k, v in config.items() if k in collection_config_fields}
            self.config = CollectionConfig(**filtered_dict)
        elif isinstance(config, CollectionConfig):
            self.config = config
        else:
            self.config = CollectionConfig()
        
        # 数据记录
        self.absorbance_history: deque = deque(maxlen=self.config.slope_window_size)
        self.time_history: deque = deque(maxlen=self.config.slope_window_size)
        self.is_collecting: bool = False
        
        print("\n" + "="*80)
        print("✓ 工作站协调器初始化完成")
        print(f"  配置: {self.config}")
        print("="*80)
    
    def post_init(self, ros_node: Union[ROS2WorkstationNode, BaseROS2DeviceNode]):
        """后初始化 - 绑定ROS节点"""
        super().post_init(ros_node)
        self._ros_node = ros_node
        
        # 🔧 注意：post_init 接收的是设备自己的节点，不是父节点
        # 父工作站引用通过 bind_parent_station() 单独注入（在 workstation.py 中调用）
        
        print(f"\n✓ 协调器的ROS节点已创建: {ros_node.device_id}")
        print(f"  节点类型: {type(ros_node).__name__}")
        
        if isinstance(ros_node, ROS2WorkstationNode):
            print(f"  自己的 sub_devices 数量: {len(ros_node.sub_devices)}")
            # 注意：这是协调器自己的空工作站节点，不是父节点

    def _get_station_node(self) -> ROS2WorkstationNode:
        """获取父工作站节点（用于访问sub_devices）"""
        if self._parent_station:
            # 使用父工作站节点（通过 bind_parent_station 注入）
            return self._parent_station
        else:
            raise RuntimeError(
                "协调器无法访问父工作站节点。\n"
                f"当前 _parent_station: {self._parent_station}\n"
                f"请确保在 workstation.py 中正确调用了 bind_parent_station()"
            )
    
    def bind_parent_station(self, parent_station: ROS2WorkstationNode):
        """手动绑定父工作站节点（用于Python脚本）"""
        self._parent_station = parent_station
        print(f"\n✓ 手动绑定父工作站: {parent_station.device_id}")
        print(f"✓ 可访问的子设备: {list(parent_station.sub_devices.keys())}")

    def run_sth(self):
        """测试方法"""
        station = self._get_station_node()
        motor_x: XY35Motor = station.sub_devices["motor_x"].driver_instance
        motor_x.move_to_position()
        print(station.sub_devices["motor_x"])
    
    # ==================== 电机控制方法 ====================
    
    def initialize_motors(self) -> bool:
        """初始化电机 - 回零操作"""
        print("\n" + "="*80)
        print("开始电机归零操作")
        print("="*80)
        
        try:
            station = self._get_station_node()
            motor_x: XY35Motor = station.sub_devices["motor_x"].driver_instance
            motor_y: XY35Motor = station.sub_devices["motor_y"].driver_instance
            
            # X轴使能并归零
            print("\n>>> X轴电机归零...")
            motor_x.enable()
            time.sleep(0.5)
            motor_x.zero(speed=-200)
            print("等待X轴归零完成...")
            if not motor_x.wait_until_stopped(timeout=60):
                print("✗ X轴归零超时或失败")
                return False
            print("✓ X轴归零完成")
            
            # Y轴使能并归零
            print("\n>>> Y轴电机归零...")
            motor_y.enable()
            time.sleep(0.5)
            motor_y.zero(speed=-200)
            print("等待Y轴归零完成...")
            if not motor_y.wait_until_stopped(timeout=60):
                print("✗ Y轴归零超时或失败")
                return False
            print("✓ Y轴归零完成")
            
            print("\n" + "="*80)
            print("✓ 电机归零操作完成")
            print("="*80)
            return True
            
        except Exception as e:
            print(f"\n✗ 电机归零失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def move_motors_to_position(self, x_distance: float, y_distance: float, 
                               speed: float = None, acceleration: int = None) -> bool:
        """移动电机到指定位置"""
        speed = speed or self.config.motor_speed
        acceleration = acceleration or self.config.motor_acceleration
        
        print("\n" + "="*80)
        print(f"移动电机: X={x_distance}mm, Y={y_distance}mm")
        print("="*80)
        
        try:
            station = self._get_station_node()
            motor_x: XY35Motor = station.sub_devices["motor_x"].driver_instance
            motor_y: XY35Motor = station.sub_devices["motor_y"].driver_instance
            
            # X轴移动
            print(f"\n>>> X轴移动 {x_distance} mm...")
            success_x = motor_x.move_distance(
                distance_mm=x_distance,
                speed_mm_per_sec=speed,
                acceleration=acceleration
            )
            
            if not success_x:
                print("✗ X轴移动指令发送失败")
                return False
            
            # Y轴移动
            print(f"\n>>> Y轴移动 {y_distance} mm...")
            success_y = motor_y.move_distance(
                distance_mm=y_distance,
                speed_mm_per_sec=speed,
                acceleration=acceleration
            )
            
            if not success_y:
                print("✗ Y轴移动指令发送失败")
                return False
            
            # 等待到位
            print("\n等待X轴到位...")
            if not motor_x.wait_until_stopped(timeout=30):
                print("✗ X轴移动超时")
                return False
            print("✓ X轴到位")
            
            print("等待Y轴到位...")
            if not motor_y.wait_until_stopped(timeout=30):
                print("✗ Y轴移动超时")
                return False
            print("✓ Y轴到位")
            
            print("\n" + "="*80)
            print("✓ 电机已到达目标位置")
            print("="*80)
            return True
            
        except Exception as e:
            print(f"\n✗ 电机移动失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def move_motors_to_collection_position(self) -> bool:
        """移动电机到液体收集位置"""
        return self.move_motors_to_position(
            x_distance=self.config.x_move_distance,
            y_distance=self.config.y_move_distance
        )
    
    # ==================== 泵控制方法 ====================

    def sample_loading(
        self,
        inlet_valve_position: Union[int, str, float],
        outlet_valve_position: Union[int, str, float],
        volume: float,
        aspirate_velocity: float = None,
        dispense_velocity: float = None,
        wait_time_after_aspirate: float = 0.5,
        wait_time_after_dispense: float = 0.5
    ) -> Dict:
        """执行上样操作"""
        print("\n" + "="*80)
        print("执行上样操作")
        print("="*80)
        
        station = self._get_station_node()
        pump: RunzeSyringePump = station.sub_devices["guozhuji_pump"].driver_instance
        
        return pump.sample_loading(
            inlet_valve_position=inlet_valve_position,
            outlet_valve_position=outlet_valve_position,
            volume=volume,
            aspirate_velocity=aspirate_velocity,
            dispense_velocity=dispense_velocity,
            wait_time_after_aspirate=wait_time_after_aspirate,
            wait_time_after_dispense=wait_time_after_dispense
        )

    def blow_dry(
        self,
        air_inlet_valve_position: Union[int, str, float] = None,
        air_outlet_valve_position: Union[int, str, float] = None,
        volume: float = None,
        cycles: int = None,
        aspirate_velocity: float = None,
        dispense_velocity: float = None,
        wait_time_after_aspirate: float = 0.2,
        wait_time_after_dispense: float = 0.2,
        wait_time_between_cycles: float = 0.1
    ) -> Dict:
        """执行吹干操作"""
        air_inlet_valve_position = air_inlet_valve_position or self.config.pump_air_inlet_valve
        air_outlet_valve_position = air_outlet_valve_position or self.config.pump_air_outlet_valve
        volume = volume or self.config.pump_blow_volume
        cycles = cycles or self.config.pump_blow_cycles
        aspirate_velocity = aspirate_velocity or self.config.pump_aspirate_velocity
        dispense_velocity = dispense_velocity or self.config.pump_dispense_velocity
    
        print("\n" + "="*80)
        print("执行吹干操作")
        print("="*80)
    
        station = self._get_station_node()
        pump: RunzeSyringePump = station.sub_devices["guozhuji_pump"].driver_instance
    
        return pump.blow_dry(
            air_inlet_valve_position=air_inlet_valve_position,
            air_outlet_valve_position=air_outlet_valve_position,
            volume=volume,
            cycles=cycles,
            aspirate_velocity=aspirate_velocity,
            dispense_velocity=dispense_velocity,
            wait_time_after_aspirate=wait_time_after_aspirate,
            wait_time_after_dispense=wait_time_after_dispense,
            wait_time_between_cycles=wait_time_between_cycles
        )

    def collect_liquid(self) -> bool:
        """使用泵收集液体"""
        try:
            result = self.blow_dry()
            if result.get("status") == "success":
                print("\n✓ 液体收集完成")
                return True
            else:
                print(f"\n✗ 液体收集失败: {result.get('error')}")
                return False
        except Exception as e:
            print(f"\n✗ 液体收集异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== 光谱仪控制方法 ====================
    
    def calibrate_spectrometer(self) -> bool:
        """校准光谱仪"""
        station = self._get_station_node()
        spectrometer: JingfeiSpectrometer = station.sub_devices["jingfei_spectrometer"].driver_instance
        return spectrometer.calibrate()

    def measure_absorbance(self, wavelength: int = None, verbose: bool = False) -> Optional[float]:
        """测量吸光度"""
        wavelength = wavelength or self.config.monitor_wavelength
        station = self._get_station_node()
        spectrometer: JingfeiSpectrometer = station.sub_devices["jingfei_spectrometer"].driver_instance
        return spectrometer.measure_absorbance_at_wavelength(
            wavelength=wavelength,
            verbose=verbose
        )
    
    def calculate_slope(self) -> Optional[float]:
        """计算吸光度斜率"""
        if len(self.time_history) < 2:
            return None
        times = np.array(self.time_history)
        absorbances = np.array(self.absorbance_history)
        coefficients = np.polyfit(times, absorbances, 1)
        return coefficients[0]
    
    # ==================== 自动流程 ====================
    
    def run_auto_collection(self, max_duration: Optional[float] = None) -> Dict:
        """运行自动液体收集流程"""
        print("\n" + "="*80)
        print("开始自动液体收集流程")
        print("="*80)
        
        station = self._get_station_node()
        spectrometer: JingfeiSpectrometer = station.sub_devices["jingfei_spectrometer"].driver_instance
        
        if spectrometer.zeroline is None or spectrometer.baseline is None:
            print("✗ 光谱仪未校准")
            return {"status": "error", "message": "光谱仪未校准"}
        
        stats = {
            "status": "running",
            "start_time": time.time(),
            "data_points": 0,
            "collection_triggered": False,
            "collection_success": False,
            "absorbance_records": []
        }
        
        print(f"\n监测波长: {self.config.monitor_wavelength} nm")
        print(f"监测间隔: {self.config.monitor_interval} 秒")
        print(f"斜率阈值: {self.config.slope_threshold}")
        print("-" * 80)
        
        start_time = time.time()
        
        try:
            while True:
                current_time = time.time() - start_time
                
                if max_duration and current_time > max_duration:
                    break
                
                absorbance = self.measure_absorbance(verbose=False)
                if absorbance is None:
                    time.sleep(self.config.monitor_interval)
                    continue
                
                self.time_history.append(current_time)
                self.absorbance_history.append(absorbance)
                stats["data_points"] += 1
                stats["absorbance_records"].append({"time": current_time, "absorbance": absorbance})
                
                slope = self.calculate_slope()
                
                if not self.is_collecting and slope is not None and slope > self.config.slope_threshold:
                    print(f"\n⚡ 触发收集! 斜率={slope:.4f}")
                    self.is_collecting = True
                    stats["collection_triggered"] = True
                    stats["trigger_time"] = current_time
                    stats["trigger_slope"] = slope
                    
                    if self.move_motors_to_collection_position():
                        if self.collect_liquid():
                            stats["collection_success"] = True
                            print("\n✓ 收集完成")
                            break
                
                time.sleep(self.config.monitor_interval)
                
        except KeyboardInterrupt:
            print("\n手动停止")
            stats["status"] = "manual_stop"
        except Exception as e:
            print(f"\n✗ 异常: {e}")
            stats["status"] = "error"
            stats["error"] = str(e)
        finally:
            stats["end_time"] = time.time()
            stats["total_duration"] = stats["end_time"] - stats["start_time"]
        
        return stats
    
    def close(self):
        """关闭设备"""
        print("\n关闭设备...")
        try:
            station = self._get_station_node()
            station.sub_devices["motor_x"].driver_instance.disable()
            station.sub_devices["motor_y"].driver_instance.disable()
        except:
            pass
        print("✓ 设备已关闭")
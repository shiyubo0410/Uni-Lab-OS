from threading import Lock, Event
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock, Event
from typing import Union, Optional

import serial.tools.list_ports
from serial import Serial
from serial.serialutil import SerialException


class RunzeSyringePumpMode(Enum):
    Normal = 0
    AccuratePos = 1
    AccuratePosVel = 2


pulse_freq_grades = {
    6000: "0",
    5600: "1",
    5000: "2",
    4400: "3",
    3800: "4",
    3200: "5",
    2600: "6",
    2200: "7",
    2000: "8",
    1800: "9",
    1600: "10",
    1400: "11",
    1200: "12",
    1000: "13",
    800: "14",
    600: "15",
    400: "16",
    200: "17",
    190: "18",
    180: "19",
    170: "20",
    160: "21",
    150: "22",
    140: "23",
    130: "24",
    120: "25",
    110: "26",
    100: "27",
    90: "28",
    80: "29",
    70: "30",
    60: "31",
    50: "32",
    40: "33",
    30: "34",
    20: "35",
    18: "36",
    16: "37",
    14: "38",
    12: "39",
    10: "40",
}


class RunzeSyringePumpConnectionError(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class RunzeSyringePumpInfo:
    port: str
    address: str = "1"

    max_volume: float = 25.0
    mode: RunzeSyringePumpMode = RunzeSyringePumpMode.Normal

    def create(self):
        return RunzeSyringePump(self.port, self.address, self.max_volume, self.mode)


class RunzeSyringePump:
    def __init__(self, port: str, address: str = "1", max_volume: float = 25.0, mode: RunzeSyringePumpMode = None ,**kwargs):
        self.port = port
        self.address = address

        self.max_volume = max_volume
        self.total_steps = self.total_steps_vel = 6000

        self._status = "Idle"
        self._mode = mode
        self._max_velocity = 0
        self._valve_position = "I"
        self._position = 0

        try:
            # if port in serial_ports and serial_ports[port].is_open:
            #     self.hardware_interface = serial_ports[port]
            # else:
            #     serial_ports[port] = self.hardware_interface = Serial(
            #         baudrate=9600,
            #         port=port
            #     )
            self.hardware_interface = Serial(baudrate=9600, port=port)

        except (OSError, SerialException) as e:
            # raise RunzeSyringePumpConnectionError from e
            self.hardware_interface = port

        self._busy = False
        self._closing = False
        self._error_event = Event()
        self._query_lock = Lock()
        self._run_lock = Lock()

    def _adjust_total_steps(self):
        self.total_steps = 6000 if self.mode == RunzeSyringePumpMode.Normal else 48000
        self.total_steps_vel = 48000 if self.mode == RunzeSyringePumpMode.AccuratePosVel else 6000

    def send_command(self, full_command: str):
        full_command_data = bytearray(full_command, "ascii")
        response = self.hardware_interface.write(full_command_data)
        time.sleep(0.05)
        output = self._receive(self.hardware_interface.read_until(b"\n"))
        return output

    def _query(self, command: str):
        with self._query_lock:
            if self._closing:
                raise RunzeSyringePumpConnectionError

            run = "R" if "?" not in command else ""
            full_command = f"/{self.address}{command}{run}\r\n"

            output = self.send_command(full_command)[3:-3]
        return output

    def _parse(self, data: bytes, dtype: Optional[type] = None):
        response = data.decode()

        if dtype == bool:
            return response == "1"
        elif dtype == int:
            return int(response)
        else:
            return response

    def _receive(self, data: bytes):
        ascii_string = "".join(chr(byte) for byte in data)
        was_busy = self._busy
        self._busy = ((data[0] & (1 << 5)) < 1) or ascii_string.startswith("@")
        return ascii_string

    def _run(self, command: str):
        with self._run_lock:
            try:
                response = self._query(command)
                while True:
                    time.sleep(0.5)  # Wait for 0.5 seconds before polling again

                    status = self.get_status()
                    if status == "Idle":
                        break
            finally:
                pass
        return response

    def initialize(self):
        print("Initializing Runze Syringe Pump")
        response = self._run("Z")
        # if self.mode:
        #     self.set_mode(self.mode)
        # else:
        #     # self.mode = RunzeSyringePumpMode.Normal
        #     # self.set_mode(self.mode)
        #     self.mode = self.get_mode()
        return response

    # Settings

    def set_baudrate(self, baudrate):
        if baudrate == 9600:
            return self._run("U41")
        elif baudrate == 38400:
            return self._run("U47")
        else:
            raise ValueError("Unsupported baudrate")

    # Device Status
    @property
    def status(self) -> str:
        return self._status

    def _standardize_status(self, status_raw):
        return "Idle" if status_raw == "`" else "Busy"

    def get_status(self):
        status_raw = self._query("Q")
        self._status = self._standardize_status(status_raw)
        return self._status

    # Mode Settings and Queries

    @property
    def mode(self) -> int:
        return self._mode

    # def set_mode(self, mode: RunzeSyringePumpMode):
    #     self.mode = mode
    #     self._adjust_total_steps()
    #     command = f"N{mode.value}"
    #     return self._run(command)

    # def get_mode(self):
    #     response = self._query("?28")
    #     status_raw, mode = response[0], int(response[1])
    #     self.mode = RunzeSyringePumpMode._value2member_map_[mode]
    #     self._adjust_total_steps()
    #     return self.mode

    # Speed Settings and Queries

    @property
    def max_velocity(self) -> float:
        return self._max_velocity

    def set_max_velocity(self, velocity: float):
        self._max_velocity = velocity
        pulse_freq = int(velocity / self.max_volume * self.total_steps_vel)
        pulse_freq = min(6000, pulse_freq)
        return self._run(f"V{pulse_freq}")

    def get_max_velocity(self):
        response = self._query("?2")
        status_raw, pulse_freq = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        self._max_velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return self._max_velocity

    def set_velocity_grade(self, velocity: Union[int, str]):
        return self._run(f"S{velocity}")

    def get_velocity_grade(self) -> str:
        response = self._query("?2")
        status_raw, pulse_freq = response[0], int(response[1:])
        g = "-1"
        for freq, grade in pulse_freq_grades.items():
            if pulse_freq >= freq:
                g = grade
                break
        return g

    def get_velocity_init(self) -> tuple:
        response = self._query("?1")
        status_raw, pulse_freq = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return pulse_freq, velocity

    def get_velocity_end(self) -> tuple:
        response = self._query("?3")
        status_raw, pulse_freq = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return pulse_freq, velocity

    # Operations

    # Valve Setpoint and Queries

    @property
    def valve_position(self) -> str:
        return self._valve_position

    def set_valve_position(self, position: Union[int, str, float]):
        if isinstance(position, float):
            position = round(position / 120)
        command = f"I{position}" if isinstance(position, int) or ord(position) <= 57 else position.upper()
        response = self._run(command)
        self._valve_position = f"{position}" if isinstance(position, int) or ord(position) <= 57 else position.upper()
        return response

    def get_valve_position(self) -> str:
        response = self._query("?6")
        status_raw, pos_valve = response[0], response[1].upper()
        self._valve_position = pos_valve
        self._status = self._standardize_status(status_raw)
        return pos_valve

    # Plunger Setpoint and Queries

    @property
    def position(self) -> float:
        return self._position

    def get_position(self):
        response = self._query("?0")
        status_raw, pos_step = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        return pos_step / self.total_steps * self.max_volume

    def set_position(self, position: float, max_velocity: float = None):
        """
        Move to absolute volume (unit: ml)

        Args:
            position (float): absolute position of the plunger, unit: ml
            max_velocity (float): maximum velocity of the plunger, unit: ml/s

        Returns:
            None
        """
        if max_velocity is not None:
            self.set_max_velocity(max_velocity)
            pulse_freq = int(max_velocity / self.max_volume * self.total_steps_vel)
            pulse_freq = min(6000, pulse_freq)
            velocity_cmd = f"V{pulse_freq}"
        else:
            velocity_cmd = ""
        pos_step = int(position / self.max_volume * self.total_steps)
        return self._run(f"{velocity_cmd}A{pos_step}")

    def pull_plunger(self, volume: float):
        """
        Pull a fixed volume (unit: ml)

        Args:
            volume (float): absolute position of the plunger, unit: mL

        Returns:
            None
        """
        pos_step = int(volume / self.max_volume * self.total_steps)
        return self._run(f"P{pos_step}")

    def push_plunger(self, volume: float):
        """
        Push a fixed volume (unit: ml)

        Args:
            volume (float): absolute position of the plunger, unit: mL

        Returns:
            None
        """
        pos_step = int(volume / self.max_volume * self.total_steps)
        return self._run(f"D{pos_step}")

    def get_plunger_position(self) -> float:
        response = self._query("?4")
        status, pos_step = response[0], int(response[1:])
        return pos_step / self.total_steps * self.max_volume

    def stop_operation(self):
        return self._run("T")

    # Queries

    def query_command_buffer_status(self):
        return self._query("?10")

    def query_backlash_position(self):
        return self._query("?12")

    def query_aux_input_status_1(self):
        return self._query("?13")

    def query_aux_input_status_2(self):
        return self._query("?14")

    def query_software_version(self):
        return self._query("?23")

    def wait_error(self):
        self._error_event.wait()

    def close(self):
        if self._closing:
            raise RunzeSyringePumpConnectionError

        self._closing = True
        self.hardware_interface.close()

    @staticmethod
    def list():
        for item in serial.tools.list_ports.comports():
            yield RunzeSyringePumpInfo(port=item.device)

    def sample_loading(
        self,
        inlet_valve_position: Union[int, str, float],
        outlet_valve_position: Union[int, str, float],
        volume: float,
        aspirate_velocity: float = None,
        dispense_velocity: float = None,
        wait_time_after_aspirate: float = 0.5,
        wait_time_after_dispense: float = 0.5
    ):
        """
        执行上样操作：设置阀门位置 -> 吸取液体 -> 切换阀门 -> 排出液体
        
        Args:
            inlet_valve_position (Union[int, str, float]): 进液阀门位置
                - int: 0-9 的位置编号
                - str: "I", "O", "E" 等字符位置
                - float: 角度值(会转换为最近的位置)
            outlet_valve_position (Union[int, str, float]): 出液阀门位置
            volume (float): 液体体积，单位：mL
            aspirate_velocity (float, optional): 吸取速度，单位：mL/s。默认使用当前设置
            dispense_velocity (float, optional): 排出速度，单位：mL/s。默认使用当前设置
            wait_time_after_aspirate (float, optional): 吸取后等待时间，单位：秒。默认0.5秒
            wait_time_after_dispense (float, optional): 排出后等待时间，单位：秒。默认0.5秒
            
        Returns:
            dict: 包含操作状态的字典
            
        Raises:
            ValueError: 如果体积超过最大容量
            RunzeSyringePumpConnectionError: 如果设备连接失败
            
        Example:
            >>> pump.sample_loading(
            ...     inlet_valve_position="I",
            ...     outlet_valve_position="O", 
            ...     volume=5.0,
            ...     aspirate_velocity=2.0,
            ...     dispense_velocity=3.0
            ... )
        """
        # 参数验证
        if volume <= 0:
            raise ValueError(f"体积必须大于0，当前值: {volume}")
        if volume > self.max_volume:
            raise ValueError(f"体积 {volume} mL 超过最大容量 {self.max_volume} mL")
        
        result = {
            "status": "success",
            "steps": [],
            "inlet_valve": inlet_valve_position,
            "outlet_valve": outlet_valve_position,
            "volume": volume,
            "aspirate_velocity": aspirate_velocity,
            "dispense_velocity": dispense_velocity
        }
        
        try:
            # 步骤1: 设置进液阀门位置
            print(f"步骤1: 设置进液阀门位置到 {inlet_valve_position}")
            self.set_valve_position(inlet_valve_position)
            result["steps"].append(f"设置进液阀门: {inlet_valve_position}")
            time.sleep(0.2)  # 短暂等待阀门切换完成
            
            # 步骤2: 吸取液体
            print(f"步骤2: 吸取 {volume} mL 液体")
            if aspirate_velocity is not None:
                self.set_max_velocity(aspirate_velocity)
                result["steps"].append(f"设置吸取速度: {aspirate_velocity} mL/s")
            
            self.pull_plunger(volume)
            result["steps"].append(f"吸取液体: {volume} mL")
            time.sleep(wait_time_after_aspirate)
            
            # 步骤3: 切换到出液阀门位置
            print(f"步骤3: 切换阀门位置到 {outlet_valve_position}")
            self.set_valve_position(outlet_valve_position)
            result["steps"].append(f"设置出液阀门: {outlet_valve_position}")
            time.sleep(0.2)
            
            # 步骤4: 排出液体
            print(f"步骤4: 排出 {volume} mL 液体")
            if dispense_velocity is not None:
                self.set_max_velocity(dispense_velocity)
                result["steps"].append(f"设置排出速度: {dispense_velocity} mL/s")
            
            self.push_plunger(volume)
            result["steps"].append(f"排出液体: {volume} mL")
            time.sleep(wait_time_after_dispense)
            
            # 获取最终状态
            final_position = self.get_position()
            final_valve = self.get_valve_position()
            result["final_position"] = final_position
            result["final_valve"] = final_valve
            
            print(f"上样完成！当前柱塞位置: {final_position:.2f} mL, 阀门位置: {final_valve}")
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"上样操作失败: {e}")
            raise
        
        return result

    def blow_dry(
        self,
        air_inlet_valve_position: Union[int, str, float],
        air_outlet_valve_position: Union[int, str, float],
        volume: float,
        cycles: int = 1,
        aspirate_velocity: float = None,
        dispense_velocity: float = None,
        wait_time_after_aspirate: float = 0.2,
        wait_time_after_dispense: float = 0.2,
        wait_time_between_cycles: float = 0.1
    ):
        """
        执行吹干操作：从指定阀门吸气 -> 从指定阀门吹气，可循环多次
        
        Args:
            air_inlet_valve_position (Union[int, str, float]): 进气阀门位置
                - int: 0-9 的位置编号
                - str: "I", "O", "E" 等字符位置
                - float: 角度值(会转换为最近的位置)
            air_outlet_valve_position (Union[int, str, float]): 出气阀门位置
            volume (float): 每次吸气/吹气的体积，单位：mL
            cycles (int, optional): 吹干循环次数。默认1次
            aspirate_velocity (float, optional): 吸气速度，单位：mL/s。默认使用当前设置
            dispense_velocity (float, optional): 吹气速度，单位：mL/s。默认使用当前设置
            wait_time_after_aspirate (float, optional): 吸气后等待时间，单位：秒。默认0.2秒
            wait_time_after_dispense (float, optional): 吹气后等待时间，单位：秒。默认0.2秒
            wait_time_between_cycles (float, optional): 循环间隔时间，单位：秒。默认0.1秒
            
        Returns:
            dict: 包含操作状态的字典
            
        Raises:
            ValueError: 如果体积超过最大容量或循环次数无效
            RunzeSyringePumpConnectionError: 如果设备连接失败
            
        Example:
            >>> pump.blow_dry(
            ...     air_inlet_valve_position="I",
            ...     air_outlet_valve_position="O",
            ...     volume=10.0,
            ...     cycles=3,
            ...     aspirate_velocity=5.0,
            ...     dispense_velocity=8.0
            ... )
        """
        # 参数验证
        if volume <= 0:
            raise ValueError(f"体积必须大于0，当前值: {volume}")
        if volume > self.max_volume:
            raise ValueError(f"体积 {volume} mL 超过最大容量 {self.max_volume} mL")
        if cycles <= 0:
            raise ValueError(f"循环次数必须大于0，当前值: {cycles}")
        
        result = {
            "status": "success",
            "steps": [],
            "air_inlet_valve": air_inlet_valve_position,
            "air_outlet_valve": air_outlet_valve_position,
            "volume": volume,
            "cycles": cycles,
            "aspirate_velocity": aspirate_velocity,
            "dispense_velocity": dispense_velocity,
            "completed_cycles": 0
        }
        
        try:
            print(f"开始吹干操作，共 {cycles} 个循环")
            
            for cycle in range(1, cycles + 1):
                print(f"\n=== 循环 {cycle}/{cycles} ===")
                
                # 步骤1: 设置进气阀门位置
                print(f"步骤1: 设置进气阀门位置到 {air_inlet_valve_position}")
                self.set_valve_position(air_inlet_valve_position)
                result["steps"].append(f"循环{cycle} - 设置进气阀门: {air_inlet_valve_position}")
                time.sleep(0.2)  # 短暂等待阀门切换完成
                
                # 步骤2: 吸气
                print(f"步骤2: 吸入 {volume} mL 气体")
                if aspirate_velocity is not None:
                    self.set_max_velocity(aspirate_velocity)
                    if cycle == 1:  # 只在第一次循环记录速度设置
                        result["steps"].append(f"设置吸气速度: {aspirate_velocity} mL/s")
                
                self.pull_plunger(volume)
                result["steps"].append(f"循环{cycle} - 吸入气体: {volume} mL")
                time.sleep(wait_time_after_aspirate)
                
                # 步骤3: 切换到出气阀门位置
                print(f"步骤3: 切换阀门位置到 {air_outlet_valve_position}")
                self.set_valve_position(air_outlet_valve_position)
                result["steps"].append(f"循环{cycle} - 设置出气阀门: {air_outlet_valve_position}")
                time.sleep(0.2)
                
                # 步骤4: 吹气
                print(f"步骤4: 吹出 {volume} mL 气体")
                if dispense_velocity is not None:
                    self.set_max_velocity(dispense_velocity)
                    if cycle == 1:  # 只在第一次循环记录速度设置
                        result["steps"].append(f"设置吹气速度: {dispense_velocity} mL/s")
                
                self.push_plunger(volume)
                result["steps"].append(f"循环{cycle} - 吹出气体: {volume} mL")
                time.sleep(wait_time_after_dispense)
                
                result["completed_cycles"] = cycle
                
                # 如果不是最后一个循环，等待一段时间
                if cycle < cycles:
                    time.sleep(wait_time_between_cycles)
            
            # 获取最终状态
            final_position = self.get_position()
            final_valve = self.get_valve_position()
            result["final_position"] = final_position
            result["final_valve"] = final_valve
            
            print(f"\n吹干操作完成！完成 {cycles} 个循环")
            print(f"当前柱塞位置: {final_position:.2f} mL, 阀门位置: {final_valve}")
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["failed_at_cycle"] = result["completed_cycles"] + 1
            print(f"吹干操作在第 {result['failed_at_cycle']} 个循环失败: {e}")
            raise
        
        return result


if __name__ == "__main__":
    r = RunzeSyringePump("COM7", "3", 25.0)
    r.initialize()

from threading import Lock, Event
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Literal, Optional, Union

import serial.tools.list_ports
from serial import Serial
from serial.serialutil import SerialException

from unilabos.devices.wxf.shared_bus import get_serial, release_serial
from unilabos.registry.decorators import action, device, not_action, topic_config, HardwareInterface
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode


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


# 已迁移到 shared_bus.py 公共串口池，与传感器等设备共享同一个 Serial 对象


@dataclass(frozen=True, kw_only=True)
class RunzeSyringePumpInfo:
    port: str
    address: str = "1"

    max_volume: float = 25.0
    mode: RunzeSyringePumpMode = RunzeSyringePumpMode.Normal

    def create(self):
        return RunzeSyringePump(self.port, self.address, self.max_volume, self.mode)


class RunzeSyringePump:
    def __init__(self, port: str, address: str = "1", max_volume: float = 25.0, mode: RunzeSyringePumpMode = None, **kwargs):
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
            self.hardware_interface, self._port_lock = get_serial(port, 9600)
        except (OSError, SerialException) as e:
            self.hardware_interface = port
            self._port_lock = Lock()

        self._busy = False
        self._closing = False
        self._error_event = Event()
        self._query_lock = self._port_lock
        self._run_lock = Lock()

    def _adjust_total_steps(self):
        self.total_steps = 6000 if self.mode == RunzeSyringePumpMode.Normal else 48000
        self.total_steps_vel = 48000 if self.mode == RunzeSyringePumpMode.AccuratePosVel else 6000

    def send_command(self, full_command: str):
        full_command_data = bytearray(full_command, "ascii")
        self.hardware_interface.reset_input_buffer()
        self.hardware_interface.write(full_command_data)
        time.sleep(0.05)
        raw = self.hardware_interface.read_until(b"\n")
        if len(raw) < 4:
            return "\x00\x00\x00`\x00\x00\x00"
        output = self._receive(raw)
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
        if not data:
            return ""
        ascii_string = "".join(chr(byte) for byte in data)
        was_busy = self._busy
        self._busy = ((data[0] & (1 << 5)) < 1) or ascii_string.startswith("@")
        return ascii_string

    def _safe_parse_response(self, response: str):
        """Parse response into (status_char, numeric_value). Returns None on failure."""
        if not response or len(response) < 2:
            return None
        try:
            return response[0], int(response[1:])
        except (ValueError, IndexError):
            return None

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
        response = self._query("Q")
        if not response:
            return self._status
        self._status = self._standardize_status(response[0] if len(response) >= 1 else "")
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
        parsed = self._safe_parse_response(response)
        if parsed is None:
            return self._max_velocity
        status_raw, pulse_freq = parsed
        self._status = self._standardize_status(status_raw)
        self._max_velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return self._max_velocity

    def set_velocity_grade(self, velocity: Union[int, str]):
        return self._run(f"S{velocity}")

    def get_velocity_grade(self) -> str:
        response = self._query("?2")
        parsed = self._safe_parse_response(response)
        if parsed is None:
            return "-1"
        status_raw, pulse_freq = parsed
        g = "-1"
        for freq, grade in pulse_freq_grades.items():
            if pulse_freq >= freq:
                g = grade
                break
        return g

    def get_velocity_init(self) -> tuple:
        response = self._query("?1")
        parsed = self._safe_parse_response(response)
        if parsed is None:
            return 0, 0.0
        status_raw, pulse_freq = parsed
        self._status = self._standardize_status(status_raw)
        velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return pulse_freq, velocity

    def get_velocity_end(self) -> tuple:
        response = self._query("?3")
        parsed = self._safe_parse_response(response)
        if parsed is None:
            return 0, 0.0
        status_raw, pulse_freq = parsed
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
        if not response or len(response) < 2:
            return self._valve_position
        try:
            status_raw, pos_valve = response[0], response[1].upper()
            self._valve_position = pos_valve
            self._status = self._standardize_status(status_raw)
            return pos_valve
        except (IndexError, ValueError):
            return self._valve_position

    # Plunger Setpoint and Queries

    @property
    def position(self) -> float:
        return self._position

    def get_position(self):
        response = self._query("?0")
        parsed = self._safe_parse_response(response)
        if parsed is None:
            return self._position
        status_raw, pos_step = parsed
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

    # 液体来源 -> 阀门口编号映射（进液口）
    LIQUID_SOURCE_MAP = {
        "液体1": 1,
        "液体2": 2,
        "液体3": 3,
    }

    # 目标柱子 -> 阀门口编号映射（出液口）
    COLUMN_TARGET_MAP = {
        "柱1": 4,
        "柱2": 5,
        "柱3": 6,
    }

    # 固定泵速（mL/s）
    FIXED_VELOCITY = 5.0

    def add_liquid(
        self,
        liquid_source: str,
        column_target: str,
        volume: float,
    ):
        """
        加液体操作：从指定液体口吸取液体，注入指定柱子。
        泵速固定为 5 mL/s。

        Args:
            liquid_source (str): 液体来源，可选 "液体1" / "液体2" / "液体3"
            column_target (str): 目标柱子，可选 "柱1" / "柱2" / "柱3"
            volume (float): 液体体积，单位：mL

        Returns:
            dict: 包含操作状态的字典
        """
        if liquid_source not in self.LIQUID_SOURCE_MAP:
            raise ValueError(f"liquid_source 必须为 {list(self.LIQUID_SOURCE_MAP.keys())}，当前值: {liquid_source}")
        if column_target not in self.COLUMN_TARGET_MAP:
            raise ValueError(f"column_target 必须为 {list(self.COLUMN_TARGET_MAP.keys())}，当前值: {column_target}")
        if volume <= 0:
            raise ValueError(f"体积必须大于0，当前值: {volume}")
        if volume > self.max_volume:
            raise ValueError(f"体积 {volume} mL 超过最大容量 {self.max_volume} mL")

        inlet_port = self.LIQUID_SOURCE_MAP[liquid_source]
        outlet_port = self.COLUMN_TARGET_MAP[column_target]

        result = {
            "status": "success",
            "steps": [],
            "liquid_source": liquid_source,
            "column_target": column_target,
            "volume": volume,
        }

        try:
            self.set_max_velocity(self.FIXED_VELOCITY)
            result["steps"].append(f"设置泵速: {self.FIXED_VELOCITY} mL/s")

            print(f"步骤1: 设置进液阀门到 {liquid_source}（口{inlet_port}）")
            self.set_valve_position(inlet_port)
            result["steps"].append(f"设置进液阀门: {liquid_source}（口{inlet_port}）")
            time.sleep(0.2)

            print(f"步骤2: 吸取 {volume} mL 液体")
            self.pull_plunger(volume)
            result["steps"].append(f"吸取液体: {volume} mL")
            time.sleep(0.3)

            print(f"步骤3: 切换阀门到 {column_target}（口{outlet_port}）")
            self.set_valve_position(outlet_port)
            result["steps"].append(f"设置出液阀门: {column_target}（口{outlet_port}）")
            time.sleep(0.2)

            print(f"步骤4: 排出 {volume} mL 液体")
            self.push_plunger(volume)
            result["steps"].append(f"排出液体: {volume} mL")
            time.sleep(0.3)

            final_position = self.get_position()
            final_valve = self.get_valve_position()
            result["final_position"] = final_position
            result["final_valve"] = final_valve
            print(f"加液体完成！当前柱塞位置: {final_position:.2f} mL, 阀门位置: {final_valve}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"加液体操作失败: {e}")
            raise

        return result

    def add_sample(
        self,
        liquid_source: str,
        column_target: str,
        volume: float,
    ):
        """
        加样品操作：从指定样品口吸取样品，注入指定柱子。
        泵速固定为 5 mL/s。

        Args:
            liquid_source (str): 样品来源，可选 "液体1" / "液体2" / "液体3"
            column_target (str): 目标柱子，可选 "柱1" / "柱2" / "柱3"
            volume (float): 样品体积，单位：mL

        Returns:
            dict: 包含操作状态的字典
        """
        if liquid_source not in self.LIQUID_SOURCE_MAP:
            raise ValueError(f"liquid_source 必须为 {list(self.LIQUID_SOURCE_MAP.keys())}，当前值: {liquid_source}")
        if column_target not in self.COLUMN_TARGET_MAP:
            raise ValueError(f"column_target 必须为 {list(self.COLUMN_TARGET_MAP.keys())}，当前值: {column_target}")
        if volume <= 0:
            raise ValueError(f"体积必须大于0，当前值: {volume}")
        if volume > self.max_volume:
            raise ValueError(f"体积 {volume} mL 超过最大容量 {self.max_volume} mL")

        inlet_port = self.LIQUID_SOURCE_MAP[liquid_source]
        outlet_port = self.COLUMN_TARGET_MAP[column_target]

        result = {
            "status": "success",
            "steps": [],
            "liquid_source": liquid_source,
            "column_target": column_target,
            "volume": volume,
        }

        try:
            self.set_max_velocity(self.FIXED_VELOCITY)
            result["steps"].append(f"设置泵速: {self.FIXED_VELOCITY} mL/s")

            print(f"步骤1: 设置进样阀门到 {liquid_source}（口{inlet_port}）")
            self.set_valve_position(inlet_port)
            result["steps"].append(f"设置进样阀门: {liquid_source}（口{inlet_port}）")
            time.sleep(0.2)

            print(f"步骤2: 吸取 {volume} mL 样品")
            self.pull_plunger(volume)
            result["steps"].append(f"吸取样品: {volume} mL")
            time.sleep(0.5)

            print(f"步骤3: 切换阀门到 {column_target}（口{outlet_port}）")
            self.set_valve_position(outlet_port)
            result["steps"].append(f"设置出样阀门: {column_target}（口{outlet_port}）")
            time.sleep(0.2)

            print(f"步骤4: 排出 {volume} mL 样品")
            self.push_plunger(volume)
            result["steps"].append(f"排出样品: {volume} mL")
            time.sleep(0.5)

            final_position = self.get_position()
            final_valve = self.get_valve_position()
            result["final_position"] = final_position
            result["final_valve"] = final_valve
            print(f"加样品完成！当前柱塞位置: {final_position:.2f} mL, 阀门位置: {final_valve}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"加样品操作失败: {e}")
            raise

        return result

    def wait_error(self):
        self._error_event.wait()

    def close(self):
        if self._closing:
            raise RunzeSyringePumpConnectionError

        self._closing = True
        release_serial(self.port)

    @staticmethod
    def list():
        for item in serial.tools.list_ports.comports():
            yield RunzeSyringePumpInfo(port=item.device)


# =====================================================================
# 高层设备类：上样泵1、上样泵2、加液泵
# 三个注射泵协同工作：两台负责上样，一台负责加溶液，共5路通道。
# =====================================================================


@device(
    id="wxf.sample_pump_1",
    category=["pump_and_valve", "wxf", "runze"],
    description="上样泵1 - 负责通道1/2/3的上样操作（8口阀润泽注射泵，含气吹清洗）",
    display_name="上样泵1",
    hardware_interface=HardwareInterface(name="hardware_interface", read="send_command", write="send_command"),
)
class SamplePump1:
    """上样泵1：管理通道1/2/3的样品输送。

    阀门口映射：
      通道1 → 8号口进样, 1号口出样
      通道2 → 7号口进样, 2号口出样
      通道3 → 6号口进样, 3号口出样
      5号口 → 接空气，用于气吹清洗管路
    """

    _ros_node: BaseROS2DeviceNode

    CHANNEL_MAP: Dict[str, Dict[str, int]] = {
        "通道1": {"intake": 4, "outlet": 1},
        "通道2": {"intake": 7, "outlet": 2},
        "通道3": {"intake": 6, "outlet": 3},
    }
    AIR_PORT = 5
    FIXED_VELOCITY = 5.0

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        port: str = "COM9",
        address: str = "1",
        max_volume: float = 25.0,
        **kwargs,
    ):
        self.device_id = device_id or "sample_pump_1"
        self.config = config or {}
        self._port = self.config.get("port", port)
        self._address = self.config.get("address", address)
        self.max_volume = float(self.config.get("max_volume", max_volume))
        self.pump = RunzeSyringePump(self._port, self._address, self.max_volume)
        self._status = "Idle"

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @property
    def hardware_interface(self):
        return self.pump.hardware_interface

    @not_action
    def send_command(self, full_command: str):
        return self.pump.send_command(full_command)

    @property
    @topic_config()
    def status(self) -> str:
        return self._status

    @action(description="初始化上样泵1")
    def initialize(self) -> dict:
        self.pump.initialize()
        self._status = "Ready"
        return {"status": "initialized"}

    @action(description="上样：选择通道(1/2/3)和体积(mL)，将样品打入指定通道")
    def load_sample(
        self,
        channel: Literal["通道1", "通道2", "通道3"],
        volume: float,
    ) -> dict:
        """
        上样操作：从进样口吸取样品注入出样口。

        Args:
            channel: 目标通道
            volume: 样品体积，单位 mL
        """
        if channel not in self.CHANNEL_MAP:
            raise ValueError(f"通道必须为 {list(self.CHANNEL_MAP.keys())}，当前值: {channel}")
        if volume <= 0:
            raise ValueError(f"体积必须大于 0，当前值: {volume}")

        mapping = self.CHANNEL_MAP[channel]
        intake_port = mapping["intake"]
        outlet_port = mapping["outlet"]

        self._status = "Busy"
        result: Dict[str, Any] = {"status": "success", "channel": channel, "volume": volume, "steps": []}

        try:
            self.pump.set_max_velocity(self.FIXED_VELOCITY)
            remaining = volume
            while remaining > 1e-6:
                batch = min(remaining, self.max_volume)

                self.pump.set_valve_position(intake_port)
                time.sleep(0.2)
                self.pump.pull_plunger(batch)
                time.sleep(0.3)

                self.pump.set_valve_position(outlet_port)
                time.sleep(0.2)
                self.pump.push_plunger(batch)
                time.sleep(0.3)

                remaining -= batch
                result["steps"].append(f"注入 {batch:.2f} mL → {channel}")
                print(f"[上样泵1] 注入 {batch:.2f} mL → {channel}，剩余 {max(remaining, 0):.2f} mL")

            self._status = "Idle"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._status = "Error"
            print(f"[上样泵1] 上样失败: {e}")
            raise

        return result

    @action(description="气吹清洗：选择通道(1/2/3)和气吹体积(mL)，用空气吹扫管路")
    def air_blow(
        self,
        channel: Literal["通道1", "通道2", "通道3"],
        volume: float = 25.0,
    ) -> dict:
        """
        气吹清洗：从空气口吸入空气，吹扫指定通道的管路。

        Args:
            channel: 目标通道
            volume: 气吹体积，单位 mL，默认 25.0
        """
        if channel not in self.CHANNEL_MAP:
            raise ValueError(f"通道必须为 {list(self.CHANNEL_MAP.keys())}，当前值: {channel}")
        if volume <= 0:
            raise ValueError(f"体积必须大于 0，当前值: {volume}")

        outlet_port = self.CHANNEL_MAP[channel]["outlet"]

        self._status = "Busy"
        result: Dict[str, Any] = {"status": "success", "channel": channel, "volume": volume, "steps": []}

        try:
            self.pump.set_max_velocity(self.FIXED_VELOCITY)
            remaining = volume
            while remaining > 1e-6:
                batch = min(remaining, self.max_volume)
                self.pump.set_valve_position(self.AIR_PORT)
                time.sleep(0.2)
                self.pump.pull_plunger(batch)
                time.sleep(0.3)
                self.pump.set_valve_position(outlet_port)
                time.sleep(0.2)
                self.pump.push_plunger(batch)
                time.sleep(0.3)
                remaining -= batch
            result["steps"].append(f"气吹清洗完成，共 {volume:.2f} mL")
            print(f"[上样泵1] {channel} 气吹清洗完成，{volume:.2f} mL")

            self._status = "Idle"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._status = "Error"
            print(f"[上样泵1] 气吹失败: {e}")
            raise

        return result

    @action(description="关闭上样泵1连接")
    def close(self):
        self.pump.close()


@device(
    id="wxf.sample_pump_2",
    category=["pump_and_valve", "wxf", "runze"],
    description="上样泵2 - 负责通道4/5的上样操作（8口阀润泽注射泵，含气吹清洗）",
    display_name="上样泵2",
    hardware_interface=HardwareInterface(name="hardware_interface", read="send_command", write="send_command"),
)
class SamplePump2:
    """上样泵2：管理通道4/5的样品输送。

    阀门口映射：
      通道4 → 2号口进样, 8号口出样
      通道5 → 1号口进样, 7号口出样
      4号口 → 接空气，用于气吹清洗管路
    """

    _ros_node: BaseROS2DeviceNode

    CHANNEL_MAP: Dict[str, Dict[str, int]] = {
        "通道4": {"intake": 2, "outlet": 8},
        "通道5": {"intake": 1, "outlet": 7},
    }
    AIR_PORT = 4
    FIXED_VELOCITY = 5.0

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        port: str = "COM9",
        address: str = "2",
        max_volume: float = 25.0,
        **kwargs,
    ):
        self.device_id = device_id or "sample_pump_2"
        self.config = config or {}
        self._port = self.config.get("port", port)
        self._address = self.config.get("address", address)
        self.max_volume = float(self.config.get("max_volume", max_volume))
        self.pump = RunzeSyringePump(self._port, self._address, self.max_volume)
        self._status = "Idle"

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @property
    def hardware_interface(self):
        return self.pump.hardware_interface

    @not_action
    def send_command(self, full_command: str):
        return self.pump.send_command(full_command)

    @property
    @topic_config()
    def status(self) -> str:
        return self._status

    @action(description="初始化上样泵2")
    def initialize(self) -> dict:
        self.pump.initialize()
        self._status = "Ready"
        return {"status": "initialized"}

    @action(description="上样：选择通道(4/5)和体积(mL)，将样品打入指定通道")
    def load_sample(
        self,
        channel: Literal["通道4", "通道5"],
        volume: float,
    ) -> dict:
        """
        上样操作：从进样口吸取样品注入出样口。

        Args:
            channel: 目标通道
            volume: 样品体积，单位 mL
        """
        if channel not in self.CHANNEL_MAP:
            raise ValueError(f"通道必须为 {list(self.CHANNEL_MAP.keys())}，当前值: {channel}")
        if volume <= 0:
            raise ValueError(f"体积必须大于 0，当前值: {volume}")

        mapping = self.CHANNEL_MAP[channel]
        intake_port = mapping["intake"]
        outlet_port = mapping["outlet"]

        self._status = "Busy"
        result: Dict[str, Any] = {"status": "success", "channel": channel, "volume": volume, "steps": []}

        try:
            self.pump.set_max_velocity(self.FIXED_VELOCITY)
            remaining = volume
            while remaining > 1e-6:
                batch = min(remaining, self.max_volume)

                self.pump.set_valve_position(intake_port)
                time.sleep(0.2)
                self.pump.pull_plunger(batch)
                time.sleep(0.3)

                self.pump.set_valve_position(outlet_port)
                time.sleep(0.2)
                self.pump.push_plunger(batch)
                time.sleep(0.3)

                remaining -= batch
                result["steps"].append(f"注入 {batch:.2f} mL → {channel}")
                print(f"[上样泵2] 注入 {batch:.2f} mL → {channel}，剩余 {max(remaining, 0):.2f} mL")

            self._status = "Idle"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._status = "Error"
            print(f"[上样泵2] 上样失败: {e}")
            raise

        return result

    @action(description="气吹清洗：选择通道(4/5)和气吹体积(mL)，用空气吹扫管路")
    def air_blow(
        self,
        channel: Literal["通道4", "通道5"],
        volume: float = 25.0,
    ) -> dict:
        """
        气吹清洗：从空气口吸入空气，吹扫指定通道的管路。

        Args:
            channel: 目标通道
            volume: 气吹体积，单位 mL，默认 25.0
        """
        if channel not in self.CHANNEL_MAP:
            raise ValueError(f"通道必须为 {list(self.CHANNEL_MAP.keys())}，当前值: {channel}")
        if volume <= 0:
            raise ValueError(f"体积必须大于 0，当前值: {volume}")

        outlet_port = self.CHANNEL_MAP[channel]["outlet"]

        self._status = "Busy"
        result: Dict[str, Any] = {"status": "success", "channel": channel, "volume": volume, "steps": []}

        try:
            self.pump.set_max_velocity(self.FIXED_VELOCITY)
            remaining = volume
            while remaining > 1e-6:
                batch = min(remaining, self.max_volume)
                self.pump.set_valve_position(self.AIR_PORT)
                time.sleep(0.2)
                self.pump.pull_plunger(batch)
                time.sleep(0.3)
                self.pump.set_valve_position(outlet_port)
                time.sleep(0.2)
                self.pump.push_plunger(batch)
                time.sleep(0.3)
                remaining -= batch
            result["steps"].append(f"气吹清洗完成，共 {volume:.2f} mL")
            print(f"[上样泵2] {channel} 气吹清洗完成，{volume:.2f} mL")

            self._status = "Idle"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._status = "Error"
            print(f"[上样泵2] 气吹失败: {e}")
            raise

        return result

    @action(description="关闭上样泵2连接")
    def close(self):
        self.pump.close()


@device(
    id="wxf.solution_pump",
    category=["pump_and_valve", "wxf", "runze"],
    description="加液泵 - 负责向5个通道加入3种溶液（8口阀润泽注射泵）",
    display_name="加液泵",
    hardware_interface=HardwareInterface(name="hardware_interface", read="send_command", write="send_command"),
)
class SolutionPump:
    """加液泵：负责将3种溶液分别注入5个通道。

    阀门口映射：
      1号口 → 通道1    2号口 → 通道2    3号口 → 通道3
      4号口 → 通道4    5号口 → 通道5
      6号口 → 溶液1    7号口 → 溶液2    8号口 → 溶液3
    """

    _ros_node: BaseROS2DeviceNode

    SOLUTION_PORT_MAP: Dict[str, int] = {
        "溶液1": 6,
        "溶液2": 7,
        "溶液3": 8,
    }
    CHANNEL_PORT_MAP: Dict[str, int] = {
        "通道1": 1,
        "通道2": 2,
        "通道3": 3,
        "通道4": 4,
        "通道5": 5,
    }
    FIXED_VELOCITY = 5.0

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        port: str = "COM9",
        address: str = "3",
        max_volume: float = 25.0,
        **kwargs,
    ):
        self.device_id = device_id or "solution_pump"
        self.config = config or {}
        self._port = self.config.get("port", port)
        self._address = self.config.get("address", address)
        self.max_volume = float(self.config.get("max_volume", max_volume))
        self.pump = RunzeSyringePump(self._port, self._address, self.max_volume)
        self._status = "Idle"

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    @property
    def hardware_interface(self):
        return self.pump.hardware_interface

    @not_action
    def send_command(self, full_command: str):
        return self.pump.send_command(full_command)

    @property
    @topic_config()
    def status(self) -> str:
        return self._status

    @action(description="初始化加液泵")
    def initialize(self) -> dict:
        self.pump.initialize()
        self._status = "Ready"
        return {"status": "initialized"}

    @action(description="加液：选择溶液(1/2/3)、目标通道(1-5)和体积(mL)")
    def add_solution(
        self,
        solution: Literal["溶液1", "溶液2", "溶液3"],
        channel: Literal["通道1", "通道2", "通道3", "通道4", "通道5"],
        volume: float,
    ) -> dict:
        """
        加液操作：从溶液瓶吸取指定溶液，注入目标通道。

        Args:
            solution: 溶液来源
            channel: 目标通道
            volume: 加液体积，单位 mL
        """
        if solution not in self.SOLUTION_PORT_MAP:
            raise ValueError(f"溶液必须为 {list(self.SOLUTION_PORT_MAP.keys())}，当前值: {solution}")
        if channel not in self.CHANNEL_PORT_MAP:
            raise ValueError(f"通道必须为 {list(self.CHANNEL_PORT_MAP.keys())}，当前值: {channel}")
        if volume <= 0:
            raise ValueError(f"体积必须大于 0，当前值: {volume}")

        solution_port = self.SOLUTION_PORT_MAP[solution]
        channel_port = self.CHANNEL_PORT_MAP[channel]

        self._status = "Busy"
        result: Dict[str, Any] = {
            "status": "success",
            "solution": solution,
            "channel": channel,
            "volume": volume,
            "steps": [],
        }

        try:
            self.pump.set_max_velocity(self.FIXED_VELOCITY)
            remaining = volume
            while remaining > 1e-6:
                batch = min(remaining, self.max_volume)

                self.pump.set_valve_position(solution_port)
                time.sleep(0.2)
                self.pump.pull_plunger(batch)
                time.sleep(0.3)

                self.pump.set_valve_position(channel_port)
                time.sleep(0.2)
                self.pump.push_plunger(batch)
                time.sleep(0.3)

                remaining -= batch
                result["steps"].append(f"注入 {batch:.2f} mL {solution} → {channel}")
                print(f"[加液泵] 注入 {batch:.2f} mL {solution} → {channel}，剩余 {max(remaining, 0):.2f} mL")

            self._status = "Idle"
            print(f"[加液泵] 加液完成: {volume:.2f} mL {solution} → {channel}")
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._status = "Error"
            print(f"[加液泵] 加液失败: {e}")
            raise

        return result

    @action(description="关闭加液泵连接")
    def close(self):
        self.pump.close()


if __name__ == "__main__":
    r = RunzeSyringePump("/dev/tty.usbserial-D30JUGG5", "1", 25.0)
    r.initialize()

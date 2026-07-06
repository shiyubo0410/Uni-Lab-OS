# -*- coding: utf-8 -*-
"""
润泽精密注射泵驱动（新版接入方式：@device 装饰器 + AST 自动扫描）

通信协议：
    - RS-232 / RS-485 串口，默认波特率 9600，8N1
    - 命令格式：/{address}{command}{R}\\r\\n
    - 响应格式：起始字节 + 状态字节 + 数据 + 终止字节

关键命令（节选）：
    Q       查询状态（` 表示 Idle，其他表示 Busy）
    Z       柱塞初始化（满行程一次）
    A{n}    柱塞移动到绝对步数位置
    P{n}    从当前位置吸入 n 步
    D{n}    从当前位置排出 n 步
    I{n}    切换阀门到端口 n
    V{n}    设置最大脉冲频率（速度）
    S{n}    设置速度档位（0-40）
    T       停止运行
    U41/U47 设置波特率（9600 / 38400）
    ?0      查询柱塞当前位置（步）
    ?1      查询起始速度（脉冲频率）
    ?2      查询最大速度（脉冲频率）
    ?3      查询终止速度（脉冲频率）
    ?4      查询柱塞实际位置（步）
    ?6      查询阀门位置
    ?10     查询命令缓冲状态
    ?12     查询回程位置
    ?13/?14 查询辅助输入 1/2 状态
    ?23     查询软件版本

体积 -> 步数：
    pos_step = volume / max_volume * total_steps

使用方式：
    pump = RunzeSyringePump(port="COM5", address="1", max_volume=25.0)
    pump.initialize()
    pump.set_valve_position(1)
    pump.pull_plunger(5.0)
"""

import logging
import time
from enum import Enum
from threading import Event, Lock
from typing import Any, Dict, Optional, Union

import serial.tools.list_ports
from serial import Serial
from serial.serialutil import SerialException

from unilabos.registry.decorators import action, device, not_action, topic_config


class RunzeSyringePumpMode(Enum):
    """注射泵工作模式。"""

    Normal = 0
    AccuratePos = 1
    AccuratePosVel = 2


PULSE_FREQ_GRADES: Dict[int, str] = {
    6000: "0", 5600: "1", 5000: "2", 4400: "3", 3800: "4",
    3200: "5", 2600: "6", 2200: "7", 2000: "8", 1800: "9",
    1600: "10", 1400: "11", 1200: "12", 1000: "13", 800: "14",
    600: "15", 400: "16", 200: "17", 190: "18", 180: "19",
    170: "20", 160: "21", 150: "22", 140: "23", 130: "24",
    120: "25", 110: "26", 100: "27", 90: "28", 80: "29",
    70: "30", 60: "31", 50: "32", 40: "33", 30: "34",
    20: "35", 18: "36", 16: "37", 14: "38", 12: "39",
    10: "40",
}


class RunzeSyringePumpConnectionError(Exception):
    """串口未连接 / 已关闭时抛出的连接异常。"""


@device(
    id="pump_and_valve_runze_sy03b_t06",
    category=["pump_and_valve", "runze"],
    description=(
        "润泽精密注射泵 SY03B-T06，集成多通阀门控制的高精度流体输送系统。"
        "通过 RS-232 / RS-485 串口通信，支持柱塞精密定位、可变速度控制、阀门切换。"
        "适用于微量液体输送、精密进样、化学反应进料等实验室自动化应用。"
    ),
    display_name="润泽注射泵 SY03B-T06",
    version="1.0.0",
)
class RunzeSyringePump:
    """润泽精密注射泵驱动（@device 自动扫描注册）。

    设备 ID（注册表 key）：``pump_and_valve.runze.SY03B-T06``。
    与旧版 ``syringe_pump_with_valve.runze.SY03B-T06`` 区分，便于平滑迁移。
    """

    def __init__(
        self,
        port: str = "COM1",
        address: str = "1",
        max_volume: float = 25.0,
        baudrate: int = 9600,
        mode: Optional[int] = None,
        device_id: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化润泽注射泵。

        Args:
            port[串口号]: 设备占用的串口号，例如 "COM5" / "/dev/ttyUSB0"。
            address[设备地址]: RS-485 总线上的设备地址，默认 "1"。
            max_volume[最大容量(mL)]: 注射器最大容量，单位 mL，默认 25.0。
            baudrate[波特率]: 串口波特率，默认 9600。
            mode[工作模式]: 0=Normal, 1=AccuratePos, 2=AccuratePosVel，默认 Normal。
            device_id[设备ID]: 实例 ID，缺省时使用 'runze_pump'。
        """
        self.device_id = device_id or "runze_pump"
        self.port: str = str(port)
        self.address: str = str(address)
        self.max_volume: float = float(max_volume)
        self.baudrate: int = int(baudrate)
        try:
            self.mode: RunzeSyringePumpMode = (
                RunzeSyringePumpMode(int(mode))
                if mode is not None
                else RunzeSyringePumpMode.Normal
            )
        except (ValueError, TypeError):
            self.mode = RunzeSyringePumpMode.Normal

        self.logger = logging.getLogger(f"RunzeSyringePump.{self.device_id}")

        self._status: str = "Idle"
        self._max_velocity: float = 0.0
        self._valve_position: str = "I"
        self._position: float = 0.0

        self.total_steps: int = 6000
        self.total_steps_vel: int = 6000
        self._adjust_total_steps()

        self._busy: bool = False
        self._closing: bool = False
        self._error_event: Event = Event()
        self._query_lock: Lock = Lock()
        self._run_lock: Lock = Lock()

        self.hardware_interface: Any = self.port
        try:
            self.hardware_interface = Serial(baudrate=self.baudrate, port=self.port)
        except (OSError, SerialException) as exc:
            self.logger.warning(f"串口 {self.port} 打开失败: {exc}")

    # ------------------------------------------------------------------
    # 内部辅助（_ 开头自动跳过 AST 扫描）
    # ------------------------------------------------------------------
    def _adjust_total_steps(self) -> None:
        self.total_steps = 6000 if self.mode == RunzeSyringePumpMode.Normal else 48000
        self.total_steps_vel = (
            48000 if self.mode == RunzeSyringePumpMode.AccuratePosVel else 6000
        )

    def _standardize_status(self, status_raw: str) -> str:
        return "Idle" if status_raw == "`" else "Busy"

    def _receive(self, data: bytes) -> str:
        ascii_string = "".join(chr(byte) for byte in data)
        if data:
            self._busy = ((data[0] & (1 << 5)) < 1) or ascii_string.startswith("@")
        return ascii_string

    def _send_command_raw(self, full_command: str) -> str:
        if not hasattr(self.hardware_interface, "write"):
            raise RunzeSyringePumpConnectionError(f"串口 {self.port} 未连接")
        full_command_data = bytearray(full_command, "ascii")
        self.hardware_interface.write(full_command_data)
        time.sleep(0.05)
        return self._receive(self.hardware_interface.read_until(b"\n"))

    def _query(self, command: str) -> str:
        with self._query_lock:
            if self._closing:
                raise RunzeSyringePumpConnectionError("驱动已关闭")
            run_suffix = "R" if "?" not in command else ""
            full_command = f"/{self.address}{command}{run_suffix}\r\n"
            output = self._send_command_raw(full_command)
            return output[3:-3] if len(output) >= 6 else output

    def _run(self, command: str) -> str:
        """发送指令并轮询设备直到 Idle。"""
        with self._run_lock:
            response = self._query(command)
            while True:
                time.sleep(0.5)
                if self.get_status() == "Idle":
                    break
        return response

    # ------------------------------------------------------------------
    # 通用动作（注射泵子类型标准动作）
    # ------------------------------------------------------------------
    @action(description="柱塞初始化（满行程一次，约 3~5s）")
    def initialize(self) -> Dict[str, Any]:
        """复位注射泵柱塞到原点位置。"""
        try:
            response = self._run("Z")
            return {"success": True, "response": response, "message": "初始化完成"}
        except Exception as exc:
            self.logger.error(f"初始化失败: {exc}")
            return {"success": False, "error": str(exc)}

    @action(description="设置串口波特率（仅支持 9600 / 38400）")
    def set_baudrate(self, baudrate: int = 9600) -> Dict[str, Any]:
        """
        Args:
            baudrate[波特率]: 9600 或 38400。
        """
        baud_int = int(baudrate)
        if baud_int == 9600:
            response = self._run("U41")
        elif baud_int == 38400:
            response = self._run("U47")
        else:
            return {"success": False, "error": f"不支持的波特率: {baud_int}"}
        return {"success": True, "response": response, "baudrate": baud_int}

    @action(description="设置最大柱塞速度（mL/s）")
    def set_max_velocity(self, velocity: float) -> Dict[str, Any]:
        """
        Args:
            velocity[最大速度(mL/s)]: 最大柱塞移动速度，单位 mL/s。
        """
        v = float(velocity)
        self._max_velocity = v
        pulse_freq = int(v / self.max_volume * self.total_steps_vel)
        pulse_freq = min(6000, pulse_freq)
        response = self._run(f"V{pulse_freq}")
        return {"success": True, "response": response, "velocity": v}

    @action(description="设置速度档位（0-40，0 最快）")
    def set_velocity_grade(self, velocity: Union[int, str]) -> Dict[str, Any]:
        """
        Args:
            velocity[速度档位]: 0~40 之间的整数或字符串。
        """
        response = self._run(f"S{velocity}")
        return {"success": True, "response": response, "grade": str(velocity)}

    @action(description="切换阀门到指定端口")
    def set_valve_position(self, position: Union[int, str, float]) -> Dict[str, Any]:
        """
        Args:
            position[阀门端口]: 端口编号（int/str/float），例如 1~8 或 'I'/'O'。
        """
        pos = position
        if isinstance(pos, float):
            pos = round(pos / 120)
        if isinstance(pos, int) or (isinstance(pos, str) and ord(pos) <= 57):
            command = f"I{pos}"
            new_pos = f"{pos}"
        else:
            command = pos.upper()
            new_pos = pos.upper()
        response = self._run(command)
        self._valve_position = new_pos
        return {
            "success": True,
            "response": response,
            "valve_position": self._valve_position,
        }

    @action(description="移动柱塞到绝对位置（mL）")
    def set_position(
        self, position: float, max_velocity: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Args:
            position[目标位置(mL)]: 柱塞绝对位置，单位 mL。
            max_velocity[最大速度(mL/s)]: 移动过程的最大速度，单位 mL/s，缺省沿用上次设置。
        """
        if max_velocity is not None:
            self.set_max_velocity(max_velocity)
            pulse_freq = int(float(max_velocity) / self.max_volume * self.total_steps_vel)
            pulse_freq = min(6000, pulse_freq)
            velocity_cmd = f"V{pulse_freq}"
        else:
            velocity_cmd = ""
        pos_step = int(float(position) / self.max_volume * self.total_steps)
        response = self._run(f"{velocity_cmd}A{pos_step}")
        self._position = float(position)
        return {"success": True, "response": response, "position": float(position)}

    @action(description="抽取液体（mL，相对当前位置）")
    def pull_plunger(self, volume: float) -> Dict[str, Any]:
        """
        Args:
            volume[抽取体积(mL)]: 单位 mL。
        """
        pos_step = int(float(volume) / self.max_volume * self.total_steps)
        response = self._run(f"P{pos_step}")
        return {"success": True, "response": response, "volume": float(volume)}

    @action(description="排出液体（mL，相对当前位置）")
    def push_plunger(self, volume: float) -> Dict[str, Any]:
        """
        Args:
            volume[排出体积(mL)]: 单位 mL。
        """
        pos_step = int(float(volume) / self.max_volume * self.total_steps)
        response = self._run(f"D{pos_step}")
        return {"success": True, "response": response, "volume": float(volume)}

    @action(description="停止当前运行的指令")
    def stop_operation(self) -> Dict[str, Any]:
        try:
            response = self._run("T")
            return {"success": True, "response": response}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 通信原语（开放给上层调用，但属于高级用法）
    # ------------------------------------------------------------------
    @action(description="发送原始 ASCII 指令到串口（高级用法）")
    def send_command(self, full_command: str) -> Dict[str, Any]:
        """
        Args:
            full_command[原始指令]: 完整 ASCII 指令字符串，例如 "/1ZR\\r\\n"。
        """
        try:
            response = self._send_command_raw(full_command)
            return {"success": True, "response": response}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 查询动作
    # ------------------------------------------------------------------
    @action(description="查询命令缓冲区状态")
    def query_command_buffer_status(self) -> Dict[str, Any]:
        return {"success": True, "data": self._query("?10")}

    @action(description="查询回程位置")
    def query_backlash_position(self) -> Dict[str, Any]:
        return {"success": True, "data": self._query("?12")}

    @action(description="查询辅助输入 1 状态")
    def query_aux_input_status_1(self) -> Dict[str, Any]:
        return {"success": True, "data": self._query("?13")}

    @action(description="查询辅助输入 2 状态")
    def query_aux_input_status_2(self) -> Dict[str, Any]:
        return {"success": True, "data": self._query("?14")}

    @action(description="查询软件版本")
    def query_software_version(self) -> Dict[str, Any]:
        return {"success": True, "data": self._query("?23")}

    @action(description="阻塞等待错误事件")
    def wait_error(self) -> Dict[str, Any]:
        self._error_event.wait()
        return {"success": True}

    @action(description="关闭串口连接")
    def close(self) -> Dict[str, Any]:
        if self._closing:
            return {"success": False, "error": "已经关闭"}
        self._closing = True
        try:
            if hasattr(self.hardware_interface, "close"):
                self.hardware_interface.close()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 状态属性（自动定时广播 → status_types）
    # ------------------------------------------------------------------
    @property
    @topic_config(period=3.0)
    def status(self) -> str:
        """实时状态：Idle / Busy（软件缓存）。"""
        return self._status

    @property
    @topic_config(period=10.0)
    def mode_value(self) -> int:
        """工作模式枚举值（Normal=0 / AccuratePos=1 / AccuratePosVel=2）。"""
        return int(self.mode.value) if self.mode else 0

    @property
    @topic_config(period=5.0)
    def max_velocity(self) -> float:
        """当前设置的最大柱塞速度（mL/s，软件缓存）。"""
        return float(self._max_velocity)

    @property
    @topic_config(period=3.0)
    def valve_position(self) -> str:
        """当前阀门位置（软件缓存）。"""
        return str(self._valve_position)

    @property
    @topic_config(period=3.0)
    def position(self) -> float:
        """当前柱塞位置缓存（mL）。"""
        return float(self._position)

    @property
    @topic_config(period=5.0)
    def velocity_grade(self) -> str:
        """实时读取最大脉冲频率并换算为档位字符串（'0'~'40'，'-1' 表示未匹配）。"""
        response = self._query("?2")
        if not response:
            return "-1"
        _, pulse_freq = response[0], int(response[1:])
        for freq, grade in PULSE_FREQ_GRADES.items():
            if pulse_freq >= freq:
                return grade
        return "-1"

    @property
    @topic_config(period=5.0)
    def velocity_init(self) -> str:
        """实时查询起始速度（脉冲频率与体积速度），返回 'pulse_freq,velocity' 格式。"""
        response = self._query("?1")
        if not response:
            return "0,0.0"
        status_raw, pulse_freq = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return f"{pulse_freq},{velocity}"

    @property
    @topic_config(period=5.0)
    def velocity_end(self) -> str:
        """实时查询终止速度（脉冲频率与体积速度），返回 'pulse_freq,velocity' 格式。"""
        response = self._query("?3")
        if not response:
            return "0,0.0"
        status_raw, pulse_freq = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return f"{pulse_freq},{velocity}"

    @property
    @topic_config(period=2.0)
    def plunger_position(self) -> float:
        """实时查询柱塞位置（mL，独立于 position）。"""
        response = self._query("?4")
        if not response:
            return self._position
        _, pos_step = response[0], int(response[1:])
        return pos_step / self.total_steps * self.max_volume

    # ------------------------------------------------------------------
    # 实时查询方法（保留为内部使用 / auto-action）
    #   - 不带 @action 的公开方法 → 自动注册为 auto-{name} 动作
    #   - 必须有返回类型注解
    # ------------------------------------------------------------------
    def get_status(self) -> str:
        """实时查询并刷新当前状态（_run 内部轮询使用）。"""
        status_raw = self._query("Q")
        if status_raw:
            self._status = self._standardize_status(status_raw)
        return self._status

    def get_max_velocity(self) -> float:
        """实时读取最大速度（mL/s）。"""
        response = self._query("?2")
        if not response:
            return self._max_velocity
        status_raw, pulse_freq = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        self._max_velocity = pulse_freq / self.total_steps_vel * self.max_volume
        return self._max_velocity

    def get_valve_position(self) -> str:
        """实时查询阀门位置。"""
        response = self._query("?6")
        if not response or len(response) < 2:
            return self._valve_position
        status_raw, pos_valve = response[0], response[1].upper()
        self._valve_position = pos_valve
        self._status = self._standardize_status(status_raw)
        return pos_valve

    def get_position(self) -> float:
        """实时查询柱塞绝对位置（mL）。"""
        response = self._query("?0")
        if not response:
            return self._position
        status_raw, pos_step = response[0], int(response[1:])
        self._status = self._standardize_status(status_raw)
        self._position = pos_step / self.total_steps * self.max_volume
        return self._position

    # ------------------------------------------------------------------
    # 工具方法（@not_action 显式标记，不暴露为动作）
    # ------------------------------------------------------------------
    @not_action
    def list_available_ports(self) -> list:
        """枚举系统中所有可用的串口号。"""
        return [item.device for item in serial.tools.list_ports.comports()]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pump = RunzeSyringePump(port="COM5", address="1", max_volume=25.0)
    print(pump.initialize())
    print("status:", pump.get_status())
    print("valve:", pump.get_valve_position())
    print(pump.close())

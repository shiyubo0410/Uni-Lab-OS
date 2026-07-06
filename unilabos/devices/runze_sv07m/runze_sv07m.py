# -*- coding: utf-8 -*-
"""
润泽（Runze）SV07M 多通道切换阀驱动（@device 装饰器 + AST 自动扫描）。

设备说明：
    SV07M 多通道切换阀通过接收上位机指令控制步进电机，使转子转到指定孔位实现流路切换。
    常规通道数有 6/8/10/12/16/24/28，复位位置为 1 号孔，复位方向逆时针。

通信协议（RUNZE 自定义二进制协议）：
    - RS-232 / RS-485 总线，8 数据位、无校验、1 停止位（8N1）
    - 波特率：9600 / 19200 / 38400 / 57600 / 115200，出厂默认 9600
    - 普通下发命令帧（8 字节）：
        B0  STX     帧头 0xCC
        B1  ADDR    从机地址 0x00~0x7F（组播 0x80~0xFE，广播 0xFF）
        B2  FUNC    功能码
        B3  参数低字节（1-8 位）
        B4  参数高字节（9-16 位）
        B5  ETX     帧尾 0xDD
        B6  和校验低字节
        B7  和校验高字节
      和校验 = B0~B5 累加和，取两字节，小端存储（低字节在前）。
    - 响应帧（8 字节）：B2 为状态码 STATUS，其余结构同上。

功能码（普通指令）：
    动作指令：
        0x44  按最优路径切换到指定孔位（B3=孔位 1~max，B4=0x00）
        0x45  复位（运行到复位光耦处停止）
        0x4F  原点复位（运行到编码器原点位置）
        0xA4  按指定方向切换孔位（B3、B4 为相邻两孔位，决定转向）
        0x49  强制停止
    查询指令：
        0x20  查询地址
        0x3E  查询当前通道位置（响应 B3 = 当前孔位）
        0x3F  查询当前版本（响应 B3=主版本 B4=子版本，如 01 09 -> V1.9）
        0x4A  查询电机状态（响应 STATUS）

响应状态码（B2）：
    0x00 状态正常    0x01 帧错误      0x02 参数错误    0x03 光耦错误
    0x04 电机忙      0x05 电机堵转    0x06 未知位置    0xFE 任务挂起（正在执行）
    0xFF 未知错误

使用方式：
    valve = RunzeSV07MValve(port="COM5", address=0, max_channels=8)
    valve.initialize()                 # 复位到 1 号孔
    valve.set_valve_position(3)        # 切换到 3 号孔
    valve.query_current_position()
"""

import logging
import time
from threading import Lock
from typing import Any, Dict, Optional, Union

import serial.tools.list_ports
from serial import Serial
from serial.serialutil import SerialException

from unilabos.registry.decorators import action, device, not_action, topic_config


STX = 0xCC
ETX = 0xDD

STATUS_TEXT: Dict[int, str] = {
    0x00: "状态正常",
    0x01: "帧错误",
    0x02: "参数错误",
    0x03: "光耦错误",
    0x04: "电机忙",
    0x05: "电机堵转",
    0x06: "未知位置",
    0xFE: "任务挂起(正在执行)",
    0xFF: "未知错误",
}

FUNC_MOVE = 0x44
FUNC_RESET = 0x45
FUNC_ORIGIN_RESET = 0x4F
FUNC_MOVE_DIRECTION = 0xA4
FUNC_FORCE_STOP = 0x49
FUNC_QUERY_ADDRESS = 0x20
FUNC_QUERY_POSITION = 0x3E
FUNC_QUERY_VERSION = 0x3F
FUNC_QUERY_MOTOR = 0x4A


class RunzeSV07MConnectionError(Exception):
    """串口未连接 / 已关闭时抛出的连接异常。"""


class RunzeSV07MProtocolError(Exception):
    """响应帧解析失败（帧头/帧尾/校验错误）时抛出。"""


@device(
    id="pump_and_valve_runze_sv07m",
    category=["pump_and_valve", "runze"],
    description=(
        "润泽 SV07M 多通道切换阀，通过步进电机驱动陶瓷阀芯转动实现流路切换。"
        "采用 RUNZE 自定义二进制协议，经 RS-232 / RS-485 串口通信，"
        "支持按最优路径切换孔位、复位、原点复位、按方向切换与状态查询。"
        "常规通道数 6/8/10/12/16/24/28，适用于流体样品采集、分配与色谱进样等场景。"
    ),
    displayname="润泽多通道切换阀 SV07M",
    version="1.0.0",
)
class RunzeSV07MValve:
    """润泽 SV07M 多通道切换阀驱动（@device 自动扫描注册）。"""

    def __init__(
        self,
        port: str = "COM1",
        address: int = 0,
        max_channels: int = 8,
        baudrate: int = 9600,
        timeout: float = 2.0,
        move_timeout: float = 10.0,
        device_id: Optional[str] = None,
        **kwargs,
    ):
        """
        初始化润泽 SV07M 切换阀。

        Args:
            port[串口号]: 设备占用的串口号，例如 "COM5" / "/dev/ttyUSB0"。
            address[设备地址]: RS-485 总线从机地址，取值 0~127，默认 0。
            max_channels[最大通道数]: 阀体通道数，例如 6/8/10/12/16/24/28，默认 8。
            baudrate[波特率]: 串口波特率，默认 9600。
            timeout[读超时(s)]: 单次串口读取超时时间，单位秒，默认 2.0。
            move_timeout[切换超时(s)]: 等待切换完成的最长时间，单位秒，默认 10.0。
            device_id[设备ID]: 实例 ID，缺省时使用 'runze_sv07m'。
        """
        self.device_id = device_id or "runze_sv07m"
        self.port: str = str(port)
        self.address: int = int(address) & 0xFF
        self.max_channels: int = int(max_channels)
        self.baudrate: int = int(baudrate)
        self.timeout: float = float(timeout)
        self.move_timeout: float = float(move_timeout)

        self.logger = logging.getLogger(f"RunzeSV07MValve.{self.device_id}")

        self._status: str = "Idle"
        self._valve_position: int = 1
        self._last_status_code: int = 0x00

        self._io_lock: Lock = Lock()
        self._closing: bool = False

        self.hardware_interface: Any = self.port
        try:
            self.hardware_interface = Serial(
                port=self.port, baudrate=self.baudrate, timeout=self.timeout
            )
        except (OSError, SerialException) as exc:
            self.logger.warning(f"串口 {self.port} 打开失败: {exc}")

    # ------------------------------------------------------------------
    # 协议编解码（_ 开头自动跳过 AST 扫描）
    # ------------------------------------------------------------------
    def _build_frame(self, func: int, b3: int = 0x00, b4: int = 0x00) -> bytes:
        """构造 8 字节下发帧，自动计算并追加小端和校验。"""
        frame = bytearray([STX, self.address, func & 0xFF, b3 & 0xFF, b4 & 0xFF, ETX])
        checksum = sum(frame) & 0xFFFF
        frame.append(checksum & 0xFF)
        frame.append((checksum >> 8) & 0xFF)
        return bytes(frame)

    def _read_frame(self) -> bytes:
        """读取并定位一个完整的 8 字节响应帧（容忍前导噪声字节）。"""
        deadline = time.time() + self.timeout
        buf = bytearray()
        while time.time() < deadline:
            chunk = self.hardware_interface.read(8)
            if chunk:
                buf.extend(chunk)
                idx = buf.find(STX)
                if idx >= 0 and len(buf) - idx >= 8:
                    return bytes(buf[idx : idx + 8])
            elif buf:
                break
        raise RunzeSV07MProtocolError(f"读取响应超时或不完整: {buf.hex(' ')}")

    def _parse_response(self, frame: bytes) -> Dict[str, int]:
        """校验并解析响应帧，返回 status/b3/b4。"""
        if len(frame) != 8 or frame[0] != STX or frame[5] != ETX:
            raise RunzeSV07MProtocolError(f"非法响应帧: {frame.hex(' ')}")
        checksum = sum(frame[0:6]) & 0xFFFF
        recv_checksum = frame[6] | (frame[7] << 8)
        if checksum != recv_checksum:
            raise RunzeSV07MProtocolError(
                f"和校验错误: 期望 {checksum:#06x}, 收到 {recv_checksum:#06x}"
            )
        status_code = frame[2]
        self._last_status_code = status_code
        return {"status": status_code, "b3": frame[3], "b4": frame[4]}

    def _transact(self, func: int, b3: int = 0x00, b4: int = 0x00) -> Dict[str, int]:
        """发送一帧并接收解析一帧响应（带串口互斥锁）。"""
        with self._io_lock:
            if self._closing:
                raise RunzeSV07MConnectionError("驱动已关闭")
            if not hasattr(self.hardware_interface, "write"):
                raise RunzeSV07MConnectionError(f"串口 {self.port} 未连接")
            self.hardware_interface.reset_input_buffer()
            self.hardware_interface.write(self._build_frame(func, b3, b4))
            return self._parse_response(self._read_frame())

    def _update_status_from_code(self, code: int) -> str:
        """把响应状态码映射为统一的 Idle / Busy / Error 字符串。"""
        if code == 0x00:
            self._status = "Idle"
        elif code in (0x04, 0xFE):
            self._status = "Busy"
        else:
            self._status = "Error"
        return self._status

    def _wait_until_idle(self) -> Dict[str, Any]:
        """轮询 0x4A 电机状态，直到空闲 / 报错 / 超时。"""
        deadline = time.time() + self.move_timeout
        while time.time() < deadline:
            time.sleep(0.2)
            resp = self._transact(FUNC_QUERY_MOTOR)
            code = resp["status"]
            self._update_status_from_code(code)
            if code == 0x00:
                return {"success": True, "status_code": code}
            if code not in (0x04, 0xFE):
                return {
                    "success": False,
                    "status_code": code,
                    "error": STATUS_TEXT.get(code, f"未知状态码 {code:#04x}"),
                }
        return {"success": False, "error": "等待切换完成超时"}

    # ------------------------------------------------------------------
    # 标准动作（pump_and_valve - 切换阀）
    # ------------------------------------------------------------------
    @action(description="复位到 1 号孔（运行到复位光耦处停止）")
    def initialize(self) -> Dict[str, Any]:
        """复位切换阀到 1 号孔。"""
        try:
            self._transact(FUNC_RESET)
            wait = self._wait_until_idle()
            if wait["success"]:
                self._valve_position = 1
            return {
                "success": wait["success"],
                "valve_position": self._valve_position,
                "message": "复位完成" if wait["success"] else wait.get("error", ""),
            }
        except Exception as exc:
            self.logger.error(f"复位失败: {exc}")
            self._status = "Error"
            return {"success": False, "error": str(exc)}

    @action(description="按最优路径切换到指定孔位")
    def set_valve_position(self, position: Union[int, str]) -> Dict[str, Any]:
        """
        切换阀转动到指定孔位（自动选择最优路径）。

        Args:
            position[目标孔位]: 目标孔位编号，范围 1~max_channels。
        """
        try:
            channel = int(position)
        except (ValueError, TypeError):
            return {"success": False, "error": f"无法解析孔位: {position!r}"}
        if channel < 1 or channel > self.max_channels:
            return {
                "success": False,
                "error": f"孔位超出范围: {channel}（有效 1~{self.max_channels}）",
            }
        try:
            self._transact(FUNC_MOVE, b3=channel, b4=0x00)
            wait = self._wait_until_idle()
            if wait["success"]:
                self._valve_position = channel
            return {
                "success": wait["success"],
                "valve_position": self._valve_position,
                "message": "" if wait["success"] else wait.get("error", ""),
            }
        except Exception as exc:
            self.logger.error(f"切换孔位失败: {exc}")
            self._status = "Error"
            return {"success": False, "error": str(exc)}

    @action(description="按指定方向切换孔位（指定相邻经过孔位决定转向）")
    def set_valve_position_directional(
        self, target: int, through: int
    ) -> Dict[str, Any]:
        """
        按指定方向切换到目标孔位。

        参数 ``through`` 是紧邻 ``target`` 且位于转动方向上的孔位，用于指定转向：
        例如当前在 1 号孔，目标 4 号孔，逆时针经过 3 号则 through=3、target=4；
        顺时针经过 5 号则 through=5、target=4。

        Args:
            target[目标孔位]: 最终到达的孔位编号，范围 1~max_channels。
            through[经过孔位]: 紧邻目标且决定转向的相邻孔位，范围 1~max_channels。
        """
        try:
            target = int(target)
            through = int(through)
        except (ValueError, TypeError):
            return {"success": False, "error": "孔位参数必须为整数"}
        for ch in (target, through):
            if ch < 1 or ch > self.max_channels:
                return {
                    "success": False,
                    "error": f"孔位超出范围: {ch}（有效 1~{self.max_channels}）",
                }
        try:
            self._transact(FUNC_MOVE_DIRECTION, b3=through, b4=target)
            wait = self._wait_until_idle()
            if wait["success"]:
                self._valve_position = target
            return {
                "success": wait["success"],
                "valve_position": self._valve_position,
                "message": "" if wait["success"] else wait.get("error", ""),
            }
        except Exception as exc:
            self.logger.error(f"按方向切换失败: {exc}")
            self._status = "Error"
            return {"success": False, "error": str(exc)}

    @action(description="原点复位（运行到编码器原点位置）")
    def origin_reset(self) -> Dict[str, Any]:
        """运行到编码器原点位置（与复位光耦位置重叠）。"""
        try:
            self._transact(FUNC_ORIGIN_RESET)
            wait = self._wait_until_idle()
            if wait["success"]:
                self._valve_position = 1
            return {
                "success": wait["success"],
                "valve_position": self._valve_position,
                "message": "原点复位完成" if wait["success"] else wait.get("error", ""),
            }
        except Exception as exc:
            self.logger.error(f"原点复位失败: {exc}")
            self._status = "Error"
            return {"success": False, "error": str(exc)}

    @action(description="强制停止当前切换动作")
    def stop(self) -> Dict[str, Any]:
        """强制停止电机运行。"""
        try:
            resp = self._transact(FUNC_FORCE_STOP)
            self._update_status_from_code(resp["status"])
            return {"success": True, "status_code": resp["status"]}
        except Exception as exc:
            self.logger.error(f"强停失败: {exc}")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 查询动作
    # ------------------------------------------------------------------
    @action(description="查询当前孔位")
    def query_current_position(self) -> Dict[str, Any]:
        """查询并刷新当前孔位（响应 B3 = 孔位编号）。"""
        try:
            resp = self._transact(FUNC_QUERY_POSITION)
            self._update_status_from_code(resp["status"])
            if resp["status"] == 0x00:
                self._valve_position = resp["b3"]
            return {
                "success": resp["status"] == 0x00,
                "valve_position": self._valve_position,
                "status_code": resp["status"],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @action(description="查询电机状态")
    def query_motor_status(self) -> Dict[str, Any]:
        """查询电机运行状态（0x00 正常，其余为忙 / 错误）。"""
        try:
            resp = self._transact(FUNC_QUERY_MOTOR)
            code = resp["status"]
            self._update_status_from_code(code)
            return {
                "success": True,
                "status": self._status,
                "status_code": code,
                "message": STATUS_TEXT.get(code, f"未知状态码 {code:#04x}"),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @action(description="查询固件版本")
    def query_version(self) -> Dict[str, Any]:
        """查询固件版本（响应 B3=主版本，B4=子版本）。"""
        try:
            resp = self._transact(FUNC_QUERY_VERSION)
            version = f"V{resp['b3']}.{resp['b4']}"
            return {"success": True, "version": version}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @action(description="查询设备地址")
    def query_address(self) -> Dict[str, Any]:
        """查询设备 RS-485 地址。"""
        try:
            resp = self._transact(FUNC_QUERY_ADDRESS)
            return {"success": True, "address": resp["b3"]}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @action(description="发送原始功能码与参数（高级用法）")
    def send_raw(self, func: int, b3: int = 0, b4: int = 0) -> Dict[str, Any]:
        """
        发送原始功能码与参数字节，返回解析后的响应。

        Args:
            func[功能码]: 功能码，十进制整数（如 0x44 传 68）。
            b3[参数低字节]: 参数低字节（1-8 位），十进制整数 0~255。
            b4[参数高字节]: 参数高字节（9-16 位），十进制整数 0~255。
        """
        try:
            resp = self._transact(int(func), int(b3), int(b4))
            return {"success": True, "response": resp}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @action(description="关闭串口连接")
    def close(self) -> Dict[str, Any]:
        """关闭底层串口连接。"""
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
        """实时状态：Idle / Busy / Error（软件缓存）。"""
        return self._status

    @property
    @topic_config(period=3.0)
    def valve_position(self) -> int:
        """当前孔位编号（软件缓存）。"""
        return int(self._valve_position)

    @property
    @topic_config(period=10.0)
    def max_channel_count(self) -> int:
        """阀体最大通道数。"""
        return int(self.max_channels)

    @property
    @topic_config(period=3.0)
    def motor_status_code(self) -> int:
        """实时查询电机状态码（0x4A）。会真实读串口，可作轮询心跳，掉线时抛异常。"""
        resp = self._transact(FUNC_QUERY_MOTOR)
        self._update_status_from_code(resp["status"])
        return int(resp["status"])

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
    valve = RunzeSV07MValve(port="COM5", address=0, max_channels=8)
    print(valve.initialize())
    print(valve.set_valve_position(3))
    print(valve.query_current_position())
    print(valve.query_version())
    print(valve.close())

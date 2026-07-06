"""IKA Plate (RCT digital) / RCT 5 digital 驱动.

协议来源:
- 20000023651g_ZH_IKA Plate_RCT 5 digital_042024_web.pdf
- 接口: RS232 / USB 虚拟串口
- 串口参数: 9600, 7E1, full duplex, 无流控
- 指令: NAMUR + IKA 扩展 ASCII 命令
"""

from __future__ import annotations

import logging
import threading
import time as _time
from typing import Any, Dict, Optional

import serial

from unilabos.registry.decorators import action, device, not_action, topic_config


@device(
    id="heaterstirrer_ika_rct5_digital",
    category=["heaterstirrer"],
    description="IKA RCT 5 digital 加热磁力搅拌仪 (RS232/NAMUR ASCII)",
    display_name="IKA RCT 5 digital",
)
class IKARCT5Digital:
    """IKA RCT 5 digital 串口驱动."""

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Args:
            device_id[设备ID]: 设备实例 ID。
            config[设备配置]: 图文件中的 config 字段。
            kwargs[额外参数]: 兼容旧调用方式的参数。
        """
        self.device_id = device_id or "ika_rct5"
        self.config = config or {}

        self.port = str(self.config.get("port", kwargs.get("port", "COM10")))
        self.baudrate = int(self.config.get("baudrate", kwargs.get("baudrate", 9600)))
        self.timeout = float(self.config.get("timeout", kwargs.get("timeout", 1.0)))
        self.auto_connect = bool(self.config.get("auto_connect", kwargs.get("auto_connect", True)))
        # 手册给出结尾为 "空格 + CR + 空格 + LF"
        self.command_suffix = str(
            self.config.get("command_suffix", kwargs.get("command_suffix", " \r \n"))
        )

        self.logger = logging.getLogger(f"IKA[{self.device_id}@{self.port}]")
        self._lock = threading.Lock()
        self._serial: Optional[serial.Serial] = None
        self._is_connected = False
        self._last_error = ""

        self._status = "Idle"
        self._temp = 0.0
        self._temp_plate = 0.0
        self._temp_target = 0.0
        self._stir_speed = 0.0
        self._stir_target = 0.0

        # 健康检查约定: 成功连接时是 Serial 对象, 失败时是 port 字符串
        self.hardware_interface: Any = self.port

        if self.auto_connect and self.port:
            try:
                self._do_connect()
            except Exception as exc:
                self.logger.warning(f"自动连接失败: {exc}")

    # -------------------------
    # 内部方法
    # -------------------------
    @not_action
    def _do_connect(self) -> bool:
        if self._is_connected and self._serial and self._serial.is_open:
            return True
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.SEVENBITS,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            self._is_connected = self._serial.is_open
            if self._is_connected:
                self.hardware_interface = self._serial
            return self._is_connected
        except Exception as exc:
            self._last_error = f"connect: {exc}"
            self._is_connected = False
            self.hardware_interface = self.port
            self.logger.error(self._last_error)
            return False

    @not_action
    def _write_then_read(self, command: str, read_response: bool = True) -> str:
        """发送命令并读取一行响应."""
        if not self._is_connected or self._serial is None or not self._serial.is_open:
            if not self._do_connect():
                raise RuntimeError(f"设备未连接: {self._last_error}")

        assert self._serial is not None
        payload = f"{command}{self.command_suffix}".encode("ascii", errors="ignore")

        with self._lock:
            try:
                self._serial.reset_input_buffer()
                self._serial.write(payload)
                if not read_response:
                    return ""
                raw = self._serial.read_until(b"\n")
                return raw.decode("ascii", errors="ignore").strip()
            except Exception as exc:
                self._is_connected = False
                self.hardware_interface = self.port
                self._last_error = f"io: {exc}"
                raise RuntimeError(self._last_error) from exc

    @not_action
    def _query_float(self, command: str) -> float:
        """读取浮点数响应.

        IKA NAMUR 协议返回格式为 "值 通道号", 例如:
          IN_PV_1  -> "25.0 1"    # 通道 1 = 外部温度（PT100 探头）
          IN_PV_2  -> "25.0 2"    # 通道 2 = 加热板温度
          IN_PV_4  -> "0.0 4"     # 通道 4 = 实际转速
          IN_SP_1  -> "2.0 1"     # 通道 1 = 设定温度
          IN_SP_4  -> "300.0 4"   # 通道 4 = 设定转速
        所以这里只取空格前第一段做数字解析.
        """
        response = self._write_then_read(command, read_response=True)
        if response == "":
            raise RuntimeError(f"命令 {command} 无响应")
        token = response.split()[0] if response.split() else response
        try:
            return float(token)
        except ValueError as exc:
            raise RuntimeError(f"命令 {command} 返回非数字: {response!r}") from exc

    @not_action
    def _refresh_cache(self) -> None:
        """更新常用缓存值.

        手册没有提供"加热是否在运行"的查询命令, 这里仅根据
        当前转速 / 设温 / 实际温度做粗略推断:
          - 转速 > 0 -> Running
          - 实际温度 > 设温 + 5 或 实际温度 > 50, 视为热态 -> Heating
          - 否则 -> Idle
        """
        self._temp = self._query_float("IN_PV_1")
        self._temp_plate = self._query_float("IN_PV_2")
        self._stir_speed = self._query_float("IN_PV_4")
        self._temp_target = self._query_float("IN_SP_1")
        self._stir_target = self._query_float("IN_SP_4")

        # 用加热板温度判断"加热器是否在工作"，外部探头有热惯性不可靠
        if self._stir_speed > 0:
            self._status = "Running"
        elif self._temp_plate > 50:
            self._status = "Heating"
        else:
            self._status = "Idle"

    # -------------------------
    # 动作方法
    # -------------------------
    @action(description="打开串口连接")
    def connect(self) -> Dict[str, Any]:
        ok = self._do_connect()
        return {
            "success": ok,
            "port": self.port,
            "baudrate": self.baudrate,
            "message": "连接成功" if ok else f"连接失败: {self._last_error}",
        }

    @action(description="关闭串口连接")
    def disconnect(self) -> Dict[str, Any]:
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass
        self._is_connected = False
        self.hardware_interface = self.port
        return {"success": True, "message": "已断开连接"}

    @action(description="读取设备名称 (IN_NAME)")
    def read_name(self) -> Dict[str, Any]:
        try:
            name = self._write_then_read("IN_NAME")
            return {"success": True, "name": name}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    @action(description="读取当前关键状态")
    def read_status(self) -> Dict[str, Any]:
        try:
            self._refresh_cache()
            return {
                "success": True,
                "status": self._status,
                "temp": self._temp,
                "temp_plate": self._temp_plate,
                "temp_target": self._temp_target,
                "stir_speed": self._stir_speed,
                "stir_target": self._stir_target,
                "message": (
                    f"状态={self._status}, 外部温度={self._temp:.1f}degC, "
                    f"加热板={self._temp_plate:.1f}degC, "
                    f"设温={self._temp_target:.1f}degC, 转速={self._stir_speed:.0f}rpm"
                ),
            }
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="设置目标温度")
    def set_temperature(self, temp: float) -> Dict[str, Any]:
        """
        Args:
            temp[目标温度(degC)]: 加热目标温度, 范围 0~310 degC。
        """
        try:
            value = float(temp)
            if value < 0 or value > 310:
                return {"success": False, "message": "温度范围应为 0~310 degC"}
            self._write_then_read(f"OUT_SP_1 {value:.1f}", read_response=False)
            self._temp_target = value
            return {"success": True, "temp_target": value, "message": f"已设置目标温度 {value:.1f}degC"}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="设置目标转速")
    def set_stir_speed(self, speed: float) -> Dict[str, Any]:
        """
        Args:
            speed[转速(rpm)]: 搅拌目标转速, 范围 0~1500 rpm。
        """
        try:
            value = float(speed)
            if value < 0 or value > 1500:
                return {"success": False, "message": "转速范围应为 0~1500 rpm"}
            int_value = int(round(value))
            self._write_then_read(f"OUT_SP_4 {int_value}", read_response=False)
            self._stir_target = float(int_value)
            return {"success": True, "stir_target": self._stir_target, "message": f"已设置目标转速 {int_value}rpm"}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="启动加热: 可同时设定目标温度和持续时长")
    def start_heater(
        self,
        temp: Optional[float] = None,
        duration: float = 0,
    ) -> Dict[str, Any]:
        """
        Args:
            temp[目标温度(degC)]: 加热目标温度, 范围 0~310 degC; 留空则沿用当前设温。
            duration[加热时长(秒)]: 大于 0 时到时自动停止加热; 0 表示持续加热直到调用 stop_heater。
        """
        try:
            if temp is not None:
                res = self.set_temperature(temp)
                if not res.get("success"):
                    return res

            self._write_then_read("START_1", read_response=False)
            self._status = "Heating"

            if duration and float(duration) > 0:
                _time.sleep(float(duration))
                stop_res = self.stop_heater()
                return {
                    "success": bool(stop_res.get("success")),
                    "duration": float(duration),
                    "message": f"加热运行 {float(duration):.0f}s 后已停止",
                }
            return {
                "success": True,
                "temp_target": self._temp_target,
                "message": "加热已启动" + (f", 目标 {self._temp_target:.1f}degC" if temp is not None else ""),
            }
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="停止加热 (STOP_1)")
    def stop_heater(self) -> Dict[str, Any]:
        try:
            self._write_then_read("STOP_1", read_response=False)
            self._status = "Running" if self._stir_speed > 0 else "Idle"
            return {"success": True, "message": "加热已停止"}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="启动搅拌: 可同时设定目标转速和持续时长")
    def start_stir(
        self,
        stir_speed: Optional[float] = None,
        duration: float = 0,
    ) -> Dict[str, Any]:
        """
        Args:
            stir_speed[转速(rpm)]: 搅拌目标转速, 范围 0~1500 rpm; 留空则沿用当前设速。
            duration[搅拌时长(秒)]: 大于 0 时到时自动停止搅拌; 0 表示持续搅拌直到调用 stop_stir。
        """
        try:
            if stir_speed is not None:
                res = self.set_stir_speed(stir_speed)
                if not res.get("success"):
                    return res

            self._write_then_read("START_4", read_response=False)
            self._status = "Running"

            if duration and float(duration) > 0:
                _time.sleep(float(duration))
                stop_res = self.stop_stir()
                return {
                    "success": bool(stop_res.get("success")),
                    "duration": float(duration),
                    "message": f"搅拌运行 {float(duration):.0f}s 后已停止",
                }
            return {
                "success": True,
                "stir_target": self._stir_target,
                "message": "搅拌已启动" + (f", 目标 {self._stir_target:.0f}rpm" if stir_speed is not None else ""),
            }
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="停止搅拌 (STOP_4)")
    def stop_stir(self) -> Dict[str, Any]:
        try:
            self._write_then_read("STOP_4", read_response=False)
            self._stir_speed = 0.0
            self._stir_target = 0.0
            self._status = "Heating" if self._temp_plate > 50 else "Idle"
            return {"success": True, "message": "搅拌已停止"}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="设置操作模式 A/B/D")
    def set_mode(self, mode: str = "A") -> Dict[str, Any]:
        """
        Args:
            mode[操作模式]: A=开机后加热搅拌关闭; B=开机后恢复关机前状态; D=改值需按旋钮确认。
        """
        mode_upper = str(mode).upper()
        if mode_upper not in {"A", "B", "D"}:
            return {"success": False, "message": "mode 仅支持 A/B/D"}
        try:
            self._write_then_read(f"SET_MODE_{mode_upper}", read_response=False)
            return {"success": True, "mode": mode_upper}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="设置看门狗安全温度上限")
    def set_wd_safe_temp(self, temp: float) -> Dict[str, Any]:
        """
        Args:
            temp[WD 安全温度(degC)]: 看门狗触发时的安全温度限值, 范围 0~310 degC。
        """
        try:
            value = float(temp)
            if value < 0 or value > 310:
                return {"success": False, "message": "WD 安全温度范围应为 0~310 degC"}
            response = self._write_then_read(f"OUT_SP_12@{value:.1f}", read_response=True)
            return {"success": True, "value": value, "echo": response}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="设置看门狗安全转速上限")
    def set_wd_safe_speed(self, speed: float) -> Dict[str, Any]:
        """
        Args:
            speed[WD 安全转速(rpm)]: 看门狗触发时的安全转速限值, 范围 0~1500 rpm。
        """
        try:
            value = int(round(float(speed)))
            if value < 0 or value > 1500:
                return {"success": False, "message": "WD 安全转速范围应为 0~1500 rpm"}
            response = self._write_then_read(f"OUT_SP_42@{value}", read_response=True)
            return {"success": True, "value": value, "echo": response}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="启动 WD1 看门狗: 超时则停加热/停搅拌")
    def watchdog_mode_1(self, seconds: int = 20) -> Dict[str, Any]:
        """
        Args:
            seconds[看门狗时间(秒)]: 20~1500 秒; 超时未续命则停止加热和搅拌, 显示 Er02。
        """
        seconds = int(seconds)
        if seconds < 20 or seconds > 1500:
            return {"success": False, "message": "seconds 应为 20~1500"}
        try:
            response = self._write_then_read(f"OUT_WD1@{seconds}", read_response=True)
            return {"success": True, "watchdog": "WD1", "seconds": seconds, "echo": response}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="设置 WD2 看门狗: 超时切到安全值; 传 0 关闭看门狗")
    def watchdog_mode_2(self, seconds: int = 20) -> Dict[str, Any]:
        """
        Args:
            seconds[看门狗时间(秒)]: 20~1500 秒; 超时则把目标温度/转速切到 WD 安全值。传 0 关闭看门狗。
        """
        seconds = int(seconds)
        if seconds != 0 and (seconds < 20 or seconds > 1500):
            return {"success": False, "message": "seconds 应为 0 或 20~1500"}
        try:
            response = self._write_then_read(f"OUT_WD2@{seconds}", read_response=True)
            return {"success": True, "watchdog": "WD2", "seconds": seconds, "echo": response}
        except Exception as exc:
            self._status = "Error"
            self._last_error = str(exc)
            return {"success": False, "message": str(exc)}

    @action(description="同时停止加热和搅拌")
    def stop(self) -> Dict[str, Any]:
        heater = self.stop_heater()
        stir = self.stop_stir()
        ok = bool(heater.get("success")) and bool(stir.get("success"))
        return {
            "success": ok,
            "heater": heater,
            "stir": stir,
            "message": "已停止" if ok else "停止存在失败",
        }

    @action(description="加热搅拌复合动作: 设温+设速+运行一段时间后停止搅拌")
    def heatchill(
        self,
        vessel: str,
        temp: float,
        time: float = 3600,
        stir: bool = True,
        stir_speed: float = 300,
        purpose: str = "reaction",
    ) -> Dict[str, Any]:
        """
        Args:
            vessel[容器标识]: 当前处理容器名。
            temp[目标温度(degC)]: 目标温度, 0~310 degC。
            time[运行时长(秒)]: 搅拌运行时长。
            stir[是否搅拌]: 是否启动搅拌。
            stir_speed[搅拌转速(rpm)]: 搅拌目标转速, 0~1500 rpm。
            purpose[用途]: 业务用途描述。
        """
        _ = (vessel, purpose)
        heat_res = self.start_heater(temp=temp, duration=0)
        if not heat_res.get("success", False):
            return {"success": False, "message": f"启动加热失败: {heat_res.get('message', '')}"}

        if stir:
            stir_res = self.start_stir(stir_speed=stir_speed, duration=float(time))
            if not stir_res.get("success", False):
                return {"success": False, "message": f"启动搅拌失败: {stir_res.get('message', '')}"}

        return {
            "success": True,
            "temp_target": float(temp),
            "stir": bool(stir),
            "stir_speed": float(stir_speed),
            "duration": float(time),
            "message": "heatchill 执行完成",
        }

    # -------------------------
    # 状态属性
    # -------------------------
    @property
    @topic_config(period=5.0)
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    @topic_config(period=2.0)
    def status(self) -> str:
        try:
            self._refresh_cache()
        except Exception:
            # 串口断了 / 设备没回包 —— 标记 Error 让业务层能感知，
            # 同时把异常抛给 telemetry，让网关能识别 IO 故障并触发重连/下线。
            # 不要在这里吞异常（否则 _io_error_count 永远清零，永远不下线）。
            self._status = "Error"
            raise
        return self._status

    @property
    @topic_config(period=2.0)
    def temp(self) -> float:
        value = self._query_float("IN_PV_1")
        self._temp = value
        return value

    @property
    @topic_config(period=2.0)
    def temp_plate(self) -> float:
        value = self._query_float("IN_PV_2")
        self._temp_plate = value
        return value

    @property
    @topic_config(period=2.0)
    def stir_speed(self) -> float:
        value = self._query_float("IN_PV_4")
        self._stir_speed = value
        return value

    @property
    @topic_config(period=5.0)
    def temp_target(self) -> float:
        value = self._query_float("IN_SP_1")
        self._temp_target = value
        return value

    @property
    @topic_config(period=5.0)
    def stir_target(self) -> float:
        value = self._query_float("IN_SP_4")
        self._stir_target = value
        return value

    @property
    @topic_config(period=10.0)
    def last_error(self) -> str:
        return self._last_error


if __name__ == "__main__":
    # COM8 联调示例: 不直接通过 Uni-Lab 框架, 直接拿原始 driver 类做最小验证
    # 运行方式: python -m unilabos.devices.ika.ika
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    PORT = "COM10"

    print(f"\n=== IKA RCT 5 digital 联调 ({PORT}) ===")
    ika = IKARCT5Digital(
        device_id="ika_rct5_test",
        config={
            "port": PORT,
            "baudrate": 9600,
            "timeout": 1.0,
            # 默认 " \r \n" 是手册标准结尾; 若读不到响应, 改成 "\r\n" 再试
            "command_suffix": " \r \n",
            "auto_connect": True,
        },
    )

    try:
        # 1) 连接
        print("\n>>> connect()")
        print(ika.connect())

        # 2) 读设备名 (确认通讯是否打通的关键步骤)
        print("\n>>> read_name()")
        print(ika.read_name())

        # 3) 读完整状态: 当前温度 / 设温 / 当前转速 / 设速
        print("\n>>> read_status()")
        print(ika.read_status())

        # 4) 启动搅拌 (300 rpm, 5s 后自动停)
        print("\n>>> start_stir(stir_speed=300, duration=5)")
        print(ika.start_stir(stir_speed=300, duration=5))
        print(ika.read_status())

        # 5) 加热示例 (默认注释掉, 需要时取消注释)
        #    注意: 启用加热前请确认安全温度旋钮已调好, 否则会触发 Er25 等错误
        # print("\n>>> start_heater(temp=40, duration=10)")
        # print(ika.start_heater(temp=40, duration=10))
        # print(ika.read_status())

    except Exception as exc:
        print(f"\n[ERROR] {exc}")

    finally:
        print("\n>>> disconnect()")
        print(ika.disconnect())

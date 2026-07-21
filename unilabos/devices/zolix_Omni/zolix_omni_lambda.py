import logging
import threading
import time as time_module
from typing import Dict, Any, Optional

try:
    import serial
except ImportError:
    serial = None

try:
    from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode
except ImportError:
    BaseROS2DeviceNode = None

try:
    from unilabos.registry.decorators import device, action, topic_config, not_action
except ImportError:

    def device(**kwargs):
        def wrapper(cls):
            return cls

        return wrapper

    def action(**kwargs):
        def wrapper(func):
            return func

        return wrapper

    def topic_config(**kwargs):
        def wrapper(func):
            return func

        return wrapper

    def not_action(func):
        return func


@device(
    id="zolix_omni_lambda",
    category=["custom", "zolix_omni_lambda"],
    description="Zolix Omni-λ 单色仪/光谱仪",
    display_name="Zolix Omni-λ",
)
class ZolixOmniLambda:
    """Zolix Omni-λ 单色仪/光谱仪驱动

    通信协议: Serial (USB/RS232), ASCII 文本指令, \\r 结束符
    默认波特率: 19200, 8N1
    指令格式: "<COMMAND> [参数]\\r"
    响应格式: ASCII 文本, 以 "OK" 或 "Exx" 结尾

    支持功能:
    - 波长绝对/相对移动 (nm)
    - 波数绝对移动 (cm⁻¹)
    - 光栅切换与查询
    - 光栅台切换
    - 出入口切换
    - 系统信息查询
    - IO 端口控制
    """

    _ros_node: "BaseROS2DeviceNode"

    # ---------- 错误码映射 ----------
    ERROR_CODES = {
        "E01": "Command not recognized",
        "E02": "Parameter out of range",
        "E03": "Device busy",
        "E04": "Communication error",
        "E05": "Hardware error",
        "E06": "Timeout",
    }

    def __init__(self, device_id: str = None, config: Dict[str, Any] = None, **kwargs):
        if device_id is None and "id" in kwargs:
            device_id = kwargs.pop("id")
        if config is None and "config" in kwargs:
            config = kwargs.pop("config")

        self.device_id = device_id or "unknown_device"
        self.config = config or {}
        self.logger = logging.getLogger(f"ZolixOmniLambda.{self.device_id}")

        # self.data 必须预填充所有 @property 对应的字段
        self.data: Dict[str, Any] = {
            "status": "Offline",
            "wavelength": 0.0,
            "wavenumber": 0.0,
            "grating": "1",
            "turret": "1",
            "exit_port": "0",
            "entrance_port": "0",
            "system_info": "",
        }

        # 串口配置 — 同时从 config 和 kwargs 中查找，兼容框架不同传参方式
        self._port = self.config.get("port") or kwargs.get("port", "COM10")
        self._baudrate = int(
            self.config.get("baudrate") or kwargs.get("baudrate", 19200)
        )
        self._timeout = float(self.config.get("timeout") or kwargs.get("timeout", 5))
        self._ser: Optional[Any] = None

        # 串口 IO 互斥锁：网关 telemetry(心跳属性) 和 action(方法) 跑在不同线程，须串行化。
        self._io_lock = threading.Lock()
        # 非 ROS2(网关)环境不会调 post_init，这里兜底，避免其它地方取 _ros_node 报错。
        self._ros_node = None

        self.logger.info(
            f"Config received: config={self.config}, kwargs_keys={list(kwargs.keys())}, using port={self._port}"
        )

        # 网关加载驱动后不会自动调 initialize()，必须在 __init__ 里就把串口打开。
        # hardware_interface 约定：连上=serial 对象；失败=port 字符串（网关据此判健康/触发重连）。
        self.hardware_interface: Any = self._port
        try:
            self._connect()
            self.data["status"] = "Idle"
        except Exception as e:
            self.logger.warning(f"串口 {self._port} 打开失败: {e}")
            self.data["status"] = "Offline"

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode"):
        self._ros_node = ros_node

    # ========== 通信层 ==========

    def _connect(self):
        """打开串口连接"""
        if serial is None:
            raise ImportError(
                "pyserial is required. Install with: pip install pyserial"
            )
        if self._ser is not None and self._ser.is_open:
            return
        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self._timeout,
        )
        self.hardware_interface = self._ser
        self.logger.info(f"Serial port opened: {self._port} @ {self._baudrate}")

    def _disconnect(self):
        """关闭串口连接"""
        if self._ser is not None and self._ser.is_open:
            self._ser.close()
            self.logger.info("Serial port closed")
        self._ser = None
        self.hardware_interface = self._port

    def _on_link_lost(self):
        """心跳失败时收尾：关串口、hardware_interface 退回 port 字符串，供网关判掉线/重连。"""
        self.data["status"] = "Offline"
        try:
            if self._ser is not None and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        self._ser = None
        self.hardware_interface = self._port

    def _send_command(self, cmd: str, timeout: float = None) -> str:
        """发送 ASCII 指令并读取响应

        指令格式: "COMMAND [params]\\r"
        响应: 读取直到 "OK\\r" 或 "Exx\\r" 或超时

        Args:
            cmd: 指令字符串 (不含 \\r)
            timeout: 可选超时覆盖 (秒)

        Returns:
            响应字符串 (去除前导垃圾字节后)
        """
        if self._ser is None or not self._ser.is_open:
            self._connect()

        with self._io_lock:
            # 清空接收缓冲区
            self._ser.reset_input_buffer()

            # 发送指令
            full_cmd = f"{cmd}\r"
            self._ser.write(full_cmd.encode("ascii"))
            self.logger.debug(f"TX: {cmd}")

            # 读取响应 — 使用 buffer 累积 + 关键字匹配
            effective_timeout = timeout if timeout is not None else self._timeout
            buffer = ""
            start_time = time_module.time()

            while time_module.time() - start_time < effective_timeout:
                if self._ser.in_waiting > 0:
                    chunk = self._ser.read(self._ser.in_waiting).decode(
                        "ascii", errors="replace"
                    )
                    buffer += chunk

                    # 检查是否收到完整响应 (以 OK 或 Exx 结尾)
                    stripped = buffer.strip()
                    if stripped.endswith("OK"):
                        break
                    for code in self.ERROR_CODES:
                        if stripped.endswith(code):
                            break
                    else:
                        time_module.sleep(0.05)
                        continue
                    break
                else:
                    time_module.sleep(0.05)

        self.logger.debug(f"RX: {buffer.strip()}")
        return buffer.strip()

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析响应字符串

        Returns:
            {"success": bool, "data": str, "error": str or None}
        """
        if not response:
            return {"success": False, "data": "", "error": "No response (timeout)"}

        # 检查错误码
        for code, desc in self.ERROR_CODES.items():
            if code in response:
                return {"success": False, "data": response, "error": f"{code}: {desc}"}

        if "OK" in response:
            # 提取 OK 之前的数据部分
            idx = response.rfind("OK")
            data_part = response[:idx].strip()
            return {"success": True, "data": data_part, "error": None}

        # 没有明确的 OK 或 Exx，视为数据响应
        return {"success": True, "data": response, "error": None}

    def _wait_until_idle(self, timeout: float = 120.0):
        """轮询等待设备完成移动 (同步方法, 在底层串口通信中使用)"""
        start = time_module.time()
        while time_module.time() - start < timeout:
            resp = self._send_command("POSITION?")
            parsed = self._parse_response(resp)
            if parsed["success"]:
                return True
            if parsed.get("error", "").startswith("E03"):
                time_module.sleep(0.5)
                continue
            time_module.sleep(0.2)
        return False

    # ========== 生命周期 ==========

    @action()
    async def initialize(self) -> bool:
        """初始化设备: 打开串口, 发送 Hello 联络指令, 查询初始状态"""
        try:
            self._connect()

            # 发送 Hello 联络指令
            resp = self._send_command("Hello")
            parsed = self._parse_response(resp)
            if not parsed["success"]:
                self.logger.warning(f"Hello command failed: {parsed['error']}")

            # 查询当前波长位置
            try:
                self._do_query_position()
            except Exception as e:
                self.logger.warning(f"Initial position query failed: {e}")

            # 查询系统信息
            try:
                self._do_query_system_info()
            except Exception as e:
                self.logger.warning(f"Initial system info query failed: {e}")

            self.data["status"] = "Idle"
            self.logger.info("Device initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.data["status"] = "Offline"
            return False

    @action()
    async def cleanup(self) -> bool:
        """清理资源: 关闭串口"""
        try:
            self._disconnect()
            self.data["status"] = "Offline"
            return True
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return False

    # ========== 内部查询方法 ==========

    def _do_query_position(self):
        """查询并更新当前波长位置"""
        resp = self._send_command("POSITION?")
        parsed = self._parse_response(resp)
        if parsed["success"] and parsed["data"]:
            try:
                # 真机应答形如 "POSITION 435.834"，带关键字前缀；取最后一个 token 才是数值。
                # (直接 float("POSITION 435.834") 会 ValueError，导致波长永远更新不了)
                wl = float(parsed["data"].split()[-1])
                self.data["wavelength"] = wl
                if wl > 0:
                    self.data["wavenumber"] = 1e7 / wl  # nm -> cm⁻¹
            except (ValueError, ZeroDivisionError, IndexError):
                pass

    def _do_query_system_info(self):
        """查询并更新系统信息"""
        resp = self._send_command("SYSTEMINFO?")
        parsed = self._parse_response(resp)
        if parsed["success"]:
            info = parsed["data"]
            # 应答形如 "SYSTEMINFO Andor,Omni500,SR-3094,..."，去掉开头的关键字回显只留型号信息
            if info.upper().startswith("SYSTEMINFO"):
                info = info[len("SYSTEMINFO"):].strip()
            self.data["system_info"] = info

    # ========== 动作方法 ==========
    # 注意：所有参数类型只能用 float 或 str，不能用 int
    # 因为 UniLab-OS 的 action type mapping 只支持 float 和 str

    @action()
    async def move_to(self, wavelength: float, **kwargs) -> Dict[str, Any]:
        """绝对移动到指定波长

        Args:
            wavelength: 目标波长 (nm)

        Returns:
            {"success": bool, "wavelength": float}
        """
        wavelength = float(wavelength)
        self.data["status"] = "Busy"

        try:
            resp = self._send_command(f"MOVETO {wavelength}")
            parsed = self._parse_response(resp)

            if not parsed["success"]:
                self.data["status"] = "Idle"
                return {"success": False, "error": parsed["error"]}

            self._wait_until_idle()
            self._do_query_position()
            self.data["status"] = "Idle"
            return {"success": True, "wavelength": self.data["wavelength"]}

        except Exception as e:
            self.logger.error(f"move_to failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def move_relative(self, wavelength: float, **kwargs) -> Dict[str, Any]:
        """相对移动指定波长

        Args:
            wavelength: 相对移动量 (nm), 正值红移, 负值蓝移

        Returns:
            {"success": bool, "wavelength": float}
        """
        wavelength = float(wavelength)
        self.data["status"] = "Busy"

        try:
            resp = self._send_command(f"MOVE {wavelength}")
            parsed = self._parse_response(resp)

            if not parsed["success"]:
                self.data["status"] = "Idle"
                return {"success": False, "error": parsed["error"]}

            self._wait_until_idle()
            self._do_query_position()
            self.data["status"] = "Idle"
            return {"success": True, "wavelength": self.data["wavelength"]}

        except Exception as e:
            self.logger.error(f"move_relative failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def move_to_wavenumber(self, wavenumber: float, **kwargs) -> Dict[str, Any]:
        """绝对移动到指定波数

        Args:
            wavenumber: 目标波数 (cm⁻¹)

        Returns:
            {"success": bool, "wavenumber": float}
        """
        wavenumber = float(wavenumber)
        self.data["status"] = "Busy"

        try:
            resp = self._send_command(f"WaveNumber_abs {wavenumber}")
            parsed = self._parse_response(resp)

            if not parsed["success"]:
                self.data["status"] = "Idle"
                return {"success": False, "error": parsed["error"]}

            self._wait_until_idle()
            self._do_query_position()
            self.data["status"] = "Idle"
            return {"success": True, "wavenumber": self.data["wavenumber"]}

        except Exception as e:
            self.logger.error(f"move_to_wavenumber failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def set_grating(self, grating: str, **kwargs) -> Dict[str, Any]:
        """切换光栅

        Args:
            grating: 光栅编号 (1~3)

        Returns:
            {"success": bool, "grating": str}
        """
        grating_val = str(grating)
        self.data["status"] = "Busy"

        try:
            resp = self._send_command(f"GRATING {grating_val}")
            parsed = self._parse_response(resp)

            if not parsed["success"]:
                self.data["status"] = "Idle"
                return {"success": False, "error": parsed["error"]}

            self._wait_until_idle()
            self.data["grating"] = grating_val
            self.data["status"] = "Idle"
            return {"success": True, "grating": grating_val}

        except Exception as e:
            self.logger.error(f"set_grating failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def grating_home(self, **kwargs) -> Dict[str, Any]:
        """光栅重新定位 (回零)

        Returns:
            {"success": bool}
        """
        self.data["status"] = "Busy"

        try:
            resp = self._send_command("GRATINGHOME")
            parsed = self._parse_response(resp)

            self._wait_until_idle(timeout=60.0)
            self._do_query_position()
            self.data["status"] = "Idle"
            return {"success": parsed["success"], "error": parsed.get("error")}

        except Exception as e:
            self.logger.error(f"grating_home failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def set_turret(self, turret: str, **kwargs) -> Dict[str, Any]:
        """设置光栅台

        Args:
            turret: 光栅台编号

        Returns:
            {"success": bool, "turret": str}
        """
        turret_val = str(turret)
        self.data["status"] = "Busy"

        try:
            resp = self._send_command(f"TURRET {turret_val}")
            parsed = self._parse_response(resp)

            self._wait_until_idle()
            self.data["turret"] = turret_val
            self.data["status"] = "Idle"
            return {
                "success": parsed["success"],
                "turret": turret_val,
                "error": parsed.get("error"),
            }

        except Exception as e:
            self.logger.error(f"set_turret failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def set_exit_port(self, port: str, **kwargs) -> Dict[str, Any]:
        """切换出口

        Args:
            port: 出口编号 (0=前置, 1=侧面)

        Returns:
            {"success": bool, "exit_port": str}
        """
        port_val = str(port)

        try:
            resp = self._send_command(f"EXITPORT {port_val}")
            parsed = self._parse_response(resp)

            if parsed["success"]:
                self.data["exit_port"] = port_val
            return {
                "success": parsed["success"],
                "exit_port": port_val,
                "error": parsed.get("error"),
            }

        except Exception as e:
            self.logger.error(f"set_exit_port failed: {e}")
            return {"success": False, "error": str(e)}

    @action()
    async def set_entrance_port(self, port: str, **kwargs) -> Dict[str, Any]:
        """切换入口

        Args:
            port: 入口编号 (0=前置, 1=侧面)

        Returns:
            {"success": bool, "entrance_port": str}
        """
        port_val = str(port)

        try:
            resp = self._send_command(f"ENTRANCEPORT {port_val}")
            parsed = self._parse_response(resp)

            if parsed["success"]:
                self.data["entrance_port"] = port_val
            return {
                "success": parsed["success"],
                "entrance_port": port_val,
                "error": parsed.get("error"),
            }

        except Exception as e:
            self.logger.error(f"set_entrance_port failed: {e}")
            return {"success": False, "error": str(e)}

    @action()
    async def stop(self, **kwargs) -> Dict[str, Any]:
        """停止当前移动

        Returns:
            {"success": bool}
        """
        try:
            resp = self._send_command("STOP")
            parsed = self._parse_response(resp)
            self.data["status"] = "Idle"
            return {"success": parsed["success"], "error": parsed.get("error")}

        except Exception as e:
            self.logger.error(f"stop failed: {e}")
            self.data["status"] = "Idle"
            return {"success": False, "error": str(e)}

    @action()
    async def query_position(self, **kwargs) -> Dict[str, Any]:
        """查询当前波长位置

        Returns:
            {"success": bool, "wavelength": float, "wavenumber": float}
        """
        try:
            self._do_query_position()
            return {
                "success": True,
                "wavelength": self.data["wavelength"],
                "wavenumber": self.data["wavenumber"],
            }
        except Exception as e:
            self.logger.error(f"query_position failed: {e}")
            return {"success": False, "error": str(e)}

    @action()
    async def query_system_info(self, **kwargs) -> Dict[str, Any]:
        """查询系统信息

        Returns:
            {"success": bool, "system_info": str}
        """
        try:
            self._do_query_system_info()
            return {"success": True, "system_info": self.data["system_info"]}
        except Exception as e:
            self.logger.error(f"query_system_info failed: {e}")
            return {"success": False, "error": str(e)}

    @action()
    async def query_gratings(self, **kwargs) -> Dict[str, Any]:
        """查询光栅参数

        Returns:
            {"success": bool, "gratings_info": str}
        """
        try:
            resp = self._send_command("GRATINGS?")
            parsed = self._parse_response(resp)
            return {
                "success": parsed["success"],
                "gratings_info": parsed["data"],
                "error": parsed.get("error"),
            }
        except Exception as e:
            self.logger.error(f"query_gratings failed: {e}")
            return {"success": False, "error": str(e)}

    @action()
    async def set_port_output(self, value: str, **kwargs) -> Dict[str, Any]:
        """设置 IO 端口输出

        Args:
            value: 输出值字符串

        Returns:
            {"success": bool}
        """
        try:
            resp = self._send_command(f"PORT_OUTPUT {value}")
            parsed = self._parse_response(resp)
            return {"success": parsed["success"], "error": parsed.get("error")}
        except Exception as e:
            self.logger.error(f"set_port_output failed: {e}")
            return {"success": False, "error": str(e)}

    @action()
    async def send_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """发送自定义指令

        Args:
            command: 完整指令字符串 (不含 \\r)

        Returns:
            {"success": bool, "response": str}
        """
        try:
            resp = self._send_command(str(command))
            parsed = self._parse_response(resp)
            return {
                "success": parsed["success"],
                "response": parsed["data"],
                "error": parsed.get("error"),
            }
        except Exception as e:
            self.logger.error(f"send_command failed: {e}")
            return {"success": False, "error": str(e)}

    # ========== 属性 (property) ==========
    # 注意：@property 返回类型只能用 float, str, bool
    # 不能用 int，否则 set_<property> 自动生成时会触发
    # ValueError: Unsupported action type: <class 'int'>

    @property
    @topic_config(period=5.0)
    def device_alive(self) -> bool:
        """真读串口的心跳：发 Hello 握手（无副作用，不移动波长）。

        读不到 / 串口异常则收尾并抛异常，供网关掉线检测与自动重连。
        不要用 status/wavelength 这类纯缓存属性做心跳——它们从不抛异常，拔线判不出掉线。
        """
        # 动作执行中(Busy)时不额外发指令，避免干扰移动/与 _wait_until_idle 抢串口；此时链路显然活着。
        if self.data.get("status") == "Busy":
            return True
        try:
            resp = self._send_command("Hello", timeout=2.0)
        except Exception as e:
            self._on_link_lost()
            raise RuntimeError(f"Zolix 心跳失败: {e}")
        if not resp:
            self._on_link_lost()
            raise RuntimeError("Zolix 心跳失败: Hello 无响应")
        if self.data.get("status") == "Offline":
            self.data["status"] = "Idle"
        return True

    @property
    @topic_config()
    def status(self) -> str:
        return self.data.get("status", "Offline")

    @property
    @topic_config()
    def wavelength(self) -> float:
        """当前波长 (nm)"""
        return float(self.data.get("wavelength", 0.0))

    @property
    @topic_config()
    def wavenumber(self) -> float:
        """当前波数 (cm⁻¹)"""
        return float(self.data.get("wavenumber", 0.0))

    @property
    @topic_config()
    def grating(self) -> str:
        """当前光栅号"""
        return str(self.data.get("grating", "1"))

    @property
    @topic_config()
    def turret(self) -> str:
        """当前光栅台号"""
        return str(self.data.get("turret", "1"))

    @property
    @topic_config()
    def exit_port(self) -> str:
        """当前出口 (0=前置, 1=侧面)"""
        return str(self.data.get("exit_port", "0"))

    @property
    @topic_config()
    def entrance_port(self) -> str:
        """当前入口 (0=前置, 1=侧面)"""
        return str(self.data.get("entrance_port", "0"))

    @property
    @topic_config()
    def system_info(self) -> str:
        """仪器系统信息"""
        return str(self.data.get("system_info", ""))


# ========== 本地硬件冒烟==========
# python zolix_omni_lambda.py --port COM10 [-v]


def _smoke_main():
    import argparse
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from smoke_runner import (
        add_common_args,
        add_serial_args,
        run_smoke,
        setup_logging,
        smoke_lifecycle,
    )

    parser = argparse.ArgumentParser(description="Zolix Omni-λ 单色仪 - 本地硬件冒烟")
    add_serial_args(parser, default_port="COM10", default_baudrate=19200)
    add_common_args(parser)
    args = parser.parse_args()
    setup_logging(args.verbose)

    async def run():
        dev = ZolixOmniLambda(
            device_id="smoke_test",
            config={"port": args.port, "baudrate": args.baudrate},
        )
        return await smoke_lifecycle(dev, read_fn=lambda d: d.query_system_info())

    run_smoke(run)


if __name__ == "__main__":
    _smoke_main()

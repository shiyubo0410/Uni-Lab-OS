
"""
DHJF-2005A / DHJF-4005A low-temperature thermostatic stirring/circulation bath
Modbus RTU RS485 driver for Uni-Lab-OS.

Version note: heating permission is maintained by holding 0x0016.8 high,
based on field logs showing heating output drops when Bit8 is cleared.

Main workflow:
- set_temp(temp) is the high-level user action:
  set target temperature -> single-segment continuous control -> start run -> pulse heat key -> return parsed status.
- set_temperature(temp) is the low-level action:
  only write target temperature register, without starting run/heating.
"""

import inspect
import logging
import time as time_module
from typing import Any, Dict, List, Tuple

try:
    from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode
except ImportError:
    BaseROS2DeviceNode = None

try:
    from pymodbus.client import ModbusSerialClient  # pymodbus 3.x
except Exception:
    try:
        from pymodbus.client.sync import ModbusSerialClient  # pymodbus 2.5.x
    except Exception:
        ModbusSerialClient = None

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
    id="dhjf_circulation_bath",
    category=["heatchill"],
    description="DHJF-2005A/4005A 低温恒温搅拌循环水浴 (Modbus RTU, RS485)",
    display_name="DHJF恒温循环水浴",
)
class DHJFCirculationBath:
    """
    DHJF-2005A / DHJF-4005A temperature bath driver.

    Recommended web actions:
    - set_temp(temp): set target temperature and start continuous thermostatic heating.
    - heat_to(temp): same as set_temp, with optional wait/tolerance parameters.
    - read_status(): parse temperature, run, heating output, alarms.
    """

    _ros_node: "BaseROS2DeviceNode"

    REG_MACHINE_TYPE = 0x0000
    REG_SEGMENT_COUNT = 0x0001
    REG_CURRENT_SEGMENT = 0x0002
    REG_MEASURED_TEMP = 0x0003
    REG_DISPLAY_TEMP = 0x0004
    REG_RUN_TIME_H = 0x0005
    REG_RUN_TIME_M = 0x0006

    REG_SEG = {
        1: (0x0007, 0x0008, 0x0009),
        2: (0x000A, 0x000B, 0x000C),
        3: (0x000D, 0x000E, 0x000F),
        4: (0x0010, 0x0011, 0x0012),
        5: (0x0013, 0x0014, 0x0015),
    }

    REG_CTRL = 0x0016
    BIT_POWER_KEY = 15
    BIT_RUN = 14
    BIT_STIRRING = 13
    BIT_CIRCULATION = 12
    BIT_COOL_OUT = 11       # read-only feedback
    BIT_HEAT_OUT = 10       # read-only feedback
    BIT_COOL_KEY = 9
    BIT_HEAT_KEY = 8

    REG_ALARM = 0x0017
    BIT_RUN_RESULT = 12
    BIT_RUN_STATE = 11
    BIT_LOW_ALARM = 10
    BIT_OVER_ALARM = 9
    BIT_TEMP_OVERFLOW = 7

    def __init__(
        self,
        device_id: str = None,
        port: str = "COM3",
        slave_id: int = 5,
        baudrate: int = 9600,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 1.0,
        key_pulse_sec: float = 0.3,
        **kwargs,
    ):
        """DHJF-2005A 恒温循环水浴驱动 (Modbus RTU)。

        Args:
            device_id: 设备唯一标识。
            port: RS-485 串口号，例如 COM3 或 /dev/ttyUSB0。
            slave_id: Modbus 从站地址，默认 5。
            baudrate: 串口波特率，默认 9600。
            bytesize: 数据位，默认 8。
            parity: 校验位，N/E/O，默认 N。
            stopbits: 停止位，默认 1。
            timeout: 串口读超时时间，单位秒。
            key_pulse_sec: 模拟按键的脉冲时长，单位秒。
        """
        if device_id is None and "id" in kwargs:
            device_id = kwargs.pop("id")
        # 兼容旧的 config 字典传参：平铺参数优先，config 兜底。
        config = kwargs.pop("config", None) or {}

        self.device_id = device_id or "dhjf_circulation_bath"
        self.config = config
        self.logger = logging.getLogger(f"DHJFCirculationBath.{self.device_id}")
        self.logger.setLevel(logging.DEBUG)

        self.port = config.get("port", port)
        self.slave_id = int(config.get("slave_id", slave_id))
        self.baudrate = int(config.get("baudrate", baudrate))
        self.bytesize = int(config.get("bytesize", bytesize))
        self.parity = str(config.get("parity", parity))
        self.stopbits = int(config.get("stopbits", stopbits))
        self.timeout = float(config.get("timeout", timeout))
        self.key_pulse_sec = float(config.get("key_pulse_sec", key_pulse_sec))

        self.client = None
        self._connected = False

        self.data: Dict[str, Any] = {
            "status": "Idle",
            "temp": 0.0,
            "temp_target": 0.0,
            "stir_speed": 0.0,
            "temp_warning": 0.0,
            "segment_count": 1,
            "current_segment": 1,
            "run_time_h": 0,
            "run_time_m": 0,
            "low_temp_alarm": False,
            "over_temp_alarm": False,
            "temp_overflow": False,
            "run": False,
            "run_state": False,
            "run_finished": False,
            "circulation": False,
            "stirring": False,
            "cooling_output": False,
            "heating_output": False,
            "ctrl_hex": "0x0000",
            "alarm_hex": "0x0000",
        }

        self.logger.info(
            "[INIT] DHJF initialized: "
            f"port={self.port}, slave_id={self.slave_id}, baudrate={self.baudrate}, "
            f"{self.bytesize}{self.parity}{self.stopbits}, timeout={self.timeout}, "
            f"key_pulse_sec={self.key_pulse_sec}"
        )

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode"):
        self._ros_node = ros_node
        self.logger.info("[POST_INIT] ROS node set")

    def _detect_param_name(self, func) -> str:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        self.logger.debug(f"[DETECT] Function {func.__name__} params: {params}")
        if "device_id" in params:
            return "device_id"
        if "slave" in params:
            return "slave"
        if "unit" in params:
            return "unit"
        self.logger.warning("[DETECT] No device id parameter detected; calling without slave id")
        return None

    def _mark_disconnected(self):
        self._connected = False
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.client = None

    def _connect(self) -> bool:
        if self._connected and self.client:
            return True
        if ModbusSerialClient is None:
            self.logger.error("[CONNECT] pymodbus/pyserial missing. Install: pip install pymodbus pyserial")
            return False
        self.logger.info(
            f"[CONNECT] Opening {self.port}, slave_id={self.slave_id}, "
            f"baudrate={self.baudrate}, {self.bytesize}{self.parity}{self.stopbits}"
        )
        self.client = ModbusSerialClient(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            timeout=self.timeout,
        )
        ok = bool(self.client.connect())
        if not ok:
            self.logger.error(f"[CONNECT] Failed to open serial port: {self.port}")
            self._mark_disconnected()
            return False
        self._connected = True
        self.logger.info("[CONNECT] Serial port opened")
        return True

    def _disconnect(self):
        self._mark_disconnected()
        self.logger.info("[DISCONNECT] Serial port closed")

    def _read_regs(self, addr: int, count: int = 1):
        if not self._connect():
            self.logger.error(f"[READ] Not connected; failed to read 0x{addr:04X}")
            return None
        fn = self.client.read_holding_registers
        param_name = self._detect_param_name(fn)
        kw = {"address": int(addr), "count": int(count)}
        if param_name:
            kw[param_name] = self.slave_id
        self.logger.debug(f"[READ] read_holding_registers: {kw}")
        try:
            res = fn(**kw)
            if hasattr(res, "isError") and res.isError():
                self.logger.error(f"[READ] Failed: 0x{addr:04X}, response={res}")
                return None
            regs = getattr(res, "registers", None)
            if regs is not None:
                self.logger.info(f"[READ] 0x{addr:04X} = {regs}")
            return regs
        except Exception as e:
            self.logger.error(f"[READ] Exception: 0x{addr:04X}, {e}")
            self._mark_disconnected()
            return None

    def _write_reg(self, addr: int, value: int) -> bool:
        if not self._connect():
            self.logger.error(f"[WRITE] Not connected; failed to write 0x{addr:04X}")
            return False
        fn = self.client.write_register
        param_name = self._detect_param_name(fn)
        val = int(value) & 0xFFFF
        kw = {"address": int(addr), "value": val}
        if param_name:
            kw[param_name] = self.slave_id
        self.logger.debug(f"[WRITE] write_register: {kw}")
        try:
            res = fn(**kw)
            if hasattr(res, "isError") and res.isError():
                self.logger.error(f"[WRITE] Failed: 0x{addr:04X}={val}, response={res}")
                return False
            self.logger.info(f"[WRITE] 0x{addr:04X}={val} written")
            return True
        except Exception as e:
            self.logger.error(f"[WRITE] Exception: 0x{addr:04X}={val}, {e}")
            self._mark_disconnected()
            return False

    def _set_bit(self, addr: int, bit: int, enable: bool, verify: bool = True) -> bool:
        self.logger.info(f"[SET_BIT] 0x{addr:04X}.Bit{bit} = {enable}")
        regs = self._read_regs(addr, 1)
        if not regs:
            self.logger.error("[SET_BIT] Failed: cannot read current word")
            return False
        cur = int(regs[0]) & 0xFFFF
        new_val = (cur | (1 << bit)) if enable else (cur & ~(1 << bit))
        self.logger.debug(f"[SET_BIT] current=0x{cur:04X}, new=0x{new_val:04X}")
        ok = self._write_reg(addr, new_val)
        if ok and verify:
            verify_regs = self._read_regs(addr, 1)
            if verify_regs:
                self.logger.info(f"[SET_BIT] verified=0x{int(verify_regs[0]) & 0xFFFF:04X}")
        return ok

    async def _sleep(self, seconds: float):
        seconds = max(float(seconds), 0.0)
        if getattr(self, "_ros_node", None):
            await self._ros_node.sleep(seconds)
        else:
            time_module.sleep(seconds)

    async def _pulse_bit(self, addr: int, bit: int, pulse_sec: float = None) -> bool:
        if pulse_sec is None:
            pulse_sec = self.key_pulse_sec
        ok = self._set_bit(addr, bit, True, verify=False)
        if not ok:
            return False
        await self._sleep(max(float(pulse_sec), 0.05))
        return self._set_bit(addr, bit, False, verify=True)

    def _encode_temp(self, temp: float) -> int:
        return int(round(float(temp) * 100)) & 0xFFFF

    def _decode_temp(self, raw: int) -> float:
        raw = int(raw) & 0xFFFF
        if raw >= 0x8000:
            raw -= 0x10000
        return raw / 100.0

    def _read_ctrl_word(self) -> int:
        regs = self._read_regs(self.REG_CTRL, 1)
        return int(regs[0]) & 0xFFFF if regs else 0

    def _read_alarm_word(self) -> int:
        regs = self._read_regs(self.REG_ALARM, 1)
        return int(regs[0]) & 0xFFFF if regs else 0

    def _update_from_ctrl_alarm(self, ctrl_v: int, alarm_v: int):
        self.data.update({
            "ctrl_hex": f"0x{ctrl_v:04X}",
            "alarm_hex": f"0x{alarm_v:04X}",
            "run": bool((ctrl_v >> self.BIT_RUN) & 1),
            "stirring": bool((ctrl_v >> self.BIT_STIRRING) & 1),
            "circulation": bool((ctrl_v >> self.BIT_CIRCULATION) & 1),
            "cooling_output": bool((ctrl_v >> self.BIT_COOL_OUT) & 1),
            "heating_output": bool((ctrl_v >> self.BIT_HEAT_OUT) & 1),
            "run_finished": bool((alarm_v >> self.BIT_RUN_RESULT) & 1),
            "run_state": bool((alarm_v >> self.BIT_RUN_STATE) & 1),
            "low_temp_alarm": bool((alarm_v >> self.BIT_LOW_ALARM) & 1),
            "over_temp_alarm": bool((alarm_v >> self.BIT_OVER_ALARM) & 1),
            "temp_overflow": bool((alarm_v >> self.BIT_TEMP_OVERFLOW) & 1),
        })

    def _refresh(self):
        t = self._read_regs(self.REG_MEASURED_TEMP, 1)
        if t:
            self.data["temp"] = self._decode_temp(t[0])
        s1t = self._read_regs(self.REG_SEG[1][0], 1)
        if s1t:
            self.data["temp_target"] = self._decode_temp(s1t[0])
        sc = self._read_regs(self.REG_SEGMENT_COUNT, 1)
        if sc:
            self.data["segment_count"] = int(sc[0])
        cs = self._read_regs(self.REG_CURRENT_SEGMENT, 1)
        if cs:
            self.data["current_segment"] = int(cs[0])
        hh = self._read_regs(self.REG_RUN_TIME_H, 1)
        if hh:
            self.data["run_time_h"] = int(hh[0])
        mm = self._read_regs(self.REG_RUN_TIME_M, 1)
        if mm:
            self.data["run_time_m"] = int(mm[0])
        ctrl_v = self._read_ctrl_word()
        alarm_v = self._read_alarm_word()
        self._update_from_ctrl_alarm(ctrl_v, alarm_v)

    @action()
    async def initialize(self, **kwargs) -> bool:
        self.logger.info("[INITIALIZE] Starting device initialization")
        self.data["status"] = "Busy"
        if not self._connect():
            self.data["status"] = "Idle"
            return False
        machine_type = self._read_regs(self.REG_MACHINE_TYPE, 1)
        if not machine_type:
            self.logger.error(
                f"[INITIALIZE] No device response. Check port={self.port}, slave_id={self.slave_id}, "
                f"baudrate={self.baudrate}, wiring, and 8N1."
            )
            self.data["status"] = "Idle"
            return False
        self.logger.info(f"[INITIALIZE] Device responded, machine_type={machine_type}")
        self._refresh()
        self.data["status"] = "Idle"
        self.logger.info("[INITIALIZE] Done")
        return True

    @action()
    async def cleanup(self, **kwargs) -> bool:
        self._disconnect()
        self.data["status"] = "Idle"
        return True

    @property
    def status(self) -> str:
        return self.data.get("status", "Idle")
    @property
    def temp(self) -> float:
        return float(self.data.get("temp", 0.0))
    @property
    def temp_target(self) -> float:
        return float(self.data.get("temp_target", 0.0))
    @property
    def stir_speed(self) -> float:
        return float(self.data.get("stir_speed", 0.0))
    @property
    def temp_warning(self) -> float:
        return float(self.data.get("temp_warning", 0.0))
    @property
    def segment_count(self) -> int:
        return int(self.data.get("segment_count", 1))
    @property
    def current_segment(self) -> int:
        return int(self.data.get("current_segment", 1))
    @property
    def run_time_h(self) -> int:
        return int(self.data.get("run_time_h", 0))
    @property
    def run_time_m(self) -> int:
        return int(self.data.get("run_time_m", 0))
    @property
    def low_temp_alarm(self) -> bool:
        return bool(self.data.get("low_temp_alarm", False))
    @property
    def over_temp_alarm(self) -> bool:
        return bool(self.data.get("over_temp_alarm", False))
    @property
    def heating_output(self) -> bool:
        return bool(self.data.get("heating_output", False))
    @property
    def cooling_output(self) -> bool:
        return bool(self.data.get("cooling_output", False))

    @action()
    async def read_status(self, **kwargs) -> Dict[str, Any]:
        t = self._read_regs(self.REG_MEASURED_TEMP, 1)
        target = self._read_regs(self.REG_SEG[1][0], 1)
        ctrl_v = self._read_ctrl_word()
        alarm_v = self._read_alarm_word()
        current_temp = self._decode_temp(t[0]) if t else None
        target_temp = self._decode_temp(target[0]) if target else None
        if current_temp is not None:
            self.data["temp"] = current_temp
        if target_temp is not None:
            self.data["temp_target"] = target_temp
        self._update_from_ctrl_alarm(ctrl_v, alarm_v)
        result = {
            "success": bool(t or target or ctrl_v or alarm_v),
            "temp": current_temp,
            "temp_target": target_temp,
            "ctrl_hex": f"0x{ctrl_v:04X}",
            "alarm_hex": f"0x{alarm_v:04X}",
            "power_key_or_state": bool((ctrl_v >> self.BIT_POWER_KEY) & 1),
            "run": bool((ctrl_v >> self.BIT_RUN) & 1),
            "stirring": bool((ctrl_v >> self.BIT_STIRRING) & 1),
            "circulation": bool((ctrl_v >> self.BIT_CIRCULATION) & 1),
            "cooling_output": bool((ctrl_v >> self.BIT_COOL_OUT) & 1),
            "heating_output": bool((ctrl_v >> self.BIT_HEAT_OUT) & 1),
            "cool_key": bool((ctrl_v >> self.BIT_COOL_KEY) & 1),
            "heat_key": bool((ctrl_v >> self.BIT_HEAT_KEY) & 1),
            "run_finished": bool((alarm_v >> self.BIT_RUN_RESULT) & 1),
            "run_state": bool((alarm_v >> self.BIT_RUN_STATE) & 1),
            "low_temp_alarm": bool((alarm_v >> self.BIT_LOW_ALARM) & 1),
            "over_temp_alarm": bool((alarm_v >> self.BIT_OVER_ALARM) & 1),
            "temp_overflow": bool((alarm_v >> self.BIT_TEMP_OVERFLOW) & 1),
        }
        self.logger.info(f"[READ_STATUS] {result}")
        return result

    @action()
    async def info(self, **kwargs) -> Dict[str, Any]:
        machine = self._read_regs(self.REG_MACHINE_TYPE, 1)
        status = await self.read_status()
        return {
            "success": bool(machine),
            "device_id": self.device_id,
            "port": self.port,
            "slave_id": self.slave_id,
            "baudrate": self.baudrate,
            "serial": f"{self.bytesize}{self.parity}{self.stopbits}",
            "machine_type": machine[0] if machine else None,
            "status": status,
        }

    @action()
    async def set_temperature(self, temp: float, **kwargs) -> bool:
        temp = float(temp)
        addr = self.REG_SEG[1][0]
        val = self._encode_temp(temp)
        self.logger.info(f"[SET_TEMPERATURE] 0x{addr:04X}={val}, temp={temp} °C")
        ok = self._write_reg(addr, val)
        if ok:
            self.data["temp_target"] = temp
            verify = self._read_regs(addr, 1)
            if verify:
                actual = self._decode_temp(verify[0])
                self.logger.info(f"[SET_TEMPERATURE] verify={actual} °C, raw={verify[0]}")
        return ok

    @action()
    async def set_temp(self, temp: float, **kwargs) -> Dict[str, Any]:
        return await self.heat_to(temp=temp, wait=False, **kwargs)

    @action()
    async def heat_to(
        self,
        temp: float,
        tolerance: float = 0.5,
        wait: bool = False,
        timeout: float = 3600,
        poll_interval: float = 5.0,
        enable_circulation: bool = False,
        enable_stirring: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        temp = float(temp)
        tolerance = float(tolerance)
        timeout = float(timeout)
        poll_interval = float(poll_interval)
        self.logger.info(f"[HEAT_TO] temp={temp} °C, wait={wait}, circulation={enable_circulation}, stirring={enable_stirring}")
        self.data["status"] = "Busy"
        ok = True
        ok &= await self.set_segments(1)
        ok &= await self.set_segment(1, temp, 0, 0)
        if enable_circulation:
            ok &= await self.start_circulation()
        if enable_stirring:
            ok &= await self.start_stirring()
        ok &= self._set_bit(self.REG_CTRL, self.BIT_RUN, True)
        # 保持加热允许 Bit8=1；不要用脉冲清零，否则加热输出会消失。
        ok &= self._set_bit(self.REG_CTRL, self.BIT_HEAT_KEY, True)
        status = await self.read_status()
        if not ok:
            self.data["status"] = "Idle"
            return {"success": False, "message": "Failed to set target or start thermostatic heating", "status": status}
        if not wait:
            self.data["status"] = "Idle"
            return {
                "success": True,
                "message": f"Target set to {temp} °C. Run bit and heat enable have been applied; internal controller will hold temperature.",
                "status": status,
            }
        start_time = time_module.time()
        while True:
            status = await self.read_status()
            current = status.get("temp")
            if current is not None and abs(float(current) - temp) <= tolerance:
                self.data["status"] = "Idle"
                return {"success": True, "message": f"Reached target {temp} °C; current={current} °C", "status": status}
            if status.get("low_temp_alarm") or status.get("over_temp_alarm") or status.get("temp_overflow"):
                self.data["status"] = "Idle"
                return {"success": False, "message": "Alarm detected while waiting for target temperature", "status": status}
            if time_module.time() - start_time > timeout:
                self.data["status"] = "Idle"
                return {"success": False, "message": f"Timeout before reaching target {temp} °C", "status": status}
            await self._sleep(poll_interval)

    @action()
    async def start(self, **kwargs) -> bool:
        self.data["status"] = "Busy"
        ok = self._set_bit(self.REG_CTRL, self.BIT_RUN, True)
        await self.read_status()
        self.data["status"] = "Idle"
        return ok

    @action()
    async def stop(self, **kwargs) -> bool:
        self.data["status"] = "Busy"
        ok = self._set_bit(self.REG_CTRL, self.BIT_RUN, False)
        await self.read_status()
        self.data["status"] = "Idle"
        return ok

    @action()
    async def start_run(self, **kwargs) -> bool:
        return await self.start(**kwargs)
    @action()
    async def stop_run(self, **kwargs) -> bool:
        return await self.stop(**kwargs)

    @action()
    async def start_stirring(self, **kwargs) -> bool:
        ok = self._set_bit(self.REG_CTRL, self.BIT_STIRRING, True)
        await self.read_status()
        return ok
    @action()
    async def stop_stirring(self, **kwargs) -> bool:
        ok = self._set_bit(self.REG_CTRL, self.BIT_STIRRING, False)
        await self.read_status()
        return ok
    @action()
    async def stir_on(self, **kwargs) -> bool:
        return await self.start_stirring(**kwargs)
    @action()
    async def stir_off(self, **kwargs) -> bool:
        return await self.stop_stirring(**kwargs)
    @action()
    async def set_stir_speed(self, speed: float, **kwargs) -> bool:
        self.data["stir_speed"] = float(speed)
        self.logger.warning("[SET_STIR_SPEED] Only cached in data; real speed is hardware-knob controlled")
        return True

    @action()
    async def start_circulation(self, **kwargs) -> bool:
        ok = self._set_bit(self.REG_CTRL, self.BIT_CIRCULATION, True)
        await self.read_status()
        return ok
    @action()
    async def stop_circulation(self, **kwargs) -> bool:
        ok = self._set_bit(self.REG_CTRL, self.BIT_CIRCULATION, False)
        await self.read_status()
        return ok
    @action()
    async def circ_on(self, **kwargs) -> bool:
        return await self.start_circulation(**kwargs)
    @action()
    async def circ_off(self, **kwargs) -> bool:
        return await self.stop_circulation(**kwargs)

    @action()
    async def start_heating(self, **kwargs) -> bool:
        """
        开启加热允许：保持 0x0016.8 = 1。

        实测日志显示：
        - 0xC100：加热允许 Bit8 已置 1
        - 0xC500：加热允许 Bit8 + 加热输出 Bit10 同时为 1
        - 清除 Bit8 后寄存器回到 0xC000，加热输出消失

        因此本机型的 Modbus 加热允许不应按短脉冲处理，而应保持 Bit8=1，
        直到调用 stop_heating()/heat_off()。
        """
        ok = self._set_bit(self.REG_CTRL, self.BIT_HEAT_KEY, True)
        await self.read_status()
        return ok
    @action()
    async def stop_heating(self, **kwargs) -> bool:
        """
        关闭加热允许：设置 0x0016.8 = 0。
        注意：0x0016.10 是加热输出反馈位，只读，不要强行写入。
        """
        ok = self._set_bit(self.REG_CTRL, self.BIT_HEAT_KEY, False)
        await self.read_status()
        return ok
    @action()
    async def heat_on(self, **kwargs) -> bool:
        return await self.start_heating(**kwargs)
    @action()
    async def heat_off(self, **kwargs) -> bool:
        return await self.stop_heating(**kwargs)

    @action()
    async def start_cooling(self, **kwargs) -> bool:
        ok = await self._pulse_bit(self.REG_CTRL, self.BIT_COOL_KEY, self.key_pulse_sec)
        await self.read_status()
        return ok
    @action()
    async def stop_cooling(self, **kwargs) -> bool:
        ok = await self._pulse_bit(self.REG_CTRL, self.BIT_COOL_KEY, self.key_pulse_sec)
        await self.read_status()
        return ok
    @action()
    async def cool_on(self, **kwargs) -> bool:
        return await self.start_cooling(**kwargs)
    @action()
    async def cool_off(self, **kwargs) -> bool:
        return await self.stop_cooling(**kwargs)

    @action()
    async def power_on(self, **kwargs) -> bool:
        ok = await self._pulse_bit(self.REG_CTRL, self.BIT_POWER_KEY, self.key_pulse_sec)
        await self.read_status()
        return ok
    @action()
    async def power_off(self, **kwargs) -> bool:
        ok = await self._pulse_bit(self.REG_CTRL, self.BIT_POWER_KEY, self.key_pulse_sec)
        await self.read_status()
        return ok

    @action()
    async def set_segments(self, count: int, **kwargs) -> bool:
        count = int(count)
        if count < 1 or count > 5:
            self.logger.error(f"[SET_SEGMENTS] invalid count={count}; expected 1..5")
            return False
        ok = self._write_reg(self.REG_SEGMENT_COUNT, count)
        if ok:
            self.data["segment_count"] = count
        return ok

    @action()
    async def set_segment(self, index: int, temperature: float, hours: int, minutes: int, **kwargs) -> bool:
        index = int(index)
        temperature = float(temperature)
        hours = int(hours)
        minutes = int(minutes)
        if index not in self.REG_SEG or hours < 0 or minutes < 0 or minutes > 59:
            self.logger.error(f"[SET_SEGMENT] invalid parameters: index={index}, hours={hours}, minutes={minutes}")
            return False
        reg_t, reg_h, reg_m = self.REG_SEG[index]
        ok = True
        ok &= self._write_reg(reg_t, self._encode_temp(temperature))
        ok &= self._write_reg(reg_h, hours & 0xFFFF)
        ok &= self._write_reg(reg_m, minutes & 0xFFFF)
        if index == 1 and ok:
            self.data["temp_target"] = temperature
        return ok

    @action()
    async def set_seg(self, index: int, temperature: float, hours: int = 0, minutes: int = 0, **kwargs) -> bool:
        return await self.set_segment(index=index, temperature=temperature, hours=hours, minutes=minutes, **kwargs)

    @action()
    async def program(self, segments: List[Tuple[float, int, int]], **kwargs) -> bool:
        n = len(segments)
        if n < 1 or n > 5:
            self.logger.error(f"[PROGRAM] invalid number of segments: {n}")
            return False
        ok = await self.set_segments(n)
        for i, triplet in enumerate(segments, start=1):
            if len(triplet) != 3:
                self.logger.error(f"[PROGRAM] invalid segment #{i}: {triplet}")
                return False
            t, h, m = float(triplet[0]), int(triplet[1]), int(triplet[2])
            ok &= await self.set_segment(i, t, h, m)
        return ok

    @action()
    async def time(self, **kwargs) -> Dict[str, Any]:
        h = self._read_regs(self.REG_RUN_TIME_H, 1)
        m = self._read_regs(self.REG_RUN_TIME_M, 1)
        if h:
            self.data["run_time_h"] = int(h[0])
        if m:
            self.data["run_time_m"] = int(m[0])
        return {"success": bool(h or m), "run_time_h": self.data["run_time_h"], "run_time_m": self.data["run_time_m"]}

    @action()
    async def set_temp_warning(self, temp: float, **kwargs) -> bool:
        self.data["temp_warning"] = float(temp)
        return True

    @action()
    async def close(self, **kwargs) -> bool:
        return await self.cleanup(**kwargs)

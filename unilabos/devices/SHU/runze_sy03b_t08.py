"""
Runze SY-03B Ceramic Syringe Pump Driver for T-08 distribution valve
润泽 SY-03B 陶瓷阀芯注射泵驱动（T-08 八通分配阀）

Key fixes in this version:
1. Treat T-08 as a distribution valve: C connects selectively to port 1-8.
   Valve selection uses I<n>R uniformly by default, like Uni-Lab-OS Runze backbone logic.
2. Do NOT judge idle by response address "0". Parse the SY-03B status byte.
   Ready/idle is status_byte & 0x20 != 0, normally '`' (0x60).
   Busy/not-ready is usually '@' (0x40).
3. Detect non-zero low-nibble error codes, especially error 15 command overflow.
4. Use CRLF command ending for better compatibility: /<addr><cmd>\r\n.
5. Add moderate default speeds for 25 mL syringe:
   aspirate_velocity_ml_s = 1.4 mL/s -> V336
   dispense_velocity_ml_s = 2.8 mL/s -> V672
   post_pull_settle_seconds = 3.0 s for liquid settling after aspiration
   post_push_settle_seconds = 1.5 s after dispense
   These can be overridden in JSON config.
"""

import asyncio
import logging
import serial
import time as time_module
from typing import Dict, Any, Optional, Tuple

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
    id="runze_sy03b_t08",
    category=["pump"],
    description="润泽 SY-03B 陶瓷阀芯注射泵 (T-08 八通分配阀, RS485)",
    display_name="润泽SY-03B注射泵",
)
class RunzeSY03BT08:
    """Runze SY-03B syringe pump with T-08 distribution valve."""

    _ros_node: "BaseROS2DeviceNode"

    SYRINGE_STEPS_PER_ML = {
        25.0: 240,  # 25 mL syringe, 6000 steps full stroke
        10.0: 600,
        5.0: 1200,
        2.5: 2400,
        1.0: 6000,
    }

    ERROR_CODES = {
        0: "No error",
        1: "Initialization error",
        2: "Invalid command",
        3: "Invalid operand",
        6: "EPROM failure",
        7: "Device not initialized",
        8: "Internal error",
        9: "Syringe overload",
        10: "Valve overload",
        11: "Plunger movement not allowed at current valve position",
        12: "Internal fault",
        14: "A/D converter fault",
        15: "Command overflow: command sent before previous motion completed",
    }

    def __init__(
        self,
        device_id: str = None,
        port: str = "COM4",
        baudrate: int = 9600,
        address: int = 8,
        serial_timeout: float = 1.0,
        max_volume: float = 25.0,
        valve_select_command: str = "I",
        aspirate_velocity_ml_s: float = 1.4,
        dispense_velocity_ml_s: float = 2.8,
        post_pull_settle_seconds: float = 3.0,
        post_push_settle_seconds: float = 1.5,
        valve_settle_seconds: float = 0.5,
        **kwargs,
    ):
        """润泽 SY-03B (T-08 分配阀) 注射泵驱动。

        Args:
            device_id: 设备唯一标识。
            port: RS-485 串口号，例如 COM4 或 /dev/ttyUSB0。
            baudrate: 串口波特率，默认 9600。
            address: 泵的 RS-485 从站地址，默认 8。
            serial_timeout: 串口读超时时间，单位秒。
            max_volume: 注射器量程 (mL)，默认 25。
            valve_select_command: T-08 阀选通指令，I 或 O，默认 I。
            aspirate_velocity_ml_s: 抽液速度 (mL/s)，默认 1.4。
            dispense_velocity_ml_s: 排液速度 (mL/s)，默认 2.8。
            post_pull_settle_seconds: 抽液完成后稳定等待，单位秒。
            post_push_settle_seconds: 排液完成后稳定等待，单位秒。
            valve_settle_seconds: 阀切换后稳定等待，单位秒。
        """
        if device_id is None and "id" in kwargs:
            device_id = kwargs.pop("id")
        # 兼容旧的 config 字典传参：平铺参数优先，config 兜底。
        config = kwargs.pop("config", None) or {}

        self.device_id = device_id or "runze_sy03b_t08"
        self.config = config

        self.logger = logging.getLogger(f"RunzeSY03BT08.{self.device_id}")

        self.port = config.get("port", port)
        self.baudrate = int(config.get("baudrate", baudrate))
        self.address = int(config.get("address", address))
        self.ascii_address = str(self.address)
        self.serial_timeout = float(config.get("serial_timeout", serial_timeout))

        # Accept both old and new config names.
        self.syringe_volume = float(
            self.config.get("syringe_volume", self.config.get("max_volume", max_volume))
        )
        self.steps_per_ml = int(
            self.config.get(
                "steps_per_ml",
                self.SYRINGE_STEPS_PER_ML.get(self.syringe_volume, int(6000 / self.syringe_volume)),
            )
        )
        self.max_steps = int(self.config.get("max_steps", self.syringe_volume * self.steps_per_ml))

        # T-08 distribution valve: use I<n>R by default for valve selection.
        # If your actual device requires reverse direction, set valve_select_command="O" in JSON.
        self.valve_select_command = str(self.config.get("valve_select_command", valve_select_command)).upper()[0]
        if self.valve_select_command not in ("I", "O"):
            self.valve_select_command = "I"

        # Faster but still conservative defaults. For 25 mL syringe:
        # V336 ≈ 1.4 mL/s aspiration, V672 ≈ 2.8 mL/s dispense.
        self.aspirate_velocity_ml_s = float(self.config.get("aspirate_velocity_ml_s", aspirate_velocity_ml_s))
        self.dispense_velocity_ml_s = float(self.config.get("dispense_velocity_ml_s", dispense_velocity_ml_s))
        self.aspirate_velocity_grade = int(
            self.config.get("aspirate_velocity_grade", self._ml_s_to_velocity_grade(self.aspirate_velocity_ml_s))
        )
        self.dispense_velocity_grade = int(
            self.config.get("dispense_velocity_grade", self._ml_s_to_velocity_grade(self.dispense_velocity_ml_s))
        )
        self.aspirate_velocity_grade = self._clamp_velocity_grade(self.aspirate_velocity_grade)
        self.dispense_velocity_grade = self._clamp_velocity_grade(self.dispense_velocity_grade)

        # Settling wait after confirmed motion completion, not a replacement for Q waiting.
        self.post_pull_settle_seconds = float(self.config.get("post_pull_settle_seconds", post_pull_settle_seconds))
        self.post_push_settle_seconds = float(self.config.get("post_push_settle_seconds", post_push_settle_seconds))
        self.valve_settle_seconds = float(self.config.get("valve_settle_seconds", valve_settle_seconds))

        self.serial: Optional[serial.Serial] = None
        self._initialized = False
        self._velocity = self.aspirate_velocity_grade

        self.data = {
            "status": "Offline",
            "valve_position": "0",
            "position": 0.0,
            "max_velocity": self.aspirate_velocity_ml_s,
            "mode": 0,
            "plunger_position": "0",
            "velocity_grade": str(self._velocity),
            "velocity_init": str(self.aspirate_velocity_grade),
            "velocity_end": str(self.dispense_velocity_grade),
            "batch_progress": "",
            "last_response": "",
            "last_status_byte": "",
            "last_error_code": 0,
        }

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode"):
        self._ros_node = ros_node

    # ==================== Conversions ====================
    def _ml_to_steps(self, ml: float) -> int:
        return int(round(float(ml) * self.steps_per_ml))

    def _steps_to_ml(self, steps: int) -> float:
        return int(steps) / self.steps_per_ml

    def _clamp_velocity_grade(self, grade: int) -> int:
        return max(1, min(6000, int(grade)))

    def _ml_s_to_velocity_grade(self, velocity_ml_s: float) -> int:
        return self._clamp_velocity_grade(round(float(velocity_ml_s) * self.steps_per_ml))

    def _velocity_grade_to_ml_s(self, grade: int) -> float:
        return self._clamp_velocity_grade(grade) / self.steps_per_ml

    # ==================== Serial helpers ====================
    def _connect(self) -> bool:
        try:
            if self.serial and self.serial.is_open:
                return True
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.serial_timeout,
                write_timeout=self.serial_timeout,
            )
            time_module.sleep(0.1)
            self.logger.info(f"Serial port {self.port} opened at {self.baudrate} bps")
            return True
        except Exception as e:
            self.logger.error(f"Failed to open {self.port}: {e}")
            return False

    def _disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()

    def _send_command(self, command: str, wait_response: bool = True) -> str:
        """Send a raw SY-03B command body, e.g. 'I2R', 'P240R', 'Q', 'ZR'."""
        if not self._connect():
            return ""
        command = str(command).strip()
        frame = f"/{self.ascii_address}{command}\r\n"
        try:
            if self.serial.in_waiting > 0:
                self.serial.read(self.serial.in_waiting)
            self.serial.write(frame.encode("ascii"))
            self.logger.debug(f"Sent: {frame.strip()}")
            if not wait_response:
                return ""

            response = b""
            start_time = time_module.time()
            while time_module.time() - start_time < max(5.0, self.serial_timeout):
                if self.serial.in_waiting > 0:
                    response += self.serial.read(1)
                    if response.endswith(b"\r\n") or response.endswith(b"\r") or response.endswith(b"\n"):
                        # Read trailing ETX or CRLF remnants if present.
                        time_module.sleep(0.03)
                        if self.serial.in_waiting > 0:
                            response += self.serial.read(self.serial.in_waiting)
                        break
                time_module.sleep(0.005)
            text = response.decode("ascii", errors="ignore")
            self.data["last_response"] = repr(text)
            return text
        except Exception as e:
            self.logger.error(f"Communication error while sending {command}: {e}")
            return ""

    def _clean_response(self, response: str) -> str:
        return (
            (response or "")
            .replace("\x03", "")
            .replace("\r", "")
            .replace("\n", "")
            .strip()
        )

    def _parse_response(self, response: str) -> Tuple[str, str]:
        """Backward-compatible parser: returns (address_or_error, payload)."""
        clean = self._clean_response(response)
        if not clean:
            return ("error", "")
        if clean.startswith("?"):
            return ("error", clean[:2])
        if clean.startswith("/"):
            clean = clean[1:]
        if len(clean) >= 1:
            return (clean[0], clean[1:] if len(clean) > 1 else "")
        return ("unknown", clean)

    def _parse_status_byte(self, response: str) -> Dict[str, Any]:
        """Parse SY-03B status byte.

        Response examples seen in logs:
            /0@\x03\r  -> address 0, status byte '@' = 0x40, not ready, no error
            /0`\x03\r  -> address 0, status byte '`' = 0x60, ready, no error
            /0O\x03\r  -> address 0, status byte 'O' = 0x4F, not ready, error 15
        """
        clean = self._clean_response(response)
        result = {
            "raw": response,
            "clean": clean,
            "ok": False,
            "address": "",
            "status_char": "",
            "status_value": None,
            "ready": False,
            "busy": True,
            "error_code": None,
            "error_message": "",
        }
        if not clean:
            result["error_code"] = -1
            result["error_message"] = "Empty response"
            return result
        if clean.startswith("?"):
            result["error_code"] = -2
            result["error_message"] = f"Protocol error response: {clean}"
            return result
        if clean.startswith("/"):
            clean = clean[1:]
        if len(clean) < 2:
            result["error_code"] = -3
            result["error_message"] = f"Response too short: {repr(response)}"
            return result

        status_char = clean[1]
        status_value = ord(status_char)
        ready = bool(status_value & 0x20)  # manual: status bit 5, 1 = ready to accept command
        error_code = status_value & 0x0F
        result.update(
            {
                "ok": True,
                "address": clean[0],
                "status_char": status_char,
                "status_value": status_value,
                "ready": ready,
                "busy": not ready,
                "error_code": error_code,
                "error_message": self.ERROR_CODES.get(error_code, f"Unknown error {error_code}"),
            }
        )
        self.data["last_status_byte"] = f"{status_char} (0x{status_value:02X})"
        self.data["last_error_code"] = error_code
        return result

    def _check_command_response(self, response: str, command_label: str = "command") -> bool:
        info = self._parse_status_byte(response)
        self.logger.info(
            f"{command_label}: response={repr(response)}, status={info.get('status_char')} "
            f"0x{info.get('status_value') if info.get('status_value') is not None else None}, "
            f"ready={info.get('ready')}, error={info.get('error_code')} {info.get('error_message')}"
        )
        if not info["ok"]:
            self.logger.error(f"{command_label}: invalid response: {info['error_message']}")
            return False
        if info["error_code"] not in (0, None):
            self.logger.error(f"{command_label}: device error {info['error_code']} - {info['error_message']}")
            return False
        return True

    def _wait_for_idle(self, timeout: float = 30.0) -> bool:
        start_time = time_module.time()
        last_info = None
        while time_module.time() - start_time < timeout:
            response = self._send_command("Q")
            info = self._parse_status_byte(response)
            last_info = info
            self.logger.debug(
                f"Q status: raw={repr(response)}, ready={info.get('ready')}, "
                f"error={info.get('error_code')} {info.get('error_message')}"
            )
            if info["ok"] and info["error_code"] == 0 and info["ready"]:
                self.logger.info("Pump idle/ready confirmed by Q")
                return True
            if info["ok"] and info["error_code"] not in (0, None, 15):
                self.logger.error(f"Pump reports error via Q: {info['error_code']} {info['error_message']}")
                return False
            time_module.sleep(0.2)
        self.logger.error(f"_wait_for_idle TIMEOUT after {timeout}s, last Q={last_info}")
        return False

    async def _wait_for_idle_async(self, timeout: float = 30.0) -> bool:
        start_time = time_module.time()
        last_info = None
        while time_module.time() - start_time < timeout:
            response = self._send_command("Q")
            info = self._parse_status_byte(response)
            last_info = info
            elapsed = time_module.time() - start_time
            self.logger.debug(
                f"Q status async: ready={info.get('ready')}, error={info.get('error_code')} "
                f"elapsed={elapsed:.1f}s/{timeout:.1f}s, raw={repr(response)}"
            )
            if info["ok"] and info["error_code"] == 0 and info["ready"]:
                self.logger.info(f"Pump idle/ready confirmed by Q after {elapsed:.1f}s")
                return True
            if info["ok"] and info["error_code"] not in (0, None, 15):
                self.logger.error(f"Pump reports error via Q: {info['error_code']} {info['error_message']}")
                return False
            if self._ros_node:
                await self._ros_node.sleep(0.2)
            else:
                await asyncio.sleep(0.2)
        self.logger.error(f"_wait_for_idle_async TIMEOUT after {timeout}s, last Q={last_info}")
        return False

    async def _sleep_async(self, seconds: float):
        if seconds <= 0:
            return
        if self._ros_node:
            await self._ros_node.sleep(float(seconds))
        else:
            await asyncio.sleep(float(seconds))

    # ==================== Lifecycle ====================
    @action()
    async def initialize(self) -> bool:
        self.logger.info("Initializing SY-03B pump...")
        if not self._connect():
            self.data["status"] = "Offline"
            return False
        try:
            # ZR initializes the pump. Keep this close to the original driver.
            resp = self._send_command("ZR")
            if not self._check_command_response(resp, "initialize ZR"):
                self.data["status"] = "Error"
                return False
            if not await self._wait_for_idle_async(timeout=60.0):
                self.data["status"] = "Error"
                return False
            self._initialized = True
            self.data["status"] = "Idle"
            self.data["valve_position"] = "0"
            self.data["position"] = 0.0
            self.data["plunger_position"] = "0"
            self.logger.info("Pump initialized and ready")
            return True
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.data["status"] = "Error"
            return False

    @action()
    async def cleanup(self) -> bool:
        self._disconnect()
        self.data["status"] = "Offline"
        self._initialized = False
        return True

    # ==================== Properties ====================
    @property
    def status(self) -> str:
        return self.data.get("status", "Offline")

    @property
    def valve_position(self) -> str:
        return self.data.get("valve_position", "0")

    @property
    def position(self) -> float:
        return self.data.get("position", 0.0)

    @property
    def max_velocity(self) -> float:
        return self.data.get("max_velocity", self.aspirate_velocity_ml_s)

    @property
    def mode(self) -> int:
        return self.data.get("mode", 0)

    @property
    def plunger_position(self) -> str:
        return self.data.get("plunger_position", "0")

    @property
    def velocity_grade(self) -> str:
        return self.data.get("velocity_grade", str(self._velocity))

    @property
    def velocity_init(self) -> str:
        return self.data.get("velocity_init", str(self.aspirate_velocity_grade))

    @property
    def velocity_end(self) -> str:
        return self.data.get("velocity_end", str(self.dispense_velocity_grade))

    @property
    def batch_progress(self) -> str:
        return self.data.get("batch_progress", "")

    # ==================== Core commands ====================
    @action()
    def set_velocity_grade(self, velocity: str) -> bool:
        if not self._initialized:
            return False
        try:
            grade = self._clamp_velocity_grade(int(float(velocity)))
        except (ValueError, TypeError):
            return False
        resp = self._send_command(f"V{grade}R")
        if not self._check_command_response(resp, f"set_velocity_grade V{grade}R"):
            self.data["status"] = "Error"
            return False
        self._velocity = grade
        self.data["velocity_grade"] = str(grade)
        self.data["max_velocity"] = self._velocity_grade_to_ml_s(grade)
        return True

    @action()
    def set_max_velocity(self, velocity: float) -> bool:
        """Set max velocity in mL/s using V<n> pulses/s."""
        grade = self._ml_s_to_velocity_grade(float(velocity))
        return self.set_velocity_grade(str(grade))

    @action()
    def set_valve_position(self, position: str) -> bool:
        """Select T-08 distribution valve position. Default command is I<n>R."""
        if not self._initialized:
            return False
        try:
            port = int(position)
            if port < 1 or port > 8:
                return False
        except (TypeError, ValueError):
            return False
        if not self._wait_for_idle(timeout=30.0):
            self.data["status"] = "Error"
            return False
        cmd = f"{self.valve_select_command}{port}R"
        self.data["status"] = "Busy"
        resp = self._send_command(cmd)
        if not self._check_command_response(resp, f"set_valve_position {cmd}"):
            self.data["status"] = "Error"
            return False
        if not self._wait_for_idle(timeout=30.0):
            self.data["status"] = "Error"
            return False
        self.data["valve_position"] = str(port)
        self.data["status"] = "Idle"
        return True

    @action()
    def set_position(self, position: float, max_velocity: float = None) -> bool:
        if not self._initialized:
            return False
        if max_velocity is not None and not self.set_max_velocity(max_velocity):
            return False
        target_steps = max(0, min(self.max_steps, self._ml_to_steps(position)))
        if not self._wait_for_idle(timeout=30.0):
            return False
        self.data["status"] = "Busy"
        resp = self._send_command(f"A{target_steps}R")
        if not self._check_command_response(resp, f"set_position A{target_steps}R"):
            self.data["status"] = "Error"
            return False
        timeout = 10.0 + abs(target_steps - int(self.data.get("plunger_position", "0"))) / max(1, self._velocity) + 10.0
        if not self._wait_for_idle(timeout=timeout):
            self.data["status"] = "Error"
            return False
        self.data["position"] = self._steps_to_ml(target_steps)
        self.data["plunger_position"] = str(target_steps)
        self.data["status"] = "Idle"
        return True

    @action()
    def pull_plunger(self, volume: float) -> bool:
        if not self._initialized:
            return False
        steps = self._ml_to_steps(volume)
        if steps <= 0:
            return False
        if not self._wait_for_idle(timeout=30.0):
            return False
        if not self.set_velocity_grade(str(self.aspirate_velocity_grade)):
            return False
        self.data["status"] = "Busy"
        resp = self._send_command(f"P{steps}R")
        if not self._check_command_response(resp, f"pull_plunger P{steps}R"):
            self.data["status"] = "Error"
            return False
        timeout = 10.0 + steps / max(1, self.aspirate_velocity_grade) + 10.0
        if not self._wait_for_idle(timeout=timeout):
            self.data["status"] = "Error"
            return False
        current = int(self.data.get("plunger_position", "0"))
        new_steps = min(self.max_steps, current + steps)
        self.data["plunger_position"] = str(new_steps)
        self.data["position"] = self._steps_to_ml(new_steps)
        self.data["status"] = "Idle"
        return True

    @action()
    def push_plunger(self, volume: float) -> bool:
        if not self._initialized:
            return False
        steps = self._ml_to_steps(volume)
        if steps <= 0:
            return False
        if not self._wait_for_idle(timeout=30.0):
            return False
        if not self.set_velocity_grade(str(self.dispense_velocity_grade)):
            return False
        self.data["status"] = "Busy"
        resp = self._send_command(f"D{steps}R")
        if not self._check_command_response(resp, f"push_plunger D{steps}R"):
            self.data["status"] = "Error"
            return False
        timeout = 10.0 + steps / max(1, self.dispense_velocity_grade) + 10.0
        if not self._wait_for_idle(timeout=timeout):
            self.data["status"] = "Error"
            return False
        current = int(self.data.get("plunger_position", "0"))
        new_steps = max(0, current - steps)
        self.data["plunger_position"] = str(new_steps)
        self.data["position"] = self._steps_to_ml(new_steps)
        self.data["status"] = "Idle"
        return True

    @action()
    def stop_operation(self) -> bool:
        resp = self._send_command("TR")
        ok = self._check_command_response(resp, "stop_operation TR")
        self.data["status"] = "Idle" if ok else "Error"
        return ok

    async def _set_valve_position_async(self, port: int, label: str) -> bool:
        if not await self._wait_for_idle_async(timeout=30.0):
            return False
        cmd = f"{self.valve_select_command}{int(port)}R"
        self.logger.info(f"{label}: selecting valve port {port} by {cmd}")
        resp = self._send_command(cmd)
        if not self._check_command_response(resp, f"{label} {cmd}"):
            return False
        if not await self._wait_for_idle_async(timeout=30.0):
            return False
        self.data["valve_position"] = str(port)
        await self._sleep_async(self.valve_settle_seconds)
        return True

    async def _pull_async(self, volume: float, label: str) -> bool:
        steps = self._ml_to_steps(volume)
        self.logger.info(
            f"{label}: setting aspirate velocity V{self.aspirate_velocity_grade} "
            f"(~{self._velocity_grade_to_ml_s(self.aspirate_velocity_grade):.3f} mL/s)"
        )
        resp_v = self._send_command(f"V{self.aspirate_velocity_grade}R")
        if not self._check_command_response(resp_v, f"{label} V{self.aspirate_velocity_grade}R"):
            return False
        if not await self._wait_for_idle_async(timeout=30.0):
            return False
        self.logger.info(f"{label}: aspirating {volume} mL by P{steps}R")
        resp = self._send_command(f"P{steps}R")
        if not self._check_command_response(resp, f"{label} P{steps}R"):
            return False
        timeout = 10.0 + steps / max(1, self.aspirate_velocity_grade) + 10.0
        if not await self._wait_for_idle_async(timeout=timeout):
            return False
        current = int(self.data.get("plunger_position", "0"))
        new_steps = min(self.max_steps, current + steps)
        self.data["plunger_position"] = str(new_steps)
        self.data["position"] = self._steps_to_ml(new_steps)
        if self.post_pull_settle_seconds > 0:
            self.logger.info(f"{label}: post-pull settling {self.post_pull_settle_seconds:.1f}s")
            await self._sleep_async(self.post_pull_settle_seconds)
        return True

    async def _push_async(self, volume: float, label: str) -> bool:
        steps = self._ml_to_steps(volume)
        self.logger.info(
            f"{label}: setting dispense velocity V{self.dispense_velocity_grade} "
            f"(~{self._velocity_grade_to_ml_s(self.dispense_velocity_grade):.3f} mL/s)"
        )
        resp_v = self._send_command(f"V{self.dispense_velocity_grade}R")
        if not self._check_command_response(resp_v, f"{label} V{self.dispense_velocity_grade}R"):
            return False
        if not await self._wait_for_idle_async(timeout=30.0):
            return False
        self.logger.info(f"{label}: dispensing {volume} mL by D{steps}R")
        resp = self._send_command(f"D{steps}R")
        if not self._check_command_response(resp, f"{label} D{steps}R"):
            return False
        timeout = 10.0 + steps / max(1, self.dispense_velocity_grade) + 10.0
        if not await self._wait_for_idle_async(timeout=timeout):
            return False
        current = int(self.data.get("plunger_position", "0"))
        new_steps = max(0, current - steps)
        self.data["plunger_position"] = str(new_steps)
        self.data["position"] = self._steps_to_ml(new_steps)
        if self.post_push_settle_seconds > 0:
            self.logger.info(f"{label}: post-push settling {self.post_push_settle_seconds:.1f}s")
            await self._sleep_async(self.post_push_settle_seconds)
        return True

    # ==================== Batch dispensing ====================
    @action()
    async def batch_dispense(self, inlet_port: int, outlet_port: int, volume: float, cycles: int) -> str:
        if not self._initialized:
            self.logger.error("Pump not initialized, cannot batch_dispense")
            return "Error: pump not initialized"
        try:
            inlet_port = int(inlet_port)
            outlet_port = int(outlet_port)
            volume = float(volume)
            cycles = int(cycles)
        except (TypeError, ValueError):
            return "Error: inlet_port/outlet_port/volume/cycles type invalid"
        if not (1 <= inlet_port <= 8):
            return f"Error: inlet_port {inlet_port} out of range 1-8"
        if not (1 <= outlet_port <= 8):
            return f"Error: outlet_port {outlet_port} out of range 1-8"
        if inlet_port == outlet_port:
            return "Error: inlet_port and outlet_port should not be the same"
        if volume <= 0 or volume > self.syringe_volume:
            return f"Error: volume {volume}mL invalid, valid range: 0-{self.syringe_volume}mL"
        if cycles <= 0:
            return f"Error: cycles {cycles} must be positive"

        self.data["status"] = "Busy"
        total_volume = volume * cycles
        self.logger.info(
            f"batch_dispense START: inlet={inlet_port}, outlet={outlet_port}, "
            f"volume={volume}mL, cycles={cycles}, total={total_volume}mL, "
            f"valve_cmd={self.valve_select_command}, Vasp={self.aspirate_velocity_grade}, "
            f"Vdisp={self.dispense_velocity_grade}"
        )

        completed = 0
        for i in range(cycles):
            label = f"Cycle {i + 1}/{cycles}"
            self.data["batch_progress"] = f"{i + 1}/{cycles} - valve to inlet {inlet_port}"
            if not await self._set_valve_position_async(inlet_port, label):
                self.data["status"] = "Error"
                return f"Error: valve to inlet failed at cycle {i + 1}"

            self.data["batch_progress"] = f"{i + 1}/{cycles} - pull {volume}mL"
            if not await self._pull_async(volume, label):
                self.data["status"] = "Error"
                return f"Error: pull failed at cycle {i + 1}"

            self.logger.info(
                f"{label}: pull done, position={self.data['position']}mL, "
                f"plunger_position={self.data['plunger_position']} steps"
            )

            self.data["batch_progress"] = f"{i + 1}/{cycles} - valve to outlet {outlet_port}"
            if not await self._set_valve_position_async(outlet_port, label):
                self.data["status"] = "Error"
                return f"Error: valve to outlet failed at cycle {i + 1}"

            self.data["batch_progress"] = f"{i + 1}/{cycles} - push {volume}mL"
            if not await self._push_async(volume, label):
                self.data["status"] = "Error"
                return f"Error: push failed at cycle {i + 1}"

            self.logger.info(
                f"{label}: push done, position={self.data['position']}mL, "
                f"plunger_position={self.data['plunger_position']} steps"
            )
            completed += 1
            self.logger.info(f"{label}: COMPLETED ({completed}/{cycles})")

        self.data["status"] = "Idle"
        result = f"batch_dispense done: {completed} cycles, {volume}mL/cycle, {total_volume}mL total"
        self.data["batch_progress"] = result
        self.logger.info(result)
        return result

    # ==================== Debug helpers ====================
    @action()
    def raw_command(self, command: str) -> str:
        if command is None:
            return "Error: command is None"
        cmd = str(command).strip()
        if not cmd:
            return "Error: empty command"
        resp = self._send_command(cmd)
        info = self._parse_status_byte(resp)
        result = (
            f"raw_command {cmd}: response={repr(resp)}, ready={info.get('ready')}, "
            f"error={info.get('error_code')} {info.get('error_message')}, "
            f"status={info.get('last_status_byte', info.get('status_char'))}"
        )
        self.logger.info(result)
        return result

    @action()
    async def test_port_aspirate(
        self,
        port: int,
        volume: float = 1.0,
        valve_command: str = None,
        velocity_grade: int = None,
        wait_seconds: float = 0.0,
    ) -> str:
        """Small diagnostic: select one port and aspirate only. No dispense."""
        if not self._initialized:
            return "Error: pump not initialized"
        port = int(port)
        volume = float(volume)
        cmd_letter = (valve_command or self.valve_select_command).upper()[0]
        if cmd_letter not in ("I", "O"):
            return "Error: valve_command must be I or O"
        if not (1 <= port <= 8):
            return "Error: port out of range 1-8"
        steps = self._ml_to_steps(volume)
        grade = self._clamp_velocity_grade(velocity_grade or self.aspirate_velocity_grade)
        label = f"test_port_aspirate port={port}"

        if not await self._wait_for_idle_async(timeout=30.0):
            return "Error: pump not idle before test"
        r1 = self._send_command(f"{cmd_letter}{port}R")
        if not self._check_command_response(r1, f"{label} {cmd_letter}{port}R"):
            return f"Error: valve command failed, response={repr(r1)}"
        if not await self._wait_for_idle_async(timeout=30.0):
            return "Error: valve did not become idle"
        await self._sleep_async(self.valve_settle_seconds)
        r2 = self._send_command(f"V{grade}R")
        if not self._check_command_response(r2, f"{label} V{grade}R"):
            return f"Error: velocity command failed, response={repr(r2)}"
        if not await self._wait_for_idle_async(timeout=30.0):
            return "Error: pump not idle after velocity"
        r3 = self._send_command(f"P{steps}R")
        if not self._check_command_response(r3, f"{label} P{steps}R"):
            return f"Error: aspirate command failed, response={repr(r3)}"
        timeout = 10.0 + steps / max(1, grade) + 10.0
        if not await self._wait_for_idle_async(timeout=timeout):
            return "Error: aspirate motion did not complete"
        if wait_seconds:
            await self._sleep_async(float(wait_seconds))
        current = int(self.data.get("plunger_position", "0"))
        new_steps = min(self.max_steps, current + steps)
        self.data["plunger_position"] = str(new_steps)
        self.data["position"] = self._steps_to_ml(new_steps)
        return (
            f"test_port_aspirate done: {cmd_letter}{port}R -> V{grade}R -> P{steps}R; "
            f"position={self.data['position']}mL"
        )

    # Uni-Lab compatibility
    @not_action
    def open(self) -> bool:
        return True

    @not_action
    def close(self) -> bool:
        return True

    @not_action
    def is_open(self) -> bool:
        return True

    @not_action
    def is_closed(self) -> bool:
        return False


DEVICE_CLASS = RunzeSY03BT08

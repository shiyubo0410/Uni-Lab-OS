"""SJS Elite 机械臂驱动 —— PC 做 Modbus 主站，机械臂做从站。

寄存器约定（机器人从站侧保持寄存器）：
  256 — 开始
  257 — 取瓶子 / 取瓶子1
  258 — 放瓶子 / 放入瓶子1
  259 — 拿样品 / 取样品1
  260 — 取样品2（原 放回瓶子）
  261 — 取样品3（原 放回样品）
  262 — 放回样品3
  263 — 放回瓶子1
  280 — 混合开始

运行状态监控：
  轮询第300位寄存器，值为1表示动作未结束，值为0表示动作完成
"""

import logging
import socket
import struct
import time
from typing import Any, Dict, List, Optional

from unilabos.registry.decorators import action, device, not_action, topic_config
from unilabos.ros.nodes.base_device_node import BaseROS2DeviceNode

logger = logging.getLogger(__name__)

REG_START = 256
REG_PICK_BOTTLE = 257
REG_PLACE_BOTTLE = 258
REG_PICK_SAMPLE = 259
REG_RETURN_BOTTLE = 260
REG_RETURN_SAMPLE = 261

REG_PICK_BOTTLE_1 = 257
REG_PLACE_BOTTLE_1_IN = 258
REG_PICK_SAMPLE_1 = 259
REG_PICK_SAMPLE_2 = 260
REG_PICK_SAMPLE_3 = 261
REG_RETURN_SAMPLE_3 = 262
REG_RETURN_BOTTLE_1 = 263

REG_MIX_START = 280

ALL_ACTION_REGS = [
    REG_START, REG_PICK_BOTTLE, REG_PLACE_BOTTLE,
    REG_PICK_SAMPLE, REG_RETURN_BOTTLE, REG_RETURN_SAMPLE,
    REG_RETURN_SAMPLE_3, REG_RETURN_BOTTLE_1,
    REG_MIX_START,
]

REG_STATUS = 300


@device(
    id="arm.elite.sjs",
    category=["arm"],
    description="SJS Elite 机械臂 (PC 主站 Modbus TCP 控制)",
    display_name="SJS Elite 机械臂",
)
class SjsEliteArm:
    """PC 端 Modbus TCP 主站驱动，连接机械臂内置 Modbus Server (端口 502)。

    机器人端示教器程序通过轮询寄存器 256-261 来执行对应动作，
    运行期间第300位寄存器置1，完成后置0。
    """

    _ros_node: BaseROS2DeviceNode

    def __init__(
        self,
        device_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        host: str = "192.168.1.100",
        modbus_port: int = 502,
        unit_id: int = 1,
        poll_interval: float = 0.3,
        timeout: float = 120.0,
        **kwargs,
    ):
        self.device_id = device_id or "sjs_elite"
        self.config = config or {}
        self.host = self.config.get("host", host)
        self.modbus_port = self.config.get("modbus_port", modbus_port)
        self.unit_id = self.config.get("unit_id", unit_id)
        self.poll_interval = self.config.get("poll_interval", poll_interval)
        self.timeout = self.config.get("timeout", timeout)

        self._task_state: str = "Idle"
        self._sock: Optional[socket.socket] = None
        self._transaction_id: int = 0

        self._connect()

    def _connect(self):
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((self.host, self.modbus_port))
            self._task_state = "Connected"
            logger.info("已连接到机械臂 %s:%d", self.host, self.modbus_port)
        except Exception as e:
            logger.error("连接机械臂失败: %s", e)
            self._task_state = "Error"
            self._sock = None

    @not_action
    def post_init(self, ros_node: BaseROS2DeviceNode) -> None:
        self._ros_node = ros_node

    # ──────────────── Modbus TCP 底层 ────────────────

    def _next_tid(self) -> int:
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        return self._transaction_id

    @not_action
    def write_register(self, address: int, value: int) -> bool:
        """写单个保持寄存器 (FC 0x06)"""
        if not self._sock:
            raise ConnectionError("未连接")
        tid = self._next_tid()
        request = struct.pack(
            ">HHHBBHH", tid, 0, 6, self.unit_id, 0x06, address, value & 0xFFFF
        )
        self._sock.sendall(request)
        resp = self._sock.recv(1024)
        if len(resp) >= 12 and resp[7] == 0x06:
            return True
        if len(resp) >= 9 and resp[7] & 0x80:
            exc = resp[8]
            _EXC = {1: "ILLEGAL FUNCTION", 2: "ILLEGAL DATA ADDRESS", 3: "ILLEGAL DATA VALUE", 4: "SERVER FAILURE"}
            logger.warning("写寄存器 %d 异常: %s (code=%d)", address, _EXC.get(exc, "UNKNOWN"), exc)
        else:
            logger.warning("写寄存器 %d 响应异常: %s", address, resp.hex())
        return False

    @not_action
    def read_registers(self, address: int, count: int = 1) -> Optional[List[int]]:
        """读保持寄存器 (FC 0x03)"""
        if not self._sock:
            raise ConnectionError("未连接")
        tid = self._next_tid()
        request = struct.pack(
            ">HHHBBHH", tid, 0, 6, self.unit_id, 0x03, address, count
        )
        self._sock.sendall(request)
        resp = self._sock.recv(1024)
        if len(resp) >= 9 and resp[7] == 0x03:
            n = resp[8]
            data = resp[9 : 9 + n]
            return [
                int.from_bytes(data[i : i + 2], "big") for i in range(0, len(data), 2)
            ]
        if len(resp) >= 9 and resp[7] & 0x80:
            exc = resp[8]
            _EXC = {1: "ILLEGAL FUNCTION", 2: "ILLEGAL DATA ADDRESS", 3: "ILLEGAL DATA VALUE", 4: "SERVER FAILURE"}
            logger.warning("读寄存器 %d 异常: %s (code=%d)", address, _EXC.get(exc, "UNKNOWN"), exc)
        else:
            logger.warning("读寄存器 %d 响应异常: %s", address, resp.hex())
        return None

    # ──────────────── 运行状态监控 ────────────────

    @not_action
    def _is_arm_running(self) -> bool:
        """读取第300位寄存器，1=动作未结束，0=动作完成"""
        result = self.read_registers(REG_STATUS, 1)
        if result is None:
            logger.warning("无法读取运行状态寄存器")
            return False
        return result[0] == 1

    @not_action
    def _wait_arm_complete(self) -> bool:
        """阻塞等待机械臂动作完成，返回 True=完成 / False=超时"""
        time.sleep(0.5)
        start = time.time()
        while time.time() - start < self.timeout:
            if not self._is_arm_running():
                return True
            time.sleep(self.poll_interval)
        logger.error("等待机械臂完成超时 (%.0fs)", self.timeout)
        return False

    @not_action
    def _execute_action(self, register: int, name: str) -> Dict[str, Any]:
        """写寄存器触发动作 → 等待机械臂运行结束"""
        self._task_state = f"Running:{name}"
        ok = self.write_register(register, 1)
        if not ok:
            self._task_state = "Error"
            return {"success": False, "message": f"{name}: 写入寄存器 {register} 失败"}

        logger.info("已触发动作 [%s]，寄存器 %d = 1", name, register)
        completed = self._wait_arm_complete()
        if not completed:
            self._task_state = "Timeout"
            return {"success": False, "message": f"{name}: 等待完成超时"}

        self._task_state = "Idle"
        logger.info("动作 [%s] 完成", name)
        return {"success": True, "action": name}

    @not_action
    def _reset_all_registers(self):
        """将所有动作寄存器 (256-263) 清零"""
        for reg in ALL_ACTION_REGS:
            self.write_register(reg, 0)
        logger.info("所有寄存器已复位")

    # ──────────────── 动作 ────────────────

    @action(description="开始")
    def start_action(self) -> Dict[str, Any]:
        """寄存器256写1，触发开始动作"""
        return self._execute_action(REG_START, "开始")

    @action(description="混合开始")
    def mix_start(self) -> Dict[str, Any]:
        """寄存器280写1，触发混合开始动作"""
        return self._execute_action(REG_MIX_START, "混合开始")

    @action(description="取瓶子")
    def pick_bottle(self) -> Dict[str, Any]:
        """寄存器257写1，触发取瓶子动作"""
        return self._execute_action(REG_PICK_BOTTLE, "取瓶子")

    @action(description="放瓶子")
    def place_bottle(self) -> Dict[str, Any]:
        """寄存器258写1，触发放瓶子动作"""
        return self._execute_action(REG_PLACE_BOTTLE, "放瓶子")

    @action(description="拿样品")
    def pick_sample(self) -> Dict[str, Any]:
        """寄存器259写1，触发拿样品动作"""
        return self._execute_action(REG_PICK_SAMPLE, "拿样品")

    @action(description="放回瓶子")
    def return_bottle(self) -> Dict[str, Any]:
        """寄存器260写1，触发放回瓶子动作"""
        return self._execute_action(REG_RETURN_BOTTLE, "放回瓶子")

    @action(description="放回样品")
    def return_sample(self) -> Dict[str, Any]:
        """寄存器261写1，触发放回样品动作"""
        return self._execute_action(REG_RETURN_SAMPLE, "放回样品")

    @action(description="取瓶子1")
    def pick_bottle_1(self) -> Dict[str, Any]:
        """寄存器257写1，触发取瓶子1动作"""
        return self._execute_action(REG_PICK_BOTTLE_1, "取瓶子1")

    @action(description="放入瓶子1")
    def place_bottle_1(self) -> Dict[str, Any]:
        """寄存器258写1，触发放入瓶子1动作"""
        return self._execute_action(REG_PLACE_BOTTLE_1_IN, "放入瓶子1")

    @action(description="取样品1")
    def pick_sample_1(self) -> Dict[str, Any]:
        """寄存器259写1，触发取样品1动作"""
        return self._execute_action(REG_PICK_SAMPLE_1, "取样品1")

    @action(description="取样品2")
    def pick_sample_2(self) -> Dict[str, Any]:
        """寄存器260写1，触发取样品2动作"""
        return self._execute_action(REG_PICK_SAMPLE_2, "取样品2")

    @action(description="取样品3")
    def pick_sample_3(self) -> Dict[str, Any]:
        """寄存器261写1，触发取样品3动作"""
        return self._execute_action(REG_PICK_SAMPLE_3, "取样品3")

    @action(description="放回样品3")
    def return_sample_3(self) -> Dict[str, Any]:
        """寄存器262写1，触发放回样品3动作"""
        return self._execute_action(REG_RETURN_SAMPLE_3, "放回样品3")

    @action(description="放回瓶子1")
    def return_bottle_1(self) -> Dict[str, Any]:
        """寄存器263写1，触发放回瓶子1动作"""
        return self._execute_action(REG_RETURN_BOTTLE_1, "放回瓶子1")

    @action(description="结束")
    def finish(self) -> Dict[str, Any]:
        """将所有动作寄存器 (256-263) 清零"""
        self._reset_all_registers()
        self._task_state = "Idle"
        return {"success": True, "action": "结束"}

    @action(description="断开连接")
    def disconnect(self) -> Dict[str, Any]:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._task_state = "Idle"
        return {"success": True}

    # ──────────────── 状态属性 ────────────────

    @property
    @topic_config(period=2.0)
    def task_state(self) -> str:
        return self._task_state


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")

    arm = SjsEliteArm(host="192.168.1.200")
    if arm._sock:
        print("开始:", arm.start_action())
        print("取瓶子:", arm.pick_bottle())
        print("放瓶子:", arm.place_bottle())
        print("拿样品:", arm.pick_sample())
        print("放回瓶子:", arm.return_bottle())
        print("放回样品:", arm.return_sample())
        arm.disconnect()

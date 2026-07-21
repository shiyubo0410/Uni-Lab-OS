
"""
XYZ光电工作台设备驱动 - 寄存器修正版 v4
用于控制XYZ三轴运动平台和推杆装置

================== v4 关键修复（寄存器地址）==================
本次重点修复"运行轴移动指令显示寄存器错误"的问题。
根因：原代码使用了一套自编的通用寄存器地址(0x02~0x09)，
而三种设备分属三家厂商、三套完全不同的寄存器映射，必须分别处理：

1. DM2J-RS542 (X/Y轴, 雷赛): PR模式
   - 软件强制使能 Pr0.07 = 0x000F (写1)
   - 立即数据触发用 Pr9.00~9.07 (0x6200~0x6207)
       0x6200 模式(0x0001绝对/0x0041相对) 0x6201位置H 0x6202位置L
       0x6203速度(rpm) 0x6204加速 0x6205减速 0x6206停顿
   - 触发寄存器 Pr8.02 = 0x6002:
       写0x010 触发PR0; 0x020 回零; 0x021 手动设零; 0x040 急停
   - 运行状态(只读) 0x1003: bit0故障 bit1使能 bit2运行
                            bit4指令完成 bit5路径完成 bit6回零完成
   - 电机位置(只读) 0x602C(H)/0x602D(L)
   - 注意: PR模式位置单位固定 10000P/r, 速度单位 rpm

2. 俏优灵 zeta系列 (Z轴): 直接Modbus (依据俏优灵手册寄存表校正)
   - 状态(只读) 0x00; 实际步数 0x01(H)/0x02(L)
   - 使能 0x06(1使能/0失能); 停止=向急停0x04写0
   - 位置模式(绝对): 一帧FC16连写 0x10~0x15
       0x10目标步数H 0x11目标步数L 0x12保留(写0) 0x13速度rpm 0x14加速度rpm/s 0x15到位精度
     (写入即触发运动; 目标步数是相对编码器零点的绝对步数)
   - 归零 0x0F (写入值=归零速度rpm)  ← 注意是0x0F不是0x1F
   - 单位: 速度直接rpm(0x1388=5000rpm); 485位置模式固定16384步/圈(14位编码器)

3. CX-5208W (推杆, 科星): 换向式两路继电器 (互斥)
   - 不是电机! 用 FC05 写单个线圈, FC01 读线圈状态
   - 第1路(伸出/夹紧)=线圈0x0000; 第2路(缩回/释放)=线圈0x0001
   - 换向前先断开反向路再吸合目标路, 严禁两路同时吸合
   - 到位后保持通电维持夹紧力

4. 高/低16位顺序修正: 三个设备均为"高16位在前(N), 低16位在后(N+1)"

================== 重要硬件提醒 ==================
* 三个设备共用一条RS485总线(同一个COM口), 波特率必须一致!
  俏优灵默认115200, DM2J/CX-5208W默认9600。
  请先用上位机/指令把俏优灵Z轴改成9600(写0xEA=0x0000,0xEB=0x2580后重新上电),
  否则Z轴永远通信失败。本驱动统一使用 baudrate=9600。
* 各设备从站地址(slave id)请按实际拨码/配置填写 addr_mapping。
* 俏优灵串口默认: 8位数据/1停止/无校验; DM2J默认无校验1停止位。
"""

import logging
import time as time_module
from typing import Dict, Any, Optional

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


# ============ DM2J (雷赛 X/Y轴) PR模式寄存器 ============
DM2J_REG = {
    "force_enable": 0x000F,   # Pr0.07 软件强制使能 写1=强制使能
    "pr0_mode":     0x6200,   # Pr9.00 运动模式 0x0001绝对定位 / 0x0041相对定位
    "pr0_pos_h":    0x6201,   # Pr9.01 位置高16位
    "pr0_pos_l":    0x6202,   # Pr9.02 位置低16位
    "pr0_speed":    0x6203,   # Pr9.03 速度 rpm
    "pr0_acc":      0x6204,   # Pr9.04 加速时间 ms/1000rpm
    "pr0_dec":      0x6205,   # Pr9.05 减速时间 ms/1000rpm
    "pr0_dwell":    0x6206,   # Pr9.06 停顿时间
    "trigger":      0x6002,   # Pr8.02 触发寄存器
    "control_word": 0x1801,   # 辅助控制字 (0x2211保存EEPROM, 0x1111复位报警)
    "run_status":   0x1003,   # 只读 运行状态
    "alarm":        0x2203,   # 只读 当前报警
    "motor_pos_h":  0x602C,   # 只读 电机位置高16位
    "motor_pos_l":  0x602D,   # 只读 电机位置低16位
    "home_mode":    0x600A,   # 回零模式
}
DM2J_TRIG_PR0     = 0x010     # 触发PR0运行
DM2J_TRIG_HOME    = 0x020     # 回零
DM2J_TRIG_SETZERO = 0x021     # 当前位置手动设零
DM2J_TRIG_ESTOP   = 0x040     # 急停
DM2J_MODE_ABS     = 0x0001    # 绝对位置定位
DM2J_MODE_REL     = 0x0041    # 相对位置定位 (bit6=1)

# ============ 俏优灵 (Z轴) 寄存器 ============
# 依据俏优灵手册寄存表(第12-15页)校正, 单位/地址均以手册为准
YL_REG = {
    "status":        0x0000,  # 只读 0=待机/到位 1=运行 2=碰撞停 3=正光电停 4=反光电停
    "act_steps_h":   0x0001,  # 只读 实际步数高位(上电初值=编码器角度)
    "act_steps_l":   0x0002,  # 只读 实际步数低位
    "act_speed":     0x0003,  # 只读 实际速度 rpm
    "estop":         0x0004,  # 急停指令 (写0=停止, 见手册停止示例)
    "current":       0x0005,  # 只读 电流 mA
    "enable":        0x0006,  # 1=使能 0=失能, 默认1
    "output":        0x0007,  # K引脚PWM 0-1000
    "zero_single":   0x000E,  # 单圈绝对值归零
    "home":          0x000F,  # 归零指令(定点模式写入值=归零速度 rpm)
    # ---- 位置模式地址区 (0x10~0x15) ----
    "tgt_steps_h":   0x0010,  # 目标步数高位 (一帧连写0x10~0x15即触发绝对定位)
    "tgt_steps_l":   0x0011,  # 目标步数低位
    "reserved_12":   0x0012,  # 保留 (手册标注保留, 写0)
    "speed":         0x0013,  # 速度 rpm (例: 0x1388=5000rpm)
    "acc":           0x0014,  # 加速度 rpm/s (0-60000)
    "tolerance":     0x0015,  # 到位精度(步), 越小越精准但到位越慢
}


@device(
    id="xyz_guangdian",
    category=["motion"],
    description="XYZ 三维运动平台，支持三轴运动和推杆控制",
    display_name="XYZ 三维平台"
)
class XYZGuangdian:
    _ros_node: Optional["BaseROS2DeviceNode"] = None

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 9600,
        timeout: float = 2.0,
        retry_count: int = 3,
        retry_delay: float = 0.1,
        addr_x: int = 2,
        addr_y: int = 3,
        addr_z: int = 1,
        addr_push_rod: int = 4,
        x_pulses_per_mm: float = 10000.0,
        y_pulses_per_mm: float = 10000.0,
        z_steps_per_mm: float = 16384.0,
        default_speed_rpm: int = 200,
        default_speed_yl: int = 600,
        dm2j_acc: int = 50,
        dm2j_dec: int = 50,
        yl_acc: int = 30000,
        yl_tolerance: int = 100,
        home_speed_yl: int = 600,
        home_wait_s: float = 5.0,
        dm2j_has_home_switch: bool = False,
        push_rod_coil_extend: int = 0,
        push_rod_coil_retract: int = 1,
        device_id: str = "xyz_guangdian",
        **kwargs,
    ):
        """XYZ三维运动平台驱动 (X/Y=雷赛DM2J, Z=俏优灵zeta, 推杆=CX-5208W两路继电器), 共用一条RS485总线。

        Args:
            port[串口]: RS485串口号 (Windows: COMx, Linux: /dev/ttyUSBx)。
            baudrate[波特率]: 全总线统一波特率, 俏优灵需提前改成与此一致 (默认9600)。
            timeout[超时(s)]: 串口读超时, 单位秒。
            retry_count[重试次数]: Modbus读写失败重试次数。
            retry_delay[重试间隔(s)]: 每次重试的间隔, 单位秒。
            addr_x[X轴站号]: DM2J X轴 Modbus站号。
            addr_y[Y轴站号]: DM2J Y轴 Modbus站号。
            addr_z[Z轴站号]: 俏优灵 Z轴 Modbus站号。
            addr_push_rod[推杆站号]: CX-5208W继电器 Modbus站号。
            x_pulses_per_mm[X每mm脉冲]: DM2J 10000P/r ÷ 丝杆导程(mm)。
            y_pulses_per_mm[Y每mm脉冲]: DM2J 10000P/r ÷ 丝杆导程(mm)。
            z_steps_per_mm[Z每mm步数]: 俏优灵 16384步/圈 ÷ 丝杆导程(mm)。
            default_speed_rpm[X/Y默认速度(rpm)]: DM2J 运动速度。
            default_speed_yl[Z默认速度(rpm)]: 俏优灵运动速度 (直接写0x13)。
            dm2j_acc[X/Y加速度]: DM2J 加速度参数。
            dm2j_dec[X/Y减速度]: DM2J 减速度参数。
            yl_acc[Z加速度(rpm/s)]: 俏优灵加速度。
            yl_tolerance[Z到位精度(步)]: 俏优灵到位精度, 越小越精准但越慢。
            home_speed_yl[Z归零速度(rpm)]: 俏优灵归零速度。
            home_wait_s[归零等待(s)]: 归零后等待时间, 单位秒。
            dm2j_has_home_switch[X/Y是否有限位]: X/Y是否接了限位/原点开关; 未接时 go_home 改用"手动设零"避免撞机械端。
            push_rod_coil_extend[推杆伸出线圈]: 第1路继电器线圈地址 (夹紧方向)。
            push_rod_coil_retract[推杆缩回线圈]: 第2路继电器线圈地址 (释放方向)。
            device_id[设备ID]: 设备标识 (仅用于日志显示)。
        """
        self.device_id = device_id or "xyz_guangdian"
        # 保留 config dict 供 go_home/set_speed/move 等方法读取
        self.config = {
            'home_speed_yl': home_speed_yl,
            'home_wait_s': home_wait_s,
            'dm2j_acc': dm2j_acc,
            'dm2j_dec': dm2j_dec,
            'yl_acc': yl_acc,
            'yl_tolerance': yl_tolerance,
        }
        self.logger = logging.getLogger(f"XYZGuangdian.{self.device_id}.xyz_guangdian")

        # Modbus通信配置
        self.modbus_client = None
        self.port = port
        # 全总线统一波特率! 俏优灵需提前改成与此一致(默认9600)
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.retry_count = int(retry_count)
        self.retry_delay = float(retry_delay)
        # 不同 pymodbus 版本从站参数名不同(3.7+用device_id, 早期用slave/unit), 运行时探测缓存
        self._unit_kw = None

        # 设备从站地址映射 (按实际拨码/配置填写)
        self.addr_mapping = {
            'x': int(addr_x),
            'y': int(addr_y),
            'z': int(addr_z),
            'push_rod': int(addr_push_rod),
        }

        # 各轴类型 -> 决定使用哪套寄存器/协议
        self.axis_type = {
            'x': 'dm2j',
            'y': 'dm2j',
            'z': 'youling',
            'push_rod': 'relay',
        }

        # 单位换算 (脉冲/步数 每 mm), 按实际机械结构(丝杆导程)标定
        # 注: DM2J PR模式固定10000P/r; 俏优灵485位置模式固定16384步/圈(14位编码器,与细分无关)
        #     真实标定值 = 每圈步数 / 丝杆导程(mm/圈)
        self.pulses_per_mm = {
            'x': x_pulses_per_mm,  # DM2J: 10000P/r ÷ 导程
            'y': y_pulses_per_mm,
            'z': z_steps_per_mm,   # 俏优灵: 16384步/圈 ÷ 导程
        }
        # 速度默认值
        self.default_speed_rpm = default_speed_rpm      # DM2J rpm
        self.default_speed_yl = default_speed_yl        # 俏优灵 rpm(直接写0x13)
        # 推杆: 换向式两路继电器(互斥). extend=夹紧方向, retract=释放方向; 到位后保持通电维持力
        self.push_rod_coil_extend = int(push_rod_coil_extend)   # 第1路继电器
        self.push_rod_coil_retract = int(push_rod_coil_retract)  # 第2路继电器
        # X/Y(DM2J)是否接了限位/原点开关。未接时 go_home 改用"手动设零"(电机不动), 避免撞机械端
        self.dm2j_has_home_switch = dm2j_has_home_switch

        self.data = {
            "status": "Idle",
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
            "push_rod_status": "released",
            "is_enabled": False,
            "is_homed": False,
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "velocity_z": 0.0,
            "temperature": 25.0,
            "error_code": 0
        }

    @not_action
    def post_init(self, ros_node: "BaseROS2DeviceNode"):
        self._ros_node = ros_node

    # ========== 连接管理 ==========
    def _close_connection(self):
        if self.modbus_client is not None:
            try:
                if self.modbus_client.connected:
                    self.modbus_client.close()
                    self.logger.info("已关闭Modbus连接")
            except Exception as e:
                self.logger.warning(f"关闭连接时出错: {e}")
            finally:
                self.modbus_client = None

    def _ensure_connected(self) -> bool:
        if self.modbus_client and self.modbus_client.connected:
            return True
        self.logger.warning("Modbus连接断开，尝试重连...")
        self._close_connection()
        time_module.sleep(0.3)
        try:
            from pymodbus.client import ModbusSerialClient
            self.modbus_client = ModbusSerialClient(
                port=self.port, baudrate=self.baudrate,
                bytesize=8, parity='N', stopbits=1, timeout=self.timeout
            )
            if self.modbus_client.connect():
                self.logger.info("重连成功")
                return True
            self.logger.error(f"重连失败: 无法打开 {self.port}")
            self.modbus_client = None
            return False
        except Exception as e:
            self.logger.error(f"重连异常: {e}")
            self.modbus_client = None
            return False

    # ========== 底层Modbus通信 (纯同步) ==========
    def _unit_kwargs(self, slave_addr: int) -> Dict[str, int]:
        """兼容不同 pymodbus 版本的从站参数名 (device_id / slave / unit)。"""
        if self._unit_kw is None:
            import inspect
            try:
                params = inspect.signature(self.modbus_client.read_holding_registers).parameters
            except Exception:
                params = {}
            self._unit_kw = next((n for n in ("device_id", "slave", "unit") if n in params), "device_id")
        return {self._unit_kw: slave_addr}

    def _read_registers(self, slave_addr: int, register: int, count: int = 1):
        if not self._ensure_connected():
            return None
        last_exc = None
        for attempt in range(self.retry_count):
            try:
                resp = self.modbus_client.read_holding_registers(
                    register, count=count, **self._unit_kwargs(slave_addr)
                )
                if resp.isError():
                    self.logger.warning(
                        f"读寄存器失败 slave={slave_addr:#x} reg={register:#x} "
                        f"({attempt+1}/{self.retry_count}): {resp}")
                    time_module.sleep(self.retry_delay)
                    continue
                return resp
            except Exception as e:
                last_exc = e
                self.logger.warning(
                    f"读寄存器异常 slave={slave_addr:#x} reg={register:#x} "
                    f"({attempt+1}/{self.retry_count}): {e}")
                time_module.sleep(self.retry_delay)
        self.logger.error(f"读寄存器最终失败 slave={slave_addr:#x} reg={register:#x}: {last_exc}")
        return None

    def _write_register(self, slave_addr: int, register: int, value: int) -> bool:
        """FC06 写单个保持寄存器 (触发型寄存器不做回读验证)"""
        if not self._ensure_connected():
            return False
        if not (0 <= value <= 65535):
            self.logger.error(f"寄存器值超范围: {value}")
            return False
        last_exc = None
        for attempt in range(self.retry_count):
            try:
                resp = self.modbus_client.write_register(register, value, **self._unit_kwargs(slave_addr))
                if resp.isError():
                    self.logger.warning(
                        f"写寄存器失败 slave={slave_addr:#x} reg={register:#x} val={value:#x} "
                        f"({attempt+1}/{self.retry_count}): {resp}")
                    time_module.sleep(self.retry_delay)
                    continue
                return True
            except Exception as e:
                last_exc = e
                self.logger.warning(
                    f"写寄存器异常 slave={slave_addr:#x} reg={register:#x} "
                    f"({attempt+1}/{self.retry_count}): {e}")
                time_module.sleep(self.retry_delay)
        self.logger.error(f"写寄存器最终失败 slave={slave_addr:#x} reg={register:#x}: {last_exc}")
        return False

    def _write_registers(self, slave_addr: int, register: int, values) -> bool:
        """FC16 写多个连续寄存器"""
        if not self._ensure_connected():
            return False
        last_exc = None
        for attempt in range(self.retry_count):
            try:
                resp = self.modbus_client.write_registers(register, list(values), **self._unit_kwargs(slave_addr))
                if resp.isError():
                    self.logger.warning(
                        f"写多寄存器失败 slave={slave_addr:#x} reg={register:#x} "
                        f"({attempt+1}/{self.retry_count}): {resp}")
                    time_module.sleep(self.retry_delay)
                    continue
                return True
            except Exception as e:
                last_exc = e
                self.logger.warning(
                    f"写多寄存器异常 slave={slave_addr:#x} reg={register:#x} "
                    f"({attempt+1}/{self.retry_count}): {e}")
                time_module.sleep(self.retry_delay)
        self.logger.error(f"写多寄存器最终失败 slave={slave_addr:#x} reg={register:#x}: {last_exc}")
        return False

    def _write_coil(self, slave_addr: int, coil: int, on: bool) -> bool:
        """FC05 写单个线圈 (用于CX-5208W继电器)"""
        if not self._ensure_connected():
            return False
        last_exc = None
        for attempt in range(self.retry_count):
            try:
                resp = self.modbus_client.write_coil(coil, on, **self._unit_kwargs(slave_addr))
                if resp.isError():
                    self.logger.warning(
                        f"写线圈失败 slave={slave_addr:#x} coil={coil:#x} on={on} "
                        f"({attempt+1}/{self.retry_count}): {resp}")
                    time_module.sleep(self.retry_delay)
                    continue
                return True
            except Exception as e:
                last_exc = e
                self.logger.warning(
                    f"写线圈异常 slave={slave_addr:#x} coil={coil:#x} "
                    f"({attempt+1}/{self.retry_count}): {e}")
                time_module.sleep(self.retry_delay)
        self.logger.error(f"写线圈最终失败 slave={slave_addr:#x} coil={coil:#x}: {last_exc}")
        return False

    @staticmethod
    def _to_hilo(value_32: int):
        """32位有符号 -> (高16位, 低16位)无符号. 三设备均高位在前。"""
        if value_32 < 0:
            value_32 += 0x100000000
        return (value_32 >> 16) & 0xFFFF, value_32 & 0xFFFF

    @staticmethod
    def _from_hilo(high: int, low: int) -> int:
        raw = ((high & 0xFFFF) << 16) | (low & 0xFFFF)
        if raw > 0x7FFFFFFF:
            raw -= 0x100000000
        return raw

    # ========== 初始化 ==========
    @action(description="初始化设备")
    async def initialize(self) -> bool:
        try:
            self.logger.info(f"初始化XYZ光电工作台 {self.device_id}")
            try:
                from pymodbus.client import ModbusSerialClient
            except ImportError as e:
                self.logger.error(f"缺少pymodbus库: {e}")
                self.data["status"] = "Error"; self.data["error_code"] = 1001
                return False

            self._close_connection()
            time_module.sleep(0.3)
            self.modbus_client = ModbusSerialClient(
                port=self.port, baudrate=self.baudrate,
                bytesize=8, parity='N', stopbits=1, timeout=self.timeout
            )
            if not self.modbus_client.connect():
                self.logger.error(f"无法连接到端口 {self.port}")
                self.data["status"] = "Error"; self.data["error_code"] = 1002
                self.modbus_client = None
                return False

            if not self._test_communication():
                self.logger.error("设备通信测试失败")
                self.data["status"] = "Error"; self.data["error_code"] = 1003
                return False

            self.data["status"] = "Idle"; self.data["error_code"] = 0
            self.logger.info(f"设备 {self.device_id} 初始化成功")
            return True
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            self.data["status"] = "Error"; self.data["error_code"] = 1000
            return False

    def _test_communication(self) -> bool:
        """按各设备真实的可读寄存器做通信测试"""
        ok = True
        for axis in ['x', 'y', 'z', 'push_rod']:
            addr = self.addr_mapping[axis]
            atype = self.axis_type[axis]
            try:
                if atype == 'dm2j':
                    resp = self._read_registers(addr, DM2J_REG["run_status"], 1)
                elif atype == 'youling':
                    resp = self._read_registers(addr, YL_REG["status"], 1)
                else:  # relay: 读第1路线圈状态
                    if not self._ensure_connected():
                        resp = None
                    else:
                        try:
                            r = self.modbus_client.read_coils(self.push_rod_coil_extend, count=2, **self._unit_kwargs(addr))
                            resp = None if (r is None or r.isError()) else r
                        except Exception:
                            resp = None
                if resp is None:
                    self.logger.error(f"轴 {axis} (slave={addr:#x}, {atype}) 通信测试失败")
                    ok = False
                else:
                    self.logger.info(f"轴 {axis} (slave={addr:#x}, {atype}) 通信OK")
                time_module.sleep(0.05)
            except Exception as e:
                self.logger.error(f"轴 {axis} 通信异常: {e}")
                ok = False
        return ok

    # ========== 属性 ==========
    @property
    def status(self) -> str:
        return self.data.get("status", "Idle")

    @property
    def position(self) -> Dict[str, float]:
        return {"x": self.data.get("position_x", 0.0),
                "y": self.data.get("position_y", 0.0),
                "z": self.data.get("position_z", 0.0)}

    @property
    def is_homed(self) -> bool:
        return self.data.get("is_homed", False)

    @property
    def is_enabled(self) -> bool:
        return self.data.get("is_enabled", False)

    @property
    def push_rod_status(self) -> str:
        return self.data.get("push_rod_status", "released")

    @property
    def error_code(self) -> int:
        return self.data.get("error_code", 0)

    # ========== 使能 / 禁用 ==========
    @action(description="使能所有轴")
    async def enable(self) -> bool:
        try:
            self.logger.info("使能所有轴")
            ok = 0
            for axis in ['x', 'y', 'z']:
                addr = self.addr_mapping[axis]
                if self.axis_type[axis] == 'dm2j':
                    # Pr0.07 软件强制使能 写1
                    res = self._write_register(addr, DM2J_REG["force_enable"], 1)
                else:  # youling 0x06 写1
                    res = self._write_register(addr, YL_REG["enable"], 1)
                if res:
                    ok += 1
                    self.logger.info(f"轴 {axis} (slave={addr:#x}) 使能成功")
                else:
                    self.logger.error(f"轴 {axis} (slave={addr:#x}) 使能失败")
                time_module.sleep(0.05)
            self.data["is_enabled"] = (ok == 3)
            self.data["status"] = "Idle"
            return ok == 3
        except Exception as e:
            self.logger.error(f"使能失败: {e}")
            return False

    @action(description="禁用所有轴")
    async def disable(self) -> bool:
        try:
            ok = 0
            for axis in ['x', 'y', 'z']:
                addr = self.addr_mapping[axis]
                if self.axis_type[axis] == 'dm2j':
                    res = self._write_register(addr, DM2J_REG["force_enable"], 0)
                else:
                    res = self._write_register(addr, YL_REG["enable"], 0)
                if res:
                    ok += 1
                time_module.sleep(0.05)
            self.data["is_enabled"] = False
            self.data["status"] = "Idle"
            return ok > 0
        except Exception as e:
            self.logger.error(f"禁用失败: {e}")
            return False

    # ========== 回零 ==========
    @action(description="回零操作")
    async def go_home(self) -> bool:
        try:
            self.logger.info("执行回零操作")
            if not self.data["is_enabled"]:
                self.logger.error("设备未使能，无法回零")
                return False
            self.data["status"] = "Busy"
            for axis in ['x', 'y', 'z']:
                addr = self.addr_mapping[axis]
                if self.axis_type[axis] == 'dm2j':
                    if self.dm2j_has_home_switch:
                        # 有限位/原点开关: 触发真回零0x020 (回零参数需预先配置好)
                        res = self._write_register(addr, DM2J_REG["trigger"], DM2J_TRIG_HOME)
                    else:
                        # 未接限位开关: 触发真回零会撞机械端! 改用手动设零0x021(电机不动)
                        self.logger.warning(f"轴 {axis} 未配置限位开关(dm2j_has_home_switch=False), 改用手动设零")
                        res = self._write_register(addr, DM2J_REG["trigger"], DM2J_TRIG_SETZERO)
                else:
                    # 俏优灵: 归零指令0x0F, 写入值=归零速度(rpm) (Z轴有光电限位, 正常回零)
                    res = self._write_register(addr, YL_REG["home"], self.config.get('home_speed_yl', 600))
                if not res:
                    self.logger.error(f"轴 {axis} 回零指令发送失败")
                    self.data["status"] = "Error"
                    return False
                time_module.sleep(0.05)

            self.logger.info("等待回零完成...")
            time_module.sleep(self.config.get('home_wait_s', 5.0))

            self.data["is_homed"] = True
            self.data["status"] = "Idle"
            for axis in ['x', 'y', 'z']:
                self.data[f"position_{axis}"] = 0.0
            await self.get_position()
            self.logger.info("回零完成")
            return True
        except Exception as e:
            self.logger.error(f"回零失败: {e}")
            self.data["status"] = "Error"
            return False

    @action(description="手动设零(把当前位置设为0, 电机不动)")
    async def set_current_as_zero(self, axis: str = "all") -> bool:
        """安全归零: 把当前点设为坐标零点, 电机不移动。
        适用于未接限位/原点开关的轴(如本平台X/Y)。
        DM2J: 触发寄存器写0x021; 俏优灵: 0x0E单圈绝对值归零。
        axis: 'x'/'y'/'z' 或 'all'(默认全部)。
        """
        try:
            axes = ['x', 'y', 'z'] if axis == "all" else [axis]
            ok = 0
            for ax in axes:
                if ax not in self.addr_mapping:
                    self.logger.error(f"无效轴名称: {ax}")
                    continue
                addr = self.addr_mapping[ax]
                if self.axis_type[ax] == 'dm2j':
                    res = self._write_register(addr, DM2J_REG["trigger"], DM2J_TRIG_SETZERO)
                else:
                    res = self._write_register(addr, YL_REG["zero_single"], 1)
                if res:
                    ok += 1
                    self.data[f"position_{ax}"] = 0.0
                    self.logger.info(f"轴 {ax} 已手动设零")
                else:
                    self.logger.error(f"轴 {ax} 手动设零失败")
                time_module.sleep(0.05)
            return ok == len(axes)
        except Exception as e:
            self.logger.error(f"手动设零失败: {e}")
            return False

    # ========== 单轴移动实现 ==========
    def _move_dm2j(self, addr: int, pulses: int, speed_rpm: int, absolute: bool = False) -> bool:
        """DM2J PR模式立即触发: 写Pr9.00~9.06后触发0x6002=0x010
        absolute=True 走绝对定位(mode=0x0001), False 走相对定位(mode=0x0041)。
        """
        mode = DM2J_MODE_ABS if absolute else DM2J_MODE_REL
        pos_h, pos_l = self._to_hilo(pulses)
        acc = self.config.get('dm2j_acc', 50)
        dec = self.config.get('dm2j_dec', 50)
        # 连续写 Pr9.00~Pr9.06 (0x6200~0x6206) 共7个寄存器
        values = [mode, pos_h, pos_l, speed_rpm & 0xFFFF, acc, dec, 0]
        if not self._write_registers(addr, DM2J_REG["pr0_mode"], values):
            return False
        time_module.sleep(0.02)
        # 触发PR0运行
        return self._write_register(addr, DM2J_REG["trigger"], DM2J_TRIG_PR0)

    def _move_youling(self, addr: int, steps: int, speed_rpm: int) -> bool:
        """俏优灵位置模式(绝对定位): 一帧FC16连写0x10~0x15触发运动。
        步数为相对编码器零点的绝对步数。参照手册位置模式示例。
        """
        st_h, st_l = self._to_hilo(steps)
        acc = self.config.get('yl_acc', 30000)          # 加速度 rpm/s
        tolerance = self.config.get('yl_tolerance', 100)  # 到位精度(步)
        # 0x10目标H, 0x11目标L, 0x12保留=0, 0x13速度, 0x14加速度, 0x15精度; 写入即触发
        values = [st_h, st_l, 0, speed_rpm & 0xFFFF, acc & 0xFFFF, tolerance & 0xFFFF]
        return self._write_registers(addr, YL_REG["tgt_steps_h"], values)

    def _read_axis_raw(self, axis: str) -> Optional[int]:
        """读取单轴的原始脉冲/步数(有符号)。失败返回None。"""
        addr = self.addr_mapping[axis]
        if self.axis_type[axis] == 'dm2j':
            resp = self._read_registers(addr, DM2J_REG["motor_pos_h"], 2)
        else:
            resp = self._read_registers(addr, YL_REG["act_steps_h"], 2)
        if resp and hasattr(resp, "registers") and len(resp.registers) >= 2:
            return self._from_hilo(resp.registers[0], resp.registers[1])
        return None

    @action(description="相对移动")
    async def move_relative(self, x_delta: float = 0.0, y_delta: float = 0.0,
                            z_delta: float = 0.0, wait_done: bool = True) -> bool:
        try:
            if not self.data["is_enabled"]:
                self.logger.error("设备未使能，无法移动")
                return False
            self.logger.info(f"相对移动: X={x_delta:+.2f} Y={y_delta:+.2f} Z={z_delta:+.2f} (mm)")
            self.data["status"] = "Busy"

            deltas = {'x': x_delta, 'y': y_delta, 'z': z_delta}
            pulses = {ax: int(deltas[ax] * self.pulses_per_mm[ax]) for ax in deltas}

            ok = 0
            total = 0
            for axis in ['x', 'y', 'z']:
                if pulses[axis] == 0:
                    continue
                total += 1
                addr = self.addr_mapping[axis]
                self.logger.info(f"轴 {axis} (slave={addr:#x}): 目标增量={pulses[axis]}脉冲/步")
                if self.axis_type[axis] == 'dm2j':
                    # DM2J 原生相对定位
                    res = self._move_dm2j(addr, pulses[axis], self.default_speed_rpm, absolute=False)
                else:
                    # 俏优灵为绝对步数控制: 当前绝对步数 + 增量 → 绝对目标
                    cur_raw = self._read_axis_raw(axis)
                    if cur_raw is None:
                        self.logger.error(f"轴 {axis} 读取当前步数失败，无法相对移动")
                        res = False
                    else:
                        res = self._move_youling(addr, cur_raw + pulses[axis], self.default_speed_yl)
                if res:
                    ok += 1
                    self.logger.info(f"轴 {axis} 移动指令发送成功")
                else:
                    self.logger.error(f"轴 {axis} 移动指令发送失败")
                time_module.sleep(0.05)

            if total == 0:
                self.logger.info("无移动指令(所有轴增量为0)")
                self.data["status"] = "Idle"
                return True

            if wait_done and ok > 0:
                wait_time = max(1.5, abs(max(pulses.values(), key=abs)) / 20000 + 1.5)
                self.logger.info(f"等待移动完成 (约 {wait_time:.1f}s)...")
                time_module.sleep(wait_time)
                await self.get_position()

            self.data["status"] = "Idle"
            return ok > 0
        except Exception as e:
            self.logger.error(f"移动失败: {e}")
            self.data["status"] = "Error"
            return False

    @action(description="绝对位置移动")
    async def move_absolute(self, x: float = 0.0, y: float = 0.0,
                           z: float = 0.0, wait_done: bool = True) -> bool:
        """原生绝对定位: DM2J走绝对模式, 俏优灵直接下发绝对目标步数(均不依赖位置缓存)。"""
        try:
            if not self.data["is_enabled"]:
                self.logger.error("设备未使能，无法移动")
                return False
            self.logger.info(f"绝对移动: X={x:.2f} Y={y:.2f} Z={z:.2f} (mm)")
            self.data["status"] = "Busy"

            targets = {'x': x, 'y': y, 'z': z}
            pulses = {ax: int(targets[ax] * self.pulses_per_mm[ax]) for ax in targets}

            ok = 0
            for axis in ['x', 'y', 'z']:
                addr = self.addr_mapping[axis]
                self.logger.info(f"轴 {axis} (slave={addr:#x}): 绝对目标={pulses[axis]}脉冲/步")
                if self.axis_type[axis] == 'dm2j':
                    res = self._move_dm2j(addr, pulses[axis], self.default_speed_rpm, absolute=True)
                else:
                    res = self._move_youling(addr, pulses[axis], self.default_speed_yl)
                if res:
                    ok += 1
                else:
                    self.logger.error(f"轴 {axis} 绝对移动指令发送失败")
                time_module.sleep(0.05)

            if wait_done and ok > 0:
                wait_time = max(1.5, abs(max(pulses.values(), key=abs)) / 20000 + 1.5)
                self.logger.info(f"等待移动完成 (约 {wait_time:.1f}s)...")
                time_module.sleep(wait_time)
                await self.get_position()

            self.data["status"] = "Idle"
            return ok == 3
        except Exception as e:
            self.logger.error(f"绝对移动失败: {e}")
            self.data["status"] = "Error"
            return False

    # ========== 推杆 (换向式两路继电器) ==========
    def _push_rod_drive(self, extend: bool) -> bool:
        """驱动换向式推杆。extend=True 伸出(夹紧), False 缩回(释放)。
        两路继电器互斥: 先断开反向路, 再吸合目标路, 避免同时吸合造成换向短路。
        到位后保持通电以维持力(由继电器板/推杆机械/限位保证安全)。
        """
        addr = self.addr_mapping['push_rod']
        off_coil = self.push_rod_coil_retract if extend else self.push_rod_coil_extend
        on_coil = self.push_rod_coil_extend if extend else self.push_rod_coil_retract
        # 先断开相反方向
        if not self._write_coil(addr, off_coil, False):
            self.logger.error(f"推杆断开反向继电器失败 coil={off_coil:#x}")
            return False
        time_module.sleep(0.05)
        # 再吸合目标方向
        if not self._write_coil(addr, on_coil, True):
            self.logger.error(f"推杆吸合目标继电器失败 coil={on_coil:#x}")
            return False
        return True

    @action(description="夹紧玻璃")
    async def clamp_glass(self) -> bool:
        try:
            self.logger.info("执行玻璃夹紧 (推杆伸出: 缩回路断开, 伸出路吸合)")
            if self._push_rod_drive(extend=True):
                self.data["push_rod_status"] = "clamped"
                return True
            return False
        except Exception as e:
            self.logger.error(f"夹紧失败: {e}")
            return False

    @action(description="释放玻璃")
    async def release_glass(self) -> bool:
        try:
            self.logger.info("执行玻璃释放 (推杆缩回: 伸出路断开, 缩回路吸合)")
            if self._push_rod_drive(extend=False):
                self.data["push_rod_status"] = "released"
                return True
            return False
        except Exception as e:
            self.logger.error(f"释放失败: {e}")
            return False

    @action(description="推杆停止(两路继电器全部断开)")
    async def stop_push_rod(self) -> bool:
        try:
            self.logger.info("推杆停止: 两路继电器全部断开")
            addr = self.addr_mapping['push_rod']
            r1 = self._write_coil(addr, self.push_rod_coil_extend, False)
            time_module.sleep(0.05)
            r2 = self._write_coil(addr, self.push_rod_coil_retract, False)
            self.data["push_rod_status"] = "stopped"
            return r1 and r2
        except Exception as e:
            self.logger.error(f"推杆停止失败: {e}")
            return False

    # ========== 停止 ==========
    @action(description="停止所有运动")
    async def stop_all(self) -> bool:
        try:
            self.logger.info("停止所有运动")
            ok = 0
            for axis in ['x', 'y', 'z']:
                addr = self.addr_mapping[axis]
                if self.axis_type[axis] == 'dm2j':
                    res = self._write_register(addr, DM2J_REG["trigger"], DM2J_TRIG_ESTOP)
                else:
                    # 俏优灵: 停止=向急停寄存器0x04写0 (见手册停止示例)
                    res = self._write_register(addr, YL_REG["estop"], 0)
                if res:
                    ok += 1
                time_module.sleep(0.03)
            self.data["status"] = "Idle"
            return ok > 0
        except Exception as e:
            self.logger.error(f"停止失败: {e}")
            return False

    # ========== 读取位置 ==========
    @action(description="获取当前位置")
    async def get_position(self) -> Dict[str, float]:
        try:
            positions = {}
            for axis in ['x', 'y', 'z']:
                addr = self.addr_mapping[axis]
                if self.axis_type[axis] == 'dm2j':
                    resp = self._read_registers(addr, DM2J_REG["motor_pos_h"], 2)
                else:
                    resp = self._read_registers(addr, YL_REG["act_steps_h"], 2)
                if resp and hasattr(resp, "registers") and len(resp.registers) >= 2:
                    raw = self._from_hilo(resp.registers[0], resp.registers[1])
                    positions[axis] = raw / self.pulses_per_mm[axis]
                else:
                    positions[axis] = self.data.get(f"position_{axis}", 0.0)
                time_module.sleep(0.03)
            self.data["position_x"] = positions['x']
            self.data["position_y"] = positions['y']
            self.data["position_z"] = positions['z']
            return positions
        except Exception as e:
            self.logger.error(f"获取位置失败: {e}")
            return {"x": 0.0, "y": 0.0, "z": 0.0}

    # ========== 重置错误 ==========
    @action(description="重置错误")
    async def reset_error(self) -> bool:
        try:
            self.logger.info("重置设备错误")
            for axis in ['x', 'y']:
                addr = self.addr_mapping[axis]
                # DM2J: 控制字0x1801写0x1111复位当前报警
                self._write_register(addr, DM2J_REG["control_word"], 0x1111)
                time_module.sleep(0.03)
            self.data["error_code"] = 0
            self.data["status"] = "Idle"
            return True
        except Exception as e:
            self.logger.error(f"错误重置失败: {e}")
            return False

    # ========== 设置速度 ==========
    @action(description="设置轴速度")
    async def set_speed(self, axis: str, speed: float) -> bool:
        """设置轴速度, 单位均为 rpm(转/分)。DM2J写Pr9.03(0x6203); 俏优灵写0x13。
        注: 俏优灵速度随目标步数在同一帧下发, 此处仅更新默认速度缓存并预写寄存器。
        """
        try:
            if axis not in ['x', 'y', 'z']:
                self.logger.error(f"无效轴名称: {axis}")
                return False
            addr = self.addr_mapping[axis]
            val = int(speed)
            if self.axis_type[axis] == 'dm2j':
                self.default_speed_rpm = val
                res = self._write_register(addr, DM2J_REG["pr0_speed"], val & 0xFFFF)
            else:
                self.default_speed_yl = val
                res = self._write_register(addr, YL_REG["speed"], val & 0xFFFF)
            if res:
                self.logger.info(f"轴 {axis} 速度已设置为 {val} rpm")
            return res
        except Exception as e:
            self.logger.error(f"设置速度失败: {e}")
            return False

    # ========== 清理 ==========
    @action(description="清理资源")
    async def cleanup(self) -> bool:
        try:
            self.logger.info(f"清理设备 {self.device_id}")
            await self.stop_all()
            self._close_connection()
            self.data["status"] = "Offline"
            self.data["is_enabled"] = False
            return True
        except Exception as e:
            self.logger.error(f"清理失败: {e}")
            return False


# ============================================================================
# X/Y 演示 (独立运行, 不走 ROS): python -m unilabos.devices.SHU.xyz_guangdian
# 流程: 连接 -> 使能X/Y -> 手动设零(当前位置=0, 电机不动) ->
#       X走-10mm / Y走+10mm -> 读位置 -> 回到零点 -> 读位置 -> 停止。
# 说明: X/Y未接限位, 用手动设零建立坐标零点; 不碰 Z 和推杆。
#       请确保台面从当前零点向 X负/Y正 各有 >10mm 的可用行程, 避免撞机械端。
# ============================================================================
if __name__ == "__main__":
    import asyncio

    _DEMO_CONFIG = {
        "port": "COM6",
        "baudrate": 9600,
        "timeout": 2.0,
        "retry_count": 3,
        "retry_delay": 0.1,
        "addr_x": 2,
        "addr_y": 3,
        "x_pulses_per_mm": 10000,   # 10000P/r ÷ 1mm导程
        "y_pulses_per_mm": 10000,
        "default_speed_rpm": 200,   # rpm
    }

    async def _demo():
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        dev = XYZGuangdian(device_id="xyz_demo", **_DEMO_CONFIG)
        x_addr, y_addr = dev.addr_mapping['x'], dev.addr_mapping['y']

        # 1) 只打开串口(不做四设备通信自检)
        from pymodbus.client import ModbusSerialClient
        dev.modbus_client = ModbusSerialClient(
            port=dev.port, baudrate=dev.baudrate,
            bytesize=8, parity='N', stopbits=1, timeout=dev.timeout,
        )
        if not dev.modbus_client.connect():
            print(f"无法打开串口 {dev.port}")
            return

        def _report():
            rx, ry = dev._read_axis_raw('x'), dev._read_axis_raw('y')
            px = rx / dev.pulses_per_mm['x'] if rx is not None else None
            py = ry / dev.pulses_per_mm['y'] if ry is not None else None
            print(f"  X={px if px is None else round(px, 3)}mm  Y={py if py is None else round(py, 3)}mm")

        try:
            # 2) 通信自检: 读X/Y运行状态
            if dev._read_registers(x_addr, DM2J_REG["run_status"], 1) is None or \
               dev._read_registers(y_addr, DM2J_REG["run_status"], 1) is None:
                print("X/Y通信失败, 检查COM口/波特率(9600)/从站地址/接线")
                return

            # 3) 使能 X/Y (Pr0.07=1 软件强制使能)
            dev._write_register(x_addr, DM2J_REG["force_enable"], 1)
            dev._write_register(y_addr, DM2J_REG["force_enable"], 1)
            dev.data["is_enabled"] = True
            time_module.sleep(0.1)

            # 4) 手动设零: 把当前位置当作零点(电机不动)
            await dev.set_current_as_zero('x')
            await dev.set_current_as_zero('y')
            print("已把当前位置设为零点:")
            _report()

            # 5) X走-10mm, Y走+10mm (move_relative只动非零增量的轴, Z/推杆不受影响)
            print("X -10mm, Y +10mm ...")
            await dev.move_relative(x_delta=-10.0, y_delta=10.0, wait_done=False)
            time_module.sleep(4.0)
            _report()

            # 6) 回到零点: X走+10mm, Y走-10mm
            print("回到零点 (X +10mm, Y -10mm) ...")
            await dev.move_relative(x_delta=10.0, y_delta=-10.0, wait_done=False)
            time_module.sleep(4.0)
            _report()

        finally:
            # 7) 停止X/Y并关闭串口
            dev._write_register(x_addr, DM2J_REG["trigger"], DM2J_TRIG_ESTOP)
            dev._write_register(y_addr, DM2J_REG["trigger"], DM2J_TRIG_ESTOP)
            dev._close_connection()
            print("演示结束, 已清理资源")

    asyncio.run(_demo())

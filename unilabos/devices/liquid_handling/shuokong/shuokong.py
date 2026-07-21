#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOPA 气体置换式移液器 SC-STxxx 系列 RS485 通信测试脚本

通信参数（默认）：
    串口    : COM6
    波特率  : 115200
    地址    : 1
    数据位/校验/停止位: 8/N/1

协议格式（OEM）：
    主机 -> 从机:  头码('[') + 地址(ASCII) + 命令/数据(ASCII) + 尾码('E') + 校验和(1字节)
    从机 -> 主机:  头码('/') + 地址(1字节) + 数据(9字节) + 尾码('E') + 校验和(1字节)
                  其中 9 字节数据 = [状态字节(0x06)] + [错误码] + 7 字节负载

注意:
    1. 命令以 <E> 结尾才会执行，缓冲区最多 256 字符；
    2. 不论动作命令（H/A/P/D）还是报告命令（V/Q[n]），设备都会回 2 帧:
         第 1 帧 = ACK    (err = 0x0A "开始执行命令", payload 为占位 0x30 0x00...)
         第 2 帧 = 结果   动作命令: err = 0x00 表示成功; 报告命令: payload 为真正的数据
       动作命令的第 2 帧可能要等几秒;
    3. Q 必须带参数 (如 Q18/Q28), 单独的 Q 设备不响应;
    4. 设备地址不可为 47('/'), 69('E'), 91('[')。

运行：
    pip install pyserial
    python shuokong.py
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import serial

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SOPA")


# ---------------------------------------------------------------------------
# 协议常量
# ---------------------------------------------------------------------------
HEADER_OEM = 0x5B       # '['
HEADER_RESP = 0x2F      # '/'
TAIL = 0x45             # 'E'
STATUS_BYTE = 0x06      # 应答帧固定的第一个状态字节

FORBIDDEN_ADDRS = {47, 69, 91}  # '/', 'E', '['

# 错误代码（节选自手册 5.10）
ERROR_CODES = {
    0x00: "无错误",
    0x01: "上次动作未完成",
    0x02: "设备未初始化",
    0x03: "设备过载",
    0x04: "无效的指令",
    0x05: "液位探测故障",
    0x07: "超时错误",
    0x08: "执行指令失败",
    0x09: "指令缓冲溢出",
    0x0A: "开始执行命令",
    0x0B: "枪头丢失",
    0x0C: "未注册",
    0x0D: "空吸",
    0x0E: "堵针",
    0x10: "泡沫",
    0x11: "吸液超过吸头容量",
    0x12: "压力超范围",
    0x13: "少吸",
    0x14: "空排",
    0x15: "排堵",
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class ResponseFrame:
    """13 字节标准响应帧

    9 字节 data 区有两种格式:

    1) **动作类帧** (H/A/P/D 等的 ACK 和完成帧, 以及 ``E`` 报错应答):
       ``data[0] = 0x06``  (状态字节)
       ``data[1] = 错误码``  (0x00 成功, 0x0A 开始执行, 其余为错误)
       ``data[2..8] = 占位 30 00 00 00 00 00 00``

    2) **报告类数据帧** (V/Q[n] 真正的数据):
       ``data[0] = ASCII 标识符``  (例如 'V', 'l', 'T', 't', 'n')
       ``data[1..8] = 数据``       (ASCII 文本或二进制, 视具体命令而定)
    """

    address: int
    data: bytes       # 9 字节数据区
    raw: bytes        # 原始 13 字节帧

    # ---- 旧字段保留向后兼容 (只对动作类帧有意义) ----
    @property
    def status(self) -> int:
        return self.data[0]

    @property
    def error(self) -> int:
        return self.data[1]

    @property
    def payload(self) -> bytes:
        """data[2..8] 7 字节占位/扩展数据 (动作类帧)"""
        return self.data[2:9]

    # ---- 新的语义判定 ----
    @property
    def is_status_frame(self) -> bool:
        """是否为动作类帧 (status + err 结构)"""
        return self.data[0] == STATUS_BYTE

    @property
    def is_ack(self) -> bool:
        """ACK 帧 (开始执行)"""
        return self.is_status_frame and self.data[1] == 0x0A

    @property
    def is_action_done(self) -> bool:
        """动作完成且无错误"""
        return self.is_status_frame and self.data[1] == 0x00

    @property
    def is_ok(self) -> bool:
        """兼容旧名: 动作完成无错误"""
        return self.is_action_done

    @property
    def is_report_data(self) -> bool:
        """报告数据帧 (含真正的查询结果)"""
        return not self.is_status_frame

    @property
    def has_error(self) -> bool:
        """是否携带运行/即时错误码"""
        return self.is_status_frame and self.data[1] not in (0x00, 0x0A)

    @property
    def report_id(self) -> str:
        """报告数据帧的标识符字符 (如 'V', 'l', 'T'); 非报告帧返回 ''"""
        if self.is_report_data:
            return chr(self.data[0])
        return ""

    @property
    def report_payload(self) -> bytes:
        """报告数据帧标识符之后的 8 字节数据"""
        return self.data[1:9] if self.is_report_data else b""

    @property
    def error_desc(self) -> str:
        if not self.is_status_frame:
            return "(报告数据帧)"
        return ERROR_CODES.get(self.error, f"未知错误(0x{self.error:02X})")

    def __str__(self) -> str:
        if self.is_status_frame:
            return (
                f"<StatusFrame addr={self.address} status=0x{self.status:02X} "
                f"err=0x{self.error:02X}({self.error_desc}) "
                f"raw={self.raw.hex().upper()}>"
            )
        return (
            f"<ReportFrame addr={self.address} id={self.report_id!r} "
            f"data={self.report_payload.hex().upper()} raw={self.raw.hex().upper()}>"
        )


# ---------------------------------------------------------------------------
# 驱动
# ---------------------------------------------------------------------------
class ShuoKongPipette:
    """SOPA 移液器最小化驱动（RS485/OEM 协议）"""

    def __init__(
        self,
        port: str = "COM6",
        baudrate: int = 115200,
        address: int = 1,
        timeout: float = 1.0,
    ):
        if address in FORBIDDEN_ADDRS or not (1 <= address <= 254):
            raise ValueError(
                f"地址 {address} 非法（必须在 1~254 之间，且不能为 47/69/91）"
            )
        self.port = port
        self.baudrate = baudrate
        self.address = address
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    # ---------------- 串口生命周期 ----------------
    def open(self) -> None:
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        logger.info("串口已打开: %s @ %d", self.port, self.baudrate)

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("串口已关闭")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ---------------- 协议封装 ----------------
    @staticmethod
    def _checksum(data: bytes) -> int:
        return sum(data) & 0xFF

    def _build_frame(self, command: str) -> bytes:
        body = f"[{self.address}{command}E".encode("ascii")
        return body + bytes([self._checksum(body)])

    def _write(self, frame: bytes) -> None:
        assert self.ser and self.ser.is_open, "串口未打开"
        readable = "".join(
            chr(b) if 0x20 <= b <= 0x7E else f"\\x{b:02X}" for b in frame
        )
        logger.debug("TX: %s | %s", frame.hex().upper(), readable)
        self.ser.write(frame)
        self.ser.flush()

    def _read_frames(
        self,
        expected: int = 2,
        timeout: float = 5.0,
        grace_after_first: float = 0.5,
    ) -> List[ResponseFrame]:
        """读取若干个 13 字节响应帧

        - 最多读 ``expected`` 帧
        - 收到第 1 帧后, 再额外等 ``grace_after_first`` 秒看是否有后续帧;
          超过宽限期就以已收帧返回 (避免在等待第 2 帧时无谓地阻塞 timeout 秒)
        """
        assert self.ser, "串口未打开"
        buf = bytearray()
        deadline = time.time() + timeout
        frames: List[ResponseFrame] = []
        first_seen_at: Optional[float] = None
        while time.time() < deadline and len(frames) < expected:
            n = self.ser.in_waiting
            if n:
                buf.extend(self.ser.read(n))
            # 解析所有以 '/' 开头的 13 字节帧
            while True:
                idx = buf.find(bytes([HEADER_RESP]))
                if idx < 0:
                    buf.clear()
                    break
                if idx > 0:
                    del buf[:idx]
                if len(buf) < 13:
                    break
                frame_bytes = bytes(buf[:13])
                # 校验尾码和校验和
                if frame_bytes[11] != TAIL:
                    del buf[0]
                    continue
                cs_calc = self._checksum(frame_bytes[:12])
                if cs_calc != frame_bytes[12]:
                    logger.warning(
                        "校验失败 raw=%s calc=0x%02X recv=0x%02X",
                        frame_bytes.hex().upper(), cs_calc, frame_bytes[12],
                    )
                    del buf[0]
                    continue
                frame = ResponseFrame(
                    address=frame_bytes[1],
                    data=frame_bytes[2:11],
                    raw=frame_bytes,
                )
                frames.append(frame)
                if first_seen_at is None:
                    first_seen_at = time.time()
                logger.debug("RX: %s", frame)
                del buf[:13]
            if len(frames) >= expected:
                break
            # 已经拿到至少一帧, 但后续帧迟迟不来 → 提前结束
            if first_seen_at and (time.time() - first_seen_at) > grace_after_first:
                break
            time.sleep(0.02)
        return frames

    # ---------------- 高层指令 ----------------
    def send(
        self,
        command: str,
        timeout: float = 30.0,
        expected_frames: int = 2,
    ) -> List[ResponseFrame]:
        """发送一条命令字符串（无需手动加 ``E`` 与校验和）

        所有命令（动作/报告）默认均期待 2 帧应答：ACK + 结果数据。

        Args:
            command: 命令内容, 比如 ``"H"``, ``"A0"``, ``"P50"``, ``"Q18"``
            timeout: 读取超时 (s)
            expected_frames: 期望帧数, 默认 2

        Returns:
            收到的响应帧列表 (长度 0~expected_frames)
        """
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("串口未打开")
        self.ser.reset_input_buffer()
        frame = self._build_frame(command)
        logger.info("发送命令: %r", command)
        self._write(frame)
        frames = self._read_frames(expected=expected_frames, timeout=timeout)
        if not frames:
            logger.error("命令 %r 未收到任何响应", command)
            return frames
        for i, f in enumerate(frames):
            logger.info("响应[%d/%d]: %s", i + 1, len(frames), f)
        last = frames[-1]
        if last.has_error:
            logger.warning("命令 %r 返回错误: %s", command, last.error_desc)
        # 命令之间留一点空隙, 让设备和总线复位
        time.sleep(0.05)
        return frames

    # 常用快捷方法 -----------------------------------------------------------
    def query_version(self) -> List[ResponseFrame]:
        """报告固件版本 <V>"""
        return self.send("V", timeout=2.0)

    def query(self, n: int) -> List[ResponseFrame]:
        """报告指令 <Q[n]>; n 不可缺省"""
        return self.send(f"Q{n:02d}", timeout=2.0)

    def initialize(self, settle: float = 5.0) -> bool:
        """初始化活塞 <HE>

        ⚠️ 实测 V06.92 固件:
        - 当电机真正运转时, 命令只会立刻回 ACK (err=0x0A), 不主动回 DONE 帧;
        - 所以这里只确认 ACK 收到 = "命令已接收", 然后 **死等 ``settle`` 秒**
          让电机完成上下满行程初始化.
        """
        frames = self.send("H", timeout=2.0)
        if not frames or frames[-1].has_error:
            return False
        logger.info("活塞初始化命令已接收, 等待电机完成上下满行程 (%.1fs) ...", settle)
        time.sleep(settle)
        return True

    def eject_tip(self, settle: float = 1.5) -> bool:
        """顶出枪头 <RE>"""
        frames = self.send("R", timeout=2.0)
        if not frames or frames[-1].has_error:
            return False
        time.sleep(settle)
        return True

    def move_absolute(self, volume_ul: float, settle: float = 0.0) -> bool:
        """活塞绝对位置 <A[n]E>，n 为微升 0~1000

        Args:
            volume_ul: 目标位置 (µL)
            settle:    发送命令后额外死等的秒数 (实际运动期间设备不会主动回完成帧)
        """
        frames = self.send(f"A{volume_ul:g}", timeout=2.0)
        if not frames or frames[-1].has_error:
            return False
        if settle > 0:
            time.sleep(settle)
        return True

    def get_position_increment(self) -> Optional[int]:
        """查询当前活塞位置 (Q18, 单位: 增量, 1000µL ≈ 10200 增量)"""
        frames = self.query(18)
        if len(frames) < 2 or not frames[1].is_report_data:
            return None
        data = frames[1].report_payload
        # 'l' + ASCII 数字字符串 + NUL 填充
        try:
            digits = data.split(b"\x00", 1)[0].decode("ascii")
            return int(digits) if digits else 0
        except (ValueError, UnicodeDecodeError):
            return None

    def aspirate(self, volume_ul: float, settle: float = 1.0) -> bool:
        """相对抽吸 <P[n]E>，n 微升"""
        frames = self.send(f"P{volume_ul:g}", timeout=2.0)
        if not frames or frames[-1].has_error:
            return False
        if settle > 0:
            time.sleep(settle)
        return True

    def dispense(self, volume_ul: float, settle: float = 1.0) -> bool:
        """相对分配 <D[n]E>，n 微升"""
        frames = self.send(f"D{volume_ul:g}", timeout=2.0)
        if not frames or frames[-1].has_error:
            return False
        if settle > 0:
            time.sleep(settle)
        return True

    def set_speeds(
        self,
        max_speed: int = 2000,
        start_speed: int = 200,
        cutoff_speed: int = 200,
        acceleration: int = 30000,
    ) -> bool:
        """一次性设置加速度、启动速度、断流速度、最高速度（单位 0.1 µL/s）"""
        cmd = f"a{acceleration}b{start_speed}c{cutoff_speed}s{max_speed}"
        frames = self.send(cmd, timeout=2.0)
        return bool(frames) and not frames[-1].has_error

    @staticmethod
    def decode_report_payload(frame: ResponseFrame) -> str:
        """把报告数据帧解释成可读字符串

        实测的不同 ``report_id`` 对应规则:

        - ``'V'`` 固件版本: 接 2 字节大端 hex 版本号
        - ``'l'`` Q18 当前位置增量: ASCII 文本
        - ``'T'`` Q28 枪头存在: 'T0' 无 / 'T1' 有
        - ``'t'`` Q11 波特率索引: ASCII 文本 (1=115200)
        - ``'n'`` Q08 节点地址 + MAC: 实测 6 字节为 MAC
        - 其它  : 原样打印
        """
        if not frame.is_report_data:
            return f"(非报告帧) status=0x{frame.status:02X} err=0x{frame.error:02X}"

        ident = frame.report_id
        data = frame.report_payload  # 8 字节

        # 尝试解析为以 NUL 结尾的 ASCII 文本
        ascii_part = data.split(b"\x00", 1)[0]
        text_safe = "".join(
            chr(b) if 0x20 <= b <= 0x7E else f"\\x{b:02X}" for b in ascii_part
        )

        if ident == "V":
            major, minor = data[0], data[1]
            ver = f"{major:02X}.{minor:02X}"
            return f"V (固件版本) = {ver}    raw_data={data.hex().upper()}"
        if ident == "l":
            return f"l (位置增量) = {text_safe!r}    raw_data={data.hex().upper()}"
        if ident == "T":
            present = (data[0:1] == b"1")
            return f"T (枪头) = {'存在' if present else '不存在'}    raw_data={data.hex().upper()}"
        if ident == "t":
            return f"t (波特率索引) = {text_safe!r}    raw_data={data.hex().upper()}"
        if ident == "n":
            mac = ":".join(f"{b:02X}" for b in data[:6])
            return f"n (节点/MAC) MAC={mac}    raw_data={data.hex().upper()}"
        return f"{ident!r} text={text_safe!r}  raw_data={data.hex().upper()}"


# ---------------------------------------------------------------------------
# 自检测试主程序
# ---------------------------------------------------------------------------
def run_self_test(port: str, baudrate: int, address: int, do_motion: bool) -> int:
    print("=" * 60)
    print(f" SOPA 移液器自检测试 | port={port} baud={baudrate} addr={address}")
    print("=" * 60)

    def _show_report(name: str, frames: List[ResponseFrame]) -> None:
        if not frames:
            print(f"  ✗ {name}: 无响应")
            return
        if len(frames) >= 2:
            data_frame = frames[1]
            print(f"  ✓ {name}: {ShuoKongPipette.decode_report_payload(data_frame)}")
        else:
            print(f"  ⚠ {name}: 只收到 ACK，未收到数据帧 "
                  f"(payload={ShuoKongPipette.decode_report_payload(frames[0])})")

    def _has_tip(frames: List[ResponseFrame]) -> bool:
        """从 Q28 响应判断是否装有枪头"""
        if len(frames) < 2 or not frames[1].is_report_data:
            return False
        return frames[1].report_payload[:1] == b"1"

    try:
        with ShuoKongPipette(port=port, baudrate=baudrate, address=address) as pipette:

            # ---------- 1. 通信测试: 查询固件版本 ----------
            print("\n[1/4] 查询固件版本 <V> ...")
            frames = pipette.query_version()
            if not frames:
                print("  ✗ 无响应，请检查串口/接线/地址/波特率")
                return 1
            _show_report("固件版本", frames)

            # ---------- 2. 查询设备信息 ----------
            print("\n[2/4] 查询设备信息 ...")
            _show_report("节点地址 <Q08>", pipette.query(8))
            _show_report("波特率   <Q11>", pipette.query(11))
            _show_report("当前位置 <Q18>", pipette.query(18))
            tip_frames = pipette.query(28)
            _show_report("枪头状态 <Q28>", tip_frames)
            tip_present = _has_tip(tip_frames)

            # ---------- 3. 初始化活塞 ----------
            print("\n[3/4] 初始化活塞 <HE> （会上下走完整行程，约 3~5s）...")
            ok = pipette.initialize()
            print(f"  {'✓ 初始化成功' if ok else '✗ 初始化失败'}")
            if not ok:
                return 2

            # ---------- 4. 可选的小量移液动作 ----------
            if not do_motion:
                print("\n[4/4] 跳过移液动作（使用 --motion 启用）")
                print("\n所有测试完成 ✅")
                return 0

            print("\n[4/4] 执行最小动作测试 ...")
            ok = pipette.set_speeds(
                max_speed=2000, start_speed=200,
                cutoff_speed=200, acceleration=30000,
            )
            if not ok:
                print("  ✗ 速度参数设置失败")
                return 3

            # 用大行程 (满量程 1000µL ≈ 60mm), 每步死等 + Q18 验证位置真的变化
            # 满行程 60mm @ max_speed 200µL/s ≈ 5s
            print("  · 用 A 绝对位置 + Q18 位置验证 (不依赖完成帧, 死等运动结束)")

            # 估算的运动耗时 (秒); 满行程 5s, 半行程 2.5s, 留 1.5s 余量
            steps = [
                ("A0    → 0 µL    回零位",  0,    4.0),
                ("A1000 → 1000 µL 满行程", 1000, 6.0),
                ("A500  → 500 µL  中点",   500,  4.0),
                ("A0    → 0 µL    回零位",  0,    4.0),
            ]

            print(f"    起始位置 Q18 = {pipette.get_position_increment()}")
            all_ok = True
            positions: List[Optional[int]] = []
            for desc, vol, wait_s in steps:
                step_ok = pipette.move_absolute(vol, settle=wait_s)
                pos = pipette.get_position_increment()
                positions.append(pos)
                marker = "✓" if step_ok else "✗"
                print(f"    {marker} {desc:30s}  等待 {wait_s:.1f}s 后 Q18 = {pos}")
                if not step_ok:
                    all_ok = False
                    break

            # 诊断: 位置应该真的变化
            unique_positions = {p for p in positions if p is not None}
            if all_ok and len(unique_positions) <= 1:
                print("\n  ⚠ 警告: Q18 位置始终不变, 电机确实没在动!")
                print("    通信完全正常, 但活塞没动. 可能原因:")
                print("      1) 设备未接 24V 主电源 (只接了通信线 7/8)")
                print("         → 红灯不亮 = 没电, 红灯亮但不动 = 见下方")
                print("      2) 24V 电源功率不足 (<1A 峰值)")
                print("      3) 内部 1.5A 保险丝烧断")
                print("      4) 电机电流配置为 0 (用厂家 Softcontrol 工具复位)")
                print("      5) 设备型号不是 SC-STxxx-00-13 (其他型号 RS485 仅支持读)")
                print("\n    建议先用厂家的 Softcontrol 软件测试同一台设备能否运动,")
                print("    若 Softcontrol 也不能驱动, 就是硬件/电源问题.")
                return 5

            if all_ok:
                print("  ✓ 动作测试完成, 位置确实在变化")
                print("\n所有测试完成 ✅")
                return 0
            print("  ✗ 动作测试失败 (查看上方 WARNING 日志获取错误码)")
            return 4

    except serial.SerialException as e:
        print(f"\n串口异常: {e}")
        print("  ▶ 请确认 COM 口号是否正确，并已关闭占用该串口的其他程序")
        return 10
    except KeyboardInterrupt:
        print("\n用户中断")
        return 130
    except Exception as e:
        logger.exception("测试过程中出现未捕获异常")
        print(f"\n未捕获异常: {e}")
        return 99


def main() -> None:
    parser = argparse.ArgumentParser(description="SOPA SC-STxxx 移液器 RS485 测试")
    parser.add_argument("--port", default="COM6", help="串口号 (默认 COM6)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率 (默认 115200)")
    parser.add_argument("--addr", type=int, default=1, help="设备地址 (默认 1)")
    parser.add_argument("--motion", action="store_true",
                        help="执行 10µL 抽/排测试动作（请先确认安装好枪头或装在安全位置）")
    parser.add_argument("--debug", action="store_true", help="开启调试日志，打印收发原始字节")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    sys.exit(run_self_test(args.port, args.baud, args.addr, args.motion))


if __name__ == "__main__":
    main()

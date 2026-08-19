"""音频采集与播放：直接 shell 出 ALSA 的 ``arecord`` / ``aplay``。

为什么不用 PyAudio/sounddevice：在香橙派（ARM）上 PortAudio 的编译/驱动匹配容易踩坑，
而 ``arecord``/``aplay`` 是系统自带、最稳的一条路。我们只需要它们读/写裸 PCM 流。
"""

from __future__ import annotations

import logging
import subprocess
from typing import Iterator, Optional

logger = logging.getLogger("unilab.voice.audio")


class MicStream:
    """从麦克风持续读取 16-bit 单声道裸 PCM 的迭代器。

    用 ``arecord`` 起一个子进程，把它的 stdout 按块吐出来。用作上下文管理器，退出时
    自动结束子进程。
    """

    def __init__(self, device: str, rate: int, chunk_bytes: int = 4000) -> None:
        self.device = device
        self.rate = rate
        # 每块字节数：4000B ≈ 16000Hz*2B 下的 0.125s，识别延迟与 CPU 占用的折中。
        self.chunk_bytes = chunk_bytes
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self) -> "MicStream":
        cmd = [
            "arecord",
            "-q",
            "-D", self.device,
            "-f", "S16_LE",
            "-r", str(self.rate),
            "-c", "1",
            "-t", "raw",
        ]
        logger.info("[VOICE] 启动录音：%s", " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "找不到 arecord，请先安装 ALSA 工具：sudo apt install -y alsa-utils"
            ) from e
        return self

    def chunks(self) -> Iterator[bytes]:
        """逐块产出 PCM 数据；子进程结束/出错时自然停止。"""
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            data = self._proc.stdout.read(self.chunk_bytes)
            if not data:
                break
            yield data

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None


def play_pcm(pcm: bytes, device: str, rate: int) -> None:
    """把一段 16-bit 单声道裸 PCM 用 ``aplay`` 播出去（阻塞到播完）。"""
    if not pcm:
        return
    cmd = [
        "aplay",
        "-q",
        "-D", device,
        "-f", "S16_LE",
        "-r", str(rate),
        "-c", "1",
        "-t", "raw",
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise RuntimeError(
            "找不到 aplay，请先安装 ALSA 工具：sudo apt install -y alsa-utils"
        ) from e
    proc.communicate(pcm)


def apply_gain(pcm: bytes, gain: float) -> bytes:
    """对 16-bit 单声道裸 PCM 整体放大 ``gain`` 倍（带削顶保护）。gain<=1 原样返回。"""
    if gain <= 1.0 or not pcm:
        return pcm
    import array

    samples = array.array("h")
    samples.frombytes(pcm)
    lim = 32767
    for i, v in enumerate(samples):
        s = int(v * gain)
        if s > lim:
            s = lim
        elif s < -lim:
            s = -lim
        samples[i] = s
    return samples.tobytes()


def beep(device: str, rate: int, freq: int = 880, ms: int = 150) -> None:
    """播一声短提示音（唤醒确认用），失败静默忽略。"""
    import math
    import struct

    try:
        n = int(rate * ms / 1000)
        frames = bytearray()
        for i in range(n):
            # 头尾淡入淡出，避免爆音。
            env = min(1.0, i / (rate * 0.01), (n - i) / (rate * 0.01))
            val = int(0.3 * env * 32767 * math.sin(2 * math.pi * freq * i / rate))
            frames += struct.pack("<h", val)
        play_pcm(bytes(frames), device, rate)
    except Exception:  # noqa: BLE001
        pass

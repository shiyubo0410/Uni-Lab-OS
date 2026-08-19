"""离线语音合成（piper）：文字 → 裸 PCM → 扬声器。

piper 是独立的合成器（一个二进制 + 一个 ``.onnx`` 音色模型），在 ARM 上跑得动、离线、
中文音色可用（如 ``zh_CN-huayan-medium``）。这里 shell 出 piper 让它把音频以裸 PCM
写到 stdout，再交给 :func:`audio.play_pcm` 播放。

piper 缺失属"可降级"：合成失败只记日志、不抛，保证语音助手主循环不因"不会说话"而挂。
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

from .audio import apply_gain, play_pcm

logger = logging.getLogger("unilab.voice.tts")


class PiperTTS:
    """把文本合成为语音并播放。"""

    def __init__(
        self,
        piper_bin: str,
        model_path: str,
        spk_device: str,
        rate: int,
        gain: float = 1.0,
        enabled: bool = True,
    ) -> None:
        self.piper_bin = piper_bin
        self.model_path = model_path
        self.spk_device = spk_device
        self.rate = rate
        self.gain = gain
        # enabled=False：只听不发声，speak() 直接空转（连自检都跳过）。
        self.enabled = enabled
        self._ok = self._check() if enabled else False

    def _check(self) -> bool:
        """启动时自检：piper 可执行 + 模型文件在。缺则告警但不阻断。"""
        if not os.path.isfile(self.model_path):
            logger.warning(
                "[VOICE] 缺 piper 音色模型：%s —— 将只识别不发声。"
                "下载 zh_CN 音色到该路径，或用 UNILABOS_VOICE_PIPER_MODEL 指定。",
                self.model_path,
            )
            return False
        return True

    def synth(self, text: str) -> Optional[bytes]:
        """调 piper 合成，返回裸 PCM（S16_LE, 单声道, self.rate）。失败返回 None。"""
        text = (text or "").strip()
        if not text or not self._ok:
            return None
        cmd = [
            self.piper_bin,
            "-q",
            "-m", self.model_path,
            "--output-raw",
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except FileNotFoundError:
            logger.warning(
                "[VOICE] 找不到 piper 可执行（%s）。装法见部署说明；暂时只识别不发声。",
                self.piper_bin,
            )
            self._ok = False
            return None
        if proc.returncode != 0:
            logger.warning("[VOICE] piper 合成失败：%s", proc.stderr.decode("utf-8", "ignore")[:200])
            return None
        return proc.stdout

    def speak(self, text: str) -> None:
        """合成并播放（阻塞到播完）。禁用或合成不出来就静默跳过。"""
        if not self.enabled:
            return
        pcm = self.synth(text)
        if pcm:
            play_pcm(apply_gain(pcm, self.gain), self.spk_device, self.rate)

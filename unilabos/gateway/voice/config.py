"""语音助手配置（全部可用环境变量覆盖，前缀 ``UNILABOS_VOICE_``）。

放在 ``/etc/unilab-gateway.env`` 里，和网关其它配置一起被 systemd 读取。典型内容::

    UNILABOS_VOICE_MIC_DEVICE=plughw:1,0
    UNILABOS_VOICE_SPK_DEVICE=plughw:1,0
    UNILABOS_VOICE_VOSK_MODEL=/opt/unilab/voice/vosk-model-small-cn-0.22
    UNILABOS_VOICE_PIPER_MODEL=/opt/unilab/voice/zh_CN-huayan-medium.onnx
    UNILABOS_VOICE_WAKE_WORDS=小助手,你好网关

麦克风/扬声器的 ALSA 设备名用 ``arecord -l`` / ``aplay -l`` 查（形如 ``plughw:<卡号>,<设备号>``）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _env(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None and v.strip() != "" else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y")


@dataclass
class VoiceConfig:
    """语音助手运行参数。"""

    # ---- 音频设备（ALSA）----
    # arecord/aplay 的 -D 参数。"default" 走系统默认声卡；插 USB 声卡时通常是 plughw:1,0。
    mic_device: str = field(default_factory=lambda: _env("UNILABOS_VOICE_MIC_DEVICE", "default"))
    spk_device: str = field(default_factory=lambda: _env("UNILABOS_VOICE_SPK_DEVICE", "default"))
    # 录音采样率；vosk 中文模型按 16k 训练，别改。
    sample_rate: int = field(default_factory=lambda: _env_int("UNILABOS_VOICE_SAMPLE_RATE", 16000))

    # ---- STT 引擎选择 ----
    # "sherpa"（推荐，sherpa-onnx + Paraformer + VAD，准确率高）或 "vosk"（小模型，后备）。
    stt_engine: str = field(default_factory=lambda: _env("UNILABOS_VOICE_STT_ENGINE", "sherpa").lower())

    # ---- STT：sherpa-onnx（Paraformer 中文 + Silero VAD）----
    sherpa_model: str = field(default_factory=lambda: _env("UNILABOS_VOICE_SHERPA_MODEL", "/opt/unilab/voice/sherpa-onnx-paraformer-zh-small-2024-03-09/model.int8.onnx"))
    sherpa_tokens: str = field(default_factory=lambda: _env("UNILABOS_VOICE_SHERPA_TOKENS", "/opt/unilab/voice/sherpa-onnx-paraformer-zh-small-2024-03-09/tokens.txt"))
    sherpa_vad: str = field(default_factory=lambda: _env("UNILABOS_VOICE_SHERPA_VAD", "/opt/unilab/voice/silero_vad.onnx"))
    sherpa_threads: int = field(default_factory=lambda: _env_int("UNILABOS_VOICE_SHERPA_THREADS", 2))

    # ---- STT：vosk（后备）----
    # 解压好的 vosk 模型目录（含 am/ conf/ 等子目录）。
    vosk_model: str = field(default_factory=lambda: _env("UNILABOS_VOICE_VOSK_MODEL", "/opt/unilab/voice/vosk-model-small-cn-0.22"))

    # ---- 唤醒词 ----
    # 逗号分隔；先说其一再讲指令。用 vosk 语法约束识别实现，无需额外唤醒引擎。
    wake_words: List[str] = field(
        default_factory=lambda: [
            w.strip() for w in _env("UNILABOS_VOICE_WAKE_WORDS", "小助手,你好网关").split(",") if w.strip()
        ]
    )
    # 唤醒后等用户开口的最长时间（秒），超时无人说话就回到待唤醒。
    listen_timeout: float = field(default_factory=lambda: _env_float("UNILABOS_VOICE_LISTEN_TIMEOUT", 8.0))
    # 唤醒后的应答语（TTS 念出来提示"在听"）。留空则只播提示音不念字。
    wake_ack: str = field(default_factory=lambda: _env("UNILABOS_VOICE_WAKE_ACK", "在呢，请说"))

    # ---- TTS（piper）----
    # 总开关：设 UNILABOS_VOICE_TTS_ENABLED=0 则"只听不发声"——就绪提示、唤醒提示音、
    # 应答语、回复播报全部静音，只在日志里走（仍照常识别、控设备）。
    tts_enabled: bool = field(default_factory=lambda: _env_bool("UNILABOS_VOICE_TTS_ENABLED", True))
    piper_bin: str = field(default_factory=lambda: _env("UNILABOS_VOICE_PIPER_BIN", "piper"))
    piper_model: str = field(default_factory=lambda: _env("UNILABOS_VOICE_PIPER_MODEL", "/opt/unilab/voice/zh_CN-huayan-medium.onnx"))
    # piper 合成音的采样率，需与所用 voice 模型一致（medium 类一般 22050）。
    tts_rate: int = field(default_factory=lambda: _env_int("UNILABOS_VOICE_TTS_RATE", 22050))
    # 软件增益：合成音播放前整体放大的倍数（硬件音量拉满仍偏小时用）。1.0=不放大；
    # 过大会削顶失真，一般 2~4 即可。
    tts_gain: float = field(default_factory=lambda: _env_float("UNILABOS_VOICE_TTS_GAIN", 1.0))

    # ---- Agent 接口（本机回环）----
    # 复用 Web Runner 已挂的 Agent；固定 session 让"确认/取消"跨轮次生效。
    agent_url: str = field(default_factory=lambda: _env("UNILABOS_VOICE_AGENT_URL", "http://127.0.0.1/api/agent/chat"))
    session: str = field(default_factory=lambda: _env("UNILABOS_VOICE_SESSION", "voice"))
    http_timeout: float = field(default_factory=lambda: _env_float("UNILABOS_VOICE_HTTP_TIMEOUT", 120.0))

    @classmethod
    def from_env(cls) -> "VoiceConfig":
        """从环境变量装配一份配置。"""
        return cls()

"""离线语音识别（sherpa-onnx + Paraformer 中文 + Silero VAD）。

比 vosk-small 准确率高很多，仍纯离线、跑在 ARM CPU 上。流程：

1. 麦克风裸 PCM 持续喂 **Silero VAD** 做端点检测（自动判断"开始说话/说完了"）；
2. VAD 吐出的每一段完整语音，喂 **Paraformer** 离线识别成整句文本。

唤醒词识别与命令识别共用这一套——上层在识别到的文本里匹配唤醒词即可，无需单独的唤醒模型。

依赖 ``sherpa-onnx`` 与 ``numpy``，都是可选依赖：缺失时抛带安装指引的 ``RuntimeError``。
"""

from __future__ import annotations

import logging
import os
from typing import Iterator

logger = logging.getLogger("unilab.voice.stt.sherpa")


class SherpaEngine:
    """VAD 断句 + Paraformer 整句识别。对外只暴露 :meth:`segments`。"""

    def __init__(self, cfg) -> None:
        try:
            import sherpa_onnx  # type: ignore
            import numpy as np  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "未安装 sherpa-onnx / numpy。请执行：\n"
                "  /opt/unilab/venv/bin/python -m pip install sherpa-onnx numpy"
            ) from e

        self._np = np
        self.sample_rate = cfg.sample_rate

        for path, desc in [
            (cfg.sherpa_model, "Paraformer 模型 model.int8.onnx"),
            (cfg.sherpa_tokens, "tokens.txt"),
            (cfg.sherpa_vad, "silero_vad.onnx"),
        ]:
            if not os.path.isfile(path):
                raise RuntimeError(
                    f"找不到 {desc}：{path}\n"
                    "请下载 sherpa-onnx 中文 Paraformer 与 VAD 模型（见部署说明），"
                    "或用 UNILABOS_VOICE_SHERPA_* 指定路径。"
                )

        logger.info("[VOICE] 加载 sherpa Paraformer：%s（threads=%d）", cfg.sherpa_model, cfg.sherpa_threads)
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
            paraformer=cfg.sherpa_model,
            tokens=cfg.sherpa_tokens,
            num_threads=cfg.sherpa_threads,
            sample_rate=cfg.sample_rate,
            feature_dim=80,
            decoding_method="greedy_search",
        )

        vad_cfg = sherpa_onnx.VadModelConfig()
        vad_cfg.silero_vad.model = cfg.sherpa_vad
        vad_cfg.silero_vad.threshold = 0.5
        vad_cfg.silero_vad.min_silence_duration = 0.4
        vad_cfg.silero_vad.min_speech_duration = 0.25
        vad_cfg.sample_rate = cfg.sample_rate
        self._vad = sherpa_onnx.VoiceActivityDetector(vad_cfg, buffer_size_in_seconds=30)
        logger.info("[VOICE] 加载 Silero VAD：%s", cfg.sherpa_vad)

    def segments(self, chunks: Iterator[bytes]) -> Iterator[str]:
        """消费麦克风 PCM 块，每检测到一段完整语音就产出其识别文本。"""
        np = self._np
        for chunk in chunks:
            # int16 裸 PCM → float32 [-1,1]，喂给 VAD。
            samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            self._vad.accept_waveform(samples)
            while not self._vad.empty():
                segment = self._vad.front
                stream = self.recognizer.create_stream()
                stream.accept_waveform(self.sample_rate, segment.samples)
                self.recognizer.decode_stream(stream)
                text = (stream.result.text or "").strip()
                self._vad.pop()
                if text:
                    yield text

    def reset(self) -> None:
        """清空 VAD 累积状态（在自己播放 TTS 后调用，避免把回复声当成用户说话）。"""
        try:
            self._vad.reset()
        except Exception:  # noqa: BLE001
            pass

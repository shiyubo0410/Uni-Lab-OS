"""离线语音识别（vosk）：唤醒词监听 + 全量命令识别。

一份模型两用：

* **唤醒词监听**：给识别器套一个"语法约束"（只允许唤醒词 + ``[unk]``），从麦克风流里
  廉价地盯着有没有人喊唤醒词，避免误触发；
* **全量识别**：唤醒后换一个不带语法的识别器，把用户这句完整听下来。vosk 自带端点检测
  （``AcceptWaveform`` 返回 True 即认为一句说完），无需另配 VAD。

vosk 是可选依赖：没装时 :func:`load_model` 抛带安装指引的 ``RuntimeError``。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator, List

logger = logging.getLogger("unilab.voice.stt")


def load_model(model_path: str):
    """加载 vosk 模型；缺依赖或缺模型时给出清晰指引。"""
    try:
        from vosk import Model, SetLogLevel  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "未安装 vosk。请在网关的 venv 里执行：/opt/unilab/venv/bin/pip install vosk"
        ) from e
    if not os.path.isdir(model_path):
        raise RuntimeError(
            f"找不到 vosk 模型目录：{model_path}\n"
            "下载中文小模型并解压，例如：\n"
            "  wget https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip\n"
            "  unzip vosk-model-small-cn-0.22.zip -d /opt/unilab/voice/\n"
            "再用 UNILABOS_VOICE_VOSK_MODEL 指到该目录。"
        )
    SetLogLevel(-1)  # 关掉 vosk 自身的冗长日志
    logger.info("[VOICE] 加载 vosk 模型：%s", model_path)
    return Model(model_path)


class VoskSegmentEngine:
    """统一分段接口（与 :class:`~unilabos.gateway.voice.stt_sherpa.SherpaEngine` 对齐）。

    用一个不带语法的识别器持续转写，靠 vosk 自带端点检测切句，每句产出文本。上层在文本里
    匹配唤醒词，无需单独的唤醒识别器。
    """

    def __init__(self, model, rate: int) -> None:
        from vosk import KaldiRecognizer  # type: ignore

        self._rec = KaldiRecognizer(model, rate)

    def segments(self, chunks: Iterator[bytes]) -> Iterator[str]:
        for chunk in chunks:
            if self._rec.AcceptWaveform(chunk):
                text = json.loads(self._rec.Result()).get("text", "").replace(" ", "")
                if text:
                    yield text

    def reset(self) -> None:
        try:
            self._rec.Reset()
        except Exception:  # noqa: BLE001
            pass


class WakeSpotter:
    """唤醒词监听器：喂音频块，命中唤醒词返回 True。"""

    def __init__(self, model, rate: int, wake_words: List[str]) -> None:
        from vosk import KaldiRecognizer  # type: ignore

        self.wake_words = wake_words
        # 语法约束：只认唤醒词，其它一律归为 [unk]，大幅降低误唤醒。
        grammar = json.dumps(wake_words + ["[unk]"], ensure_ascii=False)
        self._rec = KaldiRecognizer(model, rate, grammar)

    def feed(self, chunk: bytes) -> bool:
        """喂一块音频；本块内识别出唤醒词则返回 True。"""
        text = ""
        if self._rec.AcceptWaveform(chunk):
            text = json.loads(self._rec.Result()).get("text", "")
        else:
            text = json.loads(self._rec.PartialResult()).get("partial", "")
        if not text:
            return False
        hit = any(w in text.replace(" ", "") for w in self.wake_words)
        if hit:
            # 命中后重置，避免残留影响下一次监听。
            self._rec.Reset()
        return hit


class CommandRecognizer:
    """全量命令识别：从音频流里听完整一句，返回文本（超时/无声返回空串）。"""

    def __init__(self, model, rate: int) -> None:
        self._model = model
        self._rate = rate

    def listen(self, chunks: Iterator[bytes], timeout: float) -> str:
        """消费音频块直到一句说完或超时。

        :param chunks: 麦克风裸 PCM 块的迭代器（与唤醒监听共用同一个流）。
        :param timeout: 从开始听算起的最长等待秒数。
        :returns: 识别到的整句文本；全程无有效语音则返回空串。
        """
        from vosk import KaldiRecognizer  # type: ignore

        rec = KaldiRecognizer(self._model, self._rate)
        start = time.monotonic()
        for chunk in chunks:
            if rec.AcceptWaveform(chunk):
                text = json.loads(rec.Result()).get("text", "").replace(" ", "")
                if text:
                    return text
                # 收到一个空的终结（纯静音）：若已超时就放弃。
                if time.monotonic() - start > timeout:
                    return ""
            if time.monotonic() - start > timeout:
                # 超时兜底：把当前累积的最终结果取出来。
                return json.loads(rec.FinalResult()).get("text", "").replace(" ", "")
        return json.loads(rec.FinalResult()).get("text", "").replace(" ", "")

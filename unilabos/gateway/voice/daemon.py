"""语音助手主循环：断句识别 → 唤醒判断 → 调 Agent → 念回复。

统一"分段引擎"（sherpa 或 vosk）持续把麦克风音频切成一句句文本，主循环按文本里有没有
唤醒词来驱动状态：

* **待唤醒**：某句里出现唤醒词 → 播提示音。若该句里唤醒词后面**还有内容**（如
  "小助手把搅拌开到四百转"），把后半句当命令**一口气执行**；否则应答"在呢请说"，把**下一句**当命令；
* **执行**：调本机 ``/api/agent/chat``（固定 session，"确认/取消"跨句生效）→ piper 念回复。

Agent 走本机回环 HTTP，因此活设备控制与写动作二次确认全部复用——你说"把搅拌开到 400 转"，
Agent 回"即将执行……请说确认"，你再说"确认"即可。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import List, Tuple

from .audio import MicStream, beep
from .config import VoiceConfig
from .tts import PiperTTS

logger = logging.getLogger("unilab.voice")

# 唤醒词后面若紧跟这些标点/空白，作为命令前先剥掉。
_LEADING_PUNCT = "，,。.！!？?、 　"


def _build_engine(cfg: VoiceConfig):
    """按配置装配分段识别引擎（sherpa 优先，vosk 后备）。"""
    if cfg.stt_engine == "sherpa":
        from .stt_sherpa import SherpaEngine

        return SherpaEngine(cfg)
    from . import stt

    model = stt.load_model(cfg.vosk_model)
    return stt.VoskSegmentEngine(model, cfg.sample_rate)


def _match_wake(text: str, wake_words: List[str]) -> Tuple[bool, str]:
    """文本里是否含唤醒词；命中则返回 (True, 唤醒词后剩余的命令文本)。"""
    t = text.replace(" ", "")
    for w in wake_words:
        idx = t.find(w)
        if idx >= 0:
            remainder = t[idx + len(w):].lstrip(_LEADING_PUNCT)
            return True, remainder
    return False, ""


# Agent 发起写动作二次确认时，回复里会带这些标记（见 agent._stage_write_action）。
_CONFIRM_PROMPT_MARKERS = ("即将对设备", '回复"确认"', "回复“确认”")
# "等确认"状态下用于判定用户回答的词（先判取消，避免"不确认"被当成确认）。
_CONFIRM_WORDS = ("确认", "确定", "好的", "好", "可以", "执行", "同意", "对", "是")
_CANCEL_WORDS = ("取消", "算了", "不用", "不要", "别", "停止", "否")


def _is_confirm_prompt(reply: str) -> bool:
    """Agent 回复是不是"请你确认写动作"的提示。"""
    r = reply or ""
    return any(m in r for m in _CONFIRM_PROMPT_MARKERS)


def _confirm_norm(text: str):
    """把用户这句归一成 "确认"/"取消"；都不像则返回 None（忽略、继续等）。"""
    t = (text or "").replace(" ", "")
    for w in _CANCEL_WORDS:
        if w in t:
            return "取消"
    for w in _CONFIRM_WORDS:
        if w in t:
            return "确认"
    return None


def _ask_agent(cfg: VoiceConfig, text: str) -> str:
    """把一句话发给本机常驻 Agent，取回复文本。"""
    payload = json.dumps({"session": cfg.session, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        cfg.agent_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.http_timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        logger.error("[VOICE] 调 Agent 失败：%s", e)
        return "网关助手没连上，请稍后再试。"
    except Exception as e:  # noqa: BLE001
        logger.error("[VOICE] 解析 Agent 回复失败：%s", e)
        return "网关助手返回异常。"
    if not body.get("success"):
        return f"出错了：{body.get('error') or '未知错误'}"
    return body.get("reply") or ""


def run(cfg: VoiceConfig) -> None:
    """启动语音助手（阻塞运行，直到进程被结束）。"""
    engine = _build_engine(cfg)
    tts = PiperTTS(
        cfg.piper_bin, cfg.piper_model, cfg.spk_device, cfg.tts_rate, cfg.tts_gain,
        enabled=cfg.tts_enabled,
    )

    logger.info(
        "[VOICE] 就绪。引擎=%s，唤醒词=%s，麦克风=%s，扬声器=%s",
        cfg.stt_engine, "/".join(cfg.wake_words), cfg.mic_device, cfg.spk_device,
    )
    tts.speak("语音助手已就绪")

    def handle(command: str) -> str:
        """把一句命令发给 Agent，播报并返回回复文本。"""
        logger.info("[VOICE] 命令：%s", command)
        reply = _ask_agent(cfg, command)
        logger.info("[VOICE] 回复：%s", reply[:80])
        tts.speak(reply)
        # 播完回复后清一下 VAD，避免把自己的回复声当成用户说话。
        if hasattr(engine, "reset"):
            engine.reset()
        return reply

    def next_state(reply: str) -> str:
        # Agent 若发起写动作确认，进入"等确认"，让用户下一句直接说确认/取消。
        return "await_confirm" if _is_confirm_prompt(reply) else "idle"

    with MicStream(cfg.mic_device, cfg.sample_rate) as mic:
        # idle=等唤醒；await_cmd=已唤醒等命令；await_confirm=等"确认/取消"
        state = "idle"
        for text in engine.segments(mic.chunks()):
            logger.info("[VOICE] 识别：%s", text)

            # 唤醒词最高优先级：任何状态都能重新唤醒/打断，避免卡死。
            hit, remainder = _match_wake(text, cfg.wake_words)
            if hit:
                logger.info("[VOICE] 已唤醒")
                if cfg.tts_enabled:
                    beep(cfg.spk_device, cfg.sample_rate)
                if remainder:
                    state = next_state(handle(remainder))
                else:
                    tts.speak(cfg.wake_ack)  # 静音时自动空转
                    if hasattr(engine, "reset"):
                        engine.reset()
                    state = "await_cmd"
                continue

            if state == "await_confirm":
                # 只认确认/取消，含糊的忽略、继续等（再喊"小助手"可打断）。
                answer = _confirm_norm(text)
                if answer is None:
                    continue
                state = next_state(handle(answer))
                continue

            if state == "await_cmd":
                # 已唤醒、这句就是命令。
                state = next_state(handle(text))
                continue

            # idle 且无唤醒词：忽略。

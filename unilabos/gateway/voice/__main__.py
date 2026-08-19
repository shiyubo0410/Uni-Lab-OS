"""语音助手入口：``python -m unilabos.gateway.voice``。

命令行参数可覆盖少量常用项，其余走环境变量（见 :mod:`config`）。
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import VoiceConfig
from .daemon import run


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m unilabos.gateway.voice",
        description="香橙派本地语音助手（vosk 唤醒+识别 / piper 合成 / 复用网关 Agent 控设备）",
    )
    parser.add_argument("--mic", help="麦克风 ALSA 设备（arecord -D），如 plughw:1,0")
    parser.add_argument("--spk", help="扬声器 ALSA 设备（aplay -D），如 plughw:1,0")
    parser.add_argument("--model", help="vosk 模型目录")
    parser.add_argument("--piper-model", help="piper 音色模型 .onnx")
    parser.add_argument("--wake", help="唤醒词，逗号分隔")
    parser.add_argument("--agent-url", help="Agent 接口地址，默认 http://127.0.0.1/api/agent/chat")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印 DEBUG 日志")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = VoiceConfig.from_env()
    if args.mic:
        cfg.mic_device = args.mic
    if args.spk:
        cfg.spk_device = args.spk
    if args.model:
        cfg.vosk_model = args.model
    if args.piper_model:
        cfg.piper_model = args.piper_model
    if args.wake:
        cfg.wake_words = [w.strip() for w in args.wake.split(",") if w.strip()]
    if args.agent_url:
        cfg.agent_url = args.agent_url

    try:
        run(cfg)
    except KeyboardInterrupt:
        print("\n已退出。")
        return 0
    except RuntimeError as e:
        # 依赖/模型缺失等：打印带指引的原因，非 0 退出。
        print(f"\n[启动失败] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# 香橙派本地语音助手

麦克风 + 扬声器直插网关，对着网关说话即可控设备。全离线：`vosk` 识别、`piper` 合成，
唤醒词也用 vosk 实现。它是**独立进程**，通过本机 HTTP 调网关已有的常驻 Agent
（`POST /api/agent/chat`），复用其活设备控制与写动作二次确认——你说"把搅拌开到 400 转"，
它会念"即将执行……请说确认"，你再说"确认"即可下发。

```
麦克风 →arecord→ vosk唤醒词"小助手" →vosk转文字→ POST /api/agent/chat
                                                         ↓（现成 Agent，带设备控制）
   扬声器 ←aplay← piper合成 ←──────────────────────── reply
```

## 前置条件

- 网关主进程 `unilab-gateway` 正在跑，且 Web Runner（management 模式）已挂 Agent，
  本机能访问 `http://127.0.0.1/api/agent/chat`。
- 一个 USB 麦克风 + 扬声器（或 USB 声卡 + 有源音箱）插在香橙派上。

## 1. 装系统音频工具，确认设备名

```bash
sudo apt update && sudo apt install -y alsa-utils
arecord -l      # 看录音设备，记下 卡号,设备号 → plughw:<卡>,<设备>
aplay -l        # 看播放设备
# 先自测能录能放：
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 3 /tmp/t.wav && aplay -D plughw:1,0 /tmp/t.wav
```

## 2. 装 STT

默认引擎是 **sherpa-onnx + Paraformer 中文 + Silero VAD**（准确率高，离线，跑在 ARM CPU）。

```bash
# 库（注意用 python -m pip，别用 bin/pip，其 shebang 可能指向别的 venv）
/opt/unilab/venv/bin/python -m pip install sherpa-onnx numpy

sudo mkdir -p /opt/unilab/voice && cd /opt/unilab/voice
# Paraformer 中文小模型（适合 1GB 板子）
sudo wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2
sudo tar xjf sherpa-onnx-paraformer-zh-small-2024-03-09.tar.bz2
# Silero VAD
sudo wget https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx
```

> **后备引擎 vosk**（小模型、准确率一般）：设 `UNILABOS_VOICE_STT_ENGINE=vosk`，并
> `pip install vosk` + 下 `vosk-model-small-cn-0.22` 到 `/opt/unilab/voice/`。

## 3. 装 TTS（piper）+ 中文音色（可选，缺了只识别不发声）

```bash
# piper 预编译二进制（选 arm64 版）：https://github.com/rhasspy/piper/releases
cd /opt/unilab/voice
sudo wget https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz
sudo tar xzf piper_linux_aarch64.tar.gz          # 得到 ./piper/piper
# 中文音色（huayan medium）：
sudo wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx
sudo wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json
```

## 4. 写配置（追加到 `/etc/unilab-gateway.env`）

```ini
UNILABOS_VOICE_MIC_DEVICE=plughw:1,0
UNILABOS_VOICE_SPK_DEVICE=plughw:1,0
UNILABOS_VOICE_VOSK_MODEL=/opt/unilab/voice/vosk-model-small-cn-0.22
UNILABOS_VOICE_PIPER_BIN=/opt/unilab/voice/piper/piper
UNILABOS_VOICE_PIPER_MODEL=/opt/unilab/voice/zh_CN-huayan-medium.onnx
UNILABOS_VOICE_WAKE_WORDS=小助手,你好网关
```

## 5. 先手动跑通

```bash
cd /opt/unilab/current
set -a; . /etc/unilab-gateway.env; set +a
/opt/unilab/venv/bin/python -m unilabos.gateway.voice -v
# 说"小助手" → 听到提示音 + "在呢，请说" → 说"列出当前设备" / "把搅拌开到400转" → "确认"
```

## 6. 做成开机自启服务

`/etc/systemd/system/unilab-voice.service`。注意：**必须用 `User=orangepi`（不能 root）**——
这个 venv 在 root/sudo 下不加载自己的 site-packages，会报"未安装 vosk"。语音守护不需要 LLM
key（它调本机 `/api/agent/chat`），所以不读 `/etc/unilab-gateway.env`，环境变量直接写进服务：

```ini
[Unit]
Description=Uni-Lab Gateway Voice Assistant
After=unilab-gateway.service sound.target
Wants=unilab-gateway.service

[Service]
Type=simple
User=orangepi
SupplementaryGroups=audio
WorkingDirectory=/opt/unilab/current
Environment=UNILABOS_VOICE_MIC_DEVICE=plughw:3,0
Environment=UNILABOS_VOICE_SPK_DEVICE=plughw:3,0
Environment=UNILABOS_VOICE_WAKE_WORDS=小助手
Environment=UNILABOS_VOICE_PIPER_BIN=/opt/unilab/voice/piper/piper
Environment=UNILABOS_VOICE_PIPER_MODEL=/opt/unilab/voice/zh_CN-huayan-medium.onnx
ExecStart=/opt/unilab/venv/bin/python -m unilabos.gateway.voice
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

（`plughw:3,0` 是 USB 声卡的实际卡号，用 `arecord -l`/`aplay -l` 核对后替换。）

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now unilab-voice
journalctl -u unilab-voice -f
```

## 常见问题

- **`找不到 arecord/aplay`**：`sudo apt install -y alsa-utils`。
- **录不到/放不出**：设备名不对，用 `arecord -l`/`aplay -l` 核对 `plughw:卡,设备`；服务用户不在 `audio` 组。
- **唤醒不灵**：环境噪声大或口音，换更近的麦克风；也可临时改成"持续监听"策略（后续可加开关）。
- **想只听不发声**：设 `UNILABOS_VOICE_TTS_ENABLED=0`，就绪提示/唤醒音/应答/回复全静音，仅识别+控设备（走日志）。
- **只识别不发声（非预期）**：piper 二进制或音色模型路径不对，看启动日志的告警。
- **音量太小**：拉满 USB 声卡硬件音量 `amixer -c 3 sset 'PCM' 100% unmute`（控件名用 `amixer -c 3 scontrols` 查），`sudo alsactl store` 保存；仍小可加软件增益 `UNILABOS_VOICE_TTS_GAIN`。
- **报"未安装 vosk"**：多为两种——① 用了 sudo/root 跑（此 venv 在 root 下不加载 site-packages，改用 `User=orangepi`）；② 用 `python -m pip install --force-reinstall --no-cache-dir vosk` 干净重装（`from vosk import Model` 能过才算好）。装时用 `/opt/unilab/venv/bin/python -m pip`，别用 `bin/pip`（其 shebang 可能指向别的 venv）。
- **识别慢**：香橙派算力有限属正常；小模型已是较快选择。

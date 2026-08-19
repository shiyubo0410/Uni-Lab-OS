"""香橙派本地语音助手（麦克风 + 扬声器直插网关）。

人对着插在网关上的麦克风说话，网关用 vosk 离线识别成文字，通过本机 HTTP 调
现成的常驻 Agent（``POST /api/agent/chat``，带活设备控制 + 写动作二次确认），再把
回复用 piper 离线合成后从扬声器念出来。

设计要点（见《网关Agent_开发文档》语音章节）：

* **独立进程**：作为单独的 systemd 服务运行，只当"耳朵 + 嘴巴"。音频链路即便崩了
  也不影响网关主进程（``unilab-gateway``）。
* **零改主进程**：不碰 ``main.py``；靠本机回环 HTTP 复用 Web Runner 已挂好的 Agent，
  因此"确认/取消"这类二次确认用语音说同样生效（固定 session）。
* **纯离线**：STT=vosk（中文小模型），TTS=piper，唤醒词也用 vosk 语法约束识别实现，
  不依赖网络与云端额度。

入口：``python -m unilabos.gateway.voice``。
"""

from .config import VoiceConfig

__all__ = ["VoiceConfig"]

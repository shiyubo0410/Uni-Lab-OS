# Uni-Lab-OS 网关内常驻 Agent — 开发文档

> 版本：v0.2（方案阶段）　｜　更新日期：2026-07-28　｜　状态：设计定稿中（LLM 已选型 GpuGeek 直连）
> 关联文档：《物联网网关 — 开发规划与进展》§4-②、§8「远程运维」
> 适用范围：GatewayPro（香橙派 Zero 2W）网关内常驻管理 Agent

---

## 一、背景与目标

### 1.1 为什么要这个 Agent

网关出货后，用户 A（不写代码的使用者）和运维都会遇到"设备在远端、出问题够不着"的场景：想看某台网关的状态、想让它重启个服务、想触发一次升级，今天只能 SSH 逐台登录。开发规划 §8 里把这一项列为「远程运维」，兜底方案是"退回 SSH 人工"——能用但不可规模化。

网关内常驻 Agent 就是把这件事收进盒子：一个跑在香橙派上的**轻量管理智能体**，用户在 Runner（PC/手机）里用自然语言下达意图，Agent 在网关本地理解并执行，再把结果回传。

### 1.2 会议结论（术语对齐）

会议里沿用了 Claude/Cursor 那套术语，套到网关上：

- **Agent**：能"听人话、调工具、自己决策"的智能体进程，常驻网关，负责运行时管理、升级、状态上报、故障排查。
- **Skill**：挂在 Agent 上的一个个本地能力（类似本仓库 `.cursor/skills/` 的 `SKILL.md`）。会议结论「Skill 放本地」= 把能力做成网关本地脚本/文档，**不走 MCP**（MCP server 在弱设备上加载不稳，踩过坑）。
- **Runner**：Agent 的"窗口/交互端"，跑在电脑或手机上，**自己不装 Skill**，只负责把人的话转给 Agent、把结果显示出来。

### 1.3 核心约束

- **脑子在云**：香橙派 Zero 2W（A53 四核、1–4GB RAM）跑不动本地大模型，推理必须调**云端 LLM**；网关只常驻轻量 Agent 进程 + （未来的）本地 Skill 工具。
- **LLM 选型与密钥（已定）**：用 **GpuGeek**（OpenAI 兼容 API）。网关**直连** GpuGeek，
  endpoint/key/model 写在网关本地 `/etc/unilab-gateway.env`（`UNILABOS_AGENT_LLM_*`）。
  → 因此**不再需要后端 LLM 代理端点**（原依赖 D2 取消）。
- **通道复用**：Runner ↔ 网关走**云端 WS 中转**，不额外暴露网关端口。

---

## 二、v1 范围

**一句话：先通链路，不做能力。**

| | 本期 v1 |
|---|---|
| ✅ 做 | 打通 `Runner ↔ 云中转 ↔ 网关 Agent ↔ 云端 LLM ↔ 原路返回` |
| ✅ 做 | LLM 网关**直连 GpuGeek**（OpenAI 兼容），key 写机器；未配 key 自动回退桩 |
| ✅ 做 | PC 端 Runner（先 CLI，后网页） |
| ✅ 做 | 本地自测通道（不依赖后端即可验证 Agent + LLM 逻辑） |
| ❌ 不做 | Skill（本地工具：看日志 / 重启服务 / 触发 OTA）——后续挂到 Agent |
| ❌ 不做 | 设备控制（与云端 job 通道重叠，需先理清边界） |
| ❌ 不做 | 手机端 Runner（后面交 APP 同事） |

---

## 三、架构

```
[Runner: PC CLI/网页]                    [香橙派网关进程 unilab-gateway]
   │ 用户输入                             ├─ GatewayClient  (已有的云WS长连)
   ▼                                      ├─ OTA agent      (进程内, 先例)
云后端 Schedule Server ──agent_msg──────► ├─ ★GatewayAgent  (新增·进程内)
   ▲                                      │    ├─ 会话管理(按 runner session)
   │ ◄──────────────agent_reply────────── │    └─ LLMClient 接口 ──► 云端LLM
   ▼                                      │         (EchoLLM桩 / CloudProxyLLM)
[Runner 显示]
```

### 3.1 关键决定：进程内组件，非独立服务

完全照抄 OTA agent 的做法（见 `unilabos/gateway/ota/selfhosted.py` + `main.py` 集成）：

- 复用网关那条云 WS 长连（`GatewayClient`）：`send_fn` 发上行，`on_message` 里按 `action` 路由下行；
- 以一个 asyncio 任务的形式挂进 `run_gateway`，随网关生命周期启停；
- 天然共享网关身份（`product_key` + `device_name`，见 `derive_sn()`）和断线重连逻辑。

理由：少一个 systemd 服务要维护、不必再开第二条连接、复用现成鉴权与重连。

### 3.2 文件划分

| 文件 | 职责 | 状态 |
|---|---|---|
| `unilabos/gateway/agent/llm.py` | `LLMClient` 接口 + `EchoLLM` 桩 + `OpenAICompatLLM`（GpuGeek 直连）+ `build_llm_from_env` + `CloudProxyLLM`（备用） | ✅ 已就位 |
| `unilabos/gateway/agent/agent.py` | `GatewayAgent`：会话管理、`handle_agent_msg`、`agent_reply` 回发、幂等去重 | ✅ 已实现（P0） |
| `unilabos/gateway/agent/local_cli.py` | 本地 CLI Runner，后端中转就绪前自测用 | ✅ 已实现（P0） |
| `unilabos/gateway/main.py`（改） | 实例化 Agent + `on_message` 路由 `agent_msg` | ✅ 已接入（P0） |

---

## 四、消息协议（网关 ↔ Runner，经云中转）

沿用现有 `{"action","data"}` 信封，新增两个 action。

### 4.1 下行 `agent_msg`（Runner → 网关）

```json
{"action":"agent_msg","data":{
  "session":"<runner会话id>",
  "msg_id":"<幂等id>",
  "text":"用户输入的话",
  "target":{"product_key":"pa7z23hl27x0","device_name":"33ed"}
}}
```

- `session`：一个 Runner 窗口一个，网关据此维护独立对话历史；
- `msg_id`：幂等键，重复投递只处理一次；
- `target`：后端中转据此把消息路由到指定网关（pk/sn 与 OTA 用的一致）。

### 4.2 上行 `agent_reply`（网关 → Runner）

```json
{"action":"agent_reply","data":{
  "session":"<原样带回>",
  "msg_id":"<原样带回>",
  "status":"done|streaming|error",
  "content":"assistant 文本"
}}
```

- `status`：v1 只用 `done`/`error`；预留 `streaming` 给将来逐字流式输出。

---

## 五、LLM 接口与直连配置（已定：GpuGeek）

Agent 只依赖一个接口，换服务不动 Agent 代码：

```python
class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def chat(self, messages: List[Message]) -> str: ...
```

实现（`agent/llm.py`）：

| 实现 | 用途 |
|---|---|
| `OpenAICompatLLM` | **主用**：OpenAI 兼容直连，适配 GpuGeek（`/chat/completions` + `Bearer`）。零新依赖（`urllib`），v1 非流式 |
| `EchoLLM` | 零依赖桩：不联网，回显 + 多轮验证。未配 key 时自动回退，链路仍可自测 |
| `CloudProxyLLM` | 备用：若将来改走后端代理端点再启用 |

### 5.1 直连配置（写在 `/etc/unilab-gateway.env`）

```bash
# GpuGeek（OpenAI 兼容）；key 只在本机，不下发到代码/仓库
UNILABOS_AGENT_LLM_API_KEY=<你的 GpuGeek API Token>
UNILABOS_AGENT_LLM_BASE_URL=https://api.gpugeek.com/v1   # 默认值，可省
UNILABOS_AGENT_LLM_MODEL=Vendor2/Claude-4.7-opus         # 默认值，可换账号下其它可用模型
# UNILABOS_AGENT_LLM_TEMPERATURE=0.6                      # 默认不发（Claude 等模型不接受该参数）；仅需要时才配
UNILABOS_AGENT_LLM_MAX_TOKENS=2048                        # 可省
```

`build_llm_from_env()` 在网关启动时读上述变量构建客户端：
- **配了 key** → `OpenAICompatLLM`（真实推理）；
- **没配 key** → 自动回退 `EchoLLM`（链路自测，不报错）。

换服务（DeepSeek/通义/自建 vLLM 等 OpenAI 兼容服务）只需改 `BASE_URL`+`MODEL`+`KEY`。

---

## 六、会话与上下文

- 按 `session`（每个 Runner 窗口一个）维护对话历史 `List[Message]`；
- 带一条 `system` 提示：声明它是网关管理 Agent、说明当前能力边界；
- 滑动窗口截断（保留最近 N 轮），防历史无限增长撑爆弱设备内存；
- v1 内存态即可，不持久化（重启网关 = 开新会话）。

---

## 七、本地自测方案（不依赖后端）

后端中转 / LLM 端点都还没有，但**整条 Agent 逻辑可先本地验证**：

1. `local_cli.py` 把终端输入直接喂进 `GatewayAgent` 会话循环、打印回复（不走 WS）；
2. 用 `EchoLLM` 验证：多轮上下文累积、消息往返、Runner 显示；
3. 后端给了 LLM 代理端点 → 换 `CloudProxyLLM`，本地 CLI 即可验证真实推理；
4. WS 的 `agent_msg`/`agent_reply` 路由同时接好（先挂着），后端中转就绪直接切。

---

## 八、后端依赖（cloud_relay 前提）

| # | 依赖 | 说明 | 谁做 |
|---|---|---|---|
| D1 | **Runner↔网关聊天中转** | 现有 WS 是设备向（job 按 lab 路由）。需后端把某 Runner 的 `agent_msg` 路由到指定网关（按 pk/sn），再把 `agent_reply` 送回该 Runner | 后端 |
| ~~D2~~ | ~~LLM 代理端点~~ | **已取消**：改为网关直连 GpuGeek，key 写机器本地（见 §5） | — |
| D3 | **Runner 鉴权/寻址** | Runner 怎么登录、怎么选中"要连哪台网关" | 后端 + 前端 |

---

## 九、分期计划

| 阶段 | 内容 | 依赖 | 状态 |
|---|---|---|---|
| **P0** | 实现 `GatewayAgent` + `local_cli.py`；`main.py` 接好 `agent_msg` 路由（先挂着）。EchoLLM 桩逻辑（多轮/幂等/回发信封）已本机验证 | 无（纯本地） | ✅ 完成 |
| **P1** | 本机/网关配 `UNILABOS_AGENT_LLM_API_KEY` 后用 `local_cli` 验证直连 GpuGeek 真实推理 | GpuGeek key（已有） | ⏳ 待你验证 |
| **P1.5** | **局域网 Web Runner（方法 B）**：管理后台挂 `/agent` 聊天页 + `/api/agent/chat`，同 WiFi 浏览器直接对话，不依赖后端 | 无 | ✅ 已实现 |
| **P2** | 打通 WS `agent_msg`/`agent_reply`，PC Runner 经云连到网关 Agent（方法 A） | D1、D3 | ⏳ 待后端 |
| **P2.5** | **设备控制 Skill**：`DeviceSkill`（list_devices / get_device_status / run_action）挂到 Agent，能对话查设备/下动作；写动作二次确认 | 无 | ✅ 已实现 |
| **P3** | 更多本地 Skill（看日志 / 重启服务 / 触发 OTA）；流式输出；手机端 Runner 交 APP | — | 规划中 |

### 9.2 设备控制 Skill（P2.5）说明

- `unilabos/gateway/agent/skill.py::DeviceSkill`，注入 `main.py` 里的 `workers` 活字典（热插拔实时可见）；
- 三个工具（OpenAI function calling）：`list_devices` / `get_device_status`（只读，Agent 直接执行喂回 LLM）、`run_action`（写，复用 `worker.execute_action`，与云端 `job_start` 同一条路）；
- **安全二次确认**：LLM 发起 `run_action` 时 Agent 不立即执行，先暂存并回一句"⚠️ 即将执行 X，回复确认"，用户回"确认"才真正下发，"取消"则放弃——确认逻辑在 Agent 内确定性实现，不依赖 LLM 自觉；
- 仅当 LLM 支持工具调用时启用（`OpenAICompatLLM.supports_tools=True`；EchoLLM 桩不支持，自动退化纯对话）；
- 前提：网关配了 `UNILABOS_AGENT_LLM_API_KEY`（GpuGeek），否则只能桩对话、不能控制设备。

### 9.1 局域网 Web Runner（方法 B）说明

- 复用网关常驻的管理后台 Web（`ProvisioningServer` mode=management，端口 80/8080）；
- 新增 `GET /agent`（聊天页 `agent.html`）+ `POST /api/agent/chat`（调 `GatewayAgent.chat_once`）+ `POST /api/agent/reset`；
- `main.py` 早建 `GatewayAgent` 注入管理后台；LLM 配置从 `/etc/unilab-gateway.env` 读；
- 两个入口（同一套接口）：
  - **管理首页悬浮按钮**（推荐）：`http://<网关IP>/`（即 `http://unilab-gateway-xxxx.local/`）右下角 💬 按钮，点开弹窗对话；按钮仅在注入 agent 时显示（`agent_enabled`）；
  - **独立聊天页**：`http://<网关IP>/agent`（整屏聊天）；
- 用户体验：同 WiFi 手机/电脑浏览器打开即可对话，**无需命令行、无需后端**；
- 注意：管理后台"保存 AK/SK"会重写 env 文件，已改为**保留** `UNILABOS_AGENT_LLM_*` 等非托管字段（`_extract_unmanaged_lines`），不会抹掉 LLM 配置。

---

## 十、待确认事项

1. ~~**（问后端）** LLM 代理端点~~ —— **已定**：网关直连 GpuGeek，key 写机器（§5）。
2. **（问后端）** Runner↔网关聊天中转（D1）——cloud_relay 的前提，是否做、怎么做。
3. **（问后端/前端）** Runner 鉴权与寻址（D3）——怎么登录、怎么选中要连哪台网关。
4. **（待理清）** Skill 阶段（P3）与云端 job 通道的边界：哪些操作走 Agent、哪些仍走云端下发。
5. **（选型微调）** GpuGeek 默认模型 `GpuGeek/Qwen3-32B`：是否够用、要不要换 DeepSeek-R1（更强但更慢更贵）。

---

*本文档处于方案阶段，随设计与开发推进持续更新。*

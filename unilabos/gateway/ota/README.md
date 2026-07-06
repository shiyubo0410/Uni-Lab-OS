# Uni-Lab OTA Agent

> 网关侧的 OTA 升级代理：连 ThingsBoard MQTT，订阅固件下发，分块下载到 `/data/ota/download/` 并 sha256 校验。配合 D1 阶段的 `ota` CLI 完成最终的 A/B 切换。

---

## 术语表（先读这个！）

| 词 | 物理位置 | 是什么 | 干啥 |
|---|---|---|---|
| **dev 机** | 开发者的 Windows / Mac PC（`D:\Uni-Lab\Uni-Lab-OS` 所在的这台）| 开发机 | 写代码、跑 Docker 模拟 TB、`scp` 推代码到 OPi |
| **TB 服务器**（ThingsBoard）| **D2 阶段**：Docker 容器，跑在 dev 机上 <br> **上线后**：公司云端真实例 | IoT 平台 | 存 firmware、下发更新、收 telemetry、画 dashboard |
| **OPi 网关** | Orange Pi Zero 2W 硬件（D2 阶段 `10.20.31.55` 测试机）| 边缘设备 | 跑 `unilab-gateway`（业务）+ `unilab-ota-agent`（升级代理） |
| **OTA Agent** | OPi 网关里的一个 Python 后台进程（systemd 服务）| 升级"快递员" | 听 TB 指挥下载固件 → sha256 校验 → 调 `ota` CLI 切分区 → reboot → 自检 |
| **`ota` CLI** | OPi 上 `/usr/local/bin/ota`（D1 已部署）| 底层 shell 工具 | A/B 分区切换的"工具人"，手动也能调，Agent 也能调 |

### 通信拓扑

```
   dev 机                        OPi 网关 (10.20.31.55)
┌─────────────────┐         ┌────────────────────────────┐
│ Cursor/VS Code  │ scp →   │ /home/orangepi/code/...    │
│                 │         │                            │
│ Docker:         │ ← MQTT →│ unilab-ota-agent (新)      │
│   TB CE         │         │   ├── 调用                  │
│   :1883 (MQTT)  │         │   ▼                        │
│   :9090 (UI)    │         │ /usr/local/bin/ota (D1)   │
└─────────────────┘         │                            │
        ▲                   │ unilab-gateway (原有)      │
        │ 浏览器              └────────────────────────────┘
        │ http://localhost:9090
        │
      你 (操作员)
```

### 一句话区分 D1 / D2 / D3

- **D1（已完成）**：写好"工具人" `ota` CLI，手动 ssh 进 OPi 也能切 A/B 分区。
- **D2（本阶段）**：写"快递员" OTA Agent，能听 TB 指挥下载固件 + 校验，**但还不调 `ota` CLI**，先验证通道。
- **D3（未来）**：让"快递员"真正去调"工具人"，把 sudo reboot + 自检接上去，闭环。

---

## 目录结构

| 文件 | 阶段 | 作用 |
|---|---|---|
| `ota` | D1 ✅ | A/B 分区切换 CLI（7 子命令），装到 `/usr/local/bin/ota` |
| `migrate_to_ab.sh` | D1 ✅ | 单分区 Armbian 镜像迁成 A/B 双分区，**一次性出厂动作** |
| `README.md` | D2 ⏳ | 本文档：端到端流程 + 部署 + 联调说明 |
| `__init__.py` | D2 ⏳ | Python 包标记 |
| `agent.py` | D2 ⏳ | Agent 主入口：asyncio 主循环 + 信号处理 + `python -m unilabos.gateway.ota.agent` |
| `tb_client.py` | D2 ⏳ | ThingsBoard MQTT 客户端：v2 chunk-based OTA 协议、telemetry、attribute 订阅 |
| `firmware_handler.py` | D2 ⏳ | 分块下载拼装 + sha256 校验（不调 ota CLI——D2 最小闭环不动系统） |
| `state.py` | D2 ⏳ | 状态机 + `/data/ota/agent_state.json` 持久化 |
| `unilab-ota-agent.service` | D2 ⏳ | systemd unit（User=orangepi，D2 阶段不需 root） |
| `unilab-ota-agent.env.example` | D2 ⏳ | 配置文件模板（部署时复制为 `/etc/unilab-ota-agent.env`） |

---

## D2 范围（最小闭环）

> **设计目标**：把"网关 ↔ TB MQTT"通道 + "分块下载 + 校验"打通，验证 TB OTA 协议跑得通。**不动系统**——不调 `sudo ota write/switch`、不 reboot、不回滚。

| 做 | 不做（D3+） |
|---|---|
| ✅ 连 TB MQTT (access token 认证) | ❌ 调 `ota write/verify/switch` CLI |
| ✅ 启动时上报 `current_fw_title/version/fw_state=UPDATED` | ❌ `sudo reboot` |
| ✅ 订阅 attributes 收 `fw_title/fw_version/fw_size/fw_checksum/fw_checksum_algorithm` | ❌ reboot 后自检 + 自动回滚 watchdog |
| ✅ v2 chunk-based 协议分块下载到 `/data/ota/download/` | ❌ `/data/ota/pending.flag` 状态机持久化 |
| ✅ sha256 校验通过后停在 `VERIFIED` | ❌ A/B 切换 |
| ✅ 全流程实时上报 `fw_state`，TB dashboard 可见 | ❌ u-boot watchdog |
| ✅ Agent 崩溃/重启后从 `agent_state.json` 恢复未完成的下载 | |

---

## 端到端流程

```
┌─────────────┐                          ┌──────────────────────────┐
│  dev 机     │                          │  OPi 网关 (10.20.31.55)  │
│  Docker     │                          │  unilab-ota-agent        │
│  TB CE      │      MQTT (1883)         │                          │
│  9090/1883  │ ←─────────────────────→  │  agent.py (orangepi 跑)  │
└─────────────┘                          └──────────────────────────┘
       ▲                                            │
       │ 浏览器                                      ▼
       │ http://localhost:9090                     /data/ota/
       │                                          ├── download/  ← chunk 拼装
       │                                          ├── log/
       │                                          └── agent_state.json
       │
   操作者 (你)
```

### 完整时序

```
[启动]
1. systemd 拉起 ota-agent
2. agent 读 /etc/unilab-ota-agent.env 拿 TB_HOST/TB_PORT/TB_TOKEN
3. 读 /data/ota/agent_state.json 恢复上次状态（首次为空）
4. 连 TB MQTT
5. 上报 current_fw_title/version/fw_state=UPDATED （让 TB 知道这台目前跑什么）
6. 订阅 v1/devices/me/attributes 等推送

[运维: 在 TB UI 上传 firmware + 推给这台 device]
   TB 推送 fw_title="uni-lab-gateway", fw_version="1.0.1", fw_size=12345678, fw_checksum=<sha256>

[Agent 收到 firmware 元数据]
7. 写 state.json: state=DOWNLOADING, ongoing={...}
8. 上报 fw_state=DOWNLOADING
9. 按 CHUNK_SIZE 计算 total_chunks
10. 循环：发送 v2/fw/request/<rid>/chunk/<cid>，收到 v2/fw/response/<rid>/chunk/<cid>，append 写文件
11. 每 N 个 chunk 上报 fw_state_progress
12. 下载完毕 → 上报 fw_state=DOWNLOADED

[校验]
13. 算 sha256，比对 fw_checksum
14. 通过 → 上报 fw_state=VERIFIED
15. 失败 → 上报 fw_state=FAILED + fw_error=<原因>，删 partial 文件

[D2 阶段到此停止]

[D3 阶段：未来] 调 sudo ota write → ota verify → ota switch → reboot → 自检 → 上报 UPDATED/FAILED
```

---

## TB MQTT 协议（v2 chunk-based OTA）

| 方向 | Topic | Payload | 用途 |
|---|---|---|---|
| Agent → TB | `v1/devices/me/telemetry` | JSON: `{"current_fw_title": "...", "current_fw_version": "..."}` | 启动时上报当前固件 |
| Agent → TB | `v1/devices/me/telemetry` | JSON: `{"fw_state": "DOWNLOADING", "fw_progress": 45}` | 状态上报 |
| Agent ← TB | `v1/devices/me/attributes` | JSON: `{"fw_title": "...", "fw_version": "...", "fw_size": 12345, "fw_checksum": "...", "fw_checksum_algorithm": "SHA256"}` | TB 推送新固件 |
| Agent → TB | `v2/fw/request/<rid>/chunk/<cid>` | 字符串 chunk size (例 `"524288"`) | 请求 chunk |
| Agent ← TB | `v2/fw/response/<rid>/chunk/<cid>` | binary chunk 数据 | TB 回 chunk |

- `rid` (request_id): Agent 自己生成，递增即可
- `cid` (chunk_id): 从 0 开始
- chunk_size：每次 request 的字节数。建议 256KB-1MB（chunk 太小 round-trip 太多）

参考：[TB 官方 OTA over MQTT](https://thingsboard.io/docs/user-guide/ota-updates/)

---

## 准备工作

### 1. dev 机起 TB CE Docker

```cmd
:: 一条命令起来，自带 postgres
docker run -d --name tb-ce ^
    -p 9090:9090 ^
    -p 1883:1883 ^
    -p 7070:7070 ^
    -v %USERPROFILE%\tb-data:/data ^
    -v %USERPROFILE%\tb-logs:/var/log/thingsboard ^
    --restart unless-stopped ^
    thingsboard/tb-postgres:latest

:: 等 1-2 分钟让 TB 启动完成
docker logs -f tb-ce
:: 看到 "Started ThingsBoardServerApplication in xxx seconds" 就好了
```

浏览器打开 `http://localhost:9090`，默认登录：
- 租户管理员: `tenant@thingsboard.org` / `tenant`
- 系统管理员: `sysadmin@thingsboard.org` / `sysadmin`

### 2. 在 TB 上创建测试 device + 拿 access token

1. 用租户账号登录 (`tenant@thingsboard.org`)
2. 左侧菜单 **Devices** → **+** → New device
3. Name: `unilab-gateway-test-001`
4. Device profile: `default`
5. 创建成功后，点这台 device → **Details** → **Copy access token**
6. 把 token 记下来，填进 §3 的配置文件

### 3. 网关侧部署

#### 3.1 装依赖

dev 机推一下 requirements.txt 改动到 OPi：

```bash
# OPi 上
cd ~/code/Uni-Lab-OS
source .venv/bin/activate
uv pip install aiomqtt
```

#### 3.2 创建 `/etc/unilab-ota-agent.env`

```bash
sudo cp ~/code/Uni-Lab-OS/unilabos/gateway/ota/unilab-ota-agent.env.example /etc/unilab-ota-agent.env
sudo nano /etc/unilab-ota-agent.env
```

填上 TB host (dev 机的局域网 IP, 例如 `10.20.31.99`) + access token。

```bash
sudo chmod 600 /etc/unilab-ota-agent.env
```

#### 3.3 确保 /data/ota/download 目录存在且 orangepi 可写

```bash
sudo mkdir -p /data/ota/download /data/ota/log
sudo chown -R orangepi:orangepi /data/ota
```

> 注意：D2 阶段 Agent 跑在 orangepi 用户，不动系统。D3 阶段加 ota write 时再切到 root。

#### 3.4 装 systemd unit

```bash
sudo install -m 644 \
    ~/code/Uni-Lab-OS/unilabos/gateway/ota/unilab-ota-agent.service \
    /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now unilab-ota-agent
sudo systemctl status unilab-ota-agent --no-pager
journalctl -u unilab-ota-agent -f
```

---

## 验证 D2 闭环（端到端 PoC）

### 1. Agent 启动后

```
[OTA] 启动 OTA Agent
[OTA] 配置: TB=10.20.31.99:1883 device_token=ABC*** chunk_size=524288
[OTA] 已加载 state.json，状态: IDLE
[OTA] 连接 TB MQTT...
[OTA] 已连接
[OTA] 上报当前固件: title=uni-lab-gateway version=1.0.0 state=UPDATED
[OTA] 订阅 attribute 推送中
[OTA] 等待 TB 推送 firmware...
```

### 2. dev 机制造一个 fake firmware

```cmd
:: 5 MB 随机数据当假固件
python -c "import os; open('fake-firmware-v1.0.1.bin','wb').write(os.urandom(5*1024*1024))"

:: 算 sha256
python -c "import hashlib; print(hashlib.sha256(open('fake-firmware-v1.0.1.bin','rb').read()).hexdigest())"
```

### 3. TB UI 上传 firmware + 分配给 device

1. 左菜单 **Resources** → **Otaupdates** → **+**
2. Title: `uni-lab-gateway`, Version: `1.0.1`, Type: `Firmware`, Device profile: `default`
3. 上传 `fake-firmware-v1.0.1.bin`
4. 回到 device `unilab-gateway-test-001` → **Details** → **Assigned firmware** → 选 `uni-lab-gateway 1.0.1`

### 4. 看 Agent 日志

```
[OTA] 收到 attribute 推送: fw_title=uni-lab-gateway fw_version=1.0.1 fw_size=5242880 fw_checksum=abc123... fw_checksum_algorithm=SHA256
[OTA] 计算分块: chunk_size=524288 total_chunks=10
[OTA] 状态: DOWNLOADING
[OTA] 已上报 fw_state=DOWNLOADING
[OTA] chunk 0/10 (524288 bytes) ok
[OTA] chunk 1/10 (524288 bytes) ok
...
[OTA] chunk 9/10 (524288 bytes) ok
[OTA] 已上报 fw_state=DOWNLOADED
[OTA] sha256 校验: 算出 abc123... 期望 abc123... ✓
[OTA] 状态: VERIFIED
[OTA] 已上报 fw_state=VERIFIED
[OTA] D2 阶段结束（不调 ota CLI，请人工 ota write 验证）
```

### 5. TB UI 看 telemetry

device → **Latest Telemetry** 里应该能看到 `fw_state=VERIFIED` 等字段。

### 6. 文件落盘检查

```bash
ls -lh /data/ota/download/
# 期望：fake-firmware-v1.0.1.bin  5.0M
sha256sum /data/ota/download/fake-firmware-v1.0.1.bin
# 期望：和 TB 上的 fw_checksum 一致
```

✅ **D2 验收通过**。

---

## 状态机

```
        ┌─────────┐
        │  IDLE   │ ←─────────────────────────┐
        └────┬────┘                            │
   收 attrs  │                                  │
        ┌────▼──────────┐                       │
        │ DOWNLOADING   │── chunk 失败 ──┐       │
        │ (received/total)               │      │
        └────┬──────────┘                │      │
   全部 ok   │                            ▼      │
        ┌────▼──────────┐          ┌────────┐  │
        │ DOWNLOADED    │          │ FAILED │──┘
        └────┬──────────┘          └────────┘
   sha256 ✓ │                          ▲
        ┌───▼──────────┐  sha256 ✗      │
        │  VERIFIED    │────────────────┘
        └──────────────┘
              ┃
              ┃ D2 终止于此
              ▼
     D3: WRITING → SWITCHING → REBOOTING → PENDING_HEALTHCHECK
                                            ↙             ↘
                                       COMMIT_OK         ROLLBACK
```

---

## 配置文件字段

`/etc/unilab-ota-agent.env`：

| 字段 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `TB_HOST` | ✓ | - | TB MQTT 服务器（IP 或域名） |
| `TB_PORT` | | `1883` | TB MQTT 端口 |
| `TB_TOKEN` | ✓ | - | device access token（TB UI 里复制） |
| `TB_QOS` | | `1` | MQTT QoS 等级，建议 1 |
| `CURRENT_FW_TITLE` | ✓ | - | 当前固件标题（必须和 TB 上传的 title 一致） |
| `CURRENT_FW_VERSION` | ✓ | - | 当前固件版本（启动时上报，TB 用这个判断是否要推） |
| `DOWNLOAD_DIR` | | `/data/ota/download` | chunk 拼装位置 |
| `STATE_FILE` | | `/data/ota/agent_state.json` | Agent 状态持久化文件 |
| `CHUNK_SIZE` | | `8192` (8KB) | 单次 chunk 字节数；**必须 ≤ TB broker max packet size**（TB Cloud 上限 65535），超过会被 disconnect |
| `CHUNK_TIMEOUT` | | `30` | 等单个 chunk 响应的秒数 |
| `CHUNK_RETRY` | | `3` | 单 chunk 失败重试次数 |
| `LOG_LEVEL` | | `INFO` | DEBUG / INFO / WARN / ERROR |

---

## 故障处理

| 现象 | 排查 |
|---|---|
| Agent 起不来 `Connection refused` | dev 机 docker 容器没起来；用 `docker ps` 看；防火墙挡 1883 端口 |
| Agent 起来但 TB UI 显示 device offline | TB_TOKEN 错；或 `last_connect_time` 没更新——查 Agent 日志 MQTT 是否真的连上 |
| TB 推 firmware 后 Agent 没反应 | 1) device profile 没绑定固件；2) device 已经报告 `current_fw_version == 推送的 version`（TB 不会重复推） |
| chunk 下载卡住 / `MqttCodeError: client is not currently connected` | `CHUNK_SIZE` 超过 broker max packet size，TB Cloud 限制 65535 (64KB)。改 `CHUNK_SIZE=8192` 重启 Agent |
| sha256 不匹配 | chunk 顺序错乱 / 缺 chunk。重启 Agent 重新下载（state.json 会清除 ongoing） |
| Agent 重启后从头下载 | state.json 没正确写入；查 `/data/ota/agent_state.json` 是否存在 + 是否能写 |

---

## D2 之后（D3+ 路线）

### D3：接通 ota CLI（动系统）

- Agent User 改为 `root`（systemd unit）
- VERIFIED 后调 `sudo ota write <下载文件>`、`sudo ota verify <sha256>`
- 写 `/data/ota/pending.flag = {target: B, try: 1, timestamp: ...}`
- `sudo ota switch B` + `sudo reboot`

### D4：自检 watchdog + 自动回滚

- 系统起来后 Agent 第一件事检查 `/data/ota/pending.flag`
- 启动 watchdog 等 `systemctl is-active unilab-gateway` 持续 N=300 秒（5 分钟）
- 通过 → 上报 `fw_state=UPDATED`，删 pending.flag
- 失败 → `sudo ota rollback + sudo reboot`，起来后上报 `fw_state=FAILED + fw_error=...`

### D5：u-boot 端 watchdog（最后一道保险）

- u-boot 启动时读 `bootlimit` 环境变量，超过 N 次启动失败自动 `ota switch <对面>`
- 进一步降低 brick 风险

---

**文档版本**：v0.1 (D2 设计稿)
**最后更新**：2026-06-22
**对应仓库版本**：D2 阶段（OTA Agent 最小闭环）

---

## 附录：母机出厂配置（D3.B symlink 部署，一次性手册）

> **场景**：你要做一台"母机" OPi，配好后用 `dd` 镜像复制给量产机。本章节描述如何把 OPi 从"代码直接跑在 `~/code/Uni-Lab-OS`"的旧布局，改造成支持 OTA 软件升级的 symlink 布局。
>
> **谁要看这个**：第一次配置母机、或者远程改造已部署的旧 OPi。
>
> **量产机不用看**：量产机用 `dd` 直接克隆母机 SD 卡，结构已经就位，不用跑下面的步骤。
>
> **历史背景**：早期有过一个 `migrate-to-symlink.sh` 脚本干这事，因为强制覆盖 systemd unit 等"破坏现状"的行为踩过坑，已删除。改用手册形式，每一步你自己 review 后再敲。

### 0. 目标布局

```
/opt/unilab/
├── versions/0.0.0/                  ← rsync 自 ~/code/Uni-Lab-OS
├── current → versions/0.0.0         ← OTA 切版本的"开关"
└── venv/                            ← Python 环境共享
/etc/systemd/system/
├── unilab-gateway.service           ← 见仓库同名文件
└── unilab-ota-agent.service         ← 见仓库同名文件
/etc/
├── unilab-gateway.env               ← 工厂刷入，含 WS_URL / AK / SK / MOUNT_UUID 等
└── unilab-ota-agent.env             ← 工厂刷入，含 TB_HOST / TB_TOKEN 等
/data/ota/
└── agent_state.json                 ← OTA Agent 初始状态文件
```

### 1. 停服务

```bash
sudo systemctl stop unilab-gateway unilab-ota-agent 2>/dev/null || true
```

### 2. 代码搬家

把 `~/code/Uni-Lab-OS` 拷到 `/opt/unilab/versions/0.0.0/`：

```bash
sudo mkdir -p /opt/unilab/versions
sudo rsync -a --delete \
    --exclude='/.venv' \
    --exclude='/__pycache__' \
    --exclude='*.pyc' \
    /home/orangepi/code/Uni-Lab-OS/ \
    /opt/unilab/versions/0.0.0/

# 让 root:dialout 拥有它（跟 service User/Group 对齐）
sudo chown -R root:dialout /opt/unilab/versions/0.0.0
```

### 3. 建立 current symlink

```bash
# .new + mv 保证原子性（虽然这是第一次建，原子性不关键，但形成习惯）
sudo ln -sfn /opt/unilab/versions/0.0.0 /opt/unilab/current.new
sudo mv -Tf /opt/unilab/current.new /opt/unilab/current

# 验证
ls -ld /opt/unilab/current
# lrwxrwxrwx ... /opt/unilab/current -> /opt/unilab/versions/0.0.0
```

### 4. 准备共享 venv

```bash
# 方案 A：从旧的 ~/code/Uni-Lab-OS/.venv 复制（快但风险高，pyvenv.cfg 路径会指错）
# 不推荐 —— 之前踩过坑，cp -a 的 venv 内部 home= 还指着系统 python，
# `import unilabos` 会因为找不到包路径出问题。

# 方案 B：重新创建（推荐，干净）
sudo python3 -m venv /opt/unilab/venv
sudo /opt/unilab/venv/bin/pip install --upgrade pip
sudo /opt/unilab/venv/bin/pip install -e /opt/unilab/current

# 验证
sudo /opt/unilab/venv/bin/python -c "import unilabos; print('OK', unilabos.__file__)"
# 期望：OK /opt/unilab/current/unilabos/__init__.py
```

### 5. 安装 systemd unit（小心，**先 review 不要直接覆盖现有的**）

**先 diff，确认仓库版本和现有版本（如果有）的差异**：

```bash
# 如果 OPi 上已经有这俩 service：
diff /etc/systemd/system/unilab-gateway.service \
     /opt/unilab/current/unilabos/gateway/ota/unilab-gateway.service

diff /etc/systemd/system/unilab-ota-agent.service \
     /opt/unilab/current/unilabos/gateway/ota/unilab-ota-agent.service
```

**diff 结果有差异**：手动用 `sed` 或 `nano` 调整必要字段（ExecStart 路径、WorkingDirectory），不要整体覆盖。
**diff 结果没差异 / 文件不存在**：直接复制：

```bash
sudo install -m 0644 \
    /opt/unilab/current/unilabos/gateway/ota/unilab-gateway.service \
    /etc/systemd/system/

sudo install -m 0644 \
    /opt/unilab/current/unilabos/gateway/ota/unilab-ota-agent.service \
    /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable unilab-gateway unilab-ota-agent
```

### 6. env 文件

如果 OPi 上已经有 `/etc/unilab-gateway.env` 和 `/etc/unilab-ota-agent.env`（工厂刷过），跳过本步。否则：

```bash
# 模板复制
sudo cp /opt/unilab/current/unilabos/gateway/ota/unilab-ota-agent.env.example \
        /etc/unilab-ota-agent.env
sudo chmod 600 /etc/unilab-ota-agent.env
sudo nano /etc/unilab-ota-agent.env   # 填 TB_HOST / TB_TOKEN

# unilab-gateway.env 暂时没有 .example 模板（TODO），找最近已部署的 OPi 抄一份。
```

### 7. 写初始 agent_state.json

```bash
sudo mkdir -p /data/ota
sudo tee /data/ota/agent_state.json > /dev/null <<'EOF'
{
  "current_fw": {
    "title": "unilab-gateway",
    "version": "0.0.0"
  },
  "ongoing": null,
  "current_software": {
    "title": "unilabos-app",
    "version": "0.0.0",
    "install_path": "/opt/unilab/versions/0.0.0",
    "activated_at": "2026-01-01T00:00:00+08:00",
    "manifest": null,
    "healthy": true
  },
  "ongoing_software": null
}
EOF
```

### 8. 启动 + 验证

```bash
sudo systemctl start unilab-gateway unilab-ota-agent
sleep 5

# 检查 service
sudo systemctl is-active unilab-gateway unilab-ota-agent

# 检查 80 端口（gateway 管理后台）
sudo ss -tlnp | grep ':80\b'

# 检查 ota-agent 连上 TB
sudo journalctl -u unilab-ota-agent -n 30 --no-pager
```

### 9. 完成后清理（量产前）

母机配好后，做镜像前**删掉本机特有的身份信息**，避免 N 台机器共用一个 TB token：

```bash
# 量产时再单独刷入这些文件
sudo rm /etc/unilab-ota-agent.env
sudo rm /etc/unilab-gateway.env
sudo rm /data/ota/agent_state.json
# /home/orangepi/.ssh/authorized_keys 之类的钥匙也清掉
```

然后才能：

```bash
# 做镜像
sudo dd if=/dev/mmcblk0 of=opi-master.img bs=4M status=progress
```

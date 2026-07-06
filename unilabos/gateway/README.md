# Uni-Lab IoT 网关 (极简版)

不依赖 ROS 2、不依赖 HostNode 的轻量边缘进程，对应文档
《Uni-Lab-OS 设备即节点——架构设计与分阶段实施计划》第 §6.1 / §7 Phase 0。

## 设计目标

- 单进程 asyncio，资源占用 < 50 MB
- 完整兼容现有 Schedule Server WebSocket 协议（`{"action", "data"}` 格式）
- 任何 Python 驱动类（带 `@property` 和普通方法）都能直接接入
- 适用于香橙派 Zero 2W / RPi Zero 2W / x86 桌面机

## 架构

```
┌─────────────────────────────────────────────┐
│        unilabos.gateway.main                │
│                                             │
│  ┌──────────┐  ┌──────────────┐             │
│  │ Device   │  │ DeviceWorker │ ─ telemetry │ ──► async send_fn ──┐
│  │ Driver   │◄─┤ (asyncio)    │ ─ action     │                    │
│  └──────────┘  └──────────────┘             │                    ▼
│                                             │       ┌────────────────────┐
│  YAML config → 实例化 → 包装                 │       │   GatewayClient    │
│                                             │       │   (websockets)      │
└─────────────────────────────────────────────┘       │  ─ 连接/重连/认证   │
                                                      │  ─ 上行队列        │
                                                      │  ─ 下行 dispatch   │
                                                      └─────────┬──────────┘
                                                                │
                                                  wss:// .../ws/schedule
                                                                ▼
                                                        Go Schedule Server
```

## 启动

### 1. 安装依赖

```bash
# 在 Uni-Lab-OS 仓库根下
source .venv/bin/activate
uv pip install pyyaml websockets
```

(`websockets` 通常之前已经装过；`pyyaml` 是新增依赖)

### 2. 准备配置文件

```bash
cp unilabos/gateway/config_example.yaml ~/gateway.yaml
# 按需修改，至少先保留 mock 设备
```

### 3. 提供 ak/sk

推荐用环境变量（不会进 git）：

```bash
export UNILABOS_BASICCONFIG_AK=your_ak
export UNILABOS_BASICCONFIG_SK=your_sk
```

或命令行参数：`--ak xxx --sk yyy`

### 4. 启动

```bash
python -m unilabos.gateway.main --config ~/gateway.yaml --log-level INFO
```

预期日志：

```
[INFO] gateway: [GW] 启动: machine_name=gw-zero2w-001 devices=1 ws=wss://uni-lab.bohrium.com/api/v1/ws/schedule reconnect_interval=5s
[INFO] gateway: [GW] 已加载设备 mock-temp-001 -> MOCK
[INFO] gateway: [DEV] mock-temp-001 启动 properties=['temperature', 'counter'] interval=2.0s
[INFO] gateway: [GW] 已连接 wss://uni-lab.bohrium.com/api/v1/ws/schedule session=a1b2c3
[INFO] gateway: [GW] host_node_ready: 上报 1 个设备
```

之后到 Bohrium 实验室页面应能看到 `mock-temp-001` 在线，温度值每 2 秒变化。

## 接入真实驱动

任意 `unilabos.devices` 下的驱动类都能接入，只要满足：

- `__init__(**kwargs)` 接受 YAML 里 `init:` 子字典作为关键字参数
- 想轮询的属性是 `@property` 或普通字段
- 想暴露的动作是普通方法（同步即可，会被 `run_in_executor` 包装）

示例（蠕动泵）：

```yaml
devices:
  - device_id: pump-001
    driver: unilabos.devices.pump_and_valve.peristaltic_pump.bt100_2j.driver.BT1002J
    init:
      port: /dev/ttyUSB0
      baudrate: 9600
      slave_id: 1
    properties: [speed, direction, status]
    poll_interval: 1.0
```

如果驱动 `__init__` 阻塞或失败（比如串口被占），网关启动时会直接抛错并退出，
日志里会有 `[GW] 实例化驱动 ... 失败: <原因>` 的提示。

## 协议覆盖度（vs §3.2）

### 已实现

| 方向 | action | 说明 |
|---|---|---|
| 上行 | `host_node_ready` | 连接/重连后注册设备清单 |
| 上行 | `device_status` | 属性值变化（或周期）上报 |
| 上行 | `job_status` | running / success / failed |
| 上行 | `report_action_state` | 简化为统一回 free=true |
| 上行 | `pong` | 自动应答 ping |
| 下行 | `ping` | 客户端内部处理 |
| 下行 | `job_start` | 调度到 DeviceWorker.execute_action |
| 下行 | `query_action_state` | 简化版，无严格状态机 |

### 暂未实现（按需补）

| 方向 | action | 触发场景 |
|---|---|---|
| 上行 | `telemetry_batch` | 高频遥测（>10Hz）批量上报 |
| 上行 | `normal_exit` | 优雅关闭 |
| 下行 | `cancel_action` / `cancel_task` | 取消正在执行的任务 |
| 下行 | `add_device` / `remove_device` | 热插拔 |
| 下行 | `add/update/remove_material` | 资源树同步 |
| 下行 | `gateway_config` | 远程改 poll_interval / telemetry_fields |

## 已知限制

1. **DeviceWorker 不并发执行同设备的多个 action** — 当前 `execute_action` 是顺序的，
   如果云端在一个动作没结束时又发了下一个 `job_start`，会等前一个完成后才执行第二个。
2. **属性轮询失败不退避** — 失败立即重试，不做指数退避，会刷日志。
3. **不持久化** — 网关进程重启后历史不保留，需要 Schedule Server 侧的时序存储。

这些限制会在文档 Phase 1 的 Simple Backend 实现中收口。

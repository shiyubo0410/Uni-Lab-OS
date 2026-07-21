# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Also follow the monorepo-level rules in `../AGENTS.md`.

## Build & Development

```bash
# Install in editable mode (requires mamba env with python 3.11)
pip install -e .
uv pip install -r unilabos/utils/requirements.txt

# Run with a device graph
unilab --graph <graph.json> --config <config.py> --backend ros
unilab --graph <graph.json> --config <config.py> --backend simple  # no ROS2 needed

# Common CLI flags
unilab --app_bridges websocket fastapi    # communication bridges
unilab --test_mode                        # simulate hardware, no real execution
unilab --check_mode                       # CI validation of registry imports
unilab --skip_env_check                   # skip auto-install of dependencies
unilab --visual rviz|web|disable          # visualization mode
unilab --is_slave                         # run as slave node

# Workflow upload subcommand
unilab workflow_upload -f <workflow.json> -n <name> --tags tag1 tag2

# Tests
pytest tests/                              # all tests
pytest tests/resources/test_resourcetreeset.py  # single test file
pytest tests/resources/test_resourcetreeset.py::TestClassName::test_method  # single test
```

## Architecture

### Startup Flow

`unilab` CLI → `unilabos/app/main.py:main()` → loads config → builds registry → reads device graph (JSON/GraphML) → starts backend thread (ROS2/simple) → starts FastAPI web server + WebSocket client.

### Core Layers

**Registry** (`unilabos/registry/`): Singleton `Registry` class discovers and catalogs all device types, resource types, and communication devices from YAML definitions. Device types live in `registry/devices/*.yaml`, resources in `registry/resources/`, comms in `registry/device_comms/`. The registry resolves class paths to actual Python classes via `utils/import_manager.py`.

**Resource Tracking** (`unilabos/resources/resource_tracker.py`): Pydantic-based `ResourceDict` → `ResourceDictInstance` → `ResourceTreeSet` hierarchy. `ResourceTreeSet` is the canonical in-memory representation of all devices and resources, used throughout the system. Graph I/O is in `resources/graphio.py` (reads JSON/GraphML device topology files into `nx.Graph` + `ResourceTreeSet`).

**Device Drivers** (`unilabos/devices/`): 30+ hardware drivers organized by device type (liquid_handling, hplc, balance, arm, etc.). Each driver is a Python class that gets wrapped by `ros/device_node_wrapper.py:ros2_device_node()` to become a ROS2 node with publishers, subscribers, and action servers.

**ROS2 Layer** (`unilabos/ros/`): `device_node_wrapper.py` dynamically wraps any device class into `ROS2DeviceNode` (defined in `ros/nodes/base_device_node.py`). Preset node types in `ros/nodes/presets/` include `host_node`, `controller_node`, `workstation`, `serial_node`, `camera`. Messages use custom `unilabos_msgs` (pre-built, distributed via releases).

**Protocol Compilation** (`unilabos/compile/`): 20+ protocol compilers (add, centrifuge, dissolve, filter, heatchill, stir, pump, etc.) that transform YAML protocol definitions into executable sequences.

**Communication** (`unilabos/device_comms/`): Hardware communication adapters — OPC-UA client, Modbus PLC, RPC, and a universal driver. `app/communication.py` provides a factory pattern for WebSocket client connections to the cloud.

**Web/API** (`unilabos/app/web/`): FastAPI server with REST API (`api.py`), Jinja2 template pages (`pages.py`), and HTTP client for cloud communication (`client.py`). Runs on port 8002 by default.

### Configuration System

- **Config classes** in `unilabos/config/config.py`: `BasicConfig`, `WSConfig`, `HTTPConfig`, `ROSConfig` — all class-level attributes, loaded from Python config files
- Config files are `.py` files with matching class names (see `config/example_config.py`)
- Environment variables override with prefix `UNILABOS_` (e.g., `UNILABOS_BASICCONFIG_PORT=9000`)
- Device topology defined in graph files (JSON with node-link format, or GraphML)

### Key Data Flow

1. Graph file → `graphio.read_node_link_json()` → `(nx.Graph, ResourceTreeSet, resource_links)`
2. `ResourceTreeSet` + `Registry` → `initialize_device.initialize_device_from_dict()` → `ROS2DeviceNode` instances
3. Device nodes communicate via ROS2 topics/actions or direct Python calls (simple backend)
4. Cloud sync via WebSocket (`app/ws_client.py`) and HTTP (`app/web/client.py`)

### Test Data

Example device graphs and experiment configs are in `unilabos/test/experiments/` (not `tests/`). Registry test fixtures in `unilabos/test/registry/`.

## Code Conventions

- Code comments and log messages in simplified Chinese
- Python 3.11+, type hints expected
- Pydantic models for data validation (`resource_tracker.py`)
- Singleton pattern via `@singleton` decorator (`utils/decorator.py`)
- Dynamic class loading via `utils/import_manager.py` — device classes resolved at runtime from registry YAML paths
- CLI argument dashes auto-converted to underscores for consistency

## 部署文件 / 远程主机改动规则（important）

修改任何**会被部署到远程主机**（OPi 网关、生产服务器等）的配置或脚本前 — 包括但不限于：

- `unilabos/gateway/ota/*.service` / `*.env*` / `*.sh`（systemd unit、env 模板、迁移脚本）
- `/etc/` 下任何文件、`/opt/unilab/` 下任何文件
- 工厂初始化脚本、镜像 provisioning 脚本

必须遵守以下流程：

1. **先拉现状**：SSH 到目标机器把现有版本拉下来对比，**禁止凭印象/记忆重写**。
   ```bash
   # 例：
   ssh orangepi@<ip> 'cat /etc/systemd/system/unilab-gateway.service' > /tmp/current.service
   diff /tmp/current.service unilabos/gateway/ota/unilab-gateway.service
   ```

2. **最小化 patch**：只改"必须改"的行（通常是路径、ExecStart、依赖项）。`User` / `Group` / `Restart*` / 端口绑定相关字段**默认保留现状**，要动必须先解释清楚为什么并问用户。

3. **覆盖类操作（`install -m`、`cp` 整体覆盖）需要事先确认**：和 `sed -i` 局部替换比，整体覆盖会丢失现场配置（手动改过的端口、内存限制、capabilities 等）。除非用户明确同意"我用一份新的覆盖掉"，否则用 sed/patch 做局部修改。

4. **改之前打印 diff 让用户 review**：在执行 `systemctl daemon-reload + restart` 之前，把"修改前 vs 修改后"的 diff 输出给用户看一眼。

5. **不要假设 root vs 非 root**：`unilabos/gateway/main.py` 等代码里有 `os.geteuid() == 0 ? port=80 : port=8080` 这种"看 euid 选行为"的逻辑，改 systemd `User` 会触发功能变化，**绝不能为了"安全感"擅自把 root 改成普通用户**。

6. **环境变量 `.env` 文件不进 git**：仓库里只允许 `.env.example`（占位符），真实 env 由工厂工具/手动刷入到 `/etc/`，仓库代码不要尝试覆盖它。

历史教训：D3.B OTA 阶段曾把 `unilab-gateway.service` 的 `User=root` 擅自改成 `User=orangepi`，导致代码自动降级到 8080 端口，破坏了用户裸 URL 访问 80 的体验。来回折腾多次才修回。

## Licensing

- Framework code: GPL-3.0
- Device drivers (`unilabos/devices/`): DP Technology Proprietary License — do not redistribute

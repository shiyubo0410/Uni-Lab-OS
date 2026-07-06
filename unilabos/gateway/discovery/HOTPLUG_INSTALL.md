# USB 热插拔安装指南

## 1. 安装 udev 规则

```bash
# 复制 udev 规则文件到系统目录
sudo cp unilabos/gateway/discovery/99-unilab-gateway.rules /etc/udev/rules.d/

# 重新加载 udev 规则
sudo udevadm control --reload-rules

# 触发已存在设备的规则（可选，测试用）
sudo udevadm trigger
```

## 2. 验证 udev 规则

```bash
# 查看规则是否生效
udevadm control --reload-rules && udevadm trigger

# 监听 udev 事件（插拔 USB 串口时会看到输出）
sudo udevadm monitor --environment --udev
```

## 3. 测试热插拔

### 3.1 启动 gateway（不插设备）

```bash
# 启动时不插任何设备
python -m unilabos.gateway.main --config gateway.yaml --auto-discover --log-level DEBUG
```

应该看到：
```
[GW] 自动发现 0 个设备
[HOTPLUG] 监听目录: /tmp/unilab-gateway/hotplug
```

### 3.2 插入 USB 串口设备

插入设备后，udev 会自动调用 `hotplug_handler.py`，你会看到：

```
[HOTPLUG] 检测到 USB 串口插入: /dev/ttyUSB0
[PROBE] /dev/ttyUSB0 匹配指纹: runze_sy03b
[HOTPLUG] 已写入信号文件: /tmp/unilab-gateway/hotplug/runzesyringepump-auto-3f4b.json
```

然后 gateway 主循环会检测到信号文件：

```
[HOTPLUG] 加载新设备: runzesyringepump-auto-3f4b
[GW] 已加载设备 runzesyringepump-auto-3f4b -> unilabos.devices.pump_and_valve.runze_backbone.RunzeSyringePump
[HOTPLUG] ✓ 设备 runzesyringepump-auto-3f4b 已上线
```

### 3.3 查看信号文件（调试用）

```bash
# 查看信号文件内容
cat /tmp/unilab-gateway/hotplug/*.json

# 清空信号文件（如果需要重新测试）
rm -f /tmp/unilab-gateway/hotplug/*.json
```

## 4. 手动测试 hotplug_handler

不依赖 udev，直接调用 handler 测试：

```bash
# 确保设备已插入
ls /dev/ttyUSB*

# 手动调用 handler
python -m unilabos.gateway.discovery.hotplug_handler /dev/ttyUSB0

# 检查信号文件是否生成
ls -lh /tmp/unilab-gateway/hotplug/
```

## 5. 常见问题

### Q: udev 规则不生效？

```bash
# 检查规则文件语法
sudo udevadm test $(udevadm info -q path -n /dev/ttyUSB0) 2>&1 | grep unilab

# 查看 udev 日志
sudo journalctl -u systemd-udevd -f
```

### Q: hotplug_handler 找不到模块？

确保 Python 环境正确：

```bash
# 检查 Python 路径
which python3

# 如果使用 conda/mamba 环境，修改 udev 规则中的 Python 路径
# 例如：/home/user/mambaforge/envs/unilab/bin/python3
```

### Q: 权限问题？

udev 规则以 root 身份运行，确保：

```bash
# hotplug_handler 可以被 root 执行
sudo python3 -m unilabos.gateway.discovery.hotplug_handler /dev/ttyUSB0

# /tmp/unilab-gateway/hotplug/ 目录权限正确
sudo chmod 777 /tmp/unilab-gateway/hotplug/
```

## 6. 卸载

```bash
# 删除 udev 规则
sudo rm /etc/udev/rules.d/99-unilab-gateway.rules
sudo udevadm control --reload-rules

# 清理信号文件目录
rm -rf /tmp/unilab-gateway/hotplug/
```

## 7. 工作原理

```
USB 插入
  ↓
udev 检测到事件
  ↓
触发 99-unilab-gateway.rules
  ↓
调用 hotplug_handler.py /dev/ttyUSB0
  ↓
探测设备指纹
  ↓
写入信号文件 /tmp/unilab-gateway/hotplug/{device_id}.json
  ↓
gateway 主循环每 2 秒扫描信号目录
  ↓
发现新文件 → 加载设备 → 启动 worker → 通知云端
  ↓
删除信号文件
```

## 8. 支持的 USB 串口芯片

- FTDI FT232 (idVendor=0403, idProduct=6001)
- CH340/CH341 (idVendor=1a86, idProduct=7523)
- CP210x (idVendor=10c4, idProduct=ea60)
- USB CDC ACM 设备（Arduino 等）
- 所有 ttyUSB* 和 ttyACM* 设备（兜底规则）

如需支持其他芯片，编辑 `99-unilab-gateway.rules` 添加对应的 idVendor/idProduct。

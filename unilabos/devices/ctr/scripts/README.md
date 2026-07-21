# 旋涂仪控制工具包

## 文件说明

- `spin_coater_controller.py` - 旋涂仪控制器主类
- `example_usage.py` - 使用示例

## 快速开始

### 1. 基本连接

```python
from scripts.spin_coater_controller import SpinCoaterController

controller = SpinCoaterController(port='COM1', baudrate=19200, station=1)
controller.connect()
```

### 2. 设备控制

```python
# 使能设备
controller.enable()

# 开启真空
controller.vacuum_on()

# 手动回原
controller.manual_home()
```

### 3. 单步运行

```python
# 设置单步参数
controller.set_single_step_speed(5000)  # 速度: 10-10000
controller.set_single_step_time(2000)    # 时间: 0-3000ms
controller.set_single_step_acceleration(5000)  # 加速度: 200-30000

# 启动单步运行
controller.single_step_start_stop()

# 查询运行状态
status = controller.single_step_running_status()
```

### 4. 多步运行

```python
# 设置多步参数（步骤1-100）
controller.set_multi_step_speed(1, 3000)
controller.set_multi_step_time(1, 1500)
controller.set_multi_step_acceleration(1, 4000)

# 启动多步运行
controller.multi_step_start_stop()

# 查询当前步骤
step = controller.get_multi_step_current_step()
```

### 5. 对中控制

```python
controller.set_alignment_speed(300)  # 速度: 100-500
controller.set_alignment_time(50)    # 时间: 1-100ms
```

### 6. 摆动控制

```python
controller.set_oscillation_speed(400)        # 速度: 10-800
controller.set_oscillation_acceleration(500) # 加速度: 10-2000
controller.set_oscillation_time(30)          # 时间: 1-100ms
controller.set_oscillation_count(5)           # 次数: 1-20
```

### 7. 状态查询

```python
# 使能状态
enable_status = controller.enable_status()

# 真空状态
vacuum_status = controller.vacuum_status()

# 真空显示值
vacuum_value = controller.vacuum_display()

# 运行速度
speed = controller.get_run_speed()

# 运行时间
time = controller.get_run_time()

# 多步总运行时间
total_time = controller.get_multi_step_total_time()
```

### 8. 页面控制

```python
# 切换到单步运行画面
controller.set_page(0x0003)

# 切换到多步运行画面
controller.set_page(0x001B)

# 获取当前页面
page = controller.get_current_page()
```

## 参数范围

### 单步参数
- 速度: 10-10000
- 时间: 0-3000ms
- 加速度: 200-30000

### 多步参数
- 步骤号: 1-100
- 速度: 0-10000
- 时间: 0-3000ms
- 加速度: 200-30000

### 对中参数
- 速度: 100-500
- 时间: 1-100ms

### 摆动参数
- 速度: 10-800
- 加速度: 10-2000
- 时间: 1-100ms
- 次数: 1-20

### 其他参数
- 减速度: 100-2500
- 真空保护值: 10-50

## 串口参数

- 协议: RS232
- 站号: 1
- 波特率: 19200
- 校验方式: EVEN
- 数据位: 8位
- 停止位: 1位

## 运行示例

```bash
python scripts/example_usage.py
```

选择示例类型:
1. 完整功能演示
2. 简单真空控制
3. 自定义旋涂流程

## 注意事项

1. 使用前确保串口参数正确
2. 写线圈命令需要发送一对命令（置位+复位）
3. 参数值必须在允许范围内
4. 使用完毕后记得断开连接

## 完整示例

```python
from scripts.spin_coater_controller import SpinCoaterController
import time

controller = SpinCoaterController(port='COM1', baudrate=19200, station=1)

if controller.connect():
    try:
        # 使能设备
        controller.enable()
        
        # 开启真空
        controller.vacuum_on()
        
        # 设置参数
        controller.set_single_step_speed(5000)
        controller.set_single_step_time(2000)
        
        # 开始运行
        controller.single_step_start_stop()
        
        # 等待完成
        while controller.single_step_running_status():
            time.sleep(1)
            print("运行中...")
        
        print("完成!")
        
    finally:
        controller.disconnect()
```

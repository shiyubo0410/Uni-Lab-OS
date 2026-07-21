# PGEA夹爪控制库 - 快速入门

## 安装

### 1. 安装依赖

```bash
pip install pyserial
```

### 2. 使用库

将 `pgea_gripper_skill` 文件夹复制到您的项目目录。

## 最简示例

```python
from pgea_gripper_skill import PGEAGripper
import time

# 1. 连接夹爪
gripper = PGEAGripper(port='/dev/ttyUSB0')  # Linux
# gripper = PGEAGripper(port='COM3')        # Windows
gripper.connect()

# 2. 初始化（首次使用必须）
if not gripper.is_initialized():
    gripper.initialize()

# 3. 设置参数
gripper.set_force(50)   # 力值 20-100%
gripper.set_speed(30)   # 速度 1-100%

# 4. 运动到指定位置
gripper.move_to(500)    # 位置 0-1000‰

# 5. 等待到位
gripper.wait_for_complete()

# 6. 断开连接
gripper.disconnect()
```

## 夹持物体

```python
from pgea_gripper_skill import PGEAGripper

gripper = PGEAGripper(port='/dev/ttyUSB0')
gripper.connect()
gripper.initialize()

# 张开
gripper.release(position=1000, speed=50)

# 夹持
gripped = gripper.grip(force=60, speed=30, wait=True)
if gripped:
    print("夹住物体了!")
else:
    print("没有夹到物体")

gripper.disconnect()
```

## 取放操作

```python
from pgea_gripper_skill import PGEAGripper

gripper = PGEAGripper(port='/dev/ttyUSB0')
gripper.connect()
gripper.initialize()

# 取物
success = gripper.pick(
    pick_position=200,    # 取物位置
    force=50,             # 夹持力
    speed=30,             # 速度
    lift_position=500,    # 提升位置
    wait_grip=True
)

if success:
    # 放物
    gripper.place(
        place_position=300,   # 放置位置
        speed=30,
        release_position=800  # 释放后位置
    )

gripper.disconnect()
```

## 使用上下文管理器

```python
from pgea_gripper_skill import PGEAGripper

# 自动管理连接
with PGEAGripper(port='/dev/ttyUSB0') as gripper:
    gripper.initialize()
    gripper.set_force(50)
    gripper.set_speed(30)
    gripper.move_to(500)
    gripper.wait_for_complete()
# 自动断开连接
```

## 状态监控

```python
from pgea_gripper_skill import PGEAGripper

gripper = PGEAGripper(port='/dev/ttyUSB0')
gripper.connect()
gripper.initialize()

# 获取完整状态
status = gripper.get_full_status()
print(f"位置: {status.position}‰")
print(f"夹持状态: {status.grip_status}")
print(f"电机温度: {status.motor_temp}°C")

# 检查错误
if status.has_error:
    print(f"错误: {status.get_error_description()}")

gripper.disconnect()
```

## 错误处理

```python
from pgea_gripper_skill import PGEAGripper

gripper = PGEAGripper(port='/dev/ttyUSB0')
gripper.connect()

# 检查错误
error = gripper.check_error()
if error:
    print(f"检测到错误: {error}")
    gripper.clear_error()
    time.sleep(0.5)

gripper.disconnect()
```

## 关键参数范围

| 参数 | 范围 | 说明 |
|------|------|------|
| 力值 | 20-100 (%) | 百分比 |
| 速度 | 1-100 (%) | 百分比 |
| 位置 | 0-1000 (‰) | 千分比 |

## 夹持状态

| 值 | 含义 |
|----|------|
| 0 | 运动中 |
| 1 | 到位(未夹到物体) |
| 2 | 已夹住物体 |
| 3 | 物体掉落 |

## 硬件接线

```
夹爪线缆        连接设备
--------        --------
绿色(485_A)  -> RS485+ / T/R+
橙色(485_B)  -> RS485- / T/R-
红色(24V)    -> 24V DC+
蓝色(GND)    -> 24V DC-
```

## 更多信息

- 完整文档: `README.md`
- AI技能说明: `SKILL.md`
- 使用示例: `examples.py`
- 文件结构: `STRUCTURE.md`

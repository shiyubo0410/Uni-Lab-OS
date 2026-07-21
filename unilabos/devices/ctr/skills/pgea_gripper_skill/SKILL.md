# PGEA夹爪控制 - AI技能说明

## 概述

这是大寰(DH-Robotics) PGEA系列驱控一体式工业平行电爪的Python控制库。

**适用型号**: PGEA-15-26, PGEA-15-40, PGEA-50-26, PGEA-50-40, PGEA-100-26, PGEA-100-40

**通信协议**: Modbus-RTU over RS485

**默认配置**: 115200波特率, 8数据位, 1停止位, 无校验, 从站ID=1

---

## 快速使用指南

### 1. 基本流程

```python
from pgea_gripper_skill import PGEAGripper

# 1. 创建实例并连接
gripper = PGEAGripper(port='/dev/ttyUSB0')  # 根据实际修改串口
gripper.connect()

# 2. 初始化（首次使用必须）
if not gripper.is_initialized():
    gripper.initialize()

# 3. 设置参数
gripper.set_force(50)   # 20-100%
gripper.set_speed(30)   # 1-100%

# 4. 运动控制
gripper.move_to(500)    # 0-1000‰
gripper.wait_for_complete()

# 5. 断开连接
gripper.disconnect()
```

### 2. 使用上下文管理器（推荐）

```python
from pgea_gripper_skill import PGEAGripper

with PGEAGripper(port='/dev/ttyUSB0') as gripper:
    gripper.initialize()
    gripper.set_force(50)
    gripper.set_speed(30)
    gripper.move_to(500)
    gripper.wait_for_complete()
# 自动断开连接
```

---

## 核心API速查

### 连接与初始化

| 方法 | 说明 | 参数 |
|------|------|------|
| `connect()` | 连接夹爪 | - |
| `disconnect()` | 断开连接 | - |
| `initialize(full=False)` | 初始化夹爪 | `full`: 是否完全标定 |
| `is_initialized()` | 检查是否已初始化 | - |

### 运动控制

| 方法 | 说明 | 参数范围 |
|------|------|----------|
| `set_force(force)` | 设置力值 | 20-100 (%) |
| `set_speed(speed)` | 设置速度 | 1-100 (%) |
| `move_to(pos)` | 运动到指定位置 | 0-1000 (‰) |
| `grip(...)` | 夹持动作 | 运动到0位置 |
| `release(...)` | 释放动作 | 运动到最大位置 |
| `jog(dir)` | 点动控制 | -1/0/1 |
| `stop()` | 停止运动 | - |

### 等待功能

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `wait_for_complete(timeout=10)` | 等待运动完成 | 最终状态码 |
| `wait_for_gripped(timeout=10)` | 等待夹住物体 | bool |

### 状态读取

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `get_full_status()` | 获取完整状态 | GripperStatus对象 |
| `get_current_position()` | 当前位置 | 0-1000 |
| `get_grip_status()` | 夹持状态 | 0-3 |
| `get_error_code()` | 错误码 | 0=无错误 |
| `get_motor_temperature()` | 电机温度 | ℃ |

### 夹持状态码

| 值 | 含义 |
|----|------|
| 0 | 运动中 |
| 1 | 到位(未夹到物体) |
| 2 | 已夹住物体 |
| 3 | 物体掉落 |

---

## 常见任务模板

### 任务1: 简单夹持物体

```python
def grip_object(gripper, force=50):
    """夹持物体"""
    # 张开
    gripper.release(position=1000, speed=50)
    time.sleep(0.5)
    
    # 夹持
    gripper.set_force(force)
    gripper.move_to(0)  # 运动到闭合位置
    
    # 等待夹住
    success = gripper.wait_for_gripped(timeout=5.0)
    return success
```

### 任务2: 取放操作

```python
def pick_and_place(gripper, pick_pos, place_pos, force=50):
    """取放操作"""
    # 取物
    gripper.set_speed(30)
    gripper.move_to(pick_pos)
    gripper.wait_for_complete()
    
    gripper.set_force(force)
    gripper.grip(wait=True)
    
    # 提升
    gripper.move_to(500)
    gripper.wait_for_complete()
    
    # 移动到放置位置
    gripper.move_to(place_pos)
    gripper.wait_for_complete()
    
    # 释放
    gripper.release(position=800, wait=True)
```

### 任务3: 循环夹持测试

```python
def cyclic_test(gripper, cycles=10):
    """循环夹持测试"""
    gripper.set_force(40)
    gripper.set_speed(50)
    
    for i in range(cycles):
        # 张开
        gripper.move_to(800)
        gripper.wait_for_complete()
        time.sleep(0.5)
        
        # 夹持
        gripper.move_to(100)
        gripper.wait_for_complete()
        time.sleep(1)
        
        # 检查是否夹住
        status = gripper.get_grip_status()
        if status == 2:
            print(f"第{i+1}次: 夹持成功")
        else:
            print(f"第{i+1}次: 未夹住物体")
```

### 任务4: 错误处理

```python
def safe_operation(gripper, operation):
    """带错误保护的操作"""
    try:
        # 检查错误
        error = gripper.check_error()
        if error:
            print(f"检测到错误: {error}")
            gripper.clear_error()
            time.sleep(0.5)
        
        # 执行操作
        return operation()
        
    except Exception as e:
        print(f"操作失败: {e}")
        return False
```

---

## 状态监控

### GripperStatus对象属性

```python
status = gripper.get_full_status()

# 基本属性
status.initialized      # bool: 是否已初始化
status.grip_status      # int:  夹持状态 (0-3)
status.position         # int:  当前位置 (0-1000)
status.speed            # int:  当前速度
status.current          # int:  当前电流
status.error_code       # int:  错误码
status.motor_temp       # int:  电机温度

# 便捷属性
status.is_moving        # bool: 是否正在运动
status.is_gripped       # bool: 是否已夹住物体
status.is_dropped       # bool: 物体是否掉落
status.in_position      # bool: 是否已到位
status.has_error        # bool: 是否有错误

# 方法
status.get_error_description()  # str: 获取错误描述
```

---

## 错误处理

### 错误码对照表

| 码 | 名称 | 处理建议 |
|----|------|----------|
| 0 | 无错误 | - |
| 1 | 欠压 | 检查电源电压(需>15V) |
| 2 | 过压 | 检查电源电压(需<28V) |
| 3 | 过流 | 减小负载或降低力值 |
| 4 | 过热 | 等待冷却，降低负载 |
| 5 | 电机缺相 | 检查电机接线 |
| 8 | 过载 | 减小夹持力 |
| 11 | 过速 | 降低速度设置 |
| 32 | 编码器异常 | 检查编码器连接 |
| 35 | 驱动IC异常 | 重启设备 |
| 36 | Flash异常 | 重启设备 |

### 错误处理流程

```python
# 1. 检查错误
error_code = gripper.get_error_code()
if error_code != 0:
    # 2. 获取错误描述
    description = ERROR_DESCRIPTIONS.get(error_code, "未知错误")
    print(f"错误: {description}")
    
    # 3. 尝试清除
    gripper.clear_error()
    time.sleep(0.5)
    
    # 4. 检查是否清除成功
    if gripper.get_error_code() != 0:
        print("错误无法清除，需要重启")
```

---

## 参数配置

### 常用配置

```python
# 设置初始化方向
gripper.set_init_direction(0)  # 0=张开归零, 1=闭合归零

# 设置上电自动初始化
gripper.set_auto_init(enable=True, full=False)

# 保存参数（修改后必须保存）
gripper.save_parameters()  # 耗时1-2秒
```

### IO参数配置

```python
# 配置4组IO参数
gripper.set_io_parameters(
    group=1, position=1000, force=50, speed=50  # 张开
)
gripper.set_io_parameters(
    group=2, position=500, force=60, speed=30   # 半闭合
)
gripper.set_io_parameters(
    group=3, position=0, force=80, speed=20     # 夹持
)
gripper.set_io_parameters(
    group=4, position=200, force=40, speed=40   # 微张
)

# 测试IO组
gripper.test_io_group(2)  # 执行第2组参数

# 开启IO模式
gripper.set_io_mode(True)

# 保存参数
gripper.save_parameters()
```

---

## 注意事项

1. **初始化是必须的**: 首次使用或更换指尖后必须执行 `initialize()`

2. **初始化方向**:
   - 默认张开方向归零
   - 可通过 `set_init_direction()` 修改

3. **力值范围**: 20-100%，低于20%可能不稳定

4. **位置单位**: 千分比(0-1000)，对应0-100%行程

5. **保存参数**: 修改参数后需调用 `save_parameters()`

6. **错误处理**: 先尝试 `clear_error()`，无法清除则重启

7. **温度保护**: 超过90℃触发保护，需冷却

8. **电压要求**: DC 15V-28V，推荐24V

---

## 硬件接线参考

```
夹爪线缆        连接设备
--------        --------
绿色(485_A)  -> RS485+ / T/R+
橙色(485_B)  -> RS485- / T/R-
红色(24V)    -> 24V DC+
蓝色(GND)    -> 24V DC-
黄色/黑色    -> IO输出(可选)
棕色/白色    -> IO输入(可选)
编织线       -> 接地
```

---

## 依赖

```bash
pip install pyserial
```

---

## 更多信息

- 完整API文档: 查看 `README.md`
- 使用示例: 查看 `examples.py`
- 常量定义: 查看 `constants.py`
- 制造商: 大寰机器人 (DH-Robotics)
- 官网: www.dh-robotics.com

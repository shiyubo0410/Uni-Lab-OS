# PGEA系列驱控一体式工业平行电爪 - Python控制库

基于Modbus-RTU协议的大寰(DH-Robotics) PGEA系列夹爪Python控制库。

## 适用型号

| 型号 | 最大夹持力 | 全行程 |
|------|-----------|--------|
| PGEA-15-26 | 15N | 26mm |
| PGEA-15-40 | 15N | 40mm |
| PGEA-50-26 | 50N | 26mm |
| PGEA-50-40 | 50N | 40mm |
| PGEA-100-26 | 100N | 26mm |
| PGEA-100-40 | 100N | 40mm |

## 通信协议

- **协议**: Modbus-RTU
- **接口**: RS485
- **默认波特率**: 115200
- **数据位**: 8
- **停止位**: 1
- **校验位**: 无
- **默认从站ID**: 1

## 硬件接线

### 线缆颜色定义

| 序号 | 线缆颜色 | 定义 | 说明 |
|------|---------|------|------|
| 1 | 绿色 | 485_A | 通讯线正 (T/R+) |
| 2 | 橙色 | 485_B | 通讯线负 (T/R-) |
| 3 | 黄色 | OUTPUT 2 | IO模式数字输出2 |
| 4 | 黑色 | OUTPUT 1 | IO模式数字输出1 |
| 5 | 红色 | 24V | 直流电源24V正极 |
| 6 | 蓝色 | GND | 直流电源GND负极 |
| 7 | 棕色 | INPUT 2 | IO模式数字输入2 |
| 8 | 白色 | INPUT 1 | IO模式数字输入1 |
| - | 编织线 | PE | 外壳接地 |

### RS485连接方式

```
夹爪端                    设备端
485_A (绿色)  ---------->  RS485+ / T/R+
485_B (橙色)  ---------->  RS485- / T/R-
24V   (红色)  ---------->  24V DC+
GND   (蓝色)  ---------->  24V DC-
```

## 安装

### 依赖

```bash
pip install pyserial
```

### 使用

将 `pgea_gripper_skill` 文件夹复制到您的项目目录中。

## 快速开始

```python
from pgea_gripper_skill import PGEAGripper

# 创建夹爪实例并连接
gripper = PGEAGripper(port='/dev/ttyUSB0')  # Linux
gripper = PGEAGripper(port='COM3')          # Windows
gripper.connect()

# 初始化夹爪（首次使用或更换指尖后必须执行）
gripper.initialize()

# 设置参数
gripper.set_force(50)      # 设置50%力值 (范围: 20-100)
gripper.set_speed(30)      # 设置30%速度 (范围: 1-100)

# 运动到指定位置 (范围: 0-1000，千分比)
gripper.move_to(500)       # 运动到50%位置

# 等待运动完成
gripper.wait_for_complete()

# 获取状态
status = gripper.get_full_status()
print(f"位置: {status.position}‰")
print(f"夹持状态: {status.grip_status}")

# 断开连接
gripper.disconnect()
```

## API文档

### 连接管理

#### `connect()`
连接夹爪。

**返回**: `bool` - 连接是否成功

#### `disconnect()`
断开与夹爪的连接。

#### `is_connected()`
检查是否已连接。

**返回**: `bool` - 是否已连接

### 初始化控制

#### `initialize(full_calibration=False, wait=True, timeout=10.0)`
初始化夹爪。

**参数**:
- `full_calibration` (bool): 是否进行完全初始化(重新标定行程)
- `wait` (bool): 是否等待初始化完成
- `timeout` (float): 等待超时时间(秒)

**返回**: `bool` - 初始化是否成功

**说明**:
- `full_calibration=False`: 单向回零，使用上次保存的行程
- `full_calibration=True`: 完全标定，重新测量最大和最小位置

### 运动控制

#### `set_force(force)`
设置夹持力值。

**参数**:
- `force` (int): 力值百分比 (20-100)

#### `set_speed(speed)`
设置运行速度。

**参数**:
- `speed` (int): 速度百分比 (1-100)

#### `move_to(position)`
运动到指定位置。

**参数**:
- `position` (int): 目标位置 (0-1000，千分比)

#### `grip(force=None, speed=None, wait=True, timeout=10.0)`
夹持动作（运动到闭合位置）。

**参数**:
- `force` (int): 夹持力，None表示使用当前设置
- `speed` (int): 速度，None表示使用当前设置
- `wait` (bool): 是否等待完成
- `timeout` (float): 超时时间

**返回**: `bool` - 是否成功夹住物体

#### `release(position=1000, speed=None, wait=True, timeout=10.0)`
释放动作（运动到张开位置）。

**参数**:
- `position` (int): 张开位置
- `speed` (int): 速度
- `wait` (bool): 是否等待完成
- `timeout` (float): 超时时间

**返回**: `bool` - 是否成功到位

### 状态读取

#### `get_full_status()`
获取完整状态。

**返回**: `GripperStatus` 对象，包含以下属性:
- `initialized` (bool): 是否已初始化
- `grip_status` (int): 夹持状态
  - `0`: 运动中
  - `1`: 到达位置(未夹到物体)
  - `2`: 夹住物体
  - `3`: 物体掉落
- `position` (int): 当前位置 (0-1000)
- `speed` (int): 当前速度
- `current` (int): 当前电流
- `error_code` (int): 错误码
- `motor_temp` (int): 电机温度

#### `get_current_position()`
获取当前实际位置。

**返回**: `int` - 当前位置 (0-1000)

#### `get_grip_status()`
获取夹持状态。

**返回**: `int` - 夹持状态码

#### `get_error_code()`
获取错误码。

**返回**: `int` - 错误码 (0表示无错误)

### 等待功能

#### `wait_for_complete(timeout=10.0, poll_interval=0.05)`
等待运动完成。

**参数**:
- `timeout` (float): 超时时间(秒)
- `poll_interval` (float): 轮询间隔(秒)

**返回**: `int` - 最终夹持状态

#### `wait_for_gripped(timeout=10.0, poll_interval=0.05)`
等待夹住物体。

**参数**:
- `timeout` (float): 超时时间(秒)
- `poll_interval` (float): 轮询间隔(秒)

**返回**: `bool` - 是否成功夹住物体

### 错误处理

#### `clear_error()`
清除错误。

**返回**: `bool` - 清除是否成功

#### `check_error()`
检查是否有错误。

**返回**: `str` 或 `None` - 错误描述，无错误返回None

### 参数配置

#### `save_parameters()`
保存参数到Flash。

**说明**: 此操作会持续1-2秒，期间不响应其他命令

#### `set_init_direction(direction)`
设置初始化方向。

**参数**:
- `direction` (int): 0=张开方向归零, 1=闭合方向归零

#### `set_auto_init(enable, full=False)`
设置上电自动初始化。

**参数**:
- `enable` (bool): 是否启用
- `full` (bool): 是否使用完全初始化

### IO控制

#### `set_io_parameters(group, position, force, speed)`
设置IO参数组。

**参数**:
- `group` (int): 参数组 (1-4)
- `position` (int): 位置 (0-1000)
- `force` (int): 力值 (20-100)
- `speed` (int): 速度 (1-100)

#### `test_io_group(group)`
测试IO参数组。

**参数**:
- `group` (int): 参数组 (1-4)

## 错误码

| 错误码 | 名称 | 说明 |
|--------|------|------|
| 0 | 无错误 | - |
| 1 | 欠压 | 电源电压低于15V |
| 2 | 过压 | 电源电压高于28V |
| 3 | 过流 | 电流超过额定值1.5倍 |
| 4 | 过热 | 电机温度超过90℃ |
| 5 | 电机缺相 | 请检查电机接线 |
| 8 | 过载 | 负载过大 |
| 11 | 过速 | 速度超过额定值1.5倍 |
| 15 | 启动异常 | 请检查编码器和电机 |
| 32 | 编码器异常 | 请检查编码器连接 |
| 33 | 编码器通讯异常 | 请检查编码器线缆 |
| 34 | 采样电路异常 | 请检查硬件 |
| 35 | 驱动IC异常 | 请重启设备 |
| 36 | Flash芯片异常 | 请重启设备 |
| 37 | 参数异常 | 请重启设备 |

## 指示灯状态

| 指示灯状态 | 说明 |
|-----------|------|
| 红灯闪烁 | 未初始化 |
| 蓝灯常亮 | 初始化完成 |
| 偏紫色闪烁 | 接收到命令 |
| 绿灯常亮 | 夹住物体 |
| 绿灯闪烁 | 物体掉落 |

## 使用示例

更多示例请参考 `examples.py` 文件。

### 基本使用

```python
from pgea_gripper_skill import PGEAGripper

with PGEAGripper(port='/dev/ttyUSB0') as gripper:
    gripper.initialize()
    
    # 设置力值和速度
    gripper.set_force(50)
    gripper.set_speed(30)
    
    # 运动到指定位置
    gripper.move_to(500)
    gripper.wait_for_complete()
```

### 夹持和释放

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
    print("成功夹住物体!")
else:
    print("未检测到物体")

gripper.disconnect()
```

### 取放操作

```python
from pgea_gripper_skill import PGEAGripper

gripper = PGEAGripper(port='/dev/ttyUSB0')
gripper.connect()
gripper.initialize()

# 取物
success = gripper.pick(
    pick_position=200,
    force=50,
    speed=30,
    lift_position=500,
    wait_grip=True
)

if success:
    # 放物
    gripper.place(
        place_position=300,
        speed=30,
        release_position=800
    )

gripper.disconnect()
```

### 状态监控

```python
from pgea_gripper_skill import PGEAGripper

gripper = PGEAGripper(port='/dev/ttyUSB0')
gripper.connect()
gripper.initialize()

# 获取完整状态
status = gripper.get_full_status()
print(f"初始化状态: {status.initialized}")
print(f"夹持状态: {status.grip_status}")
print(f"当前位置: {status.position}‰")
print(f"电机温度: {status.motor_temp}°C")

# 检查错误
if status.has_error:
    print(f"错误: {status.get_error_description()}")

gripper.disconnect()
```

## 注意事项

1. **首次使用必须初始化**: 夹爪在首次使用或更换指尖后必须进行初始化。

2. **初始化方向**: 
   - 默认初始化方向为张开方向
   - 可通过 `set_init_direction()` 修改

3. **力值范围**: 力值范围为20-100%，低于20%可能无法稳定夹持。

4. **位置单位**: 位置使用千分比(0-1000)，对应夹爪的0-100%行程。

5. **保存参数**: 修改参数后需要调用 `save_parameters()` 保存到Flash。

6. **错误处理**: 遇到错误时先尝试 `clear_error()`，无法清除时请重启设备。

7. **温度保护**: 电机温度超过90℃会触发过热保护，请降低负载或等待冷却。

8. **电压要求**: 电源电压范围为DC 15V-28V，推荐使用24V稳压电源。

## 版本信息

- **版本**: 1.0.0
- **协议**: Modbus-RTU
- **适用手册版本**: V4.0

## 技术支持

- **制造商**: 大寰机器人 (DH-Robotics)
- **官网**: www.dh-robotics.com
- **电话**: 0755-82734836

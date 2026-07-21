# PGEA夹爪控制库 - 文件结构说明

```
pgea_gripper_skill/
│
├── __init__.py              # 包初始化文件，导出主要类和常量
│
├── constants.py             # 常量定义文件
│   ├── 寄存器地址定义
│   ├── 状态码定义
│   ├── 错误码定义
│   ├── 数值范围限制
│   └── 默认配置参数
│
├── modbus_client.py         # Modbus-RTU通信客户端
│   ├── CRC16校验计算器
│   └── ModbusRTUClient类
│       ├── 连接管理
│       ├── 读取寄存器 (0x03, 0x04)
│       └── 写入寄存器 (0x06, 0x10)
│
├── gripper.py               # PGEA夹爪主控制类
│   ├── PGEAGripper类
│   │   ├── 连接管理
│   │   ├── 初始化控制
│   │   ├── 运动控制 (力/位/速)
│   │   ├── 状态读取
│   │   ├── 等待功能
│   │   ├── 高级运动 (pick/place)
│   │   ├── 错误处理
│   │   ├── 参数配置
│   │   └── IO控制
│   └── GripperStatus数据类
│
├── examples.py              # 使用示例
│   ├── 基本连接与初始化
│   ├── 基本运动控制
│   ├── 夹持与释放
│   ├── 取放操作
│   ├── 状态监控
│   ├── 错误处理
│   ├── IO模式配置
│   ├── 参数配置
│   ├── 上下文管理器
│   └── 连续操作
│
├── test_basic.py            # 基础测试脚本
│
├── README.md                # 完整使用文档
│
├── SKILL.md                 # AI技能说明文档
│
├── STRUCTURE.md             # 本文件
│
├── setup.py                 # 安装脚本
│
└── requirements.txt         # 依赖文件
```

## 模块依赖关系

```
examples.py, test_basic.py
        ↓
   gripper.py
        ↓
   modbus_client.py
        ↓
    constants.py
```

## 核心类说明

### 1. PGEAGripper (主控制类)

位置: `gripper.py`

功能: 提供高级API控制夹爪

主要方法:
- `connect()` / `disconnect()`: 连接管理
- `initialize()`: 初始化夹爪
- `set_force()` / `set_speed()`: 设置参数
- `move_to()`: 位置控制
- `grip()` / `release()`: 夹持/释放
- `get_full_status()`: 获取状态
- `wait_for_complete()`: 等待完成

### 2. ModbusRTUClient (通信客户端)

位置: `modbus_client.py`

功能: 处理Modbus-RTU协议通信

主要方法:
- `connect()` / `disconnect()`: 串口连接
- `read_holding_registers()`: 读取保持寄存器
- `write_single_register()`: 写入单个寄存器
- `write_multiple_registers()`: 写入多个寄存器

### 3. CRC16 (校验计算器)

位置: `modbus_client.py`

功能: 计算Modbus-RTU CRC16校验

主要方法:
- `calculate(data)`: 计算CRC值
- `verify(data, crc_low, crc_high)`: 验证CRC

### 4. GripperStatus (状态数据类)

位置: `gripper.py`

功能: 封装夹爪状态信息

主要属性:
- `initialized`: 是否已初始化
- `grip_status`: 夹持状态
- `position`: 当前位置
- `error_code`: 错误码
- `is_moving` / `is_gripped`: 状态判断

## 常量分类

### 寄存器地址 (constants.py)

- `REG_INIT_GRIPPER` (0x0100): 初始化
- `REG_FORCE` (0x0101): 力值
- `REG_POSITION` (0x0103): 位置
- `REG_SPEED` (0x0104): 速度
- `REG_INIT_STATUS` (0x0200): 初始化状态
- `REG_GRIP_STATUS` (0x0201): 夹持状态
- ... 更多详见代码

### 状态值

- `INIT_STATUS_NOT_INIT` (0): 未初始化
- `INIT_STATUS_SUCCESS` (1): 初始化成功
- `GRIP_STATUS_MOVING` (0): 运动中
- `GRIP_STATUS_GRIPPED` (2): 已夹住物体

### 错误码

- `ERROR_NONE` (0): 无错误
- `ERROR_UNDERVOLTAGE` (1): 欠压
- `ERROR_OVERCURRENT` (3): 过流
- `ERROR_OVERTEMP` (4): 过热
- ... 更多详见代码

## 使用流程

```
1. 导入库
   from pgea_gripper_skill import PGEAGripper

2. 创建实例
   gripper = PGEAGripper(port='/dev/ttyUSB0')

3. 连接
   gripper.connect()

4. 初始化
   gripper.initialize()

5. 控制
   gripper.set_force(50)
   gripper.move_to(500)

6. 等待
   gripper.wait_for_complete()

7. 断开
   gripper.disconnect()
```

## 扩展说明

### 添加新功能

如需添加新功能:

1. 在 `constants.py` 中添加相关常量
2. 在 `gripper.py` 的 `PGEAGripper` 类中添加方法
3. 在 `examples.py` 中添加使用示例
4. 更新 `README.md` 和 `SKILL.md` 文档

### 调试方法

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 启用调试日志后，所有通信数据都会被记录
```

### 错误排查

1. 检查串口连接: `gripper.is_connected()`
2. 检查初始化状态: `gripper.is_initialized()`
3. 检查错误码: `gripper.get_error_code()`
4. 获取完整状态: `gripper.get_full_status()`

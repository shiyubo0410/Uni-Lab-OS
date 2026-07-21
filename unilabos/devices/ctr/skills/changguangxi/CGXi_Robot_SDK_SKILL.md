# CGXi 协作机器人 Python SDK 使用手册

> 版本: v2.20e  
> 文档类型: 二次开发接口文档 (Python)

---

## 目录

1. [概述](#一概述)
2. [环境配置](#二环境配置)
3. [数据类型与结构体](#三数据类型与结构体)
4. [API接口详解](#四api接口详解)
5. [综合示例](#五综合示例)
6. [附录](#六附录)

---

## 一、概述

### 1.1 简介

CGXi 协作机器人 Python SDK 提供了完整的二次开发接口，支持通过Python语言控制机械臂完成各种操作，包括运动控制、工程管理、配置管理等功能。

### 1.2 核心特性

- **运动控制**: 支持MoveJ/MoveL、直线运动、轴空间运动等多种运动模式
- **工程管理**: 支持工程下载、上传、运行、暂停、停止
- **配置管理**: TCP/负载配置、坐标系管理、安装变量管理
- **通讯接口**: 支持Modbus主站、串口通讯、网络配置
- **高级功能**: 力控、扩展轴、轨迹记录与再现

### 1.3 基本使用流程

```python
import cgxiapi
import basestruct
from ctypes import *

# 1. 创建连接
robotHandle = 1
result = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
if result[0].value == 0:
    robotHandle = result[1].value
    
# 2. 执行操作
# ... 各种API调用 ...

# 3. 断开连接
cgxiapi.cr_destroy_robot(robotHandle)
```

---

## 二、环境配置

### 2.1 依赖库

| 库名 | 用途 |
|------|------|
| `cgxiapi` | 核心SDK库 |
| `basestruct` | 数据结构定义 |
| `ctypes` | C类型支持 |

### 2.2 连接参数

| 参数 | 说明 | 示例 |
|------|------|------|
| IP地址 | 控制柜IP | `"192.168.6.6"` |
| 端口 | 通讯端口 | `2323` |
| 密码 | 连接密码 | `"123"` |

### 2.3 虚拟臂连接

```python
# 虚拟臂用于测试，IP固定为127.0.0.1，端口2325
result = cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325, "123")
```

---

## 三、数据类型与结构体

### 3.1 返回值类型 (CRresult)

```python
class CRresult(Enum):
    success = 0                    # 成功
    # 其他错误码...
```

### 3.2 核心数据结构

#### 3.2.1 PointControlPara - 点位控制参数

```python
class PointControlPara(Structure):
    _fields_ = [
        ("jointpos", c_double * 6),           # 目标关节角度 (°)
        ("pose", c_double * 6),               # 目标位姿 (mm, °)
        ("tcpOffset", c_double * 6),          # TCP偏移
        ("tcpID", c_int),                     # TCP索引
        ("speed", c_double * 6),              # 速度
        ("acc", c_double * 6),                # 加速度
        ("coordinatePose", c_double * 6),     # 坐标系位姿
        ("jerk", c_double * 6),               # 加加速度
        ("coordinateType", CoordinateType),   # 坐标系类型
        ("pointTransType", PointTransType),   # 过渡类型
        ("pointTransRadius", c_double),       # 过渡半径
        ("poseTranType", PoseTranType),       # 姿态过渡类型
        ("motiontriggerMode", MotiontriggerMode)  # 触发模式
    ]
```

#### 3.2.2 PointControlParaSimple - 简化版点位控制参数

```python
class PointControlParaSimple(Structure):
    _fields_ = [
        ("jointpos", c_double * 6),
        ("pose", c_double * 6),
        ("tcpOffset", c_double * 6),
        ("tcpID", c_int),
        ("speed", c_double * 6),
        ("acc", c_double * 6),
        ("coordinatePose", c_double * 6),
        ("coordinateType", CoordinateType),
        ("pointTransType", PointTransType),
        ("motiontriggerMode", MotiontriggerMode)
    ]
```

#### 3.2.3 TCPMsg - TCP配置信息

```python
class TCPMsg(Structure):
    _fields_ = [
        ("tcpName", c_char * 32),             # TCP名称
        ("tcpOffset", c_double * 6),          # TCP偏移 (mm, °)
        ("tcpId", c_int)                      # TCP ID
    ]
```

#### 3.2.4 PayloadMsg - 负载配置信息

```python
class PayloadMsg(Structure):
    _fields_ = [
        ("payloadName", c_char * 32),         # 负载名称
        ("payload", c_double),                # 负载质量 (kg)
        ("centerOfGravity", c_double * 3),    # 质心偏移 (mm)
        ("payloadId", c_int)                  # 负载ID
    ]
```

#### 3.2.5 PointCSNode - 点坐标系节点

```python
class PointCSNode(Structure):
    _fields_ = [
        ("name", c_char * 32),                # 坐标系名称
        ("id", c_int),                        # 坐标系ID
        ("point", ToolPoint),                 # 工具点数据
        ("isValid", c_int)                    # 是否有效
    ]
```

#### 3.2.6 LineCSNode - 线坐标系节点

```python
class LineCSNode(Structure):
    _fields_ = [
        ("name", c_char * 32),
        ("id", c_int),
        ("firstPoint", PointCSNode),          # 第一个点
        ("secondPoint", PointCSNode),         # 第二个点
        ("coordinatePose", c_double * 6),     # 坐标系位姿
        ("coordinateJointPos", c_double * 6), # 坐标系关节角度
        ("isValid", c_int)
    ]
```

#### 3.2.7 PlaneCSNode - 面坐标系节点

```python
class PlaneCSNode(Structure):
    _fields_ = [
        ("name", c_char * 32),
        ("id", c_int),
        ("firstPoint", PointCSNode),
        ("secondPoint", PointCSNode),
        ("thirdPoint", PointCSNode),
        ("coordinatePose", c_double * 6),
        ("coordinateJointPos", c_double * 6),
        ("isValid", c_int)
    ]
```

#### 3.2.8 VariableMsg - 变量信息

```python
class VariableMsg(Structure):
    _fields_ = [
        ("variableName", c_char * 32),        # 变量名称
        ("variableType", c_int),              # 变量类型
        ("numberValue", c_double),            # 数值
        ("stringValue", c_char * 128),        # 字符串值
        ("variableID", c_int)                 # 变量ID
    ]
```

#### 3.2.9 PathData - 轨迹数据

```python
class PathData(Structure):
    _fields_ = [
        ("pathPoints", POINTER(PathPoint)),   # 轨迹点数组
        ("pathLen", c_int)                    # 轨迹长度
    ]
```

#### 3.2.10 PathPara - 轨迹参数

```python
class PathPara(Structure):
    _fields_ = [
        ("index", c_int),                     # 轨迹索引
        ("moveType", c_int)                   # 运动类型
    ]
```

#### 3.2.11 PathDownloadData - 轨迹下载数据

```python
class PathDownloadData(Structure):
    _fields_ = [
        ("pathData", PathData),
        ("pathPara", PathPara)
    ]
```

#### 3.2.12 RecordPathPara - 轨迹记录参数

```python
class RecordPathPara(Structure):
    _fields_ = [
        ("recordControl", c_int),             # 记录控制: 0-停止, 1-启动, 2-暂停
        ("sampleTime", c_int)                 # 采样时间 (ms)
    ]
```

#### 3.2.13 ForceConfig - 力控配置

```python
class ForceConfig(Structure):
    _fields_ = [
        ("forceCtrlTcpImpl", ForceCtrlTcpImpl),
        ("commuConfig", CommuConfig),
        ("sensorMessage", SensorMessage)
    ]
```

#### 3.2.14 ForceSetting - 力控设置

```python
class ForceSetting(Structure):
    _fields_ = [
        ("forceBaseType", c_int),             # 力传感器类型
        ("forceCtrlType", c_int),             # 力控类型
        ("flexibleAxis", c_int * 6)           # 柔性轴
    ]
```

#### 3.2.15 ForceCtlPara - 力控参数

```python
class ForceCtlPara(Structure):
    _fields_ = [
        ("taskFrame", c_double * 6),          # 任务坐标系
        ("wrench", c_double * 6),             # 力/力矩
        ("limits", c_double * 6),             # 限制
        ("limitsLen", c_int),
        ("mass", c_double * 6),               # 质量
        ("massLen", c_int),
        ("damping", c_double * 6),            # 阻尼
        ("dampingLen", c_int),
        ("stiffness", c_double * 6),          # 刚度
        ("stiffnessLen", c_int)
    ]
```

#### 3.2.16 ForceData - 力控数据

```python
class ForceData(Structure):
    _fields_ = [
        ("ftCtrl", c_double * 6),             # 力/力矩数据
        ("ftPayload", c_double * 6),
        ("ftPayloadTcp", c_double * 6)
    ]
```

#### 3.2.17 ExjConfig - 扩展轴配置

```python
class ExjConfig(Structure):
    _fields_ = [
        ("name", c_char * 32),                # 扩展轴名称
        ("type", c_int),                      # 类型
        ("ratio", c_double),                  # 传动比
        ("minlimit", c_double),               # 最小限位
        ("maxlimit", c_double),               # 最大限位
        ("zeroPosition", c_double),           # 零位
        ("exjToRef", c_double * 6),           # 参考坐标系
        ("masterExjName", c_char * 32),       # 主轴名称
        ("masterSlaveRate", c_double)         # 主从比
    ]
```

#### 3.2.18 RobotExjData - 机械臂与扩展轴数据

```python
class RobotExjData(Structure):
    _fields_ = [
        ("actualExjointPos", c_double * 6),   # 扩展轴实际位置
        ("actualJointPos", c_double * 6),     # 实际关节角度
        ("actualTcpVector", c_double * 6)     # 实际TCP位姿
    ]
```

#### 3.2.19 PopUpMsg - 弹窗消息

```python
class PopUpMsg(Structure):
    _fields_ = [
        ("popupType", c_int),                 # 弹窗类型
        ("var_data", c_char * 128)            # 弹窗内容
    ]
```

### 3.3 枚举类型

#### 3.3.1 CoordinateType - 坐标系类型

```python
class CoordinateType(Enum):
    baseCoordinate = 0        # 基坐标系
    toolCoordinate = 1        # 工具坐标系
    userCoordinate = 2        # 用户坐标系
    jointCoordinate = 3       # 关节坐标系
```

#### 3.3.2 PointTransType - 过渡类型

```python
class PointTransType(Enum):
    pointTransStop = 0        # 无过渡
    pointTransBlend = 1       # 过渡
```

#### 3.3.3 PoseTranType - 姿态过渡类型

```python
class PoseTranType(Enum):
    poseTranMoveToTargetPose = 0   # 运动到目标姿态
    poseTranInterpolate = 1        # 姿态插值
```

#### 3.3.4 MotiontriggerMode - 运动触发模式

```python
class MotiontriggerMode(Enum):
    MovetriggerbyOnlyRpc = 0       # 仅RPC触发
    MovetriggerbyDI = 1            # DI触发
    MovetriggerbyDIandRpc = 2      # DI和RPC触发
```

#### 3.3.5 SerialType - 串口类型

```python
class SerialType(Enum):
    rs232_CommSettings = 0
    rs485_1_CommSettings = 1
    rs485_2_CommSettings = 2
    rs485_3_CommSettings = 3
    ethernet_CommSettings = 4
```

#### 3.3.6 ModbusMasterOperate - Modbus主站操作

```python
class ModbusMasterOperate(Enum):
    Stop = 0
    Start = 1
```

#### 3.3.7 ModbusMasterFunctionNo - Modbus功能码

```python
class ModbusMasterFunctionNo(Enum):
    ReadInt16 = 0
    ReadInt32 = 1
    ReadFloat = 2
    ReadDouble = 3
    WriteInt16 = 4
    WriteInt32 = 5
    WriteFloat = 6
    WriteDouble = 7
```

#### 3.3.8 CommuVarType - 通讯变量类型

```python
class CommuVarType(Enum):
    CommuVarType_Int16 = 0
    CommuVarType_Int32 = 1
    CommuVarType_Float = 2
    CommuVarType_Double = 3
```

---

## 四、API接口详解

### 4.1 连接管理

#### 4.1.1 cr_create_robot - 创建连接

```python
cr_create_robot(robotHandle, ip, port, passwd)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄(输入) |
| ip | c_char_p | IP地址 |
| port | c_int | 端口号 |
| passwd | c_char_p | 密码 |

**返回值**: 数组 `[CRresult, robotHandle]`

**示例**:
```python
robotHandle = 1
result = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
if result[0].value == 0:
    robotHandle = result[1].value
    print("连接成功")
else:
    print("连接失败")
```

#### 4.1.2 cr_destroy_robot - 断开连接

```python
cr_destroy_robot(robotHandle)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |

**返回值**: CRresult

---

### 4.2 状态读取

#### 4.2.1 cr_get_robotMode - 读取机械臂状态

```python
cr_get_robotMode(robotHandle)
```

**返回值**: 数组 `[CRresult, robotMode]`

**robotMode状态码**:
| 值 | 状态 |
|----|------|
| 0 | 未定义 |
| 1 | 未连接 |
| 2 | 连接中 |
| 3 | 已连接 |
| 4 | 已断开 |
| 5 | 连接异常 |
| 6 | 本体未上电 |
| 7 | 本体上电中 |
| 8 | 本体已上电 |
| 9 | 使能中 |
| 10 | 使能完成 |
| 11 | 去使能中 |
| 12 | 去使能完成 |
| 13 | 运动中 |
| 14 | 运动完成 |
| 15 | 暂停中 |
| 16 | 暂停完成 |
| 17 | 停止中 |
| 18 | 停止完成 |
| 19 | 错误 |
| 20 | 错误恢复中 |
| 21 | 错误恢复完成 |
| 22 | 急停中 |
| 23 | 急停完成 |
| 24 | 安全门打开 |
| 25 | 安全门关闭 |
| 26 | 安全门异常 |
| 27 | 安全门恢复中 |
| 28 | 安全门恢复完成 |
| 29 | 安全门未连接 |
| 30 | 安全门已连接 |
| 31 | 安全门连接异常 |
| 32 | 安全门连接恢复中 |
| 33 | 安全门连接恢复完成 |
| 34 | 安全门未使能 |
| 35 | 安全门使能中 |
| 36 | 安全门使能完成 |
| 37 | 安全门去使能中 |
| 38 | 安全门去使能完成 |
| 39 | 安全门运动中 |
| 40 | 安全门运动完成 |
| 41 | 安全门暂停中 |
| 42 | 安全门暂停完成 |
| 43 | 安全门停止中 |
| 44 | 安全门停止完成 |
| 45 | 安全门错误 |
| 46 | 安全门错误恢复中 |
| 47 | 安全门错误恢复完成 |
| 48 | 安全门急停中 |
| 49 | 安全门急停完成 |
| 50 | 安全门安全门打开 |
| 51 | 安全门安全门关闭 |
| 52 | 安全门安全门异常 |
| 53 | 安全门安全门恢复中 |
| 54 | 安全门安全门恢复完成 |
| 55 | 安全门安全门未连接 |
| 56 | 安全门安全门已连接 |
| 57 | 安全门安全门连接异常 |
| 58 | 安全门安全门连接恢复中 |
| 59 | 安全门安全门连接恢复完成 |
| 60 | 安全门安全门未使能 |
| 61 | 安全门安全门使能中 |
| 62 | 安全门安全门使能完成 |
| 63 | 安全门安全门去使能中 |
| 64 | 安全门安全门去使能完成 |
| 65 | 安全门安全门运动中 |
| 66 | 安全门安全门运动完成 |
| 67 | 安全门安全门暂停中 |
| 68 | 安全门安全门暂停完成 |
| 69 | 安全门安全门停止中 |
| 70 | 安全门安全门停止完成 |
| 71 | 安全门安全门错误 |
| 72 | 安全门安全门错误恢复中 |
| 73 | 安全门安全门错误恢复完成 |
| 74 | 安全门安全门急停中 |
| 75 | 安全门安全门急停完成 |
| 100 | 未使能 |
| 101 | 未上电 |
| 102 | 上电中 |
| 103 | 空闲 |
| 104 | 暂停 |
| 105 | 运行中 |
| 106 | 拖动示教 |
| 107 | 更新中 |
| 108 | 更新完成 |
| 109 | 更新失败 |
| 110 | 更新取消 |
| 111 | 更新暂停 |
| 112 | 更新恢复 |
| 113 | 更新停止 |
| 114 | 更新错误 |
| 115 | 更新错误恢复中 |
| 116 | 更新错误恢复完成 |
| 117 | 更新急停中 |
| 118 | 更新急停完成 |

#### 4.2.2 cr_get_jointActualPos - 读取实际关节角度

```python
cr_get_jointActualPos(robotHandle, jointPos, len)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| jointPos | POINTER(c_double) | 关节角度数组(输出) |
| len | c_int | 数组长度(6) |

**返回值**: CRresult

**示例**:
```python
jointPos = [0.0] * 6
result = cgxiapi.cr_get_jointActualPos(robotHandle, jointPos, 6)
if result.value == 0:
    print(f"关节角度: {jointPos}")
```

#### 4.2.3 cr_get_tcpActualPose - 读取实际TCP位姿

```python
cr_get_tcpActualPose(robotHandle, tcpPose)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| tcpPose | POINTER(c_double) | TCP位姿数组(输出) [x,y,z,Rx,Ry,Rz] |

**返回值**: CRresult

**示例**:
```python
pose = [0.0] * 6
result = cgxiapi.cr_get_tcpActualPose(robotHandle, pose)
if result.value == 0:
    print(f"TCP位姿: x={pose[0]}, y={pose[1]}, z={pose[2]}")
```

#### 4.2.4 cr_get_robotMoveStatus - 读取机械臂运动状态

```python
cr_get_robotMoveStatus(robotHandle)
```

**返回值**: 数组 `[CRresult, moveStatus]`

**moveStatus**:
| 值 | 状态 |
|----|------|
| 0 | 停止 |
| 1 | 运动中 |

---

### 4.3 运动控制

#### 4.3.1 cr_moveJ - 轴空间运动(非阻塞)

```python
cr_moveJ(robotHandle, pointControlPara)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| pointControlPara | PointControlPara | 点位控制参数 |

**返回值**: CRresult

**示例**:
```python
pointControlPara = basestruct.PointControlPara()
pointControlPara.jointpos = (0, 0, 90, 0, -90, 0)
pointControlPara.speed = (30, 30, 30, 30, 30, 30)
pointControlPara.acc = (60, 60, 60, 60, 60, 60)
pointControlPara.coordinateType = basestruct.CoordinateType.jointCoordinate
pointControlPara.pointTransType = basestruct.PointTransType.pointTransStop
pointControlPara.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc

result = cgxiapi.cr_moveJ(robotHandle, pointControlPara)
```

#### 4.3.2 cr_moveL - 直线运动(非阻塞)

```python
cr_moveL(robotHandle, pointControlPara)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| pointControlPara | PointControlPara | 点位控制参数 |

**返回值**: CRresult

**示例**:
```python
pointControlPara = basestruct.PointControlPara()
pointControlPara.pose = (x, y, z, rx, ry, rz)
pointControlPara.coordinateType = basestruct.CoordinateType.baseCoordinate

result = cgxiapi.cr_moveL(robotHandle, pointControlPara)
```

#### 4.3.3 cr_move_joint - 轴空间运动(可阻塞)

```python
cr_move_joint(robotHandle, pointControlPara, isBlock)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| pointControlPara | PointControlPara | 点位控制参数 |
| isBlock | c_int | 是否阻塞: 0-非阻塞, 1-阻塞 |

**返回值**: CRresult

#### 4.3.4 cr_move_line - 直线运动(可阻塞)

```python
cr_move_line(robotHandle, pointControlPara, isBlock)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| pointControlPara | PointControlPara | 点位控制参数 |
| isBlock | c_int | 是否阻塞: 0-非阻塞, 1-阻塞 |

**返回值**: CRresult

#### 4.3.5 cr_move_pointControlPara_transfer - 参数转换

```python
cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, pointControlPara)
```

将简化的点位控制参数转换为完整的点位控制参数。

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| pointControlParaSimple | PointControlParaSimple | 简化参数(输入) |
| pointControlPara | PointControlPara | 完整参数(输出) |

**返回值**: CRresult

---

### 4.4 工程控制

#### 4.4.1 cr_downloadProgram - 加载程序

```python
cr_downloadProgram(robotHandle, program)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| program | c_char_p | 程序字符串 |

**返回值**: CRresult

**示例**:
```python
program = b"function main()\nmovej({0,0,90,0,-90,0})\nend"
result = cgxiapi.cr_downloadProgram(robotHandle, program)
```

#### 4.4.2 cr_downloadProject - 下载工程

```python
cr_downloadProject(robotHandle, crpFilepathname, crscriptFilepathname)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| crpFilepathname | c_char_p | .crp文件路径 |
| crscriptFilepathname | c_char_p | .crscript文件路径 |

**返回值**: CRresult

#### 4.4.3 cr_uploadProject - 上传工程

```python
cr_uploadProject(robotHandle, FilePath, filename)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| FilePath | c_char_p | 保存路径 |
| filename | c_char_p | 文件名(不含扩展名) |

**返回值**: CRresult

#### 4.4.4 cr_play - 运行程序

```python
cr_play(robotHandle)
```

**返回值**: CRresult

#### 4.4.5 cr_pause - 暂停程序

```python
cr_pause(robotHandle)
```

**返回值**: CRresult

#### 4.4.6 cr_resume - 恢复程序

```python
cr_resume(robotHandle)
```

**返回值**: CRresult

#### 4.4.7 cr_stop - 停止程序

```python
cr_stop(robotHandle)
```

**返回值**: CRresult

#### 4.4.8 cr_get_lua_scriptstatus - 读取脚本运行状态

```python
cr_get_lua_scriptstatus(robotHandle)
```

**返回值**: 数组 `[CRresult, scriptStatus]`

**scriptStatus**:
| 值 | 状态 |
|----|------|
| 0 | 未运行 |
| 1 | 运行中 |
| 2 | 暂停 |
| 3 | 停止 |

---

### 4.5 电源与使能控制

#### 4.5.1 cr_poweron - 上电

```python
cr_poweron(robotHandle)
```

**返回值**: CRresult

#### 4.5.2 cr_poweroff - 下电

```python
cr_poweroff(robotHandle)
```

**返回值**: CRresult

#### 4.5.3 cr_enable - 使能

```python
cr_enable(robotHandle)
```

**返回值**: CRresult

#### 4.5.4 cr_disable - 去使能

```python
cr_disable(robotHandle)
```

**返回值**: CRresult

---

### 4.6 正逆解

#### 4.6.1 cr_kineForward - 正解

```python
cr_kineForward(robotHandle, jointPos, toolPosition)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| jointPos | POINTER(c_double) | 关节角度(输入) |
| toolPosition | POINTER(c_double) | 工具位姿(输出) [x,y,z,Rx,Ry,Rz] |

**返回值**: CRresult

**示例**:
```python
jointPos = (0, 0, 90, 0, -90, 0)
toolPos = [0.0] * 6
result = cgxiapi.cr_kineForward(robotHandle, jointPos, toolPos)
```

#### 4.6.2 cr_kineInverse - 逆解

```python
cr_kineInverse(robotHandle, toolPosition, refJointPos, jointPos)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| toolPosition | POINTER(c_double) | 工具位姿(输入) |
| refJointPos | POINTER(c_double) | 参考关节角度(输入) |
| jointPos | POINTER(c_double) | 关节角度(输出) |

**返回值**: CRresult

---

### 4.7 轨迹记录与再现

#### 4.7.1 cr_path_recordPara_set - 设置轨迹记录参数

```python
cr_path_recordPara_set(robotHandle, recordPathPara)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| recordPathPara | RecordPathPara | 记录参数 |

**返回值**: CRresult

**示例**:
```python
recordPathPara = basestruct.RecordPathPara()
recordPathPara.recordControl = 1  # 1-启动, 0-停止, 2-暂停
recordPathPara.sampleTime = 2     # 采样时间(ms)
result = cgxiapi.cr_path_recordPara_set(robotHandle, recordPathPara)
```

#### 4.7.2 cr_path_upload - 上传轨迹

```python
cr_path_upload(robotHandle, index, pathData)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 轨迹索引(-1表示最新记录) |
| pathData | PathData | 轨迹数据(输出) |

**返回值**: CRresult

#### 4.7.3 cr_path_download - 下载轨迹

```python
cr_path_download(robotHandle, pathDownloadData)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| pathDownloadData | PathDownloadData | 轨迹下载数据 |

**返回值**: CRresult

#### 4.7.4 cr_path_all_index_get - 读取所有轨迹索引

```python
cr_path_all_index_get(robotHandle)
```

**返回值**: 数组 `[CRresult, indexArray, count]`

---

### 4.8 TCP配置

#### 4.8.1 cr_cfg_tcp_count - 读取TCP个数

```python
cr_cfg_tcp_count(robotHandle)
```

**返回值**: 数组 `[CRresult, count]`

#### 4.8.2 cr_cfg_tcp_get - 读取TCP

```python
cr_cfg_tcp_get(robotHandle, index, tcpMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | TCP索引(0-9) |
| tcpMsg | TCPMsg | TCP信息(输出) |

**返回值**: CRresult

#### 4.8.3 cr_cfg_tcp_add - 增加TCP

```python
cr_cfg_tcp_add(robotHandle, tcpMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| tcpMsg | TCPMsg | TCP信息(输入) |

**返回值**: CRresult

#### 4.8.4 cr_cfg_tcp_set - 修改TCP

```python
cr_cfg_tcp_set(robotHandle, index, tcpMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | TCP索引 |
| tcpMsg | TCPMsg | TCP信息(输入) |

**返回值**: CRresult

#### 4.8.5 cr_cfg_tcp_delete - 删除TCP

```python
cr_cfg_tcp_delete(robotHandle, index)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | TCP索引 |

**返回值**: CRresult

#### 4.8.6 cr_cfg_tcp_active_get - 读取当前激活TCP索引

```python
cr_cfg_tcp_active_get(robotHandle)
```

**返回值**: 数组 `[CRresult, index]`

#### 4.8.7 cr_cfg_tcp_active_set - 设置当前激活TCP

```python
cr_cfg_tcp_active_set(robotHandle, index)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | TCP索引 |

**返回值**: CRresult

---

### 4.9 负载配置

#### 4.9.1 cr_cfg_payload_count - 读取负载个数

```python
cr_cfg_payload_count(robotHandle)
```

**返回值**: 数组 `[CRresult, count]`

#### 4.9.2 cr_cfg_payload_get - 读取负载

```python
cr_cfg_payload_get(robotHandle, index, payloadMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 负载索引(0-9) |
| payloadMsg | PayloadMsg | 负载信息(输出) |

**返回值**: CRresult

#### 4.9.3 cr_cfg_payload_add - 增加负载

```python
cr_cfg_payload_add(robotHandle, payloadMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| payloadMsg | PayloadMsg | 负载信息(输入) |

**返回值**: CRresult

#### 4.9.4 cr_cfg_payload_set - 修改负载

```python
cr_cfg_payload_set(robotHandle, index, payloadMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 负载索引 |
| payloadMsg | PayloadMsg | 负载信息(输入) |

**返回值**: CRresult

#### 4.9.5 cr_cfg_payload_delete - 删除负载

```python
cr_cfg_payload_delete(robotHandle, index)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 负载索引 |

**返回值**: CRresult

#### 4.9.6 cr_cfg_payload_active_get - 读取当前激活负载索引

```python
cr_cfg_payload_active_get(robotHandle)
```

**返回值**: 数组 `[CRresult, index]`

#### 4.9.7 cr_cfg_payload_active_set - 设置当前激活负载

```python
cr_cfg_payload_active_set(robotHandle, index)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 负载索引 |

**返回值**: CRresult

---

### 4.10 安装变量

#### 4.10.1 cr_cfg_var_install_count - 读取安装变量个数

```python
cr_cfg_var_install_count(robotHandle)
```

**返回值**: 数组 `[CRresult, count]`

#### 4.10.2 cr_cfg_var_install_get - 读取安装变量

```python
cr_cfg_var_install_get(robotHandle, index, variableMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 变量索引(0-63) |
| variableMsg | VariableMsg | 变量信息(输出) |

**返回值**: CRresult

#### 4.10.3 cr_cfg_var_install_add - 增加安装变量

```python
cr_cfg_var_install_add(robotHandle, variableMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| variableMsg | VariableMsg | 变量信息(输入) |

**返回值**: CRresult

#### 4.10.4 cr_cfg_var_install_set - 修改安装变量

```python
cr_cfg_var_install_set(robotHandle, index, variableMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 变量索引 |
| variableMsg | VariableMsg | 变量信息(输入) |

**返回值**: CRresult

#### 4.10.5 cr_cfg_var_install_delete - 删除安装变量

```python
cr_cfg_var_install_delete(robotHandle, index)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 变量索引 |

**返回值**: CRresult

---

### 4.11 坐标系管理

#### 4.11.1 点坐标系

| 函数 | 说明 |
|------|------|
| `cr_cfg_cs_point_count(robotHandle)` | 读取点坐标系个数 |
| `cr_cfg_cs_point_get(robotHandle, index, pointCSNode)` | 读取点坐标系 |
| `cr_cfg_cs_point_accord_name_get(robotHandle, csName, pointCSNode)` | 按名称读取点坐标系 |
| `cr_cfg_cs_point_add(robotHandle, pointCSNode)` | 增加点坐标系 |
| `cr_cfg_cs_point_set(robotHandle, index, pointCSNode)` | 修改点坐标系 |
| `cr_cfg_cs_point_delete(robotHandle, index)` | 删除点坐标系 |

#### 4.11.2 线坐标系

| 函数 | 说明 |
|------|------|
| `cr_cfg_cs_line_count(robotHandle)` | 读取线坐标系个数 |
| `cr_cfg_cs_line_get(robotHandle, index, lineCSNode)` | 读取线坐标系 |
| `cr_cfg_cs_line_accord_name_get(robotHandle, csName, lineCSNode)` | 按名称读取线坐标系 |
| `cr_cfg_cs_line_add(robotHandle, lineCSNode)` | 增加线坐标系 |
| `cr_cfg_cs_line_set(robotHandle, index, lineCSNode)` | 修改线坐标系 |
| `cr_cfg_cs_line_delete(robotHandle, index)` | 删除线坐标系 |

#### 4.11.3 面坐标系

| 函数 | 说明 |
|------|------|
| `cr_cfg_cs_plane_count(robotHandle)` | 读取面坐标系个数 |
| `cr_cfg_cs_plane_get(robotHandle, index, planeCSNode)` | 读取面坐标系 |
| `cr_cfg_cs_plane_accord_name_get(robotHandle, csName, planeCSNode)` | 按名称读取面坐标系 |
| `cr_cfg_cs_plane_add(robotHandle, planeCSNode)` | 增加面坐标系 |
| `cr_cfg_cs_plane_set(robotHandle, index, planeCSNode)` | 修改面坐标系 |
| `cr_cfg_cs_plane_delete(robotHandle, index)` | 删除面坐标系 |

#### 4.11.4 基坐标系与工具坐标系

| 函数 | 说明 |
|------|------|
| `cr_cfg_cs_base_get(robotHandle, csPose, len)` | 读取基坐标系数据 |
| `cr_cfg_cs_tool_get(robotHandle, csPose, len)` | 读取工具坐标系数据 |

#### 4.11.5 坐标系计算

| 函数 | 说明 |
|------|------|
| `cr_compute_cs_point(pointPose, pLen, pointCS, csLen)` | 计算点坐标系 |
| `cr_compute_cs_line(point1Pose, p1Len, point2Pose, p2Len, lineCS, csLen)` | 计算线坐标系 |
| `cr_compute_cs_plane(point1Pose, p1Len, point2Pose, p2Len, point3Pose, p3Len, planeCS, csLen)` | 计算面坐标系 |
| `cr_compute_pose_base_to_user(basePose, basePoseLen, userPose, userPoseLen, poseInUser, poseInUserLen)` | 基坐标系转用户坐标系 |

---

### 4.12 串口通讯

#### 4.12.1 cr_cfg_comm_serial_setting_set - 设置串口配置

```python
cr_cfg_comm_serial_setting_set(robotHandle, serialType, serialCommSettings)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| serialType | SerialType | 串口类型 |
| serialCommSettings | SerialCommSettings | 串口配置 |

**返回值**: CRresult

#### 4.12.2 cr_cfg_comm_serial_setting_get - 读取串口配置

```python
cr_cfg_comm_serial_setting_get(robotHandle, serialType, serialCommSettings)
```

**返回值**: CRresult

---

### 4.13 网络配置

#### 4.13.1 cr_cfg_comm_ethernet_ip_set - 设置网络配置

```python
cr_cfg_comm_ethernet_ip_set(robotHandle, ipconfig)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| ipconfig | IPConfig | 网络配置 |

**返回值**: CRresult

#### 4.13.2 cr_cfg_comm_ethernet_ip_get - 读取网络配置

```python
cr_cfg_comm_ethernet_ip_get(robotHandle, ipconfig)
```

**返回值**: CRresult

#### 4.13.3 cr_cfg_comm_ethernet_modbus_slave_num_set - 设置从站号

```python
cr_cfg_comm_ethernet_modbus_slave_num_set(robotHandle, modbusSlaveNo)
```

**返回值**: CRresult

#### 4.13.4 cr_cfg_comm_ethernet_modbus_slave_num_get - 读取从站号

```python
cr_cfg_comm_ethernet_modbus_slave_num_get(robotHandle)
```

**返回值**: 数组 `[CRresult, modbusSlaveNo]`

---

### 4.14 Modbus主站

#### 4.14.1 从站管理

| 函数 | 说明 |
|------|------|
| `cr_cfg_comm_modbus_slave_count(robotHandle, type)` | 读取从站个数 |
| `cr_cfg_comm_modbus_slave_get(robotHandle, type, index, modbusConfig)` | 读取从站数据 |
| `cr_cfg_comm_modbus_slave_add(robotHandle, type, modbusConfig)` | 添加从站 |
| `cr_cfg_comm_modbus_slave_delete(robotHandle, type, index)` | 删除从站 |
| `cr_cfg_comm_modbus_slave_set(robotHandle, type, index, modbusConfig)` | 修改从站数据 |
| `cr_cfg_comm_modbus_slave_operate(robotHandle, type, index, modbusOperate)` | 连接/断开从站 |
| `cr_cfg_comm_modbus_slave_connect_get(robotHandle, type, index, status)` | 获取从站连接状态 |

#### 4.14.2 地址映射

| 函数 | 说明 |
|------|------|
| `cr_cfg_comm_modbus_addr_map_count(robotHandle, type, serialIndex, count)` | 读取地址映射数量 |
| `cr_cfg_comm_modbus_addr_map_get(robotHandle, type, serialIndex, index, addrMap)` | 读取地址映射数据 |
| `cr_cfg_comm_modbus_addr_map_add(robotHandle, type, serialIndex, addrMap)` | 添加地址映射 |
| `cr_cfg_comm_modbus_addr_map_delete(robotHandle, type, serialIndex, index)` | 删除地址映射 |
| `cr_cfg_comm_modbus_addr_map_set(robotHandle, type, serialIndex, index, addrMap)` | 修改地址映射数据 |

---

### 4.15 力控

#### 4.15.1 cr_force_cfg_set - 设置力控配置

```python
cr_force_cfg_set(robotHandle, forceConfig)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| forceConfig | ForceConfig | 力控配置 |

**返回值**: CRresult

#### 4.15.2 cr_force_cfg_get - 读取力控配置

```python
cr_force_cfg_get(robotHandle, forceConfig)
```

**返回值**: CRresult

#### 4.15.3 cr_force_open - 开启力控

```python
cr_force_open(robotHandle, forceSetting)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| forceSetting | ForceSetting | 力控设置 |

**返回值**: CRresult

#### 4.15.4 cr_force_close - 关闭力控

```python
cr_force_close(robotHandle)
```

**返回值**: CRresult

#### 4.15.5 cr_force_para_set - 设置力控参数

```python
cr_force_para_set(robotHandle, forceCtlPara)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| forceCtlPara | ForceCtlPara | 力控参数 |

**返回值**: CRresult

#### 4.15.6 cr_force_para_get - 读取力控参数

```python
cr_force_para_get(robotHandle, forceCtlPara)
```

**返回值**: CRresult

#### 4.15.7 cr_force_data_get - 读取力控数据

```python
cr_force_data_get(robotHandle, forceData)
```

**返回值**: CRresult

---

### 4.16 扩展轴

#### 4.16.1 cr_set_exj_enableStatus - 设置扩展轴使能状态

```python
cr_set_exj_enableStatus(robotHandle, index, status)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| index | c_int | 扩展轴索引 |
| status | c_int | 状态: 0-禁用, 1-使能 |

**返回值**: CRresult

#### 4.16.2 cr_get_exj_enableStatus - 读取扩展轴使能状态

```python
cr_get_exj_enableStatus(robotHandle, index)
```

**返回值**: 数组 `[CRresult, status]`

#### 4.16.3 cr_get_robot_exj_data - 读取机械臂和扩展轴数据

```python
cr_get_robot_exj_data(robotHandle, robotExjData)
```

**返回值**: CRresult

#### 4.16.4 cr_cfg_exj_get - 获取扩展轴配置

```python
cr_cfg_exj_get(robotHandle, exjName, exjConfig)
```

**返回值**: CRresult

#### 4.16.5 cr_cfg_exj_set - 设置扩展轴配置

```python
cr_cfg_exj_set(robotHandle, exjName, exjConfig)
```

**返回值**: CRresult

#### 4.16.6 cr_cfg_exj_add - 增加扩展轴

```python
cr_cfg_exj_add(robotHandle, exjConfig)
```

**返回值**: CRresult

#### 4.16.7 cr_cfg_exj_delete - 删除扩展轴

```python
cr_cfg_exj_delete(robotHandle)
```

**说明**: 只能删除最后一个扩展轴

**返回值**: CRresult

---

### 4.17 弹窗消息

#### 4.17.1 cr_script_popup_exist - 判断弹窗是否存在

```python
cr_script_popup_exist(robotHandle)
```

**返回值**: 数组 `[CRresult, exist]` (exist: 0-不存在, 1-存在)

#### 4.17.2 cr_script_popup_msg_get - 读取弹窗信息

```python
cr_script_popup_msg_get(robotHandle, popupMsg)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| robotHandle | c_int | 机械臂句柄 |
| popupMsg | PopUpMsg | 弹窗消息(输出) |

**返回值**: CRresult

---

## 五、综合示例

### 5.1 机械臂使能

```python
import cgxiapi
from ctypes import *
import time
import basestruct
import inspect

# 机械臂创建连接
robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")

if re0[0].value == 0:
    robotHandle = re0[1].value
    re1 = cgxiapi.cr_get_robotMode(robotHandle)
    
    if re1[0].value == 0 and re1[1].value == 6:  # 本体未上电状态
        result = cgxiapi.cr_poweron(robotHandle)
        if result.value == 0:
            while result.value == 0:
                re1 = cgxiapi.cr_get_robotMode(robotHandle)
                time.sleep(0.05)
                if re1[1].value == 8:  # 本体已上电
                    break
            
            result = cgxiapi.cr_enable(robotHandle)
            if result.value == 0:
                while result.value == 0:
                    re1 = cgxiapi.cr_get_robotMode(robotHandle)
                    time.sleep(0.05)
                    if re1[1].value == 103:  # 空闲状态
                        break
                print("使能完成")

result_destroy = cgxiapi.cr_destroy_robot(robotHandle)
```

### 5.2 工程控制

```python
import cgxiapi
from ctypes import *
import time
import basestruct

robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")

if re0[0].value == 0:
    robotHandle = re0[1].value
    re1 = cgxiapi.cr_get_lua_scriptstatus(robotHandle)
    
    if re1[0].value == 0 and re1[1].value == 1:  # 脚本停止状态
        crpFilepathname = b"./program/demo.crp"
        crscriptFilepathname = b"./program/demo.crscript"
        re2 = cgxiapi.cr_downloadProject(robotHandle, crpFilepathname, crscriptFilepathname)
        
        if re2.value == 0:
            re3 = cgxiapi.cr_play(robotHandle)
            while re3.value == 0:
                result = cgxiapi.cr_get_robotMode(robotHandle)
                if result[1].value == 103:
                    break
            
            # 上传工程
            FilePath = b"./program/"
            filename = b"test"
            re4 = cgxiapi.cr_uploadProject(robotHandle, FilePath, filename)

cgxiapi.cr_destroy_robot(robotHandle)
```

### 5.3 移动控制

```python
import cgxiapi
from ctypes import *
import time
import basestruct

robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")

if re0[0].value == 0:
    robotHandle = re0[1].value
    
    # 创建点位控制参数
    pointControlPara = basestruct.PointControlPara()
    pointControlParaSimple = basestruct.PointControlParaSimple()
    speed = 30
    acc = 60
    
    # 设置轴空间运动参数
    jointpos = (0, 0, 90, 0, -90, 0)
    pointControlPara.jointpos = jointpos
    pointControlPara.speed = (speed, speed, speed, speed, speed, speed)
    pointControlPara.acc = (acc, acc, acc, acc, acc, acc)
    pointControlPara.coordinateType = basestruct.CoordinateType.jointCoordinate
    pointControlPara.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlPara.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    
    # 执行轴空间运动
    result_movej = cgxiapi.cr_moveJ(robotHandle, pointControlPara)
    
    # 等待运动完成
    if result_movej.value == 0:
        time.sleep(0.5)
        result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
        while result_moveStatus[0].value == 0:
            result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
            if result_moveStatus[1].value == 0:
                break
    
    # 执行直线运动
    pose = [0, 0, 0, 0, 0, 0]
    cgxiapi.cr_get_tcpActualPose(robotHandle, pose)
    pose[2] = pose[2] - 150
    
    pointControlPara.coordinateType = basestruct.CoordinateType.baseCoordinate
    pointControlPara.pose = tuple(pose)
    result_movel = cgxiapi.cr_moveL(robotHandle, pointControlPara)

cgxiapi.cr_destroy_robot(robotHandle)
```

### 5.4 轨迹记录与再现

```python
import cgxiapi
from ctypes import *
import time
import basestruct

robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")

if re0[0].value == 0:
    robotHandle = re0[1].value
    
    # 运动到起始位置
    pointControlParaSimple = basestruct.PointControlParaSimple()
    pointControlPara = basestruct.PointControlPara()
    
    pointControlParaSimple.jointpos = (0, 0, 90, 0, -90, 0)
    cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, pointControlPara)
    cgxiapi.cr_move_joint(robotHandle, pointControlPara, 1)
    
    # 开始记录轨迹
    recordPathPara = basestruct.RecordPathPara()
    recordPathPara.recordControl = 1
    recordPathPara.sampleTime = 2
    cgxiapi.cr_path_recordPara_set(robotHandle, recordPathPara)
    
    time.sleep(0.5)
    
    # 执行运动
    pointControlParaSimple.jointpos = (90, 0, 90, 0, -90, 0)
    cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, pointControlPara)
    cgxiapi.cr_move_joint(robotHandle, pointControlPara, 1)
    
    # 停止记录
    recordPathPara.recordControl = 0
    cgxiapi.cr_path_recordPara_set(robotHandle, recordPathPara)
    
    # 上传轨迹
    pathData = basestruct.PathData()
    stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
    pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
    cgxiapi.cr_path_upload(robotHandle, -1, pathData)
    
    # 下载轨迹到索引2
    pathDownloadData = basestruct.PathDownloadData()
    pathDownloadData.pathData = pathData
    pathDownloadData.pathPara.index = 2
    pathDownloadData.pathPara.moveType = 1
    cgxiapi.cr_path_download(robotHandle, pathDownloadData)

cgxiapi.cr_destroy_robot(robotHandle)
```

### 5.5 TCP操作

```python
import cgxiapi
from ctypes import *
import basestruct

robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")

if re0[0].value == 0:
    robotHandle = re0[1].value
    
    # 读取当前激活的TCP索引
    result_activeTcp = cgxiapi.cr_cfg_tcp_active_get(robotHandle)
    
    if result_activeTcp[0].value == 0:
        # 读取TCP信息
        index = 0
        tcpMsg = basestruct.TCPMsg()
        result_getTcp = cgxiapi.cr_cfg_tcp_get(robotHandle, index, tcpMsg)
        
        if result_getTcp.value == 0:
            # 修改TCP偏移
            offset = [3, 10, 9, 90, 80, 70]
            for i in range(6):
                tcpMsg.tcpOffset[i] = offset[i]
            
            result_setTcp = cgxiapi.cr_cfg_tcp_set(robotHandle, index, tcpMsg)
            
            # 增加新TCP
            tcpMsg2 = basestruct.TCPMsg()
            tcpMsg2.tcpName = b'tcp_222'
            offset2 = [5, 10, 15, 10, 20, 30]
            for i in range(6):
                tcpMsg2.tcpOffset[i] = offset2[i]
            
            result_add = cgxiapi.cr_cfg_tcp_add(robotHandle, tcpMsg2)
            
            # 激活新TCP
            index = 1
            cgxiapi.cr_cfg_tcp_active_set(robotHandle, index)

cgxiapi.cr_destroy_robot(robotHandle)
```

---

## 六、附录

### 6.1 速度和加速度范围

#### 各机型关节速度范围

| 机型 | 关节速度范围(°/s) | TCP速度范围(mm/s) |
|------|------------------|-------------------|
| C3 | 1-180 | 0.01-1000 |
| C4/C6/C6-DK | 1-180 | 0.01-2000 |
| G3 | 1-360 | 0.01-2000 |
| G3a | 1-270 | 0.01-1500 |
| G4/G6/G7 | 1-360 | 0.01-3000 |
| G4a/G6a | 1-270 | 0.01-2000 |
| G9/G10/G12 | 1-240 | 0.01-3000 |
| G9a/G12a | 1-180 | 0.01-2000 |
| G18 | 1-240 | 0.01-2000 |
| G18a | 1-180 | 0.01-1500 |
| G20 | 1-270 | 0.01-4000 |
| G30 | 1-270 | 0.01-3000 |
| X6 | 1-360 | 0.01-3000 |
| X9/X12/X18 | 1-240 | 0.01-3000 |

#### 加速度范围

| 类型 | 范围 |
|------|------|
| 关节加速度 | 0.01~2500 °/s² |
| TCP加速度 | 0.01~20000 mm/s² |

#### 点动速度范围

| 类型 | 范围 |
|------|------|
| 关节点动速度 | 0.1~15 °/s |
| 关节点动加速度 | 0.01~90 °/s² |
| TCP点动速度 | 0.1~120 mm/s |
| TCP点动加速度 | 0.01~720 mm/s² |

### 6.2 常量定义

```python
# 轴数
ROB_AXIS_NUM = 6

# 最大轨迹点数
MAX_PATH_POINTS = 10000

# 最大TCP/负载数
MAX_TCP_PAYLOAD = 10

# 最大变量数
MAX_VARIABLES = 64

# 最大坐标系数
MAX_COORDINATE_SYSTEM = 10

# 最大Modbus从站数
MAX_MODBUS_SLAVES = 20

# 最大地址映射数
MAX_ADDR_MAP = 100
```

### 6.3 注意事项

1. **连接顺序**: 必须先创建连接(`cr_create_robot`)，使用完毕后断开连接(`cr_destroy_robot`)
2. **使能流程**: 上电(`cr_poweron`) → 等待上电完成 → 使能(`cr_enable`) → 等待使能完成
3. **运动等待**: 非阻塞运动需要循环查询运动状态(`cr_get_robotMoveStatus`)等待完成
4. **工程下载**: 必须在脚本停止状态(`scriptStatus == 1`)下才能下载工程
5. **坐标系**: 使用前需要确保坐标系有效(`isValid == 1`)
6. **力控**: 开启力控前需要正确配置力控参数
7. **扩展轴**: 删除扩展轴只能删除最后一个

---

*文档生成时间: 2025年*

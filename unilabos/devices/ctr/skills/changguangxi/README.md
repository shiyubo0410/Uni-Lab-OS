# CGXi 协作机器人 Python SDK 使用手册

> **版本**: v2.20e  
> **文档类型**: 二次开发接口文档 (Python)  
> **更新日期**: 2025

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

#### 4.5.2 cr_poweroff - 断电

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

#### 4.5.5 cr_FaultReset - 故障复位

```python
cr_FaultReset(robotHandle)
```

**返回值**: CRresult

---

### 4.6 配置管理

#### 4.6.1 TCP配置

| 函数 | 说明 |
|------|------|
| `cr_add_tcp` | 添加TCP |
| `cr_delete_tcp` | 删除TCP |
| `cr_update_tcp` | 更新TCP |
| `cr_get_tcp` | 获取TCP |
| `cr_get_tcp_list` | 获取TCP列表 |

#### 4.6.2 负载配置

| 函数 | 说明 |
|------|------|
| `cr_add_payload` | 添加负载 |
| `cr_delete_payload` | 删除负载 |
| `cr_update_payload` | 更新负载 |
| `cr_get_payload` | 获取负载 |
| `cr_get_payload_list` | 获取负载列表 |

#### 4.6.3 坐标系配置

| 函数 | 说明 |
|------|------|
| `cr_add_pointCS` | 添加点坐标系 |
| `cr_add_lineCS` | 添加线坐标系 |
| `cr_add_planeCS` | 添加面坐标系 |
| `cr_delete_CS` | 删除坐标系 |
| `cr_get_CS_list` | 获取坐标系列表 |

---

## 五、综合示例

### 5.1 基本运动示例

```python
import cgxiapi
import basestruct
import time

# 连接机器人
robotHandle = 1
result = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
robotHandle = result[1].value

# 上电
cgxiapi.cr_poweron(robotHandle)
time.sleep(2)

# 使能
cgxiapi.cr_enable(robotHandle)
time.sleep(2)

# MoveJ运动
pointControlPara = basestruct.PointControlPara()
pointControlPara.jointpos = (0, 0, 90, 0, -90, 0)
pointControlPara.speed = (30, 30, 30, 30, 30, 30)
pointControlPara.acc = (60, 60, 60, 60, 60, 60)
pointControlPara.coordinateType = basestruct.CoordinateType.jointCoordinate
pointControlPara.pointTransType = basestruct.PointTransType.pointTransStop
pointControlPara.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc

cgxiapi.cr_moveJ(robotHandle, pointControlPara)
time.sleep(3)

# MoveL运动
pointControlPara.pose = (300, 0, 400, 0, 180, 0)
pointControlPara.coordinateType = basestruct.CoordinateType.baseCoordinate

cgxiapi.cr_moveL(robotHandle, pointControlPara)
time.sleep(3)

# 去使能
cgxiapi.cr_disable(robotHandle)
time.sleep(2)

# 断电
cgxiapi.cr_poweroff(robotHandle)

# 断开连接
cgxiapi.cr_destroy_robot(robotHandle)
```

### 5.2 工程运行示例

```python
# 下载工程
crp_path = b"D:/project/demo.crp"
crscript_path = b"D:/project/demo.crscript"
result = cgxiapi.cr_downloadProject(robotHandle, crp_path, crscript_path)

# 运行工程
cgxiapi.cr_play(robotHandle)

# 查询运行状态
result = cgxiapi.cr_get_lua_scriptstatus(robotHandle)
script_status = result[1].value
print(f"脚本状态: {script_status}")

# 暂停工程
cgxiapi.cr_pause(robotHandle)

# 恢复工程
cgxiapi.cr_resume(robotHandle)

# 停止工程
cgxiapi.cr_stop(robotHandle)
```

---

## 六、附录

### 6.1 机械臂状态码

| 码值 | 状态 |
|------|------|
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

### 6.2 SDK文件路径

完整SDK文件位于: `inf/CGXi-Robot-SDK-Python-v2.2e/CGXi-Robot-SDK-Python-v2.2e/demo/python3.7/64位/sdk_test_Python/`

### 6.3 技术支持

如有疑问请参考设备手册或联系技术支持。

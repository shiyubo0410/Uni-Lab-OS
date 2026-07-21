# CGXi 协作机器人 Python SDK 技能包

> **版本**: v2.20e  
> **更新日期**: 2025  
> **适用设备**: CGXi 协作机器人  
> **SDK类型**: Python SDK

---

## 目录

1. [设备连接配置](#1-设备连接配置)
2. [快速开始](#2-快速开始)
3. [核心API接口](#3-核心api接口)
4. [运动控制](#4-运动控制)
5. [工程管理](#5-工程管理)
6. [配置管理](#6-配置管理)
7. [状态码说明](#7-状态码说明)

---

## 1. 设备连接配置

### 1.1 连接参数

| 参数 | 实际机器人 | 虚拟机器人 |
|------|-----------|-----------|
| **IP地址** | 192.168.6.6 | 127.0.0.1 |
| **端口** | 2323 | 2325 |
| **密码** | 123 | 123 |

### 1.2 依赖库

| 库名 | 用途 |
|------|------|
| `cgxiapi` | 核心SDK库 |
| `basestruct` | 数据结构定义 |
| `ctypes` | C类型支持 |

### 1.3 系统要求

- **操作系统**: Windows/Linux
- **Python版本**: 3.7+
- **SDK版本**: v2.20e

---

## 2. 快速开始

### 2.1 基本连接示例

```python
import cgxiapi
from ctypes import *

# 创建连接
robotHandle = 1
result = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
if result[0].value == 0:
    robotHandle = result[1].value
    print("连接成功")
else:
    print("连接失败")

# 断开连接
cgxiapi.cr_destroy_robot(robotHandle)
```

### 2.2 完整操作流程

```python
# 1. 连接机器人
robotHandle = 1
result = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
robotHandle = result[1].value

# 2. 上电
cgxiapi.cr_poweron(robotHandle)

# 3. 使能
cgxiapi.cr_enable(robotHandle)

# 4. 运动控制
# ... 运动命令 ...

# 5. 去使能
cgxiapi.cr_disable(robotHandle)

# 6. 断电
cgxiapi.cr_poweroff(robotHandle)

# 7. 断开连接
cgxiapi.cr_destroy_robot(robotHandle)
```

---

## 3. 核心API接口

### 3.1 连接管理

| 函数 | 说明 |
|------|------|
| `cr_create_robot` | 创建连接 |
| `cr_destroy_robot` | 断开连接 |

### 3.2 电源与使能

| 函数 | 说明 |
|------|------|
| `cr_poweron` | 上电 |
| `cr_poweroff` | 断电 |
| `cr_enable` | 使能 |
| `cr_disable` | 去使能 |
| `cr_FaultReset` | 故障复位 |

### 3.3 状态读取

| 函数 | 说明 |
|------|------|
| `cr_get_robotMode` | 读取机械臂状态 |
| `cr_get_jointActualPos` | 读取实际关节角度 |
| `cr_get_tcpActualPose` | 读取实际TCP位姿 |
| `cr_get_robotMoveStatus` | 读取运动状态 |
| `cr_get_robotSpeedPercent` | 读取速度百分比 |

---

## 4. 运动控制

### 4.1 运动模式

| 模式 | 函数 | 说明 |
|------|------|------|
| MoveJ | `cr_moveJ` | 轴空间运动（非阻塞） |
| MoveL | `cr_moveL` | 直线运动（非阻塞） |
| MoveJ | `cr_move_joint` | 轴空间运动（可阻塞） |
| MoveL | `cr_move_line` | 直线运动（可阻塞） |
| MoveC | `cr_moveC` | 圆弧运动 |
| MoveJog | `cr_moveJog` | 点动运动 |

### 4.2 坐标系类型

| 类型 | 值 | 说明 |
|------|---|------|
| baseCoordinate | 0 | 基坐标系 |
| toolCoordinate | 1 | 工具坐标系 |
| userCoordinate | 2 | 用户坐标系 |
| jointCoordinate | 3 | 关节坐标系 |

### 4.3 过渡类型

| 类型 | 值 | 说明 |
|------|---|------|
| pointTransStop | 0 | 无过渡 |
| pointTransBlend | 1 | 过渡 |

### 4.4 运动示例

```python
import basestruct

# MoveJ 示例
pointControlPara = basestruct.PointControlPara()
pointControlPara.jointpos = (0, 0, 90, 0, -90, 0)
pointControlPara.speed = (30, 30, 30, 30, 30, 30)
pointControlPara.acc = (60, 60, 60, 60, 60, 60)
pointControlPara.coordinateType = basestruct.CoordinateType.jointCoordinate
pointControlPara.pointTransType = basestruct.PointTransType.pointTransStop
pointControlPara.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc

cgxiapi.cr_moveJ(robotHandle, pointControlPara)

# MoveL 示例
pointControlPara = basestruct.PointControlPara()
pointControlPara.pose = (x, y, z, rx, ry, rz)
pointControlPara.coordinateType = basestruct.CoordinateType.baseCoordinate

cgxiapi.cr_moveL(robotHandle, pointControlPara)
```

---

## 5. 工程管理

### 5.1 工程操作

| 函数 | 说明 |
|------|------|
| `cr_downloadProgram` | 加载程序 |
| `cr_downloadProject` | 下载工程 |
| `cr_uploadProject` | 上传工程 |
| `cr_play` | 运行程序 |
| `cr_pause` | 暂停程序 |
| `cr_resume` | 恢复程序 |
| `cr_stop` | 停止程序 |

### 5.2 脚本状态

| 值 | 状态 |
|----|------|
| 0 | 未运行 |
| 1 | 运行中 |
| 2 | 暂停 |
| 3 | 停止 |

### 5.3 工程示例

```python
# 加载程序
program = b"function main()\nmovej({0,0,90,0,-90,0})\nend"
cgxiapi.cr_downloadProgram(robotHandle, program)

# 运行程序
cgxiapi.cr_play(robotHandle)

# 暂停程序
cgxiapi.cr_pause(robotHandle)

# 恢复程序
cgxiapi.cr_resume(robotHandle)

# 停止程序
cgxiapi.cr_stop(robotHandle)
```

---

## 6. 配置管理

### 6.1 配置类型

| 类型 | 说明 |
|------|------|
| TCP | 工具中心点配置 |
| Payload | 负载配置 |
| CoordinateSystem | 坐标系配置 |
| Variable | 变量配置 |

### 6.2 坐标系类型

| 类型 | 说明 |
|------|------|
| PointCS | 点坐标系 |
| LineCS | 线坐标系 |
| PlaneCS | 面坐标系 |

### 6.3 通讯接口

| 类型 | 说明 |
|------|------|
| ModbusMaster | Modbus主站 |
| Serial | 串口通讯 |
| Ethernet | 网络配置 |

---

## 7. 状态码说明

### 7.1 机械臂状态码

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

### 7.2 运动状态码

| 码值 | 状态 |
|------|------|
| 0 | 停止 |
| 1 | 运动中 |

---

## SDK文件路径

完整SDK文件位于: `inf/CGXi-Robot-SDK-Python-v2.2e/CGXi-Robot-SDK-Python-v2.2e/demo/python3.7/64位/sdk_test_Python/`

包含文件:
- `cgxiapi.pyd` - 核心SDK库
- `basestruct.py` - 数据结构定义
- `Demo_*.py` - 各功能示例程序
- `*.dll` - 依赖库文件

---

## 技术支持

详细API文档请参考: `CGXi_Robot_SDK_SKILL.md`

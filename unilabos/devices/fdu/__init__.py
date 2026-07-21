# -*- coding: utf-8 -*-
"""复旦大学（FDU）实验台设备驱动集合。

包含：
- KexingRelay       继电器（16 路 Modbus-RTU，兼容旧 ctr/jidianqi 模块）
- PGEAGripperDevice PGE-A 平行电爪（Modbus-RTU）
- XuantuSpinCoater  旋图旋涂仪（Modbus-RTU，9600 → 19200 切换波特率）
- CGXiRobotDevice   长光希 CGXi 六轴协作机械臂（TCP/SDK，内置命名路点库）
"""

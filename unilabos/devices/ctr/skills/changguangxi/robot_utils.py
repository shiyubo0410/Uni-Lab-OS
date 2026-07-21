#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CGXi 协作机器人工具类
提供便捷的机器人控制接口
"""

import sys
import os
import time

# 添加SDK路径
sdk_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                        'inf', 'CGXi-Robot-SDK-Python-v2.2e', 
                        'CGXi-Robot-SDK-Python-v2.2e', 'demo', 'python3.7', '64位', 'sdk_test_Python')
sys.path.insert(0, sdk_path)

# 添加SDK DLL路径到系统PATH (Windows需要这样才能找到依赖的DLL)
if os.name == 'nt':  # Windows
    os.environ['PATH'] = sdk_path + os.pathsep + os.environ.get('PATH', '')

try:
    import cgxiapi
    import basestruct
    from ctypes import *
except ImportError as e:
    # 新环境下请走 ``unilabos.devices.fdu.cgxi_native`` 的 ctypes 原生绑定；
    # 这里静默降级为 debug 日志，避免无关警告污染 offline smoke 输出。
    import logging as _logging
    _logging.getLogger(__name__).debug(
        "cgxiapi.pyd 未加载（%s），SDK路径=%s", e, sdk_path
    )


class CGXiRobot:
    """CGXi 协作机器人控制类"""
    
    def __init__(self, ip="192.168.6.6", port=2323, password="123", virtual=False):
        """
        初始化机器人连接
        
        Args:
            ip: 机器人IP地址
            port: 端口号
            password: 连接密码
            virtual: 是否使用虚拟臂
        """
        self.ip = "127.0.0.1" if virtual else ip
        self.port = 2325 if virtual else port
        self.password = password
        self.robotHandle = None
        self.connected = False
        
    def connect(self):
        """
        连接机器人
        
        Returns:
            bool: 连接是否成功
        """
        try:
            robotHandle = 1
            result = cgxiapi.cr_create_robot(robotHandle, self.ip, self.port, self.password)
            if result[0].value == 0:
                self.robotHandle = result[1].value
                self.connected = True
                print(f"机器人连接成功 (Handle: {self.robotHandle})")
                return True
            else:
                print(f"机器人连接失败，错误码: {result[0].value}")
                return False
        except Exception as e:
            print(f"连接异常: {e}")
            return False
    
    def disconnect(self):
        """断开机器人连接"""
        if self.connected and self.robotHandle is not None:
            try:
                result = cgxiapi.cr_destroy_robot(self.robotHandle)
                if result.value == 0:
                    print("机器人断开连接成功")
                else:
                    print(f"断开连接失败，错误码: {result.value}")
            except Exception as e:
                print(f"断开连接异常: {e}")
            finally:
                self.connected = False
                self.robotHandle = None
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
    
    # ==================== 电源与使能控制 ====================
    
    def power_on(self):
        """
        机器人上电
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_poweron(self.robotHandle)
        success = result.value == 0
        print(f"上电{'成功' if success else '失败'}")
        return success
    
    def power_off(self):
        """
        机器人断电
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_poweroff(self.robotHandle)
        success = result.value == 0
        print(f"断电{'成功' if success else '失败'}")
        return success
    
    def enable(self):
        """
        机器人使能
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_enable(self.robotHandle)
        success = result.value == 0
        print(f"使能{'成功' if success else '失败'}")
        return success
    
    def disable(self):
        """
        机器人去使能
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_disable(self.robotHandle)
        success = result.value == 0
        print(f"去使能{'成功' if success else '失败'}")
        return success
    
    def fault_reset(self):
        """
        故障复位
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_FaultReset(self.robotHandle)
        success = result.value == 0
        print(f"故障复位{'成功' if success else '失败'}")
        return success
    
    # ==================== 状态读取 ====================
    
    def get_robot_mode(self):
        """
        获取机器人状态
        
        Returns:
            tuple: (success, mode_code)
        """
        if not self._check_connected():
            return (False, None)
        result = cgxiapi.cr_get_robotMode(self.robotHandle)
        success = result[0].value == 0
        mode = result[1].value if success else None
        return (success, mode)
    
    def get_joint_position(self):
        """
        获取关节角度
        
        Returns:
            tuple: (success, joint_pos_list)
        """
        if not self._check_connected():
            return (False, None)
        jointPos = [0.0] * 6
        result = cgxiapi.cr_get_jointActualPos(self.robotHandle, jointPos)
        success = result.value == 0
        return (success, jointPos if success else None)
    
    def get_tcp_pose(self):
        """
        获取TCP位姿
        
        Returns:
            tuple: (success, tcp_pose_list)
        """
        if not self._check_connected():
            return (False, None)
        pose = [0.0] * 6
        result = cgxiapi.cr_get_tcpActualPose(self.robotHandle, pose)
        success = result.value == 0
        return (success, pose if success else None)
    
    def get_move_status(self):
        """
        获取运动状态
        
        Returns:
            tuple: (success, move_status)
        """
        if not self._check_connected():
            return (False, None)
        result = cgxiapi.cr_get_robotMoveStatus(self.robotHandle)
        success = result[0].value == 0
        status = result[1].value if success else None
        return (success, status)
    
    def get_speed_percent(self):
        """
        获取速度百分比
        
        Returns:
            tuple: (success, speed_percent)
        """
        if not self._check_connected():
            return (False, None)
        result = cgxiapi.cr_get_robotSpeedPercent(self.robotHandle)
        success = result[0].value == 0
        speed = result[1].value if success else None
        return (success, speed)
    
    def set_speed_percent(self, speed_percent):
        """
        设置速度百分比
        
        Args:
            speed_percent: 速度百分比 (0-100)
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_set_robotSpeedPercent(self.robotHandle, speed_percent)
        success = result.value == 0
        print(f"设置速度百分比 {speed_percent}% {'成功' if success else '失败'}")
        return success
    
    # ==================== 运动控制 ====================
    
    def movej(self, joint_pos, speed=None, acc=None, block=False):
        """
        轴空间运动 (MoveJ)
        
        Args:
            joint_pos: 关节角度列表 [j1, j2, j3, j4, j5, j6]
            speed: 速度列表，默认 (30, 30, 30, 30, 30, 30)
            acc: 加速度列表，默认 (60, 60, 60, 60, 60, 60)
            block: 是否阻塞等待运动完成
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        
        if speed is None:
            speed = (30, 30, 30, 30, 30, 30)
        if acc is None:
            acc = (60, 60, 60, 60, 60, 60)
        
        # 使用 PointControlParaSimple 创建参数，然后转换为 PointControlPara
        pointControlParaSimple = basestruct.PointControlParaSimple()
        pointControlParaSimple.jointpos = tuple(joint_pos)
        pointControlParaSimple.pose = (0, 0, 0, 0, 0, 0)
        pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
        pointControlParaSimple.tcpID = -1
        pointControlParaSimple.speed = tuple(speed)
        pointControlParaSimple.acc = tuple(acc)
        pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
        pointControlParaSimple.coordinateType = basestruct.CoordinateType.jointCoordinate
        pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
        pointControlParaSimple.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
        
        # 转换为 PointControlPara
        pointControlPara = basestruct.PointControlPara()
        result_transfer = cgxiapi.cr_move_pointControlPara_transfer(self.robotHandle, pointControlParaSimple, pointControlPara)
        if result_transfer.value != 0:
            print(f"参数转换失败: {result_transfer.value}")
            return False
        
        if block:
            result = cgxiapi.cr_move_joint(self.robotHandle, pointControlPara, 1)
        else:
            result = cgxiapi.cr_moveJ(self.robotHandle, pointControlPara)
        
        success = result.value == 0
        print(f"MoveJ运动{'成功' if success else '失败'}: {joint_pos}, 返回值: {result.value}")
        return success
    
    def movel(self, pose, speed=None, acc=None, block=False):
        """
        直线运动 (MoveL)
        
        Args:
            pose: 位姿列表 [x, y, z, rx, ry, rz]
            speed: 速度列表，默认 (30, 30, 30, 30, 30, 30)
            acc: 加速度列表，默认 (60, 60, 60, 60, 60, 60)
            block: 是否阻塞等待运动完成
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        
        if speed is None:
            speed = (30, 30, 30, 30, 30, 30)
        if acc is None:
            acc = (60, 60, 60, 60, 60, 60)
        
        # 使用 PointControlParaSimple 创建参数，然后转换为 PointControlPara
        pointControlParaSimple = basestruct.PointControlParaSimple()
        pointControlParaSimple.pose = tuple(pose)
        pointControlParaSimple.jointpos = (0, 0, 0, 0, 0, 0)
        pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
        pointControlParaSimple.tcpID = -1
        pointControlParaSimple.speed = tuple(speed)
        pointControlParaSimple.acc = tuple(acc)
        pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
        pointControlParaSimple.coordinateType = basestruct.CoordinateType.baseCoordinate
        pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
        pointControlParaSimple.motiontriggerMode = 1  # MovetriggerbyOnlyRpc

        # 转换为 PointControlPara
        pointControlPara = basestruct.PointControlPara()
        result_transfer = cgxiapi.cr_move_pointControlPara_transfer(self.robotHandle, pointControlParaSimple, pointControlPara)
        if result_transfer.value != 0:
            print(f"参数转换失败: {result_transfer.value}")
            return False

        # 先尝试非阻塞模式
        result = cgxiapi.cr_moveL(self.robotHandle, pointControlPara)
        success = result.value == 0

        if success and block:
            # 非阻塞调用成功，等待运动完成
            print("  等待运动完成...")
            timeout = 30  # 最大等待30秒
            start_time = time.time()
            while time.time() - start_time < timeout:
                move_success, move_status = self.get_move_status()
                if move_success and move_status == 0:  # 0 = STOPPED
                    break
                time.sleep(0.1)

        print(f"MoveL运动{'成功' if success else '失败'}: {pose}, 返回值: {result.value}")
        return success
    
    # ==================== 工程控制 ====================
    
    def download_program(self, program):
        """
        加载程序
        
        Args:
            program: 程序字符串
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_downloadProgram(self.robotHandle, program)
        success = result.value == 0
        print(f"加载程序{'成功' if success else '失败'}")
        return success
    
    def download_project(self, crp_path, crscript_path):
        """
        下载工程
        
        Args:
            crp_path: .crp文件路径
            crscript_path: .crscript文件路径
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_downloadProject(self.robotHandle, crp_path, crscript_path)
        success = result.value == 0
        print(f"下载工程{'成功' if success else '失败'}")
        return success
    
    def play(self):
        """
        运行程序
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_play(self.robotHandle)
        success = result.value == 0
        print(f"运行程序{'成功' if success else '失败'}")
        return success
    
    def pause(self):
        """
        暂停程序
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_pause(self.robotHandle)
        success = result.value == 0
        print(f"暂停程序{'成功' if success else '失败'}")
        return success
    
    def resume(self):
        """
        恢复程序
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_resume(self.robotHandle)
        success = result.value == 0
        print(f"恢复程序{'成功' if success else '失败'}")
        return success
    
    def stop(self):
        """
        停止程序
        
        Returns:
            bool: 是否成功
        """
        if not self._check_connected():
            return False
        result = cgxiapi.cr_stop(self.robotHandle)
        success = result.value == 0
        print(f"停止程序{'成功' if success else '失败'}")
        return success
    
    def get_script_status(self):
        """
        获取脚本运行状态
        
        Returns:
            tuple: (success, script_status)
        """
        if not self._check_connected():
            return (False, None)
        result = cgxiapi.cr_get_lua_scriptstatus(self.robotHandle)
        success = result[0].value == 0
        status = result[1].value if success else None
        return (success, status)
    
    # ==================== 辅助方法 ====================
    
    def _check_connected(self):
        """检查是否已连接"""
        if not self.connected or self.robotHandle is None:
            print("错误: 机器人未连接")
            return False
        return True
    
    def wait_move_complete(self, timeout=30):
        """
        等待运动完成
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            bool: 是否在超时前完成
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            success, status = self.get_move_status()
            if success and status == 0:
                return True
            time.sleep(0.1)
        print(f"等待运动完成超时")
        return False


class RobotMode:
    """机器人状态码常量"""
    UNDEFINED = 0
    DISCONNECTED = 1
    CONNECTING = 2
    CONNECTED = 3
    DISCONNECTED_STATE = 4
    CONNECTION_ERROR = 5
    POWER_OFF = 6
    POWERING_ON = 7
    POWERED_ON = 8
    ENABLING = 9
    ENABLED = 10
    DISABLING = 11
    DISABLED = 12
    MOVING = 13
    MOVE_COMPLETE = 14
    PAUSING = 15
    PAUSED = 16
    STOPPING = 17
    STOPPED = 18
    ERROR = 19
    ERROR_RECOVERING = 20
    ERROR_RECOVERED = 21
    EMERGENCY_STOPPING = 22
    EMERGENCY_STOPPED = 23
    NOT_ENABLED = 100
    NOT_POWERED = 101
    POWERING = 102
    IDLE = 103
    PAUSED_STATE = 104
    RUNNING = 105
    DRAG_TEACHING = 106
    UPDATING = 107
    UPDATE_COMPLETE = 108
    UPDATE_FAILED = 109


class ScriptStatus:
    """脚本状态常量"""
    NOT_RUNNING = 0
    RUNNING = 1
    PAUSED = 2
    STOPPED = 3


class MoveStatus:
    """运动状态常量"""
    STOPPED = 0
    MOVING = 1


if __name__ == '__main__':
    print("=" * 60)
    print("CGXi 协作机器人工具类测试")
    print("=" * 60)
    
    # 创建机器人实例（虚拟臂）
    robot = CGXiRobot(virtual=True)
    
    # 连接
    print("\n【连接测试】")
    if robot.connect():
        print("连接成功")
        
        # 获取状态
        print("\n【状态测试】")
        success, mode = robot.get_robot_mode()
        if success:
            print(f"机器人状态: {mode}")
        
        success, joint_pos = robot.get_joint_position()
        if success:
            print(f"关节角度: {joint_pos}")
        
        success, tcp_pose = robot.get_tcp_pose()
        if success:
            print(f"TCP位姿: {tcp_pose}")
        
        # 断开连接
        robot.disconnect()
    else:
        print("连接失败")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

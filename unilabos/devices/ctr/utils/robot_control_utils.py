#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
机器人工作函数工具模块
提供机械臂路点记录、两点间移动、键盘控制等功能
"""

import sys
import os
import time
import json
import math
from pathlib import Path
from typing import List, Tuple, Optional, Dict

# 添加SDK路径
sdk_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                        'inf', 'CGXi-Robot-SDK-Python-v2.2e', 
                        'CGXi-Robot-SDK-Python-v2.2e', 'demo', 'python3.7', '64位', 'sdk_test_Python')
sys.path.insert(0, sdk_path)

# 添加SDK DLL路径到系统PATH (Windows需要这样才能找到依赖的DLL)
if os.name == 'nt':
    os.environ['PATH'] = sdk_path + os.pathsep + os.environ.get('PATH', '')

try:
    import cgxiapi
    import basestruct
    from ctypes import *
except ImportError as e:
    # 旧 Python 3.7 SDK 无法在新 Python 版本下导入是预期现象。
    # 推荐路径是用 ``unilabos.devices.fdu.cgxi_native`` 的 ctypes 原生绑定，
    # 这里静默置 None 即可，真正被用到的两个函数 (cr_kineInverse/cr_stop)
    # 目前只在轨迹重现/急停流程里触发，offline 模式不会碰到。
    import logging as _logging
    _logging.getLogger(__name__).debug(
        "cgxiapi.pyd 未加载（%s），将依赖 fdu.cgxi_native 的 ctypes 绑定", e
    )
    cgxiapi = None
    basestruct = None


class Waypoint:
    """路点数据类"""
    
    def __init__(self, name: str = "", joint_pos: List[float] = None, 
                 tcp_pose: List[float] = None, description: str = ""):
        """
        初始化路点
        
        Args:
            name: 路点名称
            joint_pos: 关节角度 [j1, j2, j3, j4, j5, j6]
            tcp_pose: TCP位姿 [x, y, z, rx, ry, rz]
            description: 描述信息
        """
        self.name = name
        self.joint_pos = joint_pos or [0.0] * 6
        self.tcp_pose = tcp_pose or [0.0] * 6
        self.description = description
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "joint_pos": self.joint_pos,
            "tcp_pose": self.tcp_pose,
            "description": self.description,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Waypoint':
        """从字典创建"""
        wp = cls()
        wp.name = data.get("name", "")
        wp.joint_pos = data.get("joint_pos", [0.0] * 6)
        wp.tcp_pose = data.get("tcp_pose", [0.0] * 6)
        wp.description = data.get("description", "")
        wp.timestamp = data.get("timestamp", "")
        return wp
    
    def __str__(self) -> str:
        return f"路点[{self.name}]: J={self.joint_pos}, TCP={self.tcp_pose}"


class RobotController:
    """机器人控制器 - 扩展CGXiRobot功能"""
    
    def __init__(self, robot_instance):
        """
        初始化控制器
        
        Args:
            robot_instance: CGXiRobot实例
        """
        self.robot = robot_instance
        self.waypoints: List[Waypoint] = []
        self.current_waypoint_index = -1
    
    # ==================== 1. 记录机械臂当前路点 ====================
    
    def record_current_waypoint(self, name: str = "", description: str = "") -> Optional[Waypoint]:
        """
        记录机械臂当前路点
        
        Args:
            name: 路点名称（可选）
            description: 描述信息（可选）
        
        Returns:
            Waypoint: 记录的路点对象，失败返回None
        """
        print("\n" + "=" * 60)
        print("📍 记录当前路点")
        print("=" * 60)
        
        if not self.robot or not self.robot.connected:
            print("❌ 机器人未连接")
            return None
        
        # 获取当前关节位置
        success, joint_pos = self.robot.get_joint_position()
        if not success:
            print("❌ 获取关节位置失败")
            return None
        
        # 获取当前TCP位姿
        success, tcp_pose = self.robot.get_tcp_pose()
        if not success:
            print("❌ 获取TCP位姿失败")
            return None
        
        # 创建路点
        if not name:
            name = f"WP_{len(self.waypoints) + 1:03d}"
        
        waypoint = Waypoint(
            name=name,
            joint_pos=joint_pos,
            tcp_pose=tcp_pose,
            description=description
        )
        
        # 添加到列表
        self.waypoints.append(waypoint)
        self.current_waypoint_index = len(self.waypoints) - 1
        
        print(f"✓ 路点记录成功")
        print(f"  名称: {waypoint.name}")
        print(f"  关节: {[f'{j:.2f}°' for j in waypoint.joint_pos]}")
        print(f"  TCP: {[f'{p:.2f}' for p in waypoint.tcp_pose[:3]]} mm, "
              f"{[f'{p:.2f}°' for p in waypoint.tcp_pose[3:]]}")
        
        return waypoint
    
    def get_waypoint(self, index: int) -> Optional[Waypoint]:
        """
        获取指定索引的路点
        
        Args:
            index: 路点索引
        
        Returns:
            Waypoint: 路点对象，失败返回None
        """
        if 0 <= index < len(self.waypoints):
            return self.waypoints[index]
        return None
    
    def list_waypoints(self):
        """列出所有路点"""
        print("\n" + "=" * 60)
        print("📋 路点列表")
        print("=" * 60)
        
        if not self.waypoints:
            print("  暂无记录的路点")
            return
        
        for i, wp in enumerate(self.waypoints):
            marker = " 👈 当前" if i == self.current_waypoint_index else ""
            print(f"\n  [{i}] {wp.name}{marker}")
            print(f"      关节: {[f'{j:.2f}°' for j in wp.joint_pos]}")
            print(f"      TCP: {[f'{p:.2f}' for p in wp.tcp_pose[:3]]}")
            if wp.description:
                print(f"      描述: {wp.description}")
    
    def clear_waypoints(self):
        """清空所有路点"""
        self.waypoints.clear()
        self.current_waypoint_index = -1
        print("✓ 已清空所有路点")
    
    def save_waypoints(self, filepath: str, format: str = "json", append: bool = False, 
                       backup: bool = True) -> bool:
        """
        保存路点到文件
        
        Args:
            filepath: 文件路径
            format: 文件格式 ("json", "csv", "txt")
            append: 是否追加到现有文件（仅CSV格式支持）
            backup: 是否备份现有文件
        
        Returns:
            bool: 是否成功
        """
        try:
            # 确保目录存在
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # 备份现有文件
            if backup and filepath.exists():
                backup_path = filepath.with_suffix(filepath.suffix + '.bak')
                import shutil
                shutil.copy2(filepath, backup_path)
                print(f"📦 已备份现有文件到: {backup_path}")
            
            if format.lower() == "json":
                self._save_json(filepath, append)
            elif format.lower() == "csv":
                self._save_csv(filepath, append)
            elif format.lower() == "txt":
                self._save_txt(filepath, append)
            else:
                print(f"❌ 不支持的格式: {format}")
                return False
            
            print(f"✓ 已保存 {len(self.waypoints)} 个路点到: {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ 保存失败: {e}")
            return False
    
    def _save_json(self, filepath: Path, append: bool):
        """保存为JSON格式"""
        data = {
            "waypoints": [wp.to_dict() for wp in self.waypoints],
            "count": len(self.waypoints),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0"
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_csv(self, filepath: Path, append: bool):
        """保存为CSV格式"""
        import csv
        
        mode = 'a' if append and filepath.exists() else 'w'
        with open(filepath, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 如果是新文件，写入表头
            if mode == 'w':
                writer.writerow([
                    'Index', 'Name', 'J1', 'J2', 'J3', 'J4', 'J5', 'J6',
                    'X', 'Y', 'Z', 'Rx', 'Ry', 'Rz', 'Description', 'Timestamp'
                ])
            
            # 写入路点数据
            for i, wp in enumerate(self.waypoints):
                row = [
                    i, wp.name,
                    f"{wp.joint_pos[0]:.4f}", f"{wp.joint_pos[1]:.4f}",
                    f"{wp.joint_pos[2]:.4f}", f"{wp.joint_pos[3]:.4f}",
                    f"{wp.joint_pos[4]:.4f}", f"{wp.joint_pos[5]:.4f}",
                    f"{wp.tcp_pose[0]:.4f}", f"{wp.tcp_pose[1]:.4f}",
                    f"{wp.tcp_pose[2]:.4f}", f"{wp.tcp_pose[3]:.4f}",
                    f"{wp.tcp_pose[4]:.4f}", f"{wp.tcp_pose[5]:.4f}",
                    wp.description, wp.timestamp
                ]
                writer.writerow(row)
    
    def _save_txt(self, filepath: Path, append: bool):
        """保存为TXT格式"""
        mode = 'a' if append and filepath.exists() else 'w'
        with open(filepath, mode, encoding='utf-8') as f:
            if mode == 'w':
                f.write("=" * 80 + "\n")
                f.write("机器人路点文件\n")
                f.write(f"保存时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"路点数量: {len(self.waypoints)}\n")
                f.write("=" * 80 + "\n\n")
            
            for i, wp in enumerate(self.waypoints):
                f.write(f"路点 [{i}]: {wp.name}\n")
                f.write("-" * 80 + "\n")
                f.write(f"  描述: {wp.description}\n")
                f.write(f"  时间: {wp.timestamp}\n")
                f.write(f"  关节角度: J1={wp.joint_pos[0]:.4f}°, J2={wp.joint_pos[1]:.4f}°, ")
                f.write(f"J3={wp.joint_pos[2]:.4f}°, J4={wp.joint_pos[3]:.4f}°, ")
                f.write(f"J5={wp.joint_pos[4]:.4f}°, J6={wp.joint_pos[5]:.4f}°\n")
                f.write(f"  TCP位姿: X={wp.tcp_pose[0]:.4f}mm, Y={wp.tcp_pose[1]:.4f}mm, ")
                f.write(f"Z={wp.tcp_pose[2]:.4f}mm\n")
                f.write(f"           Rx={wp.tcp_pose[3]:.4f}°, Ry={wp.tcp_pose[4]:.4f}°, ")
                f.write(f"Rz={wp.tcp_pose[5]:.4f}°\n")
                f.write("\n")
    
    def load_waypoints(self, filepath: str, format: str = "auto", 
                       append: bool = False, replace: bool = False) -> bool:
        """
        从文件加载路点
        
        Args:
            filepath: 文件路径
            format: 文件格式 ("auto", "json", "csv", "txt")
            append: 是否追加到现有路点列表
            replace: 是否替换现有路点列表（优先级高于append）
        
        Returns:
            bool: 是否成功
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                print(f"❌ 文件不存在: {filepath}")
                return False
            
            # 自动检测格式
            if format == "auto":
                suffix = filepath.suffix.lower()
                if suffix == ".json":
                    format = "json"
                elif suffix == ".csv":
                    format = "csv"
                elif suffix == ".txt":
                    format = "txt"
                else:
                    print(f"❌ 无法识别文件格式: {suffix}")
                    return False
            
            # 加载路点
            if format.lower() == "json":
                new_waypoints = self._load_json(filepath)
            elif format.lower() == "csv":
                new_waypoints = self._load_csv(filepath)
            elif format.lower() == "txt":
                new_waypoints = self._load_txt(filepath)
            else:
                print(f"❌ 不支持的格式: {format}")
                return False
            
            if not new_waypoints:
                print("❌ 未加载到任何路点")
                return False
            
            # 处理路点列表
            if replace:
                self.waypoints = new_waypoints
                self.current_waypoint_index = -1
                print(f"✓ 已替换 {len(new_waypoints)} 个路点")
            elif append:
                self.waypoints.extend(new_waypoints)
                print(f"✓ 已追加 {len(new_waypoints)} 个路点 (总计: {len(self.waypoints)})")
            else:
                self.waypoints = new_waypoints
                self.current_waypoint_index = -1
                print(f"✓ 已加载 {len(new_waypoints)} 个路点")
            
            return True
            
        except Exception as e:
            print(f"❌ 加载失败: {e}")
            return False
    
    def _load_json(self, filepath: Path) -> List[Waypoint]:
        """从JSON文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        waypoints = [Waypoint.from_dict(wp) for wp in data.get("waypoints", [])]
        print(f"📄 JSON文件版本: {data.get('version', 'unknown')}")
        print(f"📄 保存时间: {data.get('saved_at', 'unknown')}")
        
        return waypoints
    
    def _load_csv(self, filepath: Path) -> List[Waypoint]:
        """从CSV文件加载"""
        import csv
        
        waypoints = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                wp = Waypoint(
                    name=row.get('Name', ''),
                    joint_pos=[
                        float(row.get('J1', 0)),
                        float(row.get('J2', 0)),
                        float(row.get('J3', 0)),
                        float(row.get('J4', 0)),
                        float(row.get('J5', 0)),
                        float(row.get('J6', 0))
                    ],
                    tcp_pose=[
                        float(row.get('X', 0)),
                        float(row.get('Y', 0)),
                        float(row.get('Z', 0)),
                        float(row.get('Rx', 0)),
                        float(row.get('Ry', 0)),
                        float(row.get('Rz', 0))
                    ],
                    description=row.get('Description', '')
                )
                wp.timestamp = row.get('Timestamp', '')
                waypoints.append(wp)
        
        return waypoints
    
    def _load_txt(self, filepath: Path) -> List[Waypoint]:
        """从TXT文件加载"""
        waypoints = []
        current_wp = None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # 检测路点开始
                if line.startswith("路点 ["):
                    if current_wp:
                        waypoints.append(current_wp)
                    idx = line[line.find('[')+1:line.find(']')]
                    name = line[line.find(':')+1:].strip()
                    current_wp = Waypoint(name=name)
                
                # 解析描述
                elif line.startswith("描述:") and current_wp:
                    current_wp.description = line[3:].strip()
                
                # 解析时间
                elif line.startswith("时间:") and current_wp:
                    current_wp.timestamp = line[3:].strip()
                
                # 解析关节角度
                elif line.startswith("关节角度:") and current_wp:
                    import re
                    matches = re.findall(r'J\d+=([-\d.]+)°', line)
                    if len(matches) == 6:
                        current_wp.joint_pos = [float(m) for m in matches]
                
                # 解析TCP位姿
                elif "TCP位姿:" in line and current_wp:
                    import re
                    xyz = re.findall(r'[XYZ]=([-\d.]+)mm', line)
                    rxyz = re.findall(r'R[xyz]=([-\d.]+)°', line)
                    if len(xyz) == 3 and len(rxyz) == 3:
                        current_wp.tcp_pose = [float(v) for v in xyz + rxyz]
            
            # 添加最后一个路点
            if current_wp:
                waypoints.append(current_wp)
        
        return waypoints
    
    def export_waypoints(self, filepath: str, format: str = "csv"):
        """
        导出路点（别名，用于向后兼容）
        
        Args:
            filepath: 文件路径
            format: 文件格式
        
        Returns:
            bool: 是否成功
        """
        return self.save_waypoints(filepath, format=format)
    
    def import_waypoints(self, filepath: str, format: str = "auto", append: bool = False):
        """
        导入路点（别名，用于向后兼容）
        
        Args:
            filepath: 文件路径
            format: 文件格式
            append: 是否追加
        
        Returns:
            bool: 是否成功
        """
        return self.load_waypoints(filepath, format=format, append=append)
    
    def validate_waypoints_file(self, filepath: str) -> Tuple[bool, str]:
        """
        验证路点文件
        
        Args:
            filepath: 文件路径
        
        Returns:
            tuple: (是否有效, 错误信息)
        """
        try:
            filepath = Path(filepath)
            
            if not filepath.exists():
                return (False, "文件不存在")
            
            suffix = filepath.suffix.lower()
            
            if suffix == ".json":
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if "waypoints" not in data:
                    return (False, "缺少waypoints字段")
                
                if not isinstance(data["waypoints"], list):
                    return (False, "waypoints必须是列表")
                
                return (True, f"JSON文件有效，包含{len(data['waypoints'])}个路点")
            
            elif suffix == ".csv":
                import csv
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if len(rows) < 2:
                        return (False, "CSV文件为空")
                    return (True, f"CSV文件有效，包含{len(rows)-1}个路点")
            
            elif suffix == ".txt":
                count = filepath.read_text(encoding='utf-8').count("路点 [")
                if count == 0:
                    return (False, "TXT文件不包含路点")
                return (True, f"TXT文件有效，包含{count}个路点")
            
            else:
                return (False, f"不支持的文件格式: {suffix}")
            
        except Exception as e:
            return (False, f"验证失败: {e}")
    
    # ==================== 2. 基于两个路点移动机械臂 ====================
    
    def move_between_waypoints(self, start_idx: int, end_idx: int, 
                               speed: float = 30.0, acc: float = 60.0,
                               use_joint_space: bool = True,
                               block: bool = True) -> bool:
        """
        基于两个路点移动机械臂
        
        Args:
            start_idx: 起始路点索引
            end_idx: 目标路点索引
            speed: 速度
            acc: 加速度
            use_joint_space: 是否使用关节空间运动（True=MoveJ, False=MoveL）
            block: 是否阻塞等待
        
        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 60)
        print(f"🚀 路点间移动: [{start_idx}] -> [{end_idx}]")
        print("=" * 60)
        
        # 验证路点索引
        if not (0 <= start_idx < len(self.waypoints)):
            print(f"❌ 起始路点索引 {start_idx} 无效")
            return False
        
        if not (0 <= end_idx < len(self.waypoints)):
            print(f"❌ 目标路点索引 {end_idx} 无效")
            return False
        
        start_wp = self.waypoints[start_idx]
        end_wp = self.waypoints[end_idx]
        
        print(f"起始路点: {start_wp.name}")
        print(f"目标路点: {end_wp.name}")
        print(f"运动方式: {'关节空间(MoveJ)' if use_joint_space else '笛卡尔空间(MoveL)'}")
        print(f"速度: {speed}, 加速度: {acc}")
        
        # 先移动到起始路点
        print(f"\n📍 步骤1: 移动到起始路点 [{start_idx}]")
        if use_joint_space:
            result = self.robot.movej(start_wp.joint_pos, 
                                      speed=[speed]*6, 
                                      acc=[acc]*6, 
                                      block=True)
        else:
            result = self.robot.movel(start_wp.tcp_pose, 
                                      speed=[speed]*6, 
                                      acc=[acc]*6, 
                                      block=True)
        
        if not result:
            print("❌ 移动到起始路点失败")
            return False
        
        print("✓ 已到达起始路点")
        
        # 再移动到目标路点
        print(f"\n📍 步骤2: 移动到目标路点 [{end_idx}]")
        if use_joint_space:
            result = self.robot.movej(end_wp.joint_pos, 
                                      speed=[speed]*6, 
                                      acc=[acc]*6, 
                                      block=block)
        else:
            result = self.robot.movel(end_wp.tcp_pose, 
                                      speed=[speed]*6, 
                                      acc=[acc]*6, 
                                      block=block)
        
        if result:
            self.current_waypoint_index = end_idx
            print("✓ 已到达目标路点")
        else:
            print("❌ 移动到目标路点失败")
        
        return result
    
    def move_to_waypoint(self, index: int, speed: float = 30.0, 
                         acc: float = 60.0, use_joint_space: bool = True,
                         block: bool = True) -> bool:
        """
        移动到指定路点
        
        Args:
            index: 路点索引
            speed: 速度
            acc: 加速度
            use_joint_space: 是否使用关节空间运动
            block: 是否阻塞等待
        
        Returns:
            bool: 是否成功
        """
        if not (0 <= index < len(self.waypoints)):
            print(f"❌ 路点索引 {index} 无效")
            return False
        
        wp = self.waypoints[index]
        print(f"\n📍 移动到路点 [{index}]: {wp.name}")
        
        if use_joint_space:
            result = self.robot.movej(wp.joint_pos, 
                                      speed=[speed]*6, 
                                      acc=[acc]*6, 
                                      block=block)
        else:
            result = self.robot.movel(wp.tcp_pose, 
                                      speed=[speed]*6, 
                                      acc=[acc]*6, 
                                      block=block)
        
        if result:
            self.current_waypoint_index = index
            print("✓ 已到达目标路点")
        
        return result
    
    def move_along_waypoints(self, indices: List[int], speed: float = 30.0,
                            acc: float = 60.0, use_joint_space: bool = True,
                            dwell_time: float = 0.0) -> bool:
        """
        沿多个路点顺序移动
        
        Args:
            indices: 路点索引列表
            speed: 速度
            acc: 加速度
            use_joint_space: 是否使用关节空间运动
            dwell_time: 每个路点停留时间（秒）
        
        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 60)
        print(f"🚀 沿路点序列移动: {indices}")
        print("=" * 60)
        
        for i, idx in enumerate(indices):
            print(f"\n步骤 {i+1}/{len(indices)}: 移动到路点 [{idx}]")
            
            if not self.move_to_waypoint(idx, speed, acc, use_joint_space, block=True):
                print(f"❌ 移动到路点 [{idx}] 失败，停止序列")
                return False
            
            if dwell_time > 0 and i < len(indices) - 1:
                print(f"⏳ 停留 {dwell_time} 秒...")
                time.sleep(dwell_time)
        
        print("\n✓ 路点序列移动完成")
        return True
    
    # ==================== 世界坐标系移动和末端垂直 ====================
    
    def move_world_z(self, distance: float, speed: float = 30.0,
                     acc: float = 60.0, block: bool = True) -> bool:
        """
        在世界坐标系Z轴方向移动（上下移动）
        使用逆运动学计算关节角度，然后用MoveJ运动（避免奇异点问题）

        Args:
            distance: 移动距离 (mm)，正值向上，负值向下
            speed: 速度
            acc: 加速度
            block: 是否阻塞等待

        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 60)
        print(f"📍 世界坐标系Z轴移动: {distance:+.2f} mm")
        print("=" * 60)

        # 获取当前TCP位姿
        success, current_pose = self.robot.get_tcp_pose()
        if not success:
            print("❌ 无法获取当前TCP位姿")
            return False

        print(f"当前位置: X={current_pose[0]:.2f}, Y={current_pose[1]:.2f}, Z={current_pose[2]:.2f}")

        # 计算目标位置（只改变Z坐标）
        target_pose = [float(x) for x in current_pose]
        target_pose[2] += distance  # Z轴移动

        direction = "向上" if distance > 0 else "向下"
        print(f"目标位置: X={target_pose[0]:.2f}, Y={target_pose[1]:.2f}, Z={target_pose[2]:.2f} ({direction})")

        # 获取当前关节角度
        success_j, current_joints = self.robot.get_joint_position()
        if not success_j:
            print("❌ 无法获取当前关节角度")
            return False

        print(f"当前关节: {[f'{j:.2f}' for j in current_joints]}")

        # 使用逆运动学计算目标关节角度
        print("  计算逆运动学...")
        try:
            import cgxiapi
            target_joints = [0.0] * 6
            # cr_kineInverse(robotHandle, toolPosition, refJointPos, jointPos)
            # self.robot 是 RobotController, RobotController.robot 是 CGXiRobot
            robot_handle = self.robot.robotHandle
            result = cgxiapi.cr_kineInverse(robot_handle, target_pose, current_joints, target_joints)
            if result.value != 0:
                print(f"❌ 逆运动学计算失败，返回值: {result.value}")
                return False
            print(f"目标关节: {[f'{j:.2f}' for j in target_joints]}")
        except Exception as e:
            print(f"❌ 逆运动学计算异常: {e}")
            return False

        # 检查机器人状态，确保已使能
        print("  检查机器人状态...")
        success_mode, mode = self.robot.get_robot_mode()
        if success_mode:
            mode_names = {
                0: "初始化", 1: "未连接", 2: "未上电", 3: "上电中",
                4: "去使能", 5: "使能中", 6: "使能", 7: "运行中",
                8: "本体已上电", 9: "暂停", 10: "恢复中", 11: "拖动中"
            }
            mode_name = mode_names.get(mode, f"未知({mode})")
            print(f"    当前状态: {mode_name}")
            if mode != 6:  # 6 = 使能状态
                print(f"    机器人未使能，尝试使能...")
                self.robot.enable()
                time.sleep(0.5)
        else:
            print("    无法获取机器人状态")

        # 使用MoveL直线运动，分多步执行以避免奇异点
        print("  使用直线运动(MoveL)，分步执行...")
        move_success = self._move_z_step_by_step(current_pose, target_pose, speed, acc)

        # 验证运动结果
        time.sleep(0.5)
        success2, final_pose = self.robot.get_tcp_pose()

        if success2:
            # 检查Z轴实际移动距离是否接近目标
            actual_z_move = abs(final_pose[2] - current_pose[2])
            target_z_move = abs(distance)
            z_move_diff = abs(actual_z_move - target_z_move)
            print(f"  Z轴目标移动: {target_z_move:.2f}mm, 实际移动: {actual_z_move:.2f}mm, 差值: {z_move_diff:.2f}mm")

            # 如果Z轴移动距离接近目标（允许10mm误差），认为成功
            if z_move_diff < 10.0:
                print(f"✓ Z轴移动完成 (实际位置: X={final_pose[0]:.2f}, Y={final_pose[1]:.2f}, Z={final_pose[2]:.2f})")
                return True
            else:
                # 计算位置偏差
                dx = final_pose[0] - target_pose[0]
                dy = final_pose[1] - target_pose[1]
                dz = final_pose[2] - target_pose[2]
                pos_diff = math.sqrt(dx*dx + dy*dy + dz*dz)
                print(f"❌ Z轴移动失败，位置偏差: {pos_diff:.2f}mm")
                return False
        else:
            print(f"❌ 无法获取最终位置")
            return False
    
    def move_world_relative(self, dx: float = 0, dy: float = 0, dz: float = 0,
                           speed: float = 30.0, acc: float = 60.0,
                           block: bool = True) -> bool:
        """
        在世界坐标系相对移动
        
        Args:
            dx: X轴偏移 (mm)
            dy: Y轴偏移 (mm)
            dz: Z轴偏移 (mm)
            speed: 速度
            acc: 加速度
            block: 是否阻塞等待
        
        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 60)
        print(f"📍 世界坐标系相对移动: dx={dx:+.2f}, dy={dy:+.2f}, dz={dz:+.2f} mm")
        print("=" * 60)
        
        # 获取当前TCP位姿
        success, current_pose = self.robot.get_tcp_pose()
        if not success:
            print("❌ 无法获取当前TCP位姿")
            return False
        
        print(f"当前位置: {[f'{p:.2f}' for p in current_pose]}")
        
        # 计算目标位置
        target_pose = current_pose.copy()
        target_pose[0] += dx
        target_pose[1] += dy
        target_pose[2] += dz
        
        print(f"目标位置: {[f'{p:.2f}' for p in target_pose]}")
        
        # 执行直线运动
        result = self.robot.movel(target_pose, speed=[speed]*6, acc=[acc]*6, block=block)
        
        if result:
            print(f"✓ 相对移动完成")
        else:
            print(f"❌ 相对移动失败")

        return result

    def _move_z_step_by_step(self, start_pose, target_pose, speed, acc, step_size=10.0):
        """
        分步执行Z轴移动，每步移动step_size毫米，避免奇异点问题

        Args:
            start_pose: 起始位姿
            target_pose: 目标位姿
            speed: 速度
            acc: 加速度
            step_size: 每步移动距离(mm)

        Returns:
            bool: 是否成功
        """
        total_z_move = target_pose[2] - start_pose[2]
        num_steps = max(1, int(abs(total_z_move) / step_size))
        z_step = total_z_move / num_steps

        print(f"  分{num_steps}步执行，每步{z_step:.2f}mm")

        current_z = start_pose[2]
        for i in range(num_steps):
            current_z += z_step
            step_target = [float(x) for x in start_pose]
            step_target[2] = current_z

            print(f"    步骤{i+1}/{num_steps}: Z={current_z:.2f}mm")

            # 使用MoveL执行单步
            result = self.robot.movel(step_target, speed=[speed]*6, acc=[acc]*6, block=True)

            if not result:
                print(f"    步骤{i+1}失败，尝试故障复位...")
                self.robot.fault_reset()
                time.sleep(0.3)
                # 重试一次
                result = self.robot.movel(step_target, speed=[speed]*6, acc=[acc]*6, block=True)
                if not result:
                    print(f"    步骤{i+1}重试失败")
                    return False

            time.sleep(0.2)

        print(f"  ✓ 分步移动完成")
        return True

    def set_tcp_vertical(self, speed: float = 30.0, acc: float = 60.0,
                         block: bool = True) -> bool:
        """
        使TCP末端垂直向下（Rx=180°, Ry=0°, Rz=0°）
        
        Args:
            speed: 速度
            acc: 加速度
            block: 是否阻塞等待
        
        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 60)
        print("📐 设置TCP末端垂直向下")
        print("=" * 60)
        
        # 获取当前TCP位姿
        success, current_pose = self.robot.get_tcp_pose()
        if not success:
            print("❌ 无法获取当前TCP位姿")
            return False
        
        print(f"当前位姿: X={current_pose[0]:.2f}, Y={current_pose[1]:.2f}, Z={current_pose[2]:.2f}")
        print(f"当前姿态: Rx={current_pose[3]:.2f}°, Ry={current_pose[4]:.2f}°, Rz={current_pose[5]:.2f}°")
        
        # 设置目标姿态（垂直向下）
        # Rx=180° 表示绕X轴旋转180度，使Z轴指向下方
        target_pose = current_pose.copy()
        target_pose[3] = 180.0  # Rx
        target_pose[4] = 0.0    # Ry
        target_pose[5] = 0.0    # Rz
        
        print(f"目标姿态: Rx={target_pose[3]:.2f}°, Ry={target_pose[4]:.2f}°, Rz={target_pose[5]:.2f}°")
        
        # 执行直线运动
        result = self.robot.movel(target_pose, speed=[speed]*6, acc=[acc]*6, block=block)
        
        # 验证运动结果（即使返回值显示失败，也检查实际位置）
        time.sleep(0.5)  # 等待运动稳定
        success2, final_pose = self.robot.get_tcp_pose()
        
        if success2:
            print(f"最终姿态: Rx={final_pose[3]:.2f}°, Ry={final_pose[4]:.2f}°, Rz={final_pose[5]:.2f}°")
            
            # 检查姿态是否接近目标（考虑角度周期性）
            rx_diff = abs(self._normalize_angle(final_pose[3] - target_pose[3]))
            ry_diff = abs(self._normalize_angle(final_pose[4] - target_pose[4]))
            rz_diff = abs(self._normalize_angle(final_pose[5] - target_pose[5]))
            
            tolerance = 5.0  # 5度容差
            
            if rx_diff < tolerance and ry_diff < tolerance and rz_diff < tolerance:
                print(f"✓ TCP已调整为垂直向下 (误差: Rx={rx_diff:.2f}°, Ry={ry_diff:.2f}°, Rz={rz_diff:.2f}°)")
                return True
            else:
                print(f"⚠️ 姿态调整未完全达到目标 (误差: Rx={rx_diff:.2f}°, Ry={ry_diff:.2f}°, Rz={rz_diff:.2f}°)")
                return False
        else:
            if result:
                print(f"✓ TCP已调整为垂直向下")
            else:
                print(f"❌ 调整失败")
            return result
    
    def _normalize_angle(self, angle: float) -> float:
        """
        归一化角度到 [-180, 180] 范围
        
        Args:
            angle: 角度值
        
        Returns:
            float: 归一化后的角度
        """
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle
    
    def set_tcp_orientation(self, rx: float, ry: float, rz: float,
                           speed: float = 30.0, acc: float = 60.0,
                           block: bool = True) -> bool:
        """
        设置TCP姿态（保持位置不变）
        
        Args:
            rx: 绕X轴旋转角度 (°)
            ry: 绕Y轴旋转角度 (°)
            rz: 绕Z轴旋转角度 (°)
            speed: 速度
            acc: 加速度
            block: 是否阻塞等待
        
        Returns:
            bool: 是否成功
        """
        print("\n" + "=" * 60)
        print(f"📐 设置TCP姿态: Rx={rx:.2f}°, Ry={ry:.2f}°, Rz={rz:.2f}°")
        print("=" * 60)
        
        # 获取当前TCP位姿
        success, current_pose = self.robot.get_tcp_pose()
        if not success:
            print("❌ 无法获取当前TCP位姿")
            return False
        
        # 保持位置，只改变姿态
        target_pose = current_pose.copy()
        target_pose[3] = rx
        target_pose[4] = ry
        target_pose[5] = rz
        
        print(f"当前位置: X={current_pose[0]:.2f}, Y={current_pose[1]:.2f}, Z={current_pose[2]:.2f}")
        print(f"目标姿态: Rx={rx:.2f}°, Ry={ry:.2f}°, Rz={rz:.2f}°")
        
        # 执行直线运动
        result = self.robot.movel(target_pose, speed=[speed]*6, acc=[acc]*6, block=block)
        
        # 验证运动结果
        time.sleep(0.5)  # 等待运动稳定
        success2, final_pose = self.robot.get_tcp_pose()
        
        if success2:
            print(f"最终姿态: Rx={final_pose[3]:.2f}°, Ry={final_pose[4]:.2f}°, Rz={final_pose[5]:.2f}°")
            
            # 检查姿态是否接近目标（考虑角度周期性）
            rx_diff = abs(self._normalize_angle(final_pose[3] - rx))
            ry_diff = abs(self._normalize_angle(final_pose[4] - ry))
            rz_diff = abs(self._normalize_angle(final_pose[5] - rz))
            
            tolerance = 5.0  # 5度容差
            
            if rx_diff < tolerance and ry_diff < tolerance and rz_diff < tolerance:
                print(f"✓ TCP姿态已调整 (误差: Rx={rx_diff:.2f}°, Ry={ry_diff:.2f}°, Rz={rz_diff:.2f}°)")
                return True
            else:
                print(f"⚠️ 姿态调整未完全达到目标 (误差: Rx={rx_diff:.2f}°, Ry={ry_diff:.2f}°, Rz={rz_diff:.2f}°)")
                return False
        else:
            if result:
                print(f"✓ TCP姿态已调整")
            else:
                print(f"❌ 调整失败")
            return result


# ==================== 3. 键盘控制机械臂移动 ====================

class KeyboardController:
    """键盘控制器 - 用于手动控制机械臂"""
    
    def __init__(self, robot_instance):
        """
        初始化键盘控制器
        
        Args:
            robot_instance: CGXiRobot实例
        """
        self.robot = robot_instance
        self.running = False
        self.step_size = 5.0  # 默认步进大小 (mm 或 degree)
        self.speed = 50.0     # 点动速度
        self.coordinate_type = "cartesian"  # "cartesian" 或 "joint"
        
        # 控制键映射
        self.key_map = {
            # 笛卡尔空间控制 (TCP坐标系)
            'w': ('cartesian', 'y', 1),      # Y+ (上)
            's': ('cartesian', 'y', -1),     # Y- (下)
            'a': ('cartesian', 'x', -1),     # X- (左)
            'd': ('cartesian', 'x', 1),      # X+ (右)
            'q': ('cartesian', 'z', 1),      # Z+ (上升)
            'e': ('cartesian', 'z', -1),     # Z- (下降)
            'r': ('cartesian', 'rx', 1),     # Rx+ (绕X旋转)
            'f': ('cartesian', 'rx', -1),    # Rx- 
            't': ('cartesian', 'ry', 1),     # Ry+ (绕Y旋转)
            'g': ('cartesian', 'ry', -1),    # Ry-
            'y': ('cartesian', 'rz', 1),     # Rz+ (绕Z旋转 - 顺时针)
            'h': ('cartesian', 'rz', -1),    # Rz- (逆时针)
            
            # 关节空间控制
            '1': ('joint', 0, 1),   # J1+
            '2': ('joint', 0, -1),  # J1-
            '3': ('joint', 1, 1),   # J2+
            '4': ('joint', 1, -1),  # J2-
            '5': ('joint', 2, 1),   # J3+
            '6': ('joint', 2, -1),  # J3-
            '7': ('joint', 3, 1),   # J4+
            '8': ('joint', 3, -1),  # J4-
            '9': ('joint', 4, 1),   # J5+
            '0': ('joint', 4, -1),  # J5-
            '-': ('joint', 5, 1),   # J6+
            '=': ('joint', 5, -1),  # J6-
        }
        
        # 用于记录路点的回调
        self.waypoint_callback = None
    
    def print_help(self):
        """打印帮助信息"""
        print("\n" + "=" * 70)
        print("🎮 键盘控制说明")
        print("=" * 70)
        print("\n【笛卡尔空间控制 (TCP坐标系)】")
        print("  W/S - Y轴 +/- (上/下)")
        print("  A/D - X轴 +/- (左/右)")
        print("  Q/E - Z轴 +/- (上升/下降)")
        print("  R/F - 绕X轴旋转 +/-")
        print("  T/G - 绕Y轴旋转 +/-")
        print("  Y/H - 绕Z轴旋转 +/- (顺时针/逆时针)")
        print("\n【关节空间控制】")
        print("  1/2 - J1 +/-")
        print("  3/4 - J2 +/-")
        print("  5/6 - J3 +/-")
        print("  7/8 - J4 +/-")
        print("  9/0 - J5 +/-")
        print("  -/= - J6 +/-")
        print("\n【其他控制】")
        print("  +/- - 调整步进大小")
        print("  [/] - 调整速度")
        print("  C   - 切换坐标系 (笛卡尔/关节)")
        print("  P   - 打印当前位置")
        print("  R   - 记录当前路点")
        print("  Space - 停止运动")
        print("  ESC/Q - 退出控制")
        print("=" * 70)
        print(f"当前设置: 步进={self.step_size}mm/°, 速度={self.speed}, 坐标系={self.coordinate_type}")
        print("=" * 70)
    
    def get_current_pose(self) -> Tuple[List[float], List[float]]:
        """获取当前位姿"""
        success, joint_pos = self.robot.get_joint_position()
        success2, tcp_pose = self.robot.get_tcp_pose()
        return joint_pos if success else None, tcp_pose if success2 else None
    
    def move_cartesian(self, axis: str, direction: int):
        """
        笛卡尔空间移动
        
        Args:
            axis: 轴名 (x, y, z, rx, ry, rz)
            direction: 方向 (1 或 -1)
        """
        joint_pos, tcp_pose = self.get_current_pose()
        if tcp_pose is None:
            print("❌ 无法获取当前位姿")
            return False
        
        # 计算目标位姿
        target_pose = tcp_pose.copy()
        axis_idx = ['x', 'y', 'z', 'rx', 'ry', 'rz'].index(axis)
        target_pose[axis_idx] += direction * self.step_size
        
        print(f"笛卡尔移动: {axis}{'+' if direction > 0 else '-'} {self.step_size}")
        print(f"  从: {[f'{p:.2f}' for p in tcp_pose]}")
        print(f"  到: {[f'{p:.2f}' for p in target_pose]}")
        
        return self.robot.movel(target_pose, speed=[self.speed]*6, block=False)
    
    def move_joint(self, joint_idx: int, direction: int):
        """
        关节空间移动
        
        Args:
            joint_idx: 关节索引 (0-5)
            direction: 方向 (1 或 -1)
        """
        joint_pos, tcp_pose = self.get_current_pose()
        if joint_pos is None:
            print("❌ 无法获取当前关节位置")
            return False
        
        # 计算目标关节位置
        target_joints = joint_pos.copy()
        target_joints[joint_idx] += direction * self.step_size
        
        print(f"关节移动: J{joint_idx+1}{'+' if direction > 0 else '-'} {self.step_size}°")
        print(f"  从: {[f'{j:.2f}°' for j in joint_pos]}")
        print(f"  到: {[f'{j:.2f}°' for j in target_joints]}")
        
        return self.robot.movej(target_joints, speed=[self.speed]*6, block=False)
    
    def handle_key(self, key: str) -> bool:
        """
        处理按键
        
        Args:
            key: 按键字符
        
        Returns:
            bool: 是否继续运行
        """
        key = key.lower()
        
        # 退出控制
        if key in ['\x1b', 'q']:  # ESC 或 Q
            print("\n👋 退出键盘控制")
            return False
        
        # 停止运动
        if key == ' ':
            print("\n⏹ 停止运动")
            try:
                # 尝试停止运动
                if cgxiapi:
                    result = cgxiapi.cr_stop(self.robot.robotHandle)
                    print(f"  停止结果: {result.value}")
            except Exception as e:
                print(f"  停止运动异常: {e}")
            return True
        
        # 打印帮助
        if key == '?':
            self.print_help()
            return True
        
        # 打印当前位置
        if key == 'p':
            joint_pos, tcp_pose = self.get_current_pose()
            print("\n📍 当前位置:")
            if joint_pos:
                print(f"  关节: {[f'{j:.2f}°' for j in joint_pos]}")
            if tcp_pose:
                print(f"  TCP:  {[f'{p:.2f}' for p in tcp_pose[:3]]} mm")
                print(f"        {[f'{p:.2f}°' for p in tcp_pose[3:]]}")
            return True
        
        # 记录路点
        if key == 'r':
            if self.waypoint_callback:
                print("\n💾 记录当前路点...")
                self.waypoint_callback()
            else:
                print("\n💡 提示: 未设置路点记录回调函数")
            return True
        
        # 调整步进大小
        if key == '+':
            self.step_size = min(self.step_size * 1.5, 100.0)
            print(f"\n📏 步进大小调整为: {self.step_size:.2f}")
            return True
        
        if key == '-':
            self.step_size = max(self.step_size / 1.5, 0.1)
            print(f"\n📏 步进大小调整为: {self.step_size:.2f}")
            return True
        
        # 调整速度
        if key == ']':
            self.speed = min(self.speed + 10, 100)
            print(f"\n⚡ 速度调整为: {self.speed}")
            return True
        
        if key == '[':
            self.speed = max(self.speed - 10, 1)
            print(f"\n⚡ 速度调整为: {self.speed}")
            return True
        
        # 切换坐标系
        if key == 'c':
            self.coordinate_type = "joint" if self.coordinate_type == "cartesian" else "cartesian"
            print(f"\n🔄 切换到{'关节空间' if self.coordinate_type == 'joint' else '笛卡尔空间'}控制")
            return True
        
        # 处理运动控制键
        if key in self.key_map:
            coord_type, axis_or_joint, direction = self.key_map[key]
            
            if coord_type == 'cartesian':
                self.move_cartesian(axis_or_joint, direction)
            else:
                self.move_joint(axis_or_joint, direction)
            
            return True
        
        # 未知按键
        print(f"\n❓ 未知按键: '{key}'，按 ? 查看帮助")
        return True
    
    def run(self):
        """运行键盘控制循环"""
        print("\n" + "=" * 70)
        print("🎮 启动键盘控制模式")
        print("=" * 70)
        
        if not self.robot or not self.robot.connected:
            print("❌ 机器人未连接")
            return
        
        self.print_help()
        self.running = True
        
        try:
            while self.running:
                # 读取按键 (跨平台方式)
                try:
                    import msvcrt  # Windows
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8', errors='ignore')
                        self.running = self.handle_key(key)
                    else:
                        time.sleep(0.01)
                except ImportError:
                    # Linux/Mac
                    import select
                    import tty
                    import termios
                    
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setcbreak(fd)
                        if select.select([sys.stdin], [], [], 0.01)[0]:
                            key = sys.stdin.read(1)
                            self.running = self.handle_key(key)
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        except KeyboardInterrupt:
            print("\n👋 用户中断")
        
        print("\n✓ 键盘控制已退出")


# ==================== 便捷函数 ====================

def create_robot_controller(robot_instance) -> RobotController:
    """
    创建机器人控制器
    
    Args:
        robot_instance: CGXiRobot实例
    
    Returns:
        RobotController: 控制器实例
    """
    return RobotController(robot_instance)


def create_keyboard_controller(robot_instance) -> KeyboardController:
    """
    创建键盘控制器
    
    Args:
        robot_instance: CGXiRobot实例
    
    Returns:
        KeyboardController: 键盘控制器实例
    """
    return KeyboardController(robot_instance)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("=" * 70)
    print("机器人控制工具模块")
    print("=" * 70)
    print("\n本模块提供以下功能:")
    print("  1. 路点记录与管理 (RobotController)")
    print("  2. 路点间移动")
    print("  3. 键盘控制 (KeyboardController)")
    print("\n使用示例:")
    print("  from robot_control_utils import create_robot_controller, create_keyboard_controller")
    print("  from robot_utils import CGXiRobot")
    print("")
    print("  # 连接机器人")
    print("  robot = CGXiRobot(ip='192.168.6.6')")
    print("  robot.connect()")
    print("")
    print("  # 创建控制器")
    print("  controller = create_robot_controller(robot)")
    print("")
    print("  # 记录路点")
    print("  controller.record_current_waypoint('起点')")
    print("")
    print("  # 键盘控制")
    print("  kb = create_keyboard_controller(robot)")
    print("  kb.run()")

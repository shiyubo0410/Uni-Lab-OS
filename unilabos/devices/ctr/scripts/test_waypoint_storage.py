#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路点文件存储功能测试脚本
测试JSON、CSV、TXT格式的保存和加载
"""

import sys
import os
from pathlib import Path

# 添加路径
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'utils'))
sys.path.insert(0, str(SCRIPT_DIR.parent / 'skills' / 'changguangxi'))

try:
    from robot_utils import CGXiRobot
    from robot_control_utils import create_robot_controller, Waypoint
except ImportError as e:
    print(f"❌ 无法导入模块 - {e}")
    sys.exit(1)


def test_json_format(controller):
    """测试JSON格式"""
    print("\n" + "=" * 70)
    print("📄 测试1: JSON格式")
    print("=" * 70)
    
    # 创建测试路点
    controller.waypoints.clear()
    controller.record_current_waypoint("起点", "测试起点")
    controller.record_current_waypoint("中间点", "测试中间点")
    controller.record_current_waypoint("终点", "测试终点")
    
    # 保存为JSON
    json_path = SCRIPT_DIR / "test_waypoints.json"
    controller.save_waypoints(str(json_path), format="json")
    
    # 清空路点
    controller.clear_waypoints()
    print(f"\n清空后路点数: {len(controller.waypoints)}")
    
    # 加载JSON
    controller.load_waypoints(str(json_path), format="json")
    print(f"加载后路点数: {len(controller.waypoints)}")
    
    # 验证
    valid, msg = controller.validate_waypoints_file(str(json_path))
    print(f"验证结果: {msg}")
    
    return True


def test_csv_format(controller):
    """测试CSV格式"""
    print("\n" + "=" * 70)
    print("📊 测试2: CSV格式")
    print("=" * 70)
    
    # 创建测试路点
    controller.waypoints.clear()
    controller.record_current_waypoint("CSV起点", "CSV测试起点")
    controller.record_current_waypoint("CSV中间点", "CSV测试中间点")
    
    # 保存为CSV
    csv_path = SCRIPT_DIR / "test_waypoints.csv"
    controller.save_waypoints(str(csv_path), format="csv")
    
    print(f"\n💡 CSV文件可以用Excel打开: {csv_path}")
    
    # 清空路点
    controller.clear_waypoints()
    
    # 追加新路点到CSV
    controller.record_current_waypoint("CSV终点", "CSV测试终点")
    controller.save_waypoints(str(csv_path), format="csv", append=True)
    
    # 加载CSV
    controller.load_waypoints(str(csv_path), format="csv")
    print(f"加载后路点数: {len(controller.waypoints)}")
    
    # 验证
    valid, msg = controller.validate_waypoints_file(str(csv_path))
    print(f"验证结果: {msg}")
    
    return True


def test_txt_format(controller):
    """测试TXT格式"""
    print("\n" + "=" * 70)
    print("📝 测试3: TXT格式")
    print("=" * 70)
    
    # 创建测试路点
    controller.waypoints.clear()
    controller.record_current_waypoint("TXT起点", "TXT测试起点")
    controller.record_current_waypoint("TXT终点", "TXT测试终点")
    
    # 保存为TXT
    txt_path = SCRIPT_DIR / "test_waypoints.txt"
    controller.save_waypoints(str(txt_path), format="txt")
    
    print(f"\n💡 TXT文件内容预览:")
    print("-" * 70)
    with open(txt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[:20]:
            print(line.rstrip())
        if len(lines) > 20:
            print(f"... (共{len(lines)}行)")
    print("-" * 70)
    
    # 清空路点
    controller.clear_waypoints()
    
    # 加载TXT
    controller.load_waypoints(str(txt_path), format="txt")
    print(f"加载后路点数: {len(controller.waypoints)}")
    
    # 验证
    valid, msg = controller.validate_waypoints_file(str(txt_path))
    print(f"验证结果: {msg}")
    
    return True


def test_format_conversion(controller):
    """测试格式转换"""
    print("\n" + "=" * 70)
    print("🔄 测试4: 格式转换")
    print("=" * 70)
    
    # 创建测试路点
    controller.waypoints.clear()
    for i in range(5):
        controller.record_current_waypoint(f"路点{i+1}", f"第{i+1}个测试路点")
    
    # 转换为不同格式
    formats = ["json", "csv", "txt"]
    for fmt in formats:
        filepath = SCRIPT_DIR / f"waypoints_convert.{fmt}"
        controller.save_waypoints(str(filepath), format=fmt, backup=False)
        print(f"✓ 已保存为 {fmt.upper()} 格式: {filepath.name}")
    
    # 从不同格式加载
    for fmt in formats:
        filepath = SCRIPT_DIR / f"waypoints_convert.{fmt}"
        controller.waypoints.clear()
        controller.load_waypoints(str(filepath), format=fmt)
        print(f"✓ 从 {fmt.upper()} 格式加载: {len(controller.waypoints)} 个路点")
    
    return True


def test_backup_and_append(controller):
    """测试备份和追加功能"""
    print("\n" + "=" * 70)
    print("📦 测试5: 备份和追加")
    print("=" * 70)
    
    # 创建初始路点
    controller.waypoints.clear()
    controller.record_current_waypoint("初始路点1", "初始路点")
    controller.record_current_waypoint("初始路点2", "初始路点")
    
    # 保存
    filepath = SCRIPT_DIR / "test_backup.json"
    controller.save_waypoints(str(filepath), format="json", backup=False)
    print(f"✓ 初始保存: {len(controller.waypoints)} 个路点")
    
    # 添加新路点
    controller.record_current_waypoint("追加路点1", "追加的路点")
    controller.record_current_waypoint("追加路点2", "追加的路点")
    
    # 再次保存（会备份）
    controller.save_waypoints(str(filepath), format="json", backup=True)
    
    # 检查备份文件
    backup_path = filepath.with_suffix(filepath.suffix + '.bak')
    if backup_path.exists():
        print(f"✓ 备份文件已创建: {backup_path.name}")
    
    # 测试追加模式
    controller.waypoints.clear()
    controller.record_current_waypoint("追加路点3", "第三个追加的路点")
    
    # 追加到CSV文件
    csv_path = SCRIPT_DIR / "test_append.csv"
    controller.save_waypoints(str(csv_path), format="csv", backup=False)
    print(f"✓ CSV初始保存: {len(controller.waypoints)} 个路点")
    
    controller.record_current_waypoint("追加路点4", "第四个追加的路点")
    controller.save_waypoints(str(csv_path), format="csv", append=True)
    
    # 加载并验证
    controller.waypoints.clear()
    controller.load_waypoints(str(csv_path), format="csv")
    print(f"✓ CSV追加后加载: {len(controller.waypoints)} 个路点")
    
    return True


def cleanup_test_files():
    """清理测试文件"""
    print("\n" + "=" * 70)
    print("🧹 清理测试文件")
    print("=" * 70)
    
    test_files = [
        "test_waypoints.json",
        "test_waypoints.json.bak",
        "test_waypoints.csv",
        "test_waypoints.txt",
        "waypoints_convert.json",
        "waypoints_convert.json.bak",
        "waypoints_convert.csv",
        "waypoints_convert.txt",
        "test_backup.json",
        "test_backup.json.bak",
        "test_append.csv"
    ]
    
    removed = 0
    for filename in test_files:
        filepath = SCRIPT_DIR / filename
        if filepath.exists():
            filepath.unlink()
            print(f"✓ 已删除: {filename}")
            removed += 1
    
    if removed == 0:
        print("没有需要清理的文件")
    else:
        print(f"\n✓ 共清理 {removed} 个文件")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='路点文件存储功能测试')
    parser.add_argument('--test', type=str, 
                       choices=['json', 'csv', 'txt', 'convert', 'backup', 'all', 'cleanup'],
                       default='all',
                       help='测试类型')
    parser.add_argument('--keep', action='store_true', help='保留测试文件')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📦 路点文件存储功能测试")
    print("=" * 70)
    
    # 创建虚拟机器人（不需要真实连接）
    robot = CGXiRobot(virtual=True)
    robot.connect()
    robot.power_on()
    robot.enable()
    
    # 创建控制器
    controller = create_robot_controller(robot)
    
    try:
        # 执行测试
        if args.test == 'json':
            test_json_format(controller)
        elif args.test == 'csv':
            test_csv_format(controller)
        elif args.test == 'txt':
            test_txt_format(controller)
        elif args.test == 'convert':
            test_format_conversion(controller)
        elif args.test == 'backup':
            test_backup_and_append(controller)
        elif args.test == 'cleanup':
            cleanup_test_files()
        elif args.test == 'all':
            test_json_format(controller)
            test_csv_format(controller)
            test_txt_format(controller)
            test_format_conversion(controller)
            test_backup_and_append(controller)
            
            if not args.keep:
                cleanup_test_files()
            else:
                print("\n💡 测试文件已保留，可以手动查看")
        
        print("\n" + "=" * 70)
        print("✓ 所有测试完成")
        print("=" * 70)
    
    except KeyboardInterrupt:
        print("\n\n👋 用户中断")
    
    finally:
        robot.disconnect()


if __name__ == '__main__':
    sys.exit(main())

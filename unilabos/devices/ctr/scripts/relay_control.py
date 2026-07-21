#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器 - 指定端口控制
支持打开/关闭/切换指定端口
"""

import socket
import sys
from pathlib import Path

# 添加 skills/jidianqi 到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILLS_PATH = SCRIPT_DIR.parent / 'skills' / 'jidianqi'
sys.path.insert(0, str(SKILLS_PATH))

try:
    from relay_utils import StringProtocol
except ImportError:
    # 备用路径
    sys.path.insert(0, r'f:\ctr\skills\jidianqi')
    from relay_utils import StringProtocol


def control_channel(ip, port, channel, action):
    """控制单个通道
    
    Args:
        ip: 继电器IP地址
        port: 端口号
        channel: 通道号 (1-16)
        action: 'on' 开启, 'off' 关闭
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        
        if action == 'on':
            cmd = StringProtocol.relay_on(channel)
            sock.send(cmd.encode('utf-8'))
            response = sock.recv(1024)
            print(f"  通道 {channel:2d}: 🔴 开启")
        else:
            cmd = StringProtocol.relay_off(channel)
            sock.send(cmd.encode('utf-8'))
            response = sock.recv(1024)
            print(f"  通道 {channel:2d}: ⚫ 关闭")
        
        sock.close()
        return True
        
    except Exception as e:
        print(f"❌ 通道 {channel} 控制失败: {e}")
        return False


def control_channels(ip, port, channels, action):
    """控制多个通道
    
    Args:
        ip: 继电器IP地址
        port: 端口号
        channels: 通道号列表，如 [1, 3, 5]
        action: 'on' 开启, 'off' 关闭
    """
    action_text = "开启" if action == 'on' else "关闭"
    print(f"\n{'='*50}")
    print(f"🔌 连接继电器 {ip}:{port}")
    print(f"🎯 {action_text}通道: {channels}")
    print('='*50)
    
    success_count = 0
    for ch in channels:
        if control_channel(ip, port, ch, action):
            success_count += 1
    
    print(f"\n✅ 成功{action_text} {success_count}/{len(channels)} 个通道")


def parse_channels(channel_str):
    """解析通道号字符串
    
    支持格式:
        1       -> [1]
        1,3,5   -> [1, 3, 5]
        1-5     -> [1, 2, 3, 4, 5]
        1-3,5,7 -> [1, 2, 3, 5, 7]
    """
    channels = []
    parts = channel_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # 范围格式: 1-5
            start, end = part.split('-')
            channels.extend(range(int(start), int(end) + 1))
        else:
            # 单个数字
            channels.append(int(part))
    
    return sorted(list(set(channels)))


if __name__ == '__main__':
    import sys
    
    # 默认配置
    ip = '192.168.1.100'
    port = 50000
    
    # 显示帮助
    if len(sys.argv) < 2 or sys.argv[1] in ['--help', '-h']:
        print("""
科星继电器端口控制工具

用法: python relay_control.py <通道> <动作> [IP:PORT]

参数:
  通道    通道号，支持: 1, 1,3,5, 1-5, 1-3,5,7
  动作    on=开启, off=关闭
  IP:PORT 可选，默认 192.168.1.100:50000

示例:
  python relay_control.py 1 on              # 开启通道1
  python relay_control.py 3 off             # 关闭通道3
  python relay_control.py 1,3,5 on          # 开启通道1,3,5
  python relay_control.py 1-5 on            # 开启通道1到5
  python relay_control.py 1-3,5,7 off       # 关闭通道1,2,3,5,7
  python relay_control.py 1 on 192.168.1.50 # 指定IP
        """)
        sys.exit(0)
    
    # 解析参数
    if len(sys.argv) >= 3:
        channel_str = sys.argv[1]
        action = sys.argv[2].lower()
        
        if action not in ['on', 'off']:
            print("❌ 动作必须是 'on' 或 'off'")
            sys.exit(1)
        
        # 解析通道列表
        channels = parse_channels(channel_str)
        
        # 解析IP和端口
        if len(sys.argv) >= 4:
            addr = sys.argv[3].split(':')
            ip = addr[0]
            if len(addr) > 1:
                port = int(addr[1])
        
        # 执行控制
        control_channels(ip, port, channels, action)
    else:
        print("❌ 参数不足，使用 --help 查看帮助")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器 - 关闭所有端口
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


def close_all_channels(ip='192.168.1.100', port=50000, channel_count=8):
    """关闭所有继电器通道"""
    print(f"\n{'='*50}")
    print(f"🔌 连接继电器 {ip}:{port}")
    print(f"🎯 关闭全部 {channel_count} 个通道")
    print('='*50)
    
    try:
        # 建立连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((ip, port))
        print("✅ 连接成功\n")
        
        # 依次关闭所有通道
        for ch in range(1, channel_count + 1):
            cmd = StringProtocol.relay_off(ch)
            sock.send(cmd.encode('utf-8'))
            response = sock.recv(1024)
            print(f"  通道 {ch:2d}: ⚫ 关闭  (响应: {response.decode('utf-8', errors='ignore').strip()[:30]}...)")
        
        sock.close()
        print(f"\n✅ 所有 {channel_count} 个通道已关闭!")
        
    except Exception as e:
        print(f"❌ 错误: {e}")


if __name__ == '__main__':
    import sys
    
    # 默认配置
    ip = '192.168.1.100'
    port = 50000
    channels = 16
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        if ':' in sys.argv[1]:
            addr = sys.argv[1].split(':')
            ip = addr[0]
            port = int(addr[1])
        else:
            ip = sys.argv[1]
    
    if len(sys.argv) > 2:
        channels = int(sys.argv[2])
    
    close_all_channels(ip, port, channels)

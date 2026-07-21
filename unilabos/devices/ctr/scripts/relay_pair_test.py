#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器 - 双点位遍历测试
测试任意两个点位同时打开的情况
"""

import socket
import time
import sys
from itertools import combinations
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


class RelayPairTester:
    """继电器双点位测试器"""
    
    def __init__(self, ip='192.168.1.100', port=50000, channel_count=16):
        self.ip = ip
        self.port = port
        self.channel_count = channel_count
        self.sock = None
        
    def connect(self):
        """建立连接"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.sock:
            self.sock.close()
            self.sock = None
    
    def send_cmd(self, cmd):
        """发送指令"""
        try:
            self.sock.send(cmd.encode('utf-8'))
            return self.sock.recv(1024)
        except Exception as e:
            print(f"发送失败: {e}")
            return None
    
    def all_off(self):
        """关闭所有通道"""
        print("  关闭所有通道...", end=' ')
        for ch in range(1, self.channel_count + 1):
            cmd = StringProtocol.relay_off(ch)
            self.send_cmd(cmd)
        print("✓")
    
    def channel_on(self, ch):
        """打开指定通道"""
        cmd = StringProtocol.relay_on(ch)
        self.send_cmd(cmd)
    
    def channel_off(self, ch):
        """关闭指定通道"""
        cmd = StringProtocol.relay_off(ch)
        self.send_cmd(cmd)
    
    def ensure_only_pair_on(self, ch1, ch2):
        """确保只有指定的两个通道打开，其他全部关闭
        
        Args:
            ch1, ch2: 要保持打开的两个通道号
        """
        print(f"  设置状态: 通道{ch1},{ch2}打开，其他关闭...", end=' ')
        
        # 对所有非测试通道发送关闭信号
        for ch in range(1, self.channel_count + 1):
            if ch != ch1 and ch != ch2:
                cmd = StringProtocol.relay_off(ch)
                self.send_cmd(cmd)
                time.sleep(0.05)  # 短暂延时避免指令堆积
        
        # 确保测试通道是打开状态
        self.channel_on(ch1)
        time.sleep(0.05)
        self.channel_on(ch2)
        
        print("✓")
    
    def test_pair(self, ch1, ch2, delay=2):
        """测试一对通道
        
        Args:
            ch1, ch2: 要测试的两个通道号
            delay: 测试持续时间(秒)
        """
        # 确保只有这两个通道打开，其他全部关闭
        self.ensure_only_pair_on(ch1, ch2)
        
        # 等待
        print(f"  保持 {delay} 秒...")
        time.sleep(delay)
        
        print(f"  ✅ 测试完成: 通道 {ch1} + {ch2}")
    
    def set_pattern_10_14_off_15_on(self):
        """设置模式: 10,14断开，15打通，其他全部关闭"""
        print("\n📋 模式1: 通道10,14断开，通道15打通")
        print("  对所有非15通道发送关闭信号...")
        
        # 关闭1-14和16
        for ch in list(range(1, 15)) + [16]:
            cmd = StringProtocol.relay_off(ch)
            self.send_cmd(cmd)
            time.sleep(0.05)
        
        # 确保15是打开的
        print("  打开通道15...")
        self.channel_on(15)
        print("  当前状态: 10⚫ 14⚫ 15🔴 (其他全部⚫)")
    
    def set_pattern_10_14_on_15_off(self):
        """设置模式: 10,14打通，15断开，其他全部关闭"""
        print("\n📋 模式2: 通道10,14打通，通道15断开")
        print("  对所有非10,14通道发送关闭信号...")
        
        # 关闭1-9, 11-13, 15-16
        for ch in list(range(1, 10)) + [11, 12, 13] + list(range(15, 17)):
            cmd = StringProtocol.relay_off(ch)
            self.send_cmd(cmd)
            time.sleep(0.05)
        
        # 确保10和14是打开的
        print("  打开通道10和14...")
        self.channel_on(10)
        time.sleep(0.05)
        self.channel_on(14)
        print("  当前状态: 10🔴 14🔴 15⚫ (其他全部⚫)")
    
    def test_specific_pattern(self):
        """测试特定模式:
        1. 10,14断开，15打通
        2. 10,14打通，15断开
        """
        print(f"\n{'='*60}")
        print("🧪 特定模式测试")
        print('='*60)
        
        if not self.connect():
            return
        
        try:
            # 模式1: 10,14断开，15打通
            self.set_pattern_10_14_off_15_on()
            time.sleep(2)
            
            # 模式2: 10,14打通，15断开
            self.set_pattern_10_14_on_15_off()
            time.sleep(2)
            
            # 恢复关闭
            print("\n  恢复所有通道关闭...")
            self.all_off()
            print("\n✅ 特定模式测试完成")
            
        finally:
            self.disconnect()
    
    def run_pair_traversal(self, delay=1, pause_between=0.5):
        """遍历测试所有双点位组合
        
        从16个通道中任选2个，测试 C(16,2) = 120 种组合
        """
        channels = list(range(1, self.channel_count + 1))
        pairs = list(combinations(channels, 2))
        total = len(pairs)
        
        print(f"\n{'='*60}")
        print(f"🔄 双点位遍历测试")
        print(f"   通道数: {self.channel_count}")
        print(f"   组合数: C({self.channel_count},2) = {total}")
        print(f"   每对持续时间: {delay}秒")
        print('='*60)
        
        if not self.connect():
            return
        
        try:
            print(f"\n按 Ctrl+C 可随时停止测试\n")
            
            for i, (ch1, ch2) in enumerate(pairs, 1):
                print(f"[{i:3d}/{total}] ", end='')
                self.test_pair(ch1, ch2, delay)
                
                if i < total:
                    time.sleep(pause_between)
                    
        except KeyboardInterrupt:
            print("\n\n⚠️  测试被用户中断")
        finally:
            print("\n  关闭所有通道...")
            self.all_off()
            self.disconnect()
            print(f"\n✅ 遍历测试结束，共完成 {i} 组测试")
    
    def test_adjacent_pairs(self, delay=1):
        """测试相邻点位对 (1-2, 2-3, 3-4, ...)"""
        print(f"\n{'='*60}")
        print("🔗 相邻点位测试")
        print('='*60)
        
        if not self.connect():
            return
        
        try:
            for i in range(1, self.channel_count):
                print(f"\n测试相邻对: {i} - {i+1}")
                self.test_pair(i, i + 1, delay)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  测试被用户中断")
        finally:
            self.all_off()
            self.disconnect()
            print("\n✅ 相邻点位测试完成")


def interactive_menu():
    """交互式菜单"""
    print("\n" + "="*60)
    print("科星继电器 - 双点位遍历测试工具")
    print("="*60)
    
    # 配置
    default_ip = '192.168.1.100'
    default_port = '50000'
    default_channels = '16'
    
    ip = input(f"请输入继电器IP地址 [默认: {default_ip}]: ").strip() or default_ip
    port = int(input(f"请输入端口号 [默认: {default_port}]: ").strip() or default_port)
    channels = int(input(f"请输入通道数量 [默认: {default_channels}]: ").strip() or default_channels)
    
    tester = RelayPairTester(ip, port, channels)
    
    while True:
        print("\n" + "="*60)
        print("请选择测试模式:")
        print("  1. 特定模式测试 (10,14/15)")
        print("  2. 遍历所有双点位组合 (C(n,2))")
        print("  3. 相邻点位测试 (1-2, 2-3, ...)")
        print("  0. 退出")
        print("="*60)
        
        choice = input("请输入选项: ").strip()
        
        if choice == '1':
            tester.test_specific_pattern()
        elif choice == '2':
            delay = float(input("每对持续时间(秒) [默认: 1]: ").strip() or '1')
            tester.run_pair_traversal(delay)
        elif choice == '3':
            delay = float(input("每对持续时间(秒) [默认: 1]: ").strip() or '1')
            tester.test_adjacent_pairs(delay)
        elif choice == '0':
            print("👋 再见!")
            break
        else:
            print("❌ 无效选项")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print("""
科星继电器双点位遍历测试工具

用法: python relay_pair_test.py [选项]

选项:
  -h, --help           显示帮助
  --pattern            运行特定模式测试 (10,14/15)
  --traverse [DELAY]   遍历所有双点位组合
  --adjacent [DELAY]   测试相邻点位
  --ip IP:PORT         指定IP和端口

示例:
  python relay_pair_test.py --pattern
  python relay_pair_test.py --traverse 2
  python relay_pair_test.py --traverse --ip 192.168.1.100:50000
            """)
        elif sys.argv[1] == '--pattern':
            ip = '192.168.1.100'
            port = 50000
            if '--ip' in sys.argv:
                idx = sys.argv.index('--ip')
                addr = sys.argv[idx + 1].split(':')
                ip = addr[0]
                port = int(addr[1]) if len(addr) > 1 else 50000
            tester = RelayPairTester(ip, port)
            tester.test_specific_pattern()
        elif sys.argv[1] == '--traverse':
            delay = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].replace('.','').isdigit() else 1
            tester = RelayPairTester()
            tester.run_pair_traversal(delay)
        elif sys.argv[1] == '--adjacent':
            delay = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].replace('.','').isdigit() else 1
            tester = RelayPairTester()
            tester.test_adjacent_pairs(delay)
        else:
            interactive_menu()
    else:
        interactive_menu()

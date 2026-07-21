#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器通道测试工具
测试每个继电器端口的开关功能
"""

import socket
import time
import json
import sys
from pathlib import Path

# 添加 skills/jidianqi 到路径
SCRIPT_DIR = Path(__file__).parent.resolve()
SKILLS_PATH = SCRIPT_DIR.parent / 'skills' / 'jidianqi'
sys.path.insert(0, str(SKILLS_PATH))

try:
    from relay_utils import ModbusRTU, ModbusTCP, KexingProtocol, StringProtocol, CRC16
except ImportError:
    # 备用路径
    sys.path.insert(0, r'f:\ctr\skills\jidianqi')
    from relay_utils import ModbusRTU, ModbusTCP, KexingProtocol, StringProtocol, CRC16


class RelayChannelTester:
    """继电器通道测试器"""
    
    def __init__(self, ip='192.168.1.100', port=50000, channel_count=8):
        self.ip = ip
        self.port = port
        self.channel_count = channel_count
        self.sock = None
        
    def connect(self):
        """建立TCP连接"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            print(f"✅ 已连接到 {self.ip}:{self.port}")
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.sock:
            self.sock.close()
            self.sock = None
            print("🔌 已断开连接")
    
    def send_modbus_tcp(self, hex_cmd):
        """发送MODBUS-TCP指令"""
        try:
            self.sock.send(bytes.fromhex(hex_cmd))
            response = self.sock.recv(1024)
            return response
        except Exception as e:
            print(f"发送失败: {e}")
            return None
    
    def send_string(self, json_cmd):
        """发送字符串协议指令"""
        try:
            self.sock.send(json_cmd.encode('utf-8'))
            response = self.sock.recv(1024)
            return response.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"发送失败: {e}")
            return None
    
    def test_single_channel_modbus(self, channel, delay=2):
        """测试单个通道 (MODBUS-TCP)"""
        print(f"\n🔘 测试第 {channel} 路继电器 (MODBUS-TCP)")
        print("-" * 50)
        
        # 开启
        print(f"  ➡️  发送开启指令...")
        on_cmd = ModbusTCP.relay_on(channel)
        print(f"     指令: {on_cmd}")
        resp = self.send_modbus_tcp(on_cmd)
        if resp:
            print(f"     响应: {resp.hex().upper()}")
        time.sleep(delay)
        
        # 关闭
        print(f"  ➡️  发送关闭指令...")
        off_cmd = ModbusTCP.relay_off(channel)
        print(f"     指令: {off_cmd}")
        resp = self.send_modbus_tcp(off_cmd)
        if resp:
            print(f"     响应: {resp.hex().upper()}")
        time.sleep(0.5)
        
        print(f"  ✅ 第 {channel} 路测试完成")
    
    def test_single_channel_string(self, channel, delay=2):
        """测试单个通道 (字符串协议)"""
        print(f"\n🔘 测试第 {channel} 路继电器 (字符串协议)")
        print("-" * 50)
        
        # 开启
        print(f"  ➡️  发送开启指令...")
        on_cmd = StringProtocol.relay_on(channel)
        print(f"     指令: {on_cmd}")
        resp = self.send_string(on_cmd)
        if resp:
            print(f"     响应: {resp}")
        time.sleep(delay)
        
        # 关闭
        print(f"  ➡️  发送关闭指令...")
        off_cmd = StringProtocol.relay_off(channel)
        print(f"     指令: {off_cmd}")
        resp = self.send_string(off_cmd)
        if resp:
            print(f"     响应: {resp}")
        time.sleep(0.5)
        
        print(f"  ✅ 第 {channel} 路测试完成")
    
    def test_all_channels(self, protocol='string', delay=2):
        """测试所有通道"""
        print(f"\n{'='*60}")
        print(f"🧪 开始测试所有 {self.channel_count} 路继电器通道")
        print(f"   协议: {protocol.upper()}")
        print(f"   每路延时: {delay}秒")
        print('='*60)
        
        if not self.connect():
            return False
        
        try:
            for ch in range(1, self.channel_count + 1):
                if protocol == 'modbus':
                    self.test_single_channel_modbus(ch, delay)
                else:
                    self.test_single_channel_string(ch, delay)
            
            print(f"\n{'='*60}")
            print(f"✅ 所有 {self.channel_count} 路继电器测试完成!")
            print('='*60)
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  测试被用户中断")
            return False
        finally:
            self.disconnect()
    
    def test_sequence(self, delay=1):
        """顺序测试 - 依次开启所有，然后依次关闭"""
        print(f"\n{'='*60}")
        print(f"🎬 顺序测试模式")
        print(f"   依次开启所有通道，然后依次关闭")
        print('='*60)
        
        if not self.connect():
            return False
        
        try:
            # 依次开启
            print("\n▶️  依次开启所有通道...")
            for ch in range(1, self.channel_count + 1):
                cmd = StringProtocol.relay_on(ch)
                print(f"  开启第 {ch} 路...", end=' ')
                resp = self.send_string(cmd)
                print("OK" if resp else "FAIL")
                time.sleep(delay)
            
            print(f"\n⏸️  所有通道已开启，等待 {delay*2} 秒...")
            time.sleep(delay * 2)
            
            # 依次关闭
            print("\n⏹️  依次关闭所有通道...")
            for ch in range(1, self.channel_count + 1):
                cmd = StringProtocol.relay_off(ch)
                print(f"  关闭第 {ch} 路...", end=' ')
                resp = self.send_string(cmd)
                print("OK" if resp else "FAIL")
                time.sleep(delay)
            
            print(f"\n✅ 顺序测试完成!")
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  测试被用户中断")
            # 确保关闭所有通道
            print("🔄 正在关闭所有通道...")
            for ch in range(1, self.channel_count + 1):
                self.send_string(StringProtocol.relay_off(ch))
            return False
        finally:
            self.disconnect()
    
    def test_chasing(self, delay=0.5):
        """流水灯测试 - 跑马灯效果"""
        print(f"\n{'='*60}")
        print(f"💫 流水灯测试模式")
        print(f"   依次点亮每个通道，形成跑马灯效果")
        print('='*60)
        
        if not self.connect():
            return False
        
        try:
            print("\n🔄 按 Ctrl+C 停止测试\n")
            
            while True:
                for ch in range(1, self.channel_count + 1):
                    # 开启当前通道
                    self.send_string(StringProtocol.relay_on(ch))
                    time.sleep(delay)
                    # 关闭当前通道
                    self.send_string(StringProtocol.relay_off(ch))
                    
        except KeyboardInterrupt:
            print("\n\n🛑 流水灯测试停止")
            # 关闭所有通道
            print("🔄 正在关闭所有通道...")
            for ch in range(1, self.channel_count + 1):
                self.send_string(StringProtocol.relay_off(ch))
            print("✅ 所有通道已关闭")
        finally:
            self.disconnect()
    
    def test_read_status(self):
        """读取继电器状态"""
        print(f"\n{'='*60}")
        print(f"📊 读取继电器状态")
        print('='*60)
        
        if not self.connect():
            return False
        
        try:
            # 使用字符串协议读取
            cmd = StringProtocol.read_status()
            print(f"\n发送指令: {cmd}")
            resp = self.send_string(cmd)
            
            if resp:
                print(f"\n收到响应:")
                print(f"  {resp}")
                
                # 解析状态
                try:
                    # 尝试解析JSON
                    if resp.strip().startswith('{'):
                        data = json.loads(resp.strip()[resp.find('{'):])
                        print(f"\n📋 状态解析:")
                        for key, value in data.items():
                            if key.startswith('A'):
                                status = "🔴 开启" if value == 1 else "⚫ 关闭"
                                print(f"   继电器 {key}: {status}")
                except:
                    pass
            else:
                print("❌ 未收到响应")
                
        except Exception as e:
            print(f"❌ 读取失败: {e}")
        finally:
            self.disconnect()


def interactive_menu():
    """交互式菜单"""
    print("\n" + "="*60)
    print("科星继电器通道测试工具")
    print("="*60)
    
    # 获取配置
    default_ip = '192.168.1.100'
    default_port = '50000'
    default_channels = '8'
    
    ip = input(f"请输入继电器IP地址 [默认: {default_ip}]: ").strip() or default_ip
    port = int(input(f"请输入端口号 [默认: {default_port}]: ").strip() or default_port)
    channels = int(input(f"请输入通道数量 [默认: {default_channels}]: ").strip() or default_channels)
    
    tester = RelayChannelTester(ip, port, channels)
    
    while True:
        print("\n" + "="*60)
        print("请选择测试模式:")
        print("  1. 单独测试每个通道 (依次开关)")
        print("  2. 顺序测试 (依次开启所有，再依次关闭)")
        print("  3. 流水灯测试 (跑马灯效果)")
        print("  4. 读取继电器状态")
        print("  0. 退出")
        print("="*60)
        
        choice = input("请输入选项: ").strip()
        
        if choice == '1':
            protocol = input("选择协议 (modbus/string) [默认: string]: ").strip() or 'string'
            delay = float(input("每路延时(秒) [默认: 2]: ").strip() or '2')
            tester.test_all_channels(protocol, delay)
            
        elif choice == '2':
            delay = float(input("每路延时(秒) [默认: 1]: ").strip() or '1')
            tester.test_sequence(delay)
            
        elif choice == '3':
            delay = float(input("流水速度(秒) [默认: 0.5]: ").strip() or '0.5')
            tester.test_chasing(delay)
            
        elif choice == '4':
            tester.test_read_status()
            
        elif choice == '0':
            print("👋 再见!")
            break
        else:
            print("❌ 无效选项，请重新选择")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # 命令行模式
        if sys.argv[1] in ['--help', '-h']:
            print("""
用法: python test_relay_channels.py [选项]

选项:
  -h, --help              显示帮助信息
  --all [IP:PORT]         测试所有通道
  --sequence [IP:PORT]    顺序测试
  --chase [IP:PORT]       流水灯测试
  --status [IP:PORT]      读取状态
  --channels N            设置通道数量 (默认: 8)
  --delay SECONDS         设置延时 (默认: 2)

示例:
  python test_relay_channels.py
  python test_relay_channels.py --all 192.168.1.100:50000
  python test_relay_channels.py --sequence --channels 16 --delay 1
  python test_relay_channels.py --chase --delay 0.3
            """)
        elif sys.argv[1] == '--all':
            addr = sys.argv[2].split(':') if len(sys.argv) > 2 else ['192.168.1.100', '50000']
            ip, port = addr[0], int(addr[1]) if len(addr) > 1 else 50000
            tester = RelayChannelTester(ip, port)
            tester.test_all_channels()
        elif sys.argv[1] == '--sequence':
            addr = sys.argv[2].split(':') if len(sys.argv) > 2 else ['192.168.1.100', '50000']
            ip, port = addr[0], int(addr[1]) if len(addr) > 1 else 50000
            tester = RelayChannelTester(ip, port)
            tester.test_sequence()
        elif sys.argv[1] == '--chase':
            addr = sys.argv[2].split(':') if len(sys.argv) > 2 else ['192.168.1.100', '50000']
            ip, port = addr[0], int(addr[1]) if len(addr) > 1 else 50000
            tester = RelayChannelTester(ip, port)
            tester.test_chasing()
        elif sys.argv[1] == '--status':
            addr = sys.argv[2].split(':') if len(sys.argv) > 2 else ['192.168.1.100', '50000']
            ip, port = addr[0], int(addr[1]) if len(addr) > 1 else 50000
            tester = RelayChannelTester(ip, port)
            tester.test_read_status()
        else:
            interactive_menu()
    else:
        # 交互模式
        interactive_menu()

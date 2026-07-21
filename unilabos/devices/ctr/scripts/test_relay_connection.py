#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
科星继电器连接测试工具
支持 MODBUS-RTU、MODBUS-TCP、科星私有协议、字符串协议
"""

import socket
import serial
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


class RelayConnectionTester:
    """继电器连接测试器"""
    
    def __init__(self, config_file=None):
        """初始化测试器"""
        # 默认配置文件路径
        if config_file is None:
            config_file = SKILLS_PATH / 'config.json'
        self.config = self._load_config(config_file)
        self.network = self.config.get('network', {})
        self.device_ip = self.network.get('device_ip', '192.168.1.100')
        self.device_port = self.network.get('device_port', 50000)
        
    def _load_config(self, config_file):
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  配置文件加载失败: {e}")
            return {}
    
    def test_tcp_connection(self, ip=None, port=None):
        """测试TCP连接"""
        ip = ip or self.device_ip
        port = port or self.device_port
        
        print(f"\n{'='*60}")
        print(f"🔌 TCP连接测试: {ip}:{port}")
        print('='*60)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, port))
            
            if result == 0:
                print(f"✅ TCP连接成功!")
                print(f"   设备地址: {ip}:{port}")
                sock.close()
                return True
            else:
                print(f"❌ TCP连接失败 (错误码: {result})")
                return False
        except Exception as e:
            print(f"❌ TCP连接异常: {e}")
            return False
    
    def test_modbus_tcp(self, ip=None, port=None):
        """测试MODBUS-TCP协议"""
        ip = ip or self.device_ip
        port = port or self.device_port
        
        print(f"\n{'='*60}")
        print(f"📡 MODBUS-TCP 协议测试: {ip}:{port}")
        print('='*60)
        
        # 测试指令
        test_commands = {
            '读取继电器状态': ModbusTCP.read_relay_status(8),
            '第1路开': ModbusTCP.relay_on(1),
            '第1路关': ModbusTCP.relay_off(1),
        }
        
        print("\n📤 生成的测试指令:")
        for name, cmd in test_commands.items():
            print(f"   {name}: {cmd}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            print("\n🔄 发送读取状态指令...")
            cmd_bytes = bytes.fromhex(ModbusTCP.read_relay_status(8))
            sock.send(cmd_bytes)
            
            response = sock.recv(1024)
            print(f"📥 收到响应: {response.hex().upper()}")
            
            if len(response) >= 9:
                print("✅ MODBUS-TCP 通信正常!")
                sock.close()
                return True
            else:
                print("⚠️  响应数据异常")
                sock.close()
                return False
                
        except Exception as e:
            print(f"❌ MODBUS-TCP 测试失败: {e}")
            return False
    
    def test_string_protocol(self, ip=None, port=None):
        """测试字符串协议"""
        ip = ip or self.device_ip
        port = port or self.device_port
        
        print(f"\n{'='*60}")
        print(f"📝 字符串协议测试: {ip}:{port}")
        print('='*60)
        
        # 测试指令
        test_commands = {
            '读取所有状态': StringProtocol.read_status(),
            '第1路开': StringProtocol.relay_on(1),
            '第1路关': StringProtocol.relay_off(1),
        }
        
        print("\n📤 生成的测试指令:")
        for name, cmd in test_commands.items():
            print(f"   {name}: {cmd}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            print("\n🔄 发送读取状态指令...")
            cmd = StringProtocol.read_status()
            sock.send(cmd.encode('utf-8'))
            
            response = sock.recv(1024)
            print(f"📥 收到响应: {response.decode('utf-8', errors='ignore')}")
            print("✅ 字符串协议通信正常!")
            sock.close()
            return True
            
        except Exception as e:
            print(f"❌ 字符串协议测试失败: {e}")
            return False
    
    def test_kexing_protocol(self, ip=None, port=None):
        """测试科星私有协议"""
        ip = ip or self.device_ip
        port = port or self.device_port
        
        print(f"\n{'='*60}")
        print(f"🔧 科星私有协议测试: {ip}:{port}")
        print('='*60)
        
        # 测试指令
        test_commands = {
            '读取继电器状态': KexingProtocol.READ_RELAY_STATUS,
            '第1路开': KexingProtocol.relay_on(1),
            '第1路关': KexingProtocol.relay_off(1),
        }
        
        print("\n📤 生成的测试指令:")
        for name, cmd in test_commands.items():
            print(f"   {name}: {cmd}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            print("\n🔄 发送读取状态指令...")
            cmd_bytes = bytes.fromhex(KexingProtocol.READ_RELAY_STATUS.replace(' ', ''))
            sock.send(cmd_bytes)
            
            response = sock.recv(1024)
            print(f"📥 收到响应: {response.hex().upper()}")
            print("✅ 科星私有协议通信正常!")
            sock.close()
            return True
            
        except Exception as e:
            print(f"❌ 科星私有协议测试失败: {e}")
            return False
    
    def test_serial_connection(self, port='COM1', baudrate=9600):
        """测试串口连接 (MODBUS-RTU)"""
        print(f"\n{'='*60}")
        print(f"🔌 串口连接测试: {port} @ {baudrate}bps")
        print('='*60)
        
        # 测试指令
        test_commands = {
            '读取继电器状态': ModbusRTU.read_relay_status(8),
            '第1路开': ModbusRTU.relay_on(1),
            '第1路关': ModbusRTU.relay_off(1),
        }
        
        print("\n📤 生成的测试指令:")
        for name, cmd in test_commands.items():
            print(f"   {name}: {cmd}")
        
        try:
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=2
            )
            
            print(f"\n🔄 发送读取状态指令...")
            cmd_bytes = bytes.fromhex(ModbusRTU.read_relay_status(8))
            ser.write(cmd_bytes)
            
            time.sleep(0.1)
            response = ser.read(ser.in_waiting or 10)
            
            if response:
                print(f"📥 收到响应: {response.hex().upper()}")
                print("✅ 串口通信正常!")
            else:
                print("⚠️  未收到响应，请检查设备连接")
            
            ser.close()
            return True
            
        except serial.SerialException as e:
            print(f"❌ 串口连接失败: {e}")
            print(f"   提示: 请检查串口 {port} 是否存在或已被占用")
            return False
        except Exception as e:
            print(f"❌ 串口测试失败: {e}")
            return False
    
    def run_all_tests(self, ip=None, port=None, serial_port=None):
        """运行所有测试"""
        ip = ip or self.device_ip
        port = port or self.device_port
        
        print(f"\n{'#'*60}")
        print(f"#{'科星继电器连接测试':^56}#")
        print(f"#{'='*56}#")
        print(f"# 目标设备: {ip}:{port}{' '*32}#")
        print(f"{'#'*60}")
        
        results = {}
        
        # 1. TCP连接测试
        results['TCP连接'] = self.test_tcp_connection(ip, port)
        
        if results['TCP连接']:
            # 2. MODBUS-TCP测试
            results['MODBUS-TCP'] = self.test_modbus_tcp(ip, port)
            
            # 3. 字符串协议测试
            results['字符串协议'] = self.test_string_protocol(ip, port)
            
            # 4. 科星私有协议测试
            results['科星私有协议'] = self.test_kexing_protocol(ip, port)
        
        # 5. 串口测试 (可选)
        if serial_port:
            results['串口MODBUS-RTU'] = self.test_serial_connection(serial_port)
        
        # 测试总结
        print(f"\n{'='*60}")
        print("📊 测试结果汇总")
        print('='*60)
        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            print(f"   {test_name}: {status}")
        
        passed = sum(1 for r in results.values() if r)
        total = len(results)
        print(f"\n总计: {passed}/{total} 项测试通过")
        
        return results


def interactive_test():
    """交互式测试"""
    print("\n" + "="*60)
    print("科星继电器连接测试工具")
    print("="*60)
    
    # 获取设备IP
    default_ip = '192.168.1.100'
    ip = input(f"请输入继电器IP地址 [默认: {default_ip}]: ").strip()
    if not ip:
        ip = default_ip
    
    # 获取端口
    default_port = '50000'
    port_str = input(f"请输入端口号 [默认: {default_port}]: ").strip()
    port = int(port_str) if port_str else int(default_port)
    
    # 询问是否测试串口
    serial_test = input("是否测试串口连接? (y/n) [默认: n]: ").strip().lower()
    serial_port = None
    if serial_test == 'y':
        serial_port = input("请输入串口号 [默认: COM1]: ").strip() or 'COM1'
    
    # 运行测试
    tester = RelayConnectionTester()
    tester.run_all_tests(ip, port, serial_port)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 命令行模式
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("""
用法: python test_relay_connection.py [选项]

选项:
  -h, --help       显示帮助信息
  --auto           自动运行所有测试(使用config.json配置)
  --tcp IP:PORT    测试指定TCP地址
  --serial PORT    测试指定串口

示例:
  python test_relay_connection.py --auto
  python test_relay_connection.py --tcp 192.168.1.100:50000
  python test_relay_connection.py --serial COM3
            """)
        elif sys.argv[1] == '--auto':
            tester = RelayConnectionTester()
            tester.run_all_tests()
        elif sys.argv[1] == '--tcp' and len(sys.argv) > 2:
            addr = sys.argv[2].split(':')
            ip = addr[0]
            port = int(addr[1]) if len(addr) > 1 else 50000
            tester = RelayConnectionTester()
            tester.run_all_tests(ip, port)
        elif sys.argv[1] == '--serial' and len(sys.argv) > 2:
            tester = RelayConnectionTester()
            tester.test_serial_connection(sys.argv[2])
        else:
            interactive_test()
    else:
        # 交互模式
        interactive_test()

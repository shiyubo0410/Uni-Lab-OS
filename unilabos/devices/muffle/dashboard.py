#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP/IP Socket 客户端，用于任务管理
"""

import socket
import sys
import argparse
import time
import atexit


class SocketClient:
    """TCP/IP Socket 客户端"""
    
    def __init__(self, host='192.168.5.205', port=29999):
        self.host = host
        self.port = port
        self.sock = None
        self.current_task = None
        
    def connect(self):
        """连接到服务器"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)  # 设置超时时间
            self.sock.connect((self.host, self.port))
            print(f"已连接到 {self.host}:{self.port}")
            return True
        except socket.error as e:
            print(f"连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.sock:
            try:
                self.sock.close()
                print("连接已关闭")
            except:
                pass
            self.sock = None
    
    def send_command(self, command):
        """发送命令并接收响应"""
        if not self.sock:
            print("错误: 未连接到服务器")
            return None
        
        try:
            # 发送命令
            self.sock.sendall((command + '\n').encode('utf-8'))
            
            # 接收响应
            response = b''
            while True:
                chunk = self.sock.recv(1024)
                if not chunk:
                    break
                response += chunk
                # 如果响应包含换行符，可能已经接收完整
                if b'\n' in response:
                    break
            
            return response.decode('utf-8').strip()
        except socket.error as e:
            print(f"通信错误: {e}")
            return None
    
    def task_load(self, task_path):
        """加载任务"""
        command = f"task -p {task_path}"
        response = self.send_command(command)
        if response:
            print(f"加载任务响应: {response}")
            self.current_task = task_path
            return response
        return None
    
    def task_status(self):
        """查询任务状态"""
        command = "task -s"
        response = self.send_command(command)
        if response:
            print(f"任务状态: {response}")
            return response
        return None
    
    def task_running(self):
        """查询任务是否在运行"""
        command = "task -r"
        response = self.send_command(command)
        if response:
            # 解析响应，判断是否在运行
            response_lower = response.lower()
            is_running = 'running' in response_lower or 'true' in response_lower or '1' in response_lower
            print(f"任务运行状态: {response} (运行中: {is_running})")
            return is_running
        return False
    
    def play(self):
        """运行当前任务"""
        command = "play"
        response = self.send_command(command)
        if response:
            print(f"运行任务响应: {response}")
            return response
        return None
    
    def stop(self):
        """停止当前任务"""
        command = "stop"
        response = self.send_command(command)
        if response:
            print(f"停止任务响应: {response}")
            return response
        return None


class MuffleDevice:
    """
    UniLab 设备入口类，只提供 start 命令，发送 play 字符串
    """
    def __init__(self, config=None, data=None, host=None, port=None):
        # 合并配置：JSON 的 config 为基础，host/port 形参可覆盖
        self.config = dict(config or {})
        self.data = dict(data or {})
        if host is not None:
            self.config["host"] = host
        if port is not None:
            self.config["port"] = port

        host_str = str(self.config.get("host", "192.168.5.205"))
        port_val = self.config.get("port", 29999)
        try:
            port_int = int(str(port_val))  # 支持字符串或整数
        except (TypeError, ValueError):
            raise ValueError(f"端口必须是整数或可转换为整数的字符串，收到: {port_val!r}")

        self.client = SocketClient(host=host_str, port=port_int)
        self.connected = False

    def start(self):
        """连接并发送 play 命令"""
        if not self.connected:
            self.connected = self.client.connect()
        if self.connected:
            result = self.client.play()
            return result
        else:
            print("无法连接到设备")
            return None

    def stop(self):
        """停止任务并断开连接"""
        if self.connected:
            try:
                self.client.stop()
            except Exception:
                pass
            self.client.disconnect()
            self.connected = False


def main():
    """主程序"""
    parser = argparse.ArgumentParser(description='TCP/IP Socket 任务管理客户端')
    parser.add_argument('--task-path', '-t', type=str, help='任务路径')
    parser.add_argument('--host', type=str, default='192.168.5.205', help='服务器IP地址')
    parser.add_argument('--port', type=int, default=29999, help='服务器端口号')
    
    args = parser.parse_args()
    
    # 创建客户端
    client = SocketClient(host=args.host, port=args.port)
    
    # 注册退出时的清理函数
    def cleanup():
        """程序退出时停止任务"""
        if client.sock:
            print("\n程序退出，正在停止当前任务...")
            client.stop()
            client.disconnect()
    
    atexit.register(cleanup)
    
    # 连接到服务器
    if not client.connect():
        sys.exit(1)
    
    # try:
    #     # 主程序逻辑
    #     if args.task_path:
    #         # 1. 先查询任务是否在运行
    #         print("查询任务是否在运行...")
    #         is_running = client.task_running()
            
    #         # 2. 如果没有运行，加载任务并运行
    #         if not is_running:
    #             print(f"任务未运行，正在加载任务: {args.task_path}")
    #             client.task_load(args.task_path)
                
    #             # 等待一下确保任务加载完成
    #             time.sleep(0.5)
                
    #             print("正在运行任务...")
    #             client.play()
    #         else:
    #             print("任务已在运行中")
            
    #         # 保持连接，直到程序被中断
    #         print("\n任务已启动，按 Ctrl+C 退出...")
    #         try:
    #             while True:
    #                 time.sleep(1)
    #         except KeyboardInterrupt:
    #             print("\n收到中断信号")
    #     else:
    #         # 如果没有提供任务路径，进入交互模式
    #         print("未提供任务路径，进入交互模式")
    #         print("可用命令: task [-h|-p <path>|-s|-r], play, stop, quit")
            
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
            
            if cmd == 'quit' or cmd == 'exit':
                break
            elif cmd == 'play':
                client.play()
            elif cmd == 'stop':
                client.stop()
            elif cmd.startswith('task '):
                parts = cmd.split()
                if len(parts) == 2 and parts[1] == '-s':
                    client.task_status()
                elif len(parts) == 2 and parts[1] == '-r':
                    client.task_running()
                elif len(parts) == 3 and parts[1] == '-p':
                    client.task_load(parts[2])
                else:
                    print("用法: task [-h|-p <task path>|-s|-r]")
            else:
                print(f"未知命令: {cmd}")
        except KeyboardInterrupt:
            break
        except EOFError:
            break
    
    # finally:
    #     cleanup()


if __name__ == '__main__':
    main()


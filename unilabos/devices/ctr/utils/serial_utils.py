#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口通信工具类
"""

import serial
import time


class SerialClient:
    """串口客户端类"""
    
    def __init__(self, port: str, baudrate: int, data_bits: int = 8, stop_bits: int = 1, parity: str = "EVEN"):
        """
        初始化串口客户端
        
        Args:
            port: 串口端口，如 "COM6"
            baudrate: 波特率
            data_bits: 数据位
            stop_bits: 停止位
            parity: 校验位，可选 "EVEN", "ODD", "NONE"
        """
        self.port = port
        self.baudrate = baudrate
        self.data_bits = data_bits
        self.stop_bits = stop_bits
        self.parity = parity
        self.ser = None
        self.connected = False
    
    def connect(self, special_flow: bool = False) -> bool:
        """
        连接串口
        
        Args:
            special_flow: 是否使用特殊流程（先9600，再切换到目标波特率）
            
        Returns:
            bool: 连接是否成功
        """
        try:
            # 映射校验位
            parity_map = {
                "EVEN": serial.PARITY_EVEN,
                "ODD": serial.PARITY_ODD,
                "NONE": serial.PARITY_NONE
            }
            
            # 映射数据位
            data_bits_map = {
                5: serial.FIVEBITS,
                6: serial.SIXBITS,
                7: serial.SEVENBITS,
                8: serial.EIGHTBITS
            }
            
            # 映射停止位
            stop_bits_map = {
                1: serial.STOPBITS_ONE,
                1.5: serial.STOPBITS_ONE_POINT_FIVE,
                2: serial.STOPBITS_TWO
            }
            
            if special_flow:
                # 特殊流程：先以9600连接
                print(f"🔧 正在以9600波特率连接...")
                temp_ser = serial.Serial(
                    port=self.port,
                    baudrate=9600,
                    bytesize=data_bits_map.get(self.data_bits, serial.EIGHTBITS),
                    parity=parity_map.get(self.parity, serial.PARITY_EVEN),
                    stopbits=stop_bits_map.get(self.stop_bits, serial.STOPBITS_ONE),
                    timeout=1
                )
                
                if temp_ser.is_open:
                    print(f"✓ 9600波特率连接成功")
                    # 关闭临时连接
                    temp_ser.close()
                    time.sleep(0.5)
                else:
                    print(f"❌ 9600波特率连接失败")
                    return False
            
            # 创建串口对象（使用目标波特率）
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=data_bits_map.get(self.data_bits, serial.EIGHTBITS),
                parity=parity_map.get(self.parity, serial.PARITY_EVEN),
                stopbits=stop_bits_map.get(self.stop_bits, serial.STOPBITS_ONE),
                timeout=1
            )
            
            # 检查串口是否打开
            if self.ser.is_open:
                self.connected = True
                print(f"✓ 串口连接成功: {self.port} @ {self.baudrate} bps")
                return True
            else:
                print(f"❌ 串口打开失败: {self.port}")
                return False
                
        except Exception as e:
            print(f"❌ 串口连接失败: {e}")
            return False
    
    def disconnect(self):
        """
        断开串口连接
        """
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                self.connected = False
                print(f"✓ 串口断开连接: {self.port}")
            except Exception as e:
                print(f"❌ 串口断开失败: {e}")
    
    def send_command(self, command: str, wait_time: float = 0.5) -> str:
        """
        发送命令并返回响应
        
        Args:
            command: 命令字符串，如 "01 05 00 10 FF 00 8D FF"
            wait_time: 等待响应的时间（秒），默认0.5秒
            
        Returns:
            str: 响应字符串，失败返回 None
        """
        if not self.connected or not self.ser:
            print("错误: 串口未连接")
            return None
        
        try:
            # 清空接收缓冲区
            self.ser.reset_input_buffer()
            
            # 将命令字符串转换为字节
            data = bytes.fromhex(command.replace(' ', ''))
            
            # 发送数据
            self.ser.write(data)
            self.ser.flush()
            
            # 等待响应
            time.sleep(wait_time)
            
            # 读取响应
            response = self.ser.read(1024)
            
            if response:
                # 将响应转换为十六进制字符串
                response_hex = ' '.join(f"{b:02X}" for b in response)
                print(f"📡 发送: {command}")
                print(f"📡 接收: {response_hex}")
                return response_hex
            else:
                print(f"⚠️  无响应: {command}")
                return None
                
        except Exception as e:
            print(f"❌ 发送命令失败: {e}")
            return None
    
    def send_raw(self, data: bytes) -> bytes:
        """
        发送原始字节数据并返回响应
        
        Args:
            data: 字节数据
            
        Returns:
            bytes: 响应字节，失败返回 b''
        """
        if not self.connected or not self.ser:
            print("错误: 串口未连接")
            return b''
        
        try:
            # 发送数据
            self.ser.write(data)
            
            # 等待响应
            time.sleep(0.1)
            
            # 读取响应
            response = self.ser.read(1024)
            return response
            
        except Exception as e:
            print(f"❌ 发送原始数据失败: {e}")
            return b''
    
    def is_connected(self) -> bool:
        """
        检查串口是否连接
        
        Returns:
            bool: 连接状态
        """
        return self.connected


if __name__ == '__main__':
    # 测试示例
    print("=" * 60)
    print("串口客户端测试")
    print("=" * 60)
    
    # 创建串口客户端
    client = SerialClient(
        port="COM6",
        baudrate=19200,
        data_bits=8,
        stop_bits=1,
        parity="EVEN"
    )
    
    # 连接串口
    if client.connect():
        # 测试发送命令
        print("\n测试发送命令...")
        response = client.send_command("01 03 00 10 00 01 85 C0")
        print(f"响应: {response}")
        
        # 断开连接
        client.disconnect()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

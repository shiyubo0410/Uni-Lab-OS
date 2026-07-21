"""
PGEA系列夹爪 - Modbus RTU通信客户端

提供Modbus-RTU协议的底层通信封装，包括:
- CRC16校验计算
- 数据帧组装和解析
- 读写寄存器操作
"""

import serial
import struct
import time
from typing import List, Tuple, Optional, Union

try:
    from .constants import (
        FUNCTION_CODE_READ_HOLDING,
        FUNCTION_CODE_READ_INPUT,
        FUNCTION_CODE_WRITE_SINGLE,
        FUNCTION_CODE_WRITE_MULTIPLE,
        DEFAULT_BAUDRATE,
        DEFAULT_SLAVE_ID,
        DEFAULT_DATA_BITS,
        DEFAULT_STOP_BITS,
        DEFAULT_PARITY,
    )
except ImportError:
    from constants import (
        FUNCTION_CODE_READ_HOLDING,
        FUNCTION_CODE_READ_INPUT,
        FUNCTION_CODE_WRITE_SINGLE,
        FUNCTION_CODE_WRITE_MULTIPLE,
        DEFAULT_BAUDRATE,
        DEFAULT_SLAVE_ID,
        DEFAULT_DATA_BITS,
        DEFAULT_STOP_BITS,
        DEFAULT_PARITY,
    )


class CRC16:
    """CRC16校验计算器 (Modbus-RTU标准)"""
    
    # CRC16查找表 (Modbus标准多项式: 0xA001)
    CRC_TABLE = [
        0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
        0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
        0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
        0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
        0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
        0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
        0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
        0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
        0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
        0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
        0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
        0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
        0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
        0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
        0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
        0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
        0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
        0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
        0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
        0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
        0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
        0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
        0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
        0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x73C0, 0x7280, 0xB041,
        0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
        0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
        0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
        0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
        0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
        0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
        0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
        0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040,
    ]
    
    @classmethod
    def calculate(cls, data: bytes) -> int:
        """
        计算CRC16校验值
        
        Args:
            data: 需要计算校验的数据字节
            
        Returns:
            CRC16校验值 (16位整数)
        """
        crc = 0xFFFF
        for byte in data:
            crc = (crc >> 8) ^ cls.CRC_TABLE[(crc ^ byte) & 0xFF]
        return crc
    
    @classmethod
    def verify(cls, data: bytes, crc_low: int, crc_high: int) -> bool:
        """
        验证CRC16校验
        
        Args:
            data: 数据部分
            crc_low: CRC低字节
            crc_high: CRC高字节
            
        Returns:
            校验是否通过
        """
        calculated = cls.calculate(data)
        received = (crc_high << 8) | crc_low
        return calculated == received


class ModbusRTUClient:
    """Modbus-RTU通信客户端"""
    
    def __init__(
        self,
        port: str,
        slave_id: int = DEFAULT_SLAVE_ID,
        baudrate: int = DEFAULT_BAUDRATE,
        bytesize: int = DEFAULT_DATA_BITS,
        stopbits: int = DEFAULT_STOP_BITS,
        parity: str = DEFAULT_PARITY,
        timeout: float = 1.0,
    ):
        """
        初始化Modbus-RTU客户端
        
        Args:
            port: 串口设备路径 (如 '/dev/ttyUSB0' 或 'COM3')
            slave_id: 从站ID (默认1)
            baudrate: 波特率 (默认115200)
            bytesize: 数据位 (默认8)
            stopbits: 停止位 (默认1)
            parity: 校验位 ('N':无校验, 'O':奇校验, 'E':偶校验)
            timeout: 超时时间(秒)
        """
        self.port = port
        self.slave_id = slave_id
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.parity = parity
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        """
        连接串口
        
        Returns:
            连接是否成功
        """
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                stopbits=self.stopbits,
                parity=self.parity,
                timeout=self.timeout,
            )
            return self.serial.is_open
        except serial.SerialException as e:
            raise ConnectionError(f"无法连接到串口 {self.port}: {e}")
    
    def disconnect(self) -> None:
        """断开串口连接"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.serial = None
    
    def is_connected(self) -> bool:
        """
        检查连接状态
        
        Returns:
            是否已连接
        """
        return self.serial is not None and self.serial.is_open
    
    def _send_and_receive(self, request: bytes, response_length: int) -> bytes:
        """
        发送请求并接收响应
        
        Args:
            request: 请求数据帧
            response_length: 期望的响应长度
            
        Returns:
            响应数据帧
        """
        if not self.is_connected():
            raise ConnectionError("串口未连接")
        
        # 清空缓冲区
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()
        
        # 发送请求
        self.serial.write(request)
        self.serial.flush()
        
        # 等待响应
        time.sleep(0.01)  # 小延迟确保数据接收
        
        # 读取响应
        response = self.serial.read(response_length)
        
        if len(response) < 5:  # 最小响应长度
            raise TimeoutError("接收响应超时")
        
        # 验证从站ID
        if response[0] != self.slave_id:
            raise ValueError(f"从站ID不匹配: 期望{self.slave_id}, 收到{response[0]}")
        
        # 检查是否为错误响应
        if response[1] & 0x80:
            error_code = response[2]
            raise RuntimeError(f"Modbus错误: 功能码={hex(request[1])}, 错误码={hex(error_code)}")
        
        # 验证CRC
        data_for_crc = response[:-2]
        received_crc_low = response[-2]
        received_crc_high = response[-1]
        
        if not CRC16.verify(data_for_crc, received_crc_low, received_crc_high):
            raise ValueError("CRC校验失败")
        
        return response
    
    def read_holding_registers(
        self, 
        address: int, 
        count: int = 1
    ) -> List[int]:
        """
        读取保持寄存器 (功能码0x03)
        
        Args:
            address: 寄存器起始地址
            count: 读取寄存器数量
            
        Returns:
            寄存器值列表
        """
        # 组装请求帧
        request = struct.pack(
            '>BBHH',
            self.slave_id,
            FUNCTION_CODE_READ_HOLDING,
            address,
            count
        )
        
        # 计算并添加CRC
        crc = CRC16.calculate(request)
        request += struct.pack('<H', crc)
        
        # 发送请求并接收响应
        # 响应格式: [从站ID(1)] [功能码(1)] [字节数(1)] [数据(n*2)] [CRC(2)]
        response_length = 5 + count * 2
        response = self._send_and_receive(request, response_length)
        
        # 解析响应数据
        byte_count = response[2]
        data = response[3:3 + byte_count]
        
        # 将字节转换为16位整数列表
        values = []
        for i in range(0, len(data), 2):
            value = struct.unpack('>H', data[i:i+2])[0]
            values.append(value)
        
        return values
    
    def read_input_registers(
        self, 
        address: int, 
        count: int = 1
    ) -> List[int]:
        """
        读取输入寄存器 (功能码0x04)
        
        Args:
            address: 寄存器起始地址
            count: 读取寄存器数量
            
        Returns:
            寄存器值列表
        """
        # 组装请求帧
        request = struct.pack(
            '>BBHH',
            self.slave_id,
            FUNCTION_CODE_READ_INPUT,
            address,
            count
        )
        
        # 计算并添加CRC
        crc = CRC16.calculate(request)
        request += struct.pack('<H', crc)
        
        # 发送请求并接收响应
        response_length = 5 + count * 2
        response = self._send_and_receive(request, response_length)
        
        # 解析响应数据
        byte_count = response[2]
        data = response[3:3 + byte_count]
        
        values = []
        for i in range(0, len(data), 2):
            value = struct.unpack('>H', data[i:i+2])[0]
            values.append(value)
        
        return values
    
    def write_single_register(
        self, 
        address: int, 
        value: int
    ) -> bool:
        """
        写入单个寄存器 (功能码0x06)
        
        Args:
            address: 寄存器地址
            value: 写入值 (16位无符号整数)
            
        Returns:
            写入是否成功
        """
        # 组装请求帧
        request = struct.pack(
            '>BBHH',
            self.slave_id,
            FUNCTION_CODE_WRITE_SINGLE,
            address,
            value & 0xFFFF
        )
        
        # 计算并添加CRC
        crc = CRC16.calculate(request)
        request += struct.pack('<H', crc)
        
        # 发送请求并接收响应
        response = self._send_and_receive(request, 8)
        
        # 验证响应
        resp_address = struct.unpack('>H', response[2:4])[0]
        resp_value = struct.unpack('>H', response[4:6])[0]
        
        return resp_address == address and resp_value == (value & 0xFFFF)
    
    def write_multiple_registers(
        self, 
        address: int, 
        values: List[int]
    ) -> bool:
        """
        写入多个寄存器 (功能码0x10)
        
        Args:
            address: 寄存器起始地址
            values: 写入值列表
            
        Returns:
            写入是否成功
        """
        count = len(values)
        byte_count = count * 2
        
        # 组装请求帧
        request = struct.pack(
            '>BBHHB',
            self.slave_id,
            FUNCTION_CODE_WRITE_MULTIPLE,
            address,
            count,
            byte_count
        )
        
        # 添加数据
        for value in values:
            request += struct.pack('>H', value & 0xFFFF)
        
        # 计算并添加CRC
        crc = CRC16.calculate(request)
        request += struct.pack('<H', crc)
        
        # 发送请求并接收响应
        # 响应格式: [从站ID(1)] [功能码(1)] [起始地址(2)] [寄存器数量(2)] [CRC(2)]
        response = self._send_and_receive(request, 8)
        
        # 验证响应
        resp_address = struct.unpack('>H', response[2:4])[0]
        resp_count = struct.unpack('>H', response[4:6])[0]
        
        return resp_address == address and resp_count == count
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False

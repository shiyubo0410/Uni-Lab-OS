import serial
import time
from typing import Optional, Tuple

class SpinCoaterController:
    def __init__(self, port: str, baudrate: int = 19200, station: int = 1):
        self.port = port
        self.baudrate = baudrate
        self.station = station
        self.ser: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        try:
            # 第一步：先用9600波特率连接
            print(f"  尝试用9600波特率连接...")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=9600,
                bytesize=8,
                parity=serial.PARITY_EVEN,
                stopbits=1,
                timeout=1
            )
            
            if self.ser.is_open:
                print(f"  ✓ 9600连接成功")
                
                # 第二步：切换到19200波特率
                print(f"  切换到19200波特率...")
                self.ser.baudrate = 19200
                print(f"  ✓ 波特率已切换到19200")
                return True
            else:
                print(f"  ✗ 9600连接失败")
                return False
                
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def send_command(self, command_hex: str) -> Optional[bytes]:
        if not self.ser or not self.ser.is_open:
            print("串口未连接")
            return None
        
        try:
            command_bytes = bytes.fromhex(command_hex.replace(' ', ''))
            self.ser.write(command_bytes)
            time.sleep(0.05)
            response = self.ser.readall()
            return response
        except Exception as e:
            print(f"发送命令失败: {e}")
            return None
    
    def send_command_pair(self, command_pair: str) -> Tuple[Optional[bytes], Optional[bytes]]:
        parts = command_pair.split(' -> ')
        if len(parts) != 2:
            return None, None
        
        # 发送第一条命令（置位 FF00）
        print(f"    发送命令1: {parts[0]}")
        response1 = self.send_command(parts[0])
        print(f"    响应1: {response1.hex() if response1 else '无响应'}")
        
        time.sleep(0.2)  # 等待200ms
        
        # 发送第二条命令（复位 0000）
        print(f"    发送命令2: {parts[1]}")
        response2 = self.send_command(parts[1])
        print(f"    响应2: {response2.hex() if response2 else '无响应'}")
        
        return response1, response2
    
    def enable(self) -> bool:
        command = "01 05 00 10 FF 00 8D FF -> 01 05 00 10 00 00 CC 0F"
        response1, response2 = self.send_command_pair(command)
        return response1 is not None and response2 is not None
    
    def enable_status(self) -> bool:
        command = "01 01 00 1F 00 01 CC 0C"
        response = self.send_command(command)
        if response and len(response) >= 4:
            return bool(response[3] & 0x01)
        return False
    
    def vacuum_on(self) -> bool:
        command = "01 05 00 32 FF 00 2D F5 -> 01 05 00 32 00 00 6C 05"
        response1, response2 = self.send_command_pair(command)
        return response1 is not None and response2 is not None
    
    def vacuum_status(self) -> bool:
        command = "01 01 60 00 00 01 E3 CA"
        response = self.send_command(command)
        if response and len(response) >= 4:
            return bool(response[3] & 0x01)
        return False
    
    def vacuum_display(self) -> Optional[int]:
        command = "01 03 00 DC 00 01 45 F0"
        response = self.send_command(command)
        if response and len(response) >= 5:
            return (response[3] << 8) | response[4]
        return None
    
    def set_vacuum_protection(self, value: int) -> bool:
        if not (10 <= value <= 50):
            print("真空保护值必须在10-50之间")
            return False
        
        station_byte = self.station & 0xFF
        function_code = 0x06
        address = 0xA096
        address_hi = (address >> 8) & 0xFF
        address_lo = address & 0xFF
        value_hi = (value >> 8) & 0xFF
        value_lo = value & 0xFF
        
        data = [station_byte, function_code, address_hi, address_lo, value_hi, value_lo]
        crc = self._crc16_modbus(data)
        crc_lo = crc & 0xFF
        crc_hi = (crc >> 8) & 0xFF
        data.extend([crc_lo, crc_hi])
        
        command_hex = ' '.join(f'{b:02X}' for b in data)
        response = self.send_command(command_hex)
        return response is not None
    
    def manual_home(self) -> bool:
        command = "01 05 00 14 FF 00 9D CF -> 01 05 00 14 00 00 DC 0F"
        response1, response2 = self.send_command_pair(command)
        return response1 is not None and response2 is not None
    
    def single_step_start_stop(self) -> bool:
        command = "01 05 00 07 FF 00 3D FB -> 01 05 00 07 00 00 7C 0B"
        response1, response2 = self.send_command_pair(command)
        return response1 is not None and response2 is not None
    
    def single_step_running_status(self) -> bool:
        command = "01 01 00 01 00 01 AC 0A"
        response = self.send_command(command)
        if response and len(response) >= 4:
            return bool(response[3] & 0x01)
        return False
    
    def multi_step_start_stop(self) -> bool:
        command = "01 05 00 07 FF 00 3D FB -> 01 05 00 07 00 00 7C 0B"
        response1, response2 = self.send_command_pair(command)
        return response1 is not None and response2 is not None
    
    def multi_step_running_status(self) -> bool:
        command = "01 01 00 02 00 01 5C 0A"
        response = self.send_command(command)
        if response and len(response) >= 4:
            return bool(response[3] & 0x01)
        return False
    
    def set_single_step_speed(self, speed: int) -> bool:
        if not (10 <= speed <= 10000):
            print("单步速度必须在10-10000之间")
            return False
        
        return self._write_holding_register(0xA0DA, speed)
    
    def set_single_step_time(self, time_ms: int) -> bool:
        if not (0 <= time_ms <= 3000):
            print("单步时间必须在0-3000之间")
            return False
        
        return self._write_holding_register(0xA0DB, time_ms)
    
    def set_single_step_acceleration(self, acceleration: int) -> bool:
        if not (200 <= acceleration <= 30000):
            print("单步加速度必须在200-30000之间")
            return False
        
        return self._write_holding_register(0xA0DC, acceleration)
    
    def set_deceleration(self, deceleration: int) -> bool:
        if not (100 <= deceleration <= 2500):
            print("减速度必须在100-2500之间")
            return False
        
        return self._write_holding_register(0xA09E, deceleration)
    
    def get_run_speed(self) -> Optional[int]:
        return self._read_holding_register(0x007A)
    
    def get_run_time(self) -> Optional[int]:
        return self._read_holding_register(0x0046)
    
    def get_multi_step_total_time(self) -> Optional[int]:
        return self._read_holding_register(0x0048)
    
    def get_multi_step_current_step(self) -> Optional[int]:
        return self._read_holding_register(0x005C)
    
    def set_alignment_speed(self, speed: int) -> bool:
        if not (100 <= speed <= 500):
            print("对中速度必须在100-500之间")
            return False
        
        return self._write_holding_register(0xA0A0, speed)
    
    def set_alignment_time(self, time_ms: int) -> bool:
        if not (1 <= time_ms <= 100):
            print("对中时间必须在1-100之间")
            return False
        
        return self._write_holding_register(0xA0A2, time_ms)
    
    def set_oscillation_speed(self, speed: int) -> bool:
        if not (10 <= speed <= 800):
            print("摆动速度必须在10-800之间")
            return False
        
        return self._write_holding_register(0xA0A4, speed)
    
    def set_oscillation_acceleration(self, acceleration: int) -> bool:
        if not (10 <= acceleration <= 2000):
            print("摆动加速度必须在10-2000之间")
            return False
        
        return self._write_holding_register(0xA0A6, acceleration)
    
    def set_oscillation_time(self, time_ms: int) -> bool:
        if not (1 <= time_ms <= 100):
            print("摆动时间必须在1-100之间")
            return False
        
        return self._write_holding_register(0xA0A8, time_ms)
    
    def set_oscillation_count(self, count: int) -> bool:
        if not (1 <= count <= 20):
            print("摆动次数必须在1-20之间")
            return False
        
        return self._write_holding_register(0xAA0A, count)
    
    def set_multi_step_speed(self, step_num: int, speed: int) -> bool:
        if not (1 <= step_num <= 100):
            print("步骤号必须在1-100之间")
            return False
        if not (0 <= speed <= 10000):
            print("速度必须在0-10000之间")
            return False
        
        address = 0xA0E4 + (step_num - 1) * 3
        return self._write_holding_register(address, speed)
    
    def set_multi_step_time(self, step_num: int, time_ms: int) -> bool:
        if not (1 <= step_num <= 100):
            print("步骤号必须在1-100之间")
            return False
        if not (0 <= time_ms <= 3000):
            print("时间必须在0-3000之间")
            return False
        
        address = 0xA0E5 + (step_num - 1) * 3
        return self._write_holding_register(address, time_ms)
    
    def set_multi_step_acceleration(self, step_num: int, acceleration: int) -> bool:
        if not (1 <= step_num <= 100):
            print("步骤号必须在1-100之间")
            return False
        if not (200 <= acceleration <= 30000):
            print("加速度必须在200-30000之间")
            return False
        
        address = 0xA0E6 + (step_num - 1) * 3
        return self._write_holding_register(address, acceleration)
    
    def get_dispensing_value(self, step_num: int) -> Optional[int]:
        if not (1 <= step_num <= 100):
            print("步骤号必须在1-100之间")
            return None
        
        address = 0xA1AC + (step_num - 1)
        return self._read_holding_register(address)
    
    def get_current_page(self) -> Optional[int]:
        return self._read_holding_register(0x0003)
    
    def set_page(self, page_num: int) -> bool:
        if page_num not in [0x0003, 0x001B]:
            print("页面号必须是0x0003(单步运行画面)或0x001B(多步运行画面)")
            return False
        
        return self._write_holding_register(0x0006, page_num)
    
    def get_spin_stop_signal(self) -> bool:
        command = "01 01 00 5B 00 01 8C 19"
        response = self.send_command(command)
        if response and len(response) >= 4:
            return bool(response[3] & 0x01)
        return False
    
    def _read_holding_register(self, address: int) -> Optional[int]:
        station_byte = self.station & 0xFF
        function_code = 0x03
        address_hi = (address >> 8) & 0xFF
        address_lo = address & 0xFF
        count_hi = 0x00
        count_lo = 0x01
        
        data = [station_byte, function_code, address_hi, address_lo, count_hi, count_lo]
        crc = self._crc16_modbus(data)
        crc_lo = crc & 0xFF
        crc_hi = (crc >> 8) & 0xFF
        data.extend([crc_lo, crc_hi])
        
        command_hex = ' '.join(f'{b:02X}' for b in data)
        response = self.send_command(command_hex)
        
        if response and len(response) >= 5:
            return (response[3] << 8) | response[4]
        return None
    
    def _write_holding_register(self, address: int, value: int) -> bool:
        station_byte = self.station & 0xFF
        function_code = 0x06
        address_hi = (address >> 8) & 0xFF
        address_lo = address & 0xFF
        value_hi = (value >> 8) & 0xFF
        value_lo = value & 0xFF
        
        data = [station_byte, function_code, address_hi, address_lo, value_hi, value_lo]
        crc = self._crc16_modbus(data)
        crc_lo = crc & 0xFF
        crc_hi = (crc >> 8) & 0xFF
        data.extend([crc_lo, crc_hi])
        
        command_hex = ' '.join(f'{b:02X}' for b in data)
        response = self.send_command(command_hex)
        return response is not None
    
    @staticmethod
    def _crc16_modbus(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

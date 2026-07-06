import serial
import time

class ESP32Controller:
    def __init__(self, port="COM7", baudrate=115200, timeout=1):
        """初始化 ESP32 控制器
        
        Args:
            port: 串口端口号
            baudrate: 波特率
            timeout: 超时时间(秒)
        """
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.status = "idle"  # 添加状态属性
    
    def trigger_output(self, pin=None):
        """发送引脚触发指令并读取响应
        
        Args:
            pin: 要触发的引脚号,如果为 None 则发送 ON 指令
        """
        self.status = "running"
        
        # 根据是否指定引脚发送不同指令
        if pin is not None:
            command = f"PIN:{pin}:ON\n"
        else:
            command = "ON\n"
        
        self.ser.write(command.encode('utf-8'))
        
        # 读取 ESP32 返回信息
        time.sleep(0.1)  # 给 ESP32 一点时间响应
        while self.ser.in_waiting:  # 如果有串口数据
            try:
                response = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if response:  # 只打印非空响应
                    print("收到 ESP32:", response)
            except Exception as e:
                print(f"读取串口数据错误: {e}")
        
        self.status = "idle"
    
    def send_off(self, pin=None):
        """发送关闭指令
        
        Args:
            pin: 要关闭的引脚号,如果为 None 则发送 OFF 指令
        """
        self.status = "running"
        
        # 根据是否指定引脚发送不同指令
        if pin is not None:
            command = f"PIN:{pin}:OFF\n"
        else:
            command = "OFF\n"
        
        self.ser.write(command.encode('utf-8'))
        time.sleep(0.1)
        while self.ser.in_waiting:
            try:
                response = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if response:
                    print("收到 ESP32:", response)
            except Exception as e:
                print(f"读取串口数据错误: {e}")
        
        self.status = "idle"
    
    def close(self):
        """关闭串口连接"""
        self.status = "closed"
        self.ser.close()

# 使用示例
if __name__ == "__main__":
    # 创建控制器实例
    controller = ESP32Controller()
    
    # 触发指定引脚(例如引脚 2)
    controller.trigger_output(pin=17)
    
    time.sleep(1)
    
    # 关闭指定引脚
    controller.send_off(pin=2)
    
    # 或使用默认方式(不指定引脚)
    # controller.trigger_output()
    # controller.send_off()
    
    # controller.close()
import serial
import time

class ESP32Controller:
    def __init__(self, port="COM8", baudrate=115200, timeout=1):
        """初始化 ESP32 控制器
        
        Args:
            port: 串口端口号
            baudrate: 波特率
            timeout: 超时时间(秒)
        """
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
    
    def trigger_output(self):
        """发送 ON 指令并读取响应"""
        # 发送 ON 指令
        self.ser.write(b"ON\n")
        
        # 读取 ESP32 返回信息
        time.sleep(0.1)  # 给 ESP32 一点时间响应
        while self.ser.in_waiting:  # 如果有串口数据
            response = self.ser.readline().decode().strip()
            print("收到 ESP32:", response)
    
    def send_off(self):
        """发送 OFF 指令"""
        self.ser.write(b"OFF\n")
        time.sleep(0.1)
        while self.ser.in_waiting:
            response = self.ser.readline().decode().strip()
            print("收到 ESP32:", response)
    
    def close(self):
        """关闭串口连接"""
        self.ser.close()

# 使用示例
if __name__ == "__main__":
    # 创建控制器实例
    controller = ESP32Controller()
    
    # 触发输出
    controller.trigger_output()
    
    # 可选：需要时关闭
    # controller.send_off()
    # controller.close()
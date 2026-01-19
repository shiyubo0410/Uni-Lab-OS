import serial
import time

class ChinweDevice:
    """极简版 ChinWe 串口电机控制类"""

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None
        self.connect()

    def connect(self):
        """连接串口"""
        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=0.5)
            print(f"✅ 已连接到 {self.port} @ {self.baudrate}")
        except Exception as e:
            print(f"❌ 无法连接到串口: {e}")
            self.serial_port = None

    def send_command(self, command: str):
        """发送指令"""
        if not self.serial_port or not self.serial_port.is_open:
            print("⚠️ 串口未连接")
            return
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write((command + "\r").encode('utf-8'))
            self.serial_port.flush()
            print(f"➡️ 已发送指令: {command}")
            
            # 等待设备返回
            time.sleep(0.1)
            if self.serial_port.in_waiting:
                response = self.serial_port.read_all().decode(errors='ignore')
                print(f"⬅️ 设备响应: {response.strip()}")
            else:
                print("⚠️ 没有收到设备返回信息")
        except Exception as e:
            print(f"❌ 发送失败: {e}")


    def disconnect(self):
        """断开串口"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print("🔌 已断开连接")

def main():
    port = input("请输入串口号 (例如 COM10): ").strip()
    device = ChinweDevice(port)

    print("\n输入指令控制电机，例如：M 1 CW 2")
    print("输入 exit 退出程序\n")

    while True:
        cmd = input(">> ").strip()
        if cmd.lower() in ("exit", "quit"):
            break
        elif cmd:
            device.send_command(cmd)

    device.disconnect()
    print("程序已退出。")

if __name__ == "__main__":
    main()

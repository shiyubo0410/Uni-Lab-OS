"""
Zeta 一体式电机 - 修改 Modbus 从站地址工具 (寄存器 0xE0)

用途: 两个电机默认地址都是 1, 并在同一条 485 总线上会地址冲突。
      用本工具把其中一个电机地址改成 2。

⚠️ 使用前提: 总线上此刻只接【一个】要改的电机 (否则会同时改到两个)。

用法:
  python unilabos/devices/SHU/set_addr.py
按需修改下面的 PORT / NEW_ADDR。
"""

import serial
import struct
import time

PORT = "COM6"       # 电机所在串口
BAUD = 9600
NEW_ADDR = 2        # 要设成的新地址 (把这一个电机改成 2)
ADDR_REG = 0x00E0   # 设备地址寄存器


def crc(d: bytes) -> bytes:
    c = 0xFFFF
    for b in d:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return struct.pack("<H", c)


def txrx(ser, frame: bytes, note: str):
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()
    time.sleep(0.15)
    r = ser.read(64)
    print(f"{note}: TX={frame.hex(' ')}  RX={r.hex(' ') if r else '(empty)'}")
    return r


def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.3)
    print(f"打开 {PORT} @ {BAUD}")

    # 1) 用广播地址0读取当前设备地址 (手册示例: 00 03 00 E0 00 01)
    f = struct.pack(">BBHH", 0x00, 0x03, ADDR_REG, 1)
    f += crc(f)
    r = txrx(ser, f, "读当前地址")
    cur = None
    if r and len(r) >= 5 and r[1] == 0x03:
        cur = (r[3] << 8) | r[4]
        print(f"  -> 当前设备地址 = {cur}")
    else:
        print("  -> 读地址无有效返回; 若确定当前地址, 手动改下面 cur_addr")

    cur_addr = cur if cur is not None else 1  # 读不到就假定默认1

    if cur_addr == NEW_ADDR:
        print(f"当前地址已是 {NEW_ADDR}, 无需修改")
        ser.close()
        return

    # 2) 写新地址: FC06 到 0xE0
    f = struct.pack(">BBHH", cur_addr, 0x06, ADDR_REG, NEW_ADDR)
    f += crc(f)
    txrx(ser, f, f"把地址 {cur_addr} 改成 {NEW_ADDR}")

    # 3) 用新地址读回确认
    time.sleep(0.3)
    f = struct.pack(">BBHH", NEW_ADDR, 0x03, ADDR_REG, 1)
    f += crc(f)
    r = txrx(ser, f, "用新地址读回确认")
    if r and len(r) >= 5 and r[0] == NEW_ADDR and r[1] == 0x03:
        got = (r[3] << 8) | r[4]
        print(f"  -> 确认成功, 设备地址现在 = {got}")
    else:
        print("  -> 未读到新地址回复; 可能需要给电机断电重上电后地址才生效, 重上电后再跑 scan.py 验证")

    ser.close()


if __name__ == "__main__":
    main()

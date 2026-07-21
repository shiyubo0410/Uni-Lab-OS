import serial, time
from serial.tools import list_ports

# 兰格 BT100-2J 固定参数：1200bps, 8 数据位, 偶校验, 1 停止位
BAUD = 1200
PARITY = serial.PARITY_EVEN
ADDRS = range(1, 31)  # 设备地址 1~30


def stuff(data: bytes) -> bytes:
    """帧头 E9 之后的内容做字节转义：E8->E8 00, E9->E8 01"""
    out = bytearray()
    for b in data:
        if b == 0xE8:
            out += b"\xE8\x00"
        elif b == 0xE9:
            out += b"\xE8\x01"
        else:
            out.append(b)
    return bytes(out)


def unstuff(data: bytes) -> bytes:
    """接收侧还原：E8 00->E8, E8 01->E9"""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xE8 and i + 1 < len(data):
            out.append(0xE8 if data[i + 1] == 0x00 else 0xE9)
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def build(addr: int, pdu: bytes) -> bytes:
    """组帧：E9 + stuff(addr + len + pdu + fcs)，fcs = XOR(addr,len,pdu)"""
    ln = len(pdu)
    body = bytes([addr, ln]) + pdu
    fcs = 0
    for b in body:
        fcs ^= b
    return b"\xE9" + stuff(body + bytes([fcs]))


def scan_port(port: str):
    try:
        ser = serial.Serial(port, BAUD, bytesize=8, parity=PARITY,
                            stopbits=1, timeout=0.3)
    except Exception as e:
        print(f"  打开 {port} 失败: {e}")
        return
    hits = []
    for addr in ADDRS:
        # 读取设备地址命令 RID = 52 49 44
        frame = build(addr, b"\x52\x49\x44")
        ser.reset_input_buffer()
        ser.write(frame)
        ser.flush()
        time.sleep(0.15)
        r = ser.read(64)
        if r and r[0] == 0xE9:
            body = unstuff(r[1:])
            print(f"*** {port} 命中地址 {addr}: 应答 {r.hex(' ').upper()}  (还原 {body.hex(' ').upper()})")
            hits.append(addr)
    ser.close()
    if not hits:
        print(f"  {port}: 未发现任何泵 (1200/8/E/1)")
    return hits


ports = [p.device for p in list_ports.comports()]
print("本机串口:", ports)
for p in list_ports.comports():
    print(f"  {p.device}: {p.description}")

for port in ports:
    print(f"扫描 {port} ...")
    scan_port(port)

print("扫描结束")

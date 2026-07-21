def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def build_read_holding_register_command(station, address, count=1):
    station_byte = station & 0xFF
    function_code = 0x03
    address_hi = (address >> 8) & 0xFF
    address_lo = address & 0xFF
    count_hi = (count >> 8) & 0xFF
    count_lo = count & 0xFF
    
    data = [station_byte, function_code, address_hi, address_lo, count_hi, count_lo]
    crc = crc16_modbus(data)
    crc_lo = crc & 0xFF
    crc_hi = (crc >> 8) & 0xFF
    
    data.extend([crc_lo, crc_hi])
    return ' '.join(f'{b:02X}' for b in data)

def build_write_holding_register_command(station, address, value):
    station_byte = station & 0xFF
    function_code = 0x06
    address_hi = (address >> 8) & 0xFF
    address_lo = address & 0xFF
    value_hi = (value >> 8) & 0xFF
    value_lo = value & 0xFF
    
    data = [station_byte, function_code, address_hi, address_lo, value_hi, value_lo]
    crc = crc16_modbus(data)
    crc_lo = crc & 0xFF
    crc_hi = (crc >> 8) & 0xFF
    
    data.extend([crc_lo, crc_hi])
    return ' '.join(f'{b:02X}' for b in data)

def build_read_coil_command(station, address, count=1):
    station_byte = station & 0xFF
    function_code = 0x01
    address_hi = (address >> 8) & 0xFF
    address_lo = address & 0xFF
    count_hi = (count >> 8) & 0xFF
    count_lo = count & 0xFF
    
    data = [station_byte, function_code, address_hi, address_lo, count_hi, count_lo]
    crc = crc16_modbus(data)
    crc_lo = crc & 0xFF
    crc_hi = (crc >> 8) & 0xFF
    
    data.extend([crc_lo, crc_hi])
    return ' '.join(f'{b:02X}' for b in data)

def build_write_coil_command(station, address, value):
    station_byte = station & 0xFF
    function_code = 0x05
    address_hi = (address >> 8) & 0xFF
    address_lo = address & 0xFF
    value_hi = (value >> 8) & 0xFF
    value_lo = value & 0xFF
    
    data = [station_byte, function_code, address_hi, address_lo, value_hi, value_lo]
    crc = crc16_modbus(data)
    crc_lo = crc & 0xFF
    crc_hi = (crc >> 8) & 0xFF
    
    data.extend([crc_lo, crc_hi])
    return ' '.join(f'{b:02X}' for b in data)

def parse_hex_address(hex_str):
    hex_str = hex_str.strip().upper()
    if hex_str.startswith('H'):
        hex_str = hex_str[1:]
    return int(hex_str, 16)

def parse_function_code(code_str):
    if '读03' in code_str:
        return 'read_holding_register'
    elif '写06' in code_str:
        return 'write_holding_register'
    elif '读01' in code_str:
        return 'read_coil'
    elif '写05' in code_str:
        return 'write_coil'
    return None

def convert_line(line, station=1):
    parts = line.split('\t')
    if len(parts) < 4:
        return None
    
    name = parts[0].strip()
    function_code_str = parts[1].strip()
    address_hex = parts[3].strip()
    
    if not address_hex or address_hex == '......':
        return None
    
    func_type = parse_function_code(function_code_str)
    if not func_type:
        return None
    
    address = parse_hex_address(address_hex)
    
    results = []
    if func_type == 'read_holding_register':
        command = build_read_holding_register_command(station, address)
        results.append(f"{name}\t{command}")
    elif func_type == 'write_holding_register':
        command = build_write_holding_register_command(station, address, 0)
        results.append(f"{name}\t{command}")
    elif func_type == 'read_coil':
        command = build_read_coil_command(station, address)
        results.append(f"{name}\t{command}")
    elif func_type == 'write_coil':
        command_on = build_write_coil_command(station, address, 0xFF00)
        command_off = build_write_coil_command(station, address, 0x0000)
        results.append(f"{name}\t{command_on} -> {command_off}")
    
    return results

def main():
    input_file = 'inf_xuantu.txt'
    output_file = 'modbus_commands.txt'
    
    print(f"正在读取 {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"正在转换命令...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for line in lines:
            line = line.strip()
            if not line or line.startswith('设备串口参数') or line.startswith('名称'):
                continue
            
            results = convert_line(line)
            if results:
                for result in results:
                    f.write(result + '\n')
    
    print(f"转换完成！结果已保存到 {output_file}")

if __name__ == '__main__':
    main()

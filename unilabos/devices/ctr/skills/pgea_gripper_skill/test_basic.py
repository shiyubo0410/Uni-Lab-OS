"""
PGEA夹爪控制库 - 基础测试脚本

用于验证库的基本功能是否正常工作。
"""

import sys
import time


def test_imports():
    """测试导入"""
    print("测试导入...")
    try:
        from pgea_gripper_skill import (
            PGEAGripper,
            GripperStatus,
            ModbusRTUClient,
            CRC16,
            REG_INIT_GRIPPER,
            REG_FORCE,
            REG_POSITION,
            GRIP_STATUS_GRIPPED,
            ERROR_NONE,
        )
        print("✓ 导入成功")
        return True
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_crc16():
    """测试CRC16计算"""
    print("\n测试CRC16计算...")
    from pgea_gripper_skill import CRC16
    
    # 测试数据: 01 06 01 00 00 01 (初始化命令)
    test_data = bytes([0x01, 0x06, 0x01, 0x00, 0x00, 0x01])
    expected_crc = 0xF649  # 对应的CRC值 (小端: 49 F6)
    
    crc = CRC16.calculate(test_data)
    
    if crc == expected_crc:
        print(f"✓ CRC计算正确: {hex(crc)}")
        return True
    else:
        print(f"✗ CRC计算错误: 期望{hex(expected_crc)}, 实际{hex(crc)}")
        return False


def test_constants():
    """测试常量定义"""
    print("\n测试常量定义...")
    from pgea_gripper_skill import (
        FORCE_MIN, FORCE_MAX,
        POSITION_MIN, POSITION_MAX,
        SPEED_MIN, SPEED_MAX,
        DEFAULT_BAUDRATE, DEFAULT_SLAVE_ID,
    )
    
    checks = [
        (FORCE_MIN, 20, "FORCE_MIN"),
        (FORCE_MAX, 100, "FORCE_MAX"),
        (POSITION_MIN, 0, "POSITION_MIN"),
        (POSITION_MAX, 1000, "POSITION_MAX"),
        (SPEED_MIN, 1, "SPEED_MIN"),
        (SPEED_MAX, 100, "SPEED_MAX"),
        (DEFAULT_BAUDRATE, 115200, "DEFAULT_BAUDRATE"),
        (DEFAULT_SLAVE_ID, 1, "DEFAULT_SLAVE_ID"),
    ]
    
    all_passed = True
    for actual, expected, name in checks:
        if actual == expected:
            print(f"✓ {name} = {actual}")
        else:
            print(f"✗ {name}: 期望{expected}, 实际{actual}")
            all_passed = False
    
    return all_passed


def test_gripper_status():
    """测试GripperStatus数据类"""
    print("\n测试GripperStatus...")
    from pgea_gripper_skill import GripperStatus
    
    # 创建状态对象
    status = GripperStatus(
        initialized=True,
        grip_status=2,  # 已夹住
        position=500,
        speed=30,
        current=100,
        error_code=0,
        io_input=0,
        io_output=2,
        motor_temp=45,
    )
    
    checks = [
        (status.initialized, True, "initialized"),
        (status.is_gripped, True, "is_gripped"),
        (status.is_moving, False, "is_moving"),
        (status.has_error, False, "has_error"),
        (status.position, 500, "position"),
    ]
    
    all_passed = True
    for actual, expected, name in checks:
        if actual == expected:
            print(f"✓ {name} = {actual}")
        else:
            print(f"✗ {name}: 期望{expected}, 实际{actual}")
            all_passed = False
    
    return all_passed


def test_error_descriptions():
    """测试错误码描述"""
    print("\n测试错误码描述...")
    from pgea_gripper_skill import ERROR_DESCRIPTIONS, ERROR_UNDERVOLTAGE, ERROR_OVERCURRENT
    
    # 检查关键错误码是否有描述
    errors_to_check = [
        ERROR_UNDERVOLTAGE,
        ERROR_OVERCURRENT,
        0,  # 无错误
    ]
    
    all_passed = True
    for error_code in errors_to_check:
        desc = ERROR_DESCRIPTIONS.get(error_code)
        if desc:
            print(f"✓ 错误码 {error_code}: {desc[:30]}...")
        else:
            print(f"✗ 错误码 {error_code}: 无描述")
            all_passed = False
    
    return all_passed


def test_register_addresses():
    """测试寄存器地址"""
    print("\n测试寄存器地址...")
    from pgea_gripper_skill import (
        REG_INIT_GRIPPER,
        REG_FORCE,
        REG_POSITION,
        REG_SPEED,
        REG_INIT_STATUS,
        REG_GRIP_STATUS,
    )
    
    # 验证关键寄存器地址
    expected_addresses = {
        "REG_INIT_GRIPPER": (0x0100, REG_INIT_GRIPPER),
        "REG_FORCE": (0x0101, REG_FORCE),
        "REG_POSITION": (0x0103, REG_POSITION),
        "REG_SPEED": (0x0104, REG_SPEED),
        "REG_INIT_STATUS": (0x0200, REG_INIT_STATUS),
        "REG_GRIP_STATUS": (0x0201, REG_GRIP_STATUS),
    }
    
    all_passed = True
    for name, (expected, actual) in expected_addresses.items():
        if expected == actual:
            print(f"✓ {name} = 0x{actual:04X}")
        else:
            print(f"✗ {name}: 期望0x{expected:04X}, 实际0x{actual:04X}")
            all_passed = False
    
    return all_passed


def main():
    """主测试函数"""
    print("=" * 50)
    print("PGEA夹爪控制库 - 基础测试")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_crc16,
        test_constants,
        test_gripper_status,
        test_error_descriptions,
        test_register_addresses,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ 测试异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")
    
    if all(results):
        print("✓ 所有测试通过!")
        return 0
    else:
        print("✗ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

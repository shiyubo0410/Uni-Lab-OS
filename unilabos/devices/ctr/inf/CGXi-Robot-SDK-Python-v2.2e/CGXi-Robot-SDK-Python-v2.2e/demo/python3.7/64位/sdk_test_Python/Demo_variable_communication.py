import cgxiapi
from ctypes import *
import time
import basestruct

# 机械臂创建连接
robotHandle = 1
re1 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
# re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：", re1[0].value)
if re1[0].value != 0:
    print("连接失败")
    exit()
robotHandle = re1[1].value


##3.4.3通讯变量
#读bool寄存器
def api_demo_cr_get_boolRegValue():
    startAddress = 1
    offsetLength = 2
    result = cgxiapi.cr_get_boolRegValue(robotHandle, startAddress, offsetLength)
    print("读位寄存器结果：", result[0].value)
    assert (result[0].value == 0)
    i = 0
    while i < 2:
        print(result[1][i])
        i = i + 1


#写bool寄存器
def api_demo_cr_set_boolRegValue():
    startAddress = 1
    offsetLength = 5
    regData = [0, 0, 0, 0, 0]
    result = cgxiapi.cr_set_boolRegValue(robotHandle, startAddress, offsetLength, regData)
    assert (result.value == 0)
    print("写位寄存器结果：", result.value)


#读int16寄存器
def api_demo_cr_get_int16RegValue():
    startAddress = 1
    offsetLength = 2
    result = cgxiapi.cr_get_int16RegValue(robotHandle, startAddress, offsetLength)
    print("读int16寄存器结果：", result[0].value)
    assert (result[0].value == 0)
    i = 0
    while i < 2:
        print(result[1][i])
        i = i + 1


#写int16寄存器
def api_demo_cr_set_int16RegValue():
    startAddress = 1
    offsetLength = 5
    regData = [0, 0, 0, 0, 0]
    result = cgxiapi.cr_set_int16RegValue(robotHandle, startAddress, offsetLength, regData)
    assert (result.value == 0)
    print("写int16寄存器结果：", result.value)


#读int32寄存器
def api_demo_cr_get_int32RegValue():
    startAddress = 1
    offsetLength = 2
    result = cgxiapi.cr_get_int32RegValue(robotHandle, startAddress, offsetLength)
    print("读int32寄存器结果：", result[0].value)
    assert (result[0].value == 0)
    i = 0
    while i < 2:
        print(result[1][i])
        i = i + 1


#写int32寄存器
def api_demo_cr_set_int32RegValue():
    startAddress = 1
    offsetLength = 5
    regData = [0, 0, 0, 0, 0]
    result = cgxiapi.cr_set_int32RegValue(robotHandle, startAddress, offsetLength, regData)
    assert (result.value == 0)
    print("写int32寄存器结果：", result.value)


#读float寄存器
def api_demo_cr_get_floatRegValue():
    startAddress = 1
    offsetLength = 2
    result = cgxiapi.cr_get_floatRegValue(robotHandle, startAddress, offsetLength)
    print("读float寄存器结果：", result[0].value)
    assert (result[0].value == 0)
    i = 0
    while i < 2:
        print(result[1][i])
        i = i + 1


#写float寄存器
def api_demo_cr_set_floatRegValue():
    startAddress = 1
    offsetLength = 5
    regData = [0, 0, 0, 0, 0]
    result = cgxiapi.cr_set_floatRegValue(robotHandle, startAddress, offsetLength, regData)
    assert (result.value == 0)
    print("写float寄存器结果：", result.value)




#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_boolRegValue()
    api_demo_cr_set_boolRegValue()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()
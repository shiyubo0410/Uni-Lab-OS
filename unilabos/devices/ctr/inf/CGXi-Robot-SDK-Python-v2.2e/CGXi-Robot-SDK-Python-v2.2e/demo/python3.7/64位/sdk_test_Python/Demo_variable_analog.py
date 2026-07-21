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



##3.4.2模拟量
#读控制柜模拟量输出
def api_demo_cr_get_stdAnalogOut():
    index = 0
    result = cgxiapi.cr_get_stdAnalogOut(robotHandle, index)
    print("读控制柜模拟量输出结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#写控制柜模拟量输出
def api_demo_cr_set_stdAnalogOut():
    index = 0
    val = 4
    result = cgxiapi.cr_set_stdAnalogOut(robotHandle, index, val)
    print("写控制柜标准数字输出结果：", result.value)
    assert (result.value == 0)


#读工具端模拟量输入
def api_demo_cr_get_toolAnalogIn():
    index = 0
    result = cgxiapi.cr_get_toolAnalogIn(robotHandle, index)
    print("读工具端模拟量输入结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#读控制柜模拟量输入
def api_demo_cr_get_stdAnalogIn():
    index = 0
    result = cgxiapi.cr_get_stdAnalogIn(robotHandle, index)
    print("读控制柜模拟量输入结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#读机械臂控制柜和工具端上所有输入数字量和模拟量
def api_demo_cr_get_allDAInput():
    controllerDI = [0, 0, 0, 0, 0, 0, 0, 0]
    controllerCI = [0, 0, 0, 0, 0, 0, 0, 0]
    controllerAI = [0, 0, 0]
    toolDI = [0, 0]
    toolAI = [0, 0]
    result = cgxiapi.cr_get_allDAInput(robotHandle, controllerDI, controllerCI, controllerAI, toolDI, toolAI)
    print("读机械臂控制柜和工具端上所有输入数字量和模拟量结果：", result.value)
    assert (result.value == 0)
    i = 0
    while i < 8:
        print(controllerDI[i])
        print(controllerCI[i])
        i += 1
    i = 0
    while i < 3:
        print(controllerAI[i])
        i += 1
    i = 0
    while i < 2:
        print(toolDI[i])
        print(toolAI[i])
        i += 1


#读机械臂控制柜和工具端上所有输出数字量和模拟量
def api_demo_cr_get_allDAOutput():
    controllerDO = [0, 0, 0, 0, 0, 0, 0, 0]
    controllerCO = [0, 0, 0, 0, 0, 0, 0, 0]
    controllerAO = [0, 0, 0]
    toolDO = [0, 0]
    result = cgxiapi.cr_get_allDAOutput(robotHandle, controllerDO, controllerCO, controllerAO, toolDO)
    print("读机械臂控制柜和工具端上所有输出数字量和模拟量结果：", result.value)
    assert (result.value == 0)
    i = 0
    while i < 8:
        print(controllerDO[i])
        print(controllerCO[i])
        i += 1
    print(controllerAO[1])
    i = 0
    while i < 2:
        print(toolDO[i])
        i += 1


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_allDAOutput()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()

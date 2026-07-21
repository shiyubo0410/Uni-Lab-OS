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


##3.4.1数字量
#读控制柜标准数字输出
def api_demo_cr_get_stdDigitalOut():
    index = 0
    result = cgxiapi.cr_get_stdDigitalOut(robotHandle, index)
    print("读控制柜标准数字输出结果：", result[0].value)
    assert(result[0].value == 0)
    print("值为：", result[1].value)


#写控制柜标准数字输出
def api_demo_cr_set_stdDigitalOut():
    index = 1
    val = 0
    result = cgxiapi.cr_set_stdDigitalOut(robotHandle, index, val)
    print("写控制柜标准数字输出结果：", result.value)
    assert (result.value == 0)


#读控制柜可配置数字输出
def api_demo_cr_get_configDigitalOut():
    index = 0
    result = cgxiapi.cr_get_configDigitalOut(robotHandle, index)
    print("读控制柜可配置数字输出结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#写控制柜可配置数字输出
def api_demo_cr_set_configDigitalOut():
    index = 0
    val = 0
    result = cgxiapi.cr_set_configDigitalOut(robotHandle, index, val)
    print("写控制柜可配置数字输出结果：", result.value)
    assert (result.value == 0)


#读工具端数字输出
def api_demo_cr_get_toolDigitalOut():
    index = 0
    result = cgxiapi.cr_get_toolDigitalOut(robotHandle, index)
    print("读工具端数字输出结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#写工具端数字输出
def api_demo_cr_set_toolDigitalOut():
    index = 0
    val = 0
    result = cgxiapi.cr_set_toolDigitalOut(robotHandle, index, val)
    print("写工具端数字输出结果：", result.value)
    assert (result.value == 0)


#读控制柜标准数字输入
def api_demo_cr_get_stdDigitalIn():
    index = 0
    result = cgxiapi.cr_get_stdDigitalIn(robotHandle, index)
    print("读控制柜标准数字输入结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#读控制柜可配置数字输入
def api_demo_cr_get_configDigitalIn():
    index = 0
    result = cgxiapi.cr_get_configDigitalIn(robotHandle, index)
    print("读控制柜可配置数字输入结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#读工具端数字输入
def api_demo_cr_get_toolDigitalIn():
    index = 0
    result = cgxiapi.cr_get_toolDigitalIn(robotHandle, index)
    print("读工具端数字输入结果：", result[0].value)
    assert (result[0].value == 0)
    print("值为：", result[1].value)


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_stdDigitalOut()
    api_demo_cr_set_stdDigitalOut()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()
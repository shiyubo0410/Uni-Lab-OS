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


##3.4.5其它IO
#获取编码器计数数量
def api_demo_cr_get_encoderTickCnt():
    encoderChannel = 0
    result = cgxiapi.cr_get_encoderTickCnt(robotHandle, encoderChannel)
    print("获取编码器计数数量结果：", result[0].value)
    assert (result[0].value == 0)
    print("编码器计数数量：", result[1].value)

#设置监控界面的工具输出电压
def api_demo_cr_set_ToolOutputVoltage():
    toolPower = basestruct.ToolPower.Power_on
    result = cgxiapi.cr_set_ToolOutputVoltage(robotHandle, toolPower)
    print("返回结果：", result.value)
    assert (result.value == 0)

#读取监控界面的工具输出电压
def api_demo_cr_get_ToolOutputVoltage():
    toolPower = basestruct.ToolPower()
    result = cgxiapi.cr_get_ToolOutputVoltage(robotHandle, toolPower)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("监控界面的工具输出电压：", toolPower.value)

#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_encoderTickCnt()
    api_demo_cr_get_ToolOutputVoltage()
    api_demo_cr_set_ToolOutputVoltage()
    # 机械臂断开连接
    re0=cgxiapi.cr_destroy_robot(robotHandle)
    if re0.value != 0:
        print("断开失败")
        exit()

if __name__ == "__main__":
    main()
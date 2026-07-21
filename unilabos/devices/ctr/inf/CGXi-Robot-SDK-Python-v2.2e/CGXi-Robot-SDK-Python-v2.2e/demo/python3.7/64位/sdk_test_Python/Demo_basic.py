import cgxiapi
from ctypes import *
import time
import basestruct


##3.1.1基础接口
#机械臂创建连接
robotHandle = 1
ipAddr="192.168.6.6"
port=2323
passwd="123"
re1=cgxiapi.cr_create_robot(robotHandle,ipAddr,port,passwd)
# re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：",re1[0].value)
if re1[0].value != 0 :
    print("连接失败")
    exit()
robotHandle = re1[1].value

def api_demo_cr_create_robot():
    robotHandle = 1
    ipAddr = "192.168.6.6"
    port = 2323
    passwd = "123"
    re1 = cgxiapi.cr_create_robot(robotHandle, ipAddr, port, passwd)
    # re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
    print("机械臂建立连接返回值：", re1[0].value)
    assert (re1[0].value == 0)

def api_demo_cr_destroy_robot():
    result = cgxiapi.cr_destroy_robot(robotHandle)
    assert (result.value == 0)

#机械臂关机
def api_demo_cr_shutdown():
    result = cgxiapi.cr_shutdown(robotHandle)
    print("返回结果: ", result.value)
    assert (result.value == 0)


#机械臂上电
def api_demo_cr_poweron():
    result = cgxiapi.cr_poweron(robotHandle)
    print("机械臂上电结果: ", result.value)
    assert (result.value == 0)


#机械臂断电
def api_demo_cr_poweroff():
    result = cgxiapi.cr_poweroff(robotHandle)
    print("机械臂下电结果: ", result.value)
    assert (result.value == 0)


#机械臂使能
def api_demo_cr_enable():
    result = cgxiapi.cr_enable(robotHandle)
    print("机械臂使能结果：", result.value)
    assert (result.value == 0)


#机械臂关使能
def api_demo_cr_disable():
    result = cgxiapi.cr_disable(robotHandle)
    print("机械臂关使能结果：", result.value)
    assert (result.value == 0)


#机械臂故障复位
def api_demo_cr_FaultReset():
    result = cgxiapi.cr_FaultReset(robotHandle)
    print("机械臂故障复位结果: ", result.value)
    assert (result.value == 0)


# 获取控制柜状态
def api_demo_cr_get_controlMode():
    result = cgxiapi.cr_get_controlMode(robotHandle)
    print("获取控制柜状态结果：", result[0].value, "控制柜状态", result[1].value)
    assert (result[0].value == 0)


#写机械臂速度百分比
def api_demo_cr_set_robotSpeedPercent():
    speedPercent = 50
    result = cgxiapi.cr_set_robotSpeedPercent(robotHandle, speedPercent)
    print("写入速度百分比结果：", result.value)
    assert (result.value == 0)


#读机械臂速度百分比
def api_demo_cr_get_robotSpeedPercent():
    result = cgxiapi.cr_get_robotSpeedPercent(robotHandle)
    print("读速度百分比结果：", result[0].value, "速度百分比为", result[1].value)
    assert (result[0].value == 0)


#读SDK版本号
def api_demo_cr_get_sdk_version():
    result = cgxiapi.cr_get_sdk_version()
    print("读SDK版本号结果：", result[0].value)
    assert (result[0].value == 0)
    print("SDK版本号：",result[1].value)


#获取机械臂状态数据
def api_demo_cr_get_robotStateData():
    robotStateData = basestruct.RobotStateData()
    result = cgxiapi.cr_get_robotStateData(robotHandle, robotStateData)
    print("获取机械臂状态数据结果：", result.value)
    assert (result.value == 0)
    print("tcpActualPose:", list(robotStateData.tcpActualPose))
    print("jointActualPos:", list(robotStateData.jointActualPos))
    print("robotMode:", robotStateData.robotMode.value)
    print("robotMoveStatus:", robotStateData.robotMoveStatus)
    print("robotSpeedPercent:", robotStateData.robotSpeedPercent)
    print("configurableDigitalOutput:", list(robotStateData.configurableDigitalOutput))


#主函数
def main():
    #####在此处调用函数
    # api_demo_cr_enable()
    #api_demo_cr_get_robotSpeedPercent()
    api_demo_cr_get_sdk_version()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()










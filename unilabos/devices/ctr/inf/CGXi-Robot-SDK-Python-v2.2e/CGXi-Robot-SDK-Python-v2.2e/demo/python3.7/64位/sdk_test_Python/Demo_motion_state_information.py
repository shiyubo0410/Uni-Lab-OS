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



##3.2.2运动状态信息
#读实际TCP位置
def api_demo_cr_get_tcpActualPose():
    pose = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_tcpActualPose(robotHandle, pose)
    print("读机械臂实际tcp结果：", result.value)
    assert(result.value == 0)
    print("实际tcp位姿为", pose)


#读目标TCP位置
def api_demo_cr_get_tcpTargetPose():
    pose = [1, 1, 0, 0, 0, 0]
    result = cgxiapi.cr_get_tcpTargetPose(robotHandle, pose)
    print("读机械臂目标tcp结果：", result.value)
    assert (result.value == 0)
    print("目标位姿为：", pose)


#读实际TCP速度
def api_demo_cr_get_tcpActualSpeed():
    speed = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_tcpActualSpeed(robotHandle, speed)
    print("读机械臂实际tcp速度结果：", result.value)
    assert (result.value == 0)
    print("实际速度为：", speed)


#读目标TCP速度
def api_demo_cr_get_tcpTargetSpeed():
    speed = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_tcpActualSpeed(robotHandle, speed)
    print("读机械臂目标tcp速度结果：", result.value)
    assert (result.value == 0)
    print("目标速度为：", speed)


#读实际TCP加速度
def api_demo_cr_get_tcpActualAcceleration():
    acceleration = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_tcpActualAcceleration(robotHandle, acceleration)
    print("读机械臂实际TCP加速度结果：", result.value)
    assert (result.value == 0)
    print("实际加速度为：", acceleration)


#读当前使用的TCP偏移信息
def api_demo_cr_get_currentTCPmsg():
    tcpMsgList = basestruct.TCPMsg()
    result = cgxiapi.cr_get_currentTCPmsg(robotHandle, tcpMsgList)
    print("读当前使用的TCP偏移信息结果：", result.value)
    assert(result.value == 0)
    print("当前使用的TCP偏移信息为：", tcpMsgList.tcpName)
    i = 0
    while i < 6:
        print(tcpMsgList.tcpOffset[i])
        i += 1


#读取当前使用负载信息
def api_demo_cr_get_currentPayloadmsg():
    payloadMsgList = basestruct.PayLoad()
    result = cgxiapi.cr_get_currentPayloadmsg(robotHandle, payloadMsgList)
    print("读取当前使用负载信息结果：", result.value)
    assert (result.value == 0)
    print("当前使用负载信息为：", payloadMsgList.payloadName, payloadMsgList.toolPayload)
    i = 0
    while i < 3:
        print(payloadMsgList.centerOfGravity[i])
        i += 1

#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_tcpActualPose()
    api_demo_cr_get_currentTCPmsg()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()






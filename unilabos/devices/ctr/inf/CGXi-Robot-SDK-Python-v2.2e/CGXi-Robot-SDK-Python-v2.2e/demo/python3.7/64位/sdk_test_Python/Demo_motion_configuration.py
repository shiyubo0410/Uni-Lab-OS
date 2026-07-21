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


##3.2.3运动配置
#读所有TCP偏移信息列表
def api_demo_cr_get_allTCPmsg():
    stru_info = create_string_buffer(sizeof(basestruct.TCPMsg()) * 20)
    tcpMsgList = POINTER(basestruct.TCPMsg)(stru_info)
    result = cgxiapi.cr_get_allTCPmsg(robotHandle, tcpMsgList)
    print("读所有TCP偏移信息列表结果：", result[0].value, result[1].value)
    assert (result[0].value == 0)
    validNumber = result[1].value
    j = 0
    i = 0
    while j < validNumber:
        print(tcpMsgList[j].tcpName)
        while i < basestruct.ROB_AXIS_NUM:
            print(tcpMsgList[j].tcpOffset[i])
            i += 1
        j += 1
        i = 0



#读所有负载信息
def api_demo_cr_get_allPayloadmsg():
    stru_info = create_string_buffer(sizeof(basestruct.PayLoad()) * 20)
    payloadMsgList = POINTER(basestruct.PayLoad)(stru_info)
    result = cgxiapi.cr_get_allPayloadmsg(robotHandle, payloadMsgList)
    print("读所有TCP偏移信息列表结果：", result[0].value, result[1].value)
    assert (result[0].value == 0)
    validNumber = result[1].value
    j = 0
    i = 0
    while j < validNumber:
        print(payloadMsgList[j].payloadName)
        print(payloadMsgList[j].toolPayload)
        while i < 3:
            print(payloadMsgList[j].centerOfGravity[i])
            i += 1
        j += 1
        i = 0


#获取指定TCPoffset的位姿
def api_demo_cr_get_AssignTCP_Pose():
    dstTCPoffset = [0, 0, 0, 60, 60, 60]
    dstPose = [10, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_AssignTCP_Pose(robotHandle, dstTCPoffset, dstPose)
    print("获取指定TCPoffset的位姿结果：", result.value)
    assert (result.value == 0)
    print("指定TCPoffset的位姿为：", dstPose)



#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_allTCPmsg()
    #api_demo_cr_get_AssignTCP_Pose()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()
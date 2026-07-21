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


##3.5.2运动学
#正解
def api_demo_cr_kineForward():
    posetojointpose = [0, 0, 0, 0, 0, 0]
    pose = [0, 0, 0, 0, 0, 0]
    jointpose = [0, 0, 0, 0, 0, 0]
    tcpMsg = basestruct.TCPMsg()
    py_tcpMsg_pointer_ = byref(tcpMsg)
    cgxiapi.cr_get_currentTCPmsg(robotHandle, py_tcpMsg_pointer_)
    cgxiapi.cr_get_jointActualPos(robotHandle, jointpose)
    result = cgxiapi.cr_kineForward(robotHandle, jointpose, pose)
    assert (result.value == 0)
    cgxiapi.cr_poseTrans(pose, tcpMsg.tcpOffset, posetojointpose)
    print("正解结果:", posetojointpose[0], posetojointpose[1], posetojointpose[2], posetojointpose[3],
          posetojointpose[4], posetojointpose[5])


#逆解
def api_demo_cr_kineInverse():
    tarjointpose = [0, 0, 0, 0, 0, 0]
    flangepose = [0, 0, 0, 0, 0, 0]
    pose = [0, 0, 0, 0, 0, 0]
    jointpose = [0, 0, 0, 0, 0, 0]
    tcpMsg = basestruct.TCPMsg()
    py_tcpMsg_pointer_ = byref(tcpMsg)
    cgxiapi.cr_get_currentTCPmsg(robotHandle, py_tcpMsg_pointer_)
    cgxiapi.cr_get_jointActualPos(robotHandle, jointpose)
    cgxiapi.cr_get_tcpActualPose(robotHandle, pose)
    cgxiapi.cr_TcpToFlangePose(pose, tcpMsg.tcpOffset, flangepose)
    result = cgxiapi.cr_kineInverse(robotHandle, flangepose, jointpose, tarjointpose)
    print(result.value)
    assert (result.value == 0)
    print("逆解结果：", tarjointpose[0], tarjointpose[1], tarjointpose[2], tarjointpose[3], tarjointpose[4],
          tarjointpose[5])


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_kineForward()
    api_demo_cr_kineInverse()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()
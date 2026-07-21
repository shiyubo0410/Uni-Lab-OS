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



#点动运动
def api_demo_cr_moveJog():
    pointControlPara = basestruct.PointControlPara()
    pointControlPara.jointpos = (0, 0, 0, 0, 0, 0)
    pointControlPara.pose = (0, 5, 0, 0, 0, 0)
    pointControlPara.tcpOffset = (0, 0, 0, 0, 0, 0)
    pointControlPara.tcpID = -1
    pointControlPara.speed = (30, 30, 30, 30, 30, 30)
    pointControlPara.acc = (30, 30, 30, 30, 30, 30)
    pointControlPara.coordinatePose = (114.3, -390.498, 215.347, -180, 0, 0)
    pointControlPara.jerk = (60, 60, 60, 60, 60, 60)
    pointControlPara.coordinateType = basestruct.CoordinateType.PointCoordinate
    pointControlPara.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlPara.pointTransRadius = 0
    pointControlPara.poseTranType = basestruct.PoseTranType.poseTranMoveToTargetPose
    pointControlPara.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    result = cgxiapi.cr_moveJog(robotHandle, pointControlPara)
    print("点动运动结果：", result.value)
    assert (result.value == 0)


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_moveJog()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()

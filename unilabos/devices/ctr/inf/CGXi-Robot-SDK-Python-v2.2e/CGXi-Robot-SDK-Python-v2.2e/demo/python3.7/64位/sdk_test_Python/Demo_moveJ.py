import cgxiapi
from ctypes import *
import time
import basestruct


# 机械臂创建连接
robotHandle = 1
# re1 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：", re1[0].value)
if re1[0].value != 0:
    print("连接失败")
    exit()
robotHandle = re1[1].value




#轴空间运动——cr_moveJ
def api_demo_cr_moveJ():
    pointControlPara = basestruct.PointControlPara()
    speed = 10
    acc = 250
    pointControlPara.jointpos = (15, -3, 90, 0, 90, 10)
    pointControlPara.pose = (0, 0, 0, 0, 0, 0)
    pointControlPara.tcpOffset = (0, 0, 0, 0, 0, 0)
    pointControlPara.tcpID = -1
    pointControlPara.speed = (speed, speed, speed, speed, speed, speed)
    pointControlPara.acc = (acc, acc, acc, acc, acc, acc)
    pointControlPara.coordinatePose = (0, 0, 0, 0, 0, 0)
    pointControlPara.jerk = (0, 0, 0, 0, 0, 0)
    pointControlPara.coordinateType = basestruct.CoordinateType.jointCoordinate
    pointControlPara.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlPara.pointTransRadius = 0
    pointControlPara.poseTranType = basestruct.PoseTranType.poseTranMoveToTargetPose
    pointControlPara.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    result = cgxiapi.cr_moveJ(robotHandle, pointControlPara)
    print("返回结果:", result.value)
    assert (result.value == 0)


#轴空间运动——cr_move_joint
def api_demo_cr_move_joint():
    pointControlParaSimple = basestruct.PointControlParaSimple()
    pointControlPara = basestruct.PointControlPara()
    speed = 10
    acc = 250
    pointControlParaSimple.jointpos = (15, -3, 90, 0, 90, 10)
    pointControlParaSimple.pose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.tcpID = -1
    pointControlParaSimple.speed = (speed, speed, speed, speed, speed, speed)
    pointControlParaSimple.acc = (acc, acc, acc, acc, acc, acc)
    pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.coordinateType = basestruct.CoordinateType.jointCoordinate
    pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlParaSimple.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    res = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, pointControlPara)
    isBlock = 0
    result = cgxiapi.cr_move_joint(robotHandle, pointControlPara, isBlock)
    print("返回结果:", result.value)
    assert (result.value == 0)


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_move_joint()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()

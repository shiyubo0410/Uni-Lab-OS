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



def api_demo_cr_move_circle():
    pointControlParaSimple = basestruct.PointControlParaSimple()
    pointControlPara = basestruct.PointControlPara()
    pointControlParaSimple.jointpos = (60, 60, -60, 60, 60, 60)
    pointControlParaSimple.pose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.speed = (30, 30, 30, 30, 30, 30)
    pointControlParaSimple.acc = (30, 30, 30, 30, 30, 30)
    pointControlParaSimple.coordinateType = basestruct.CoordinateType.jointCoordinate
    pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlParaSimple.motiontriggerMode = \
        basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    res = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple
                                                    , pointControlPara)
    result1 = cgxiapi.cr_move_joint(robotHandle, pointControlPara, 1)  # 移动到初始点
    jointpos1 = (60, 55, -65, 60, 60, 60)
    pose1 = [0, 0, 0, 0, 0, 0]
    cgxiapi.cr_kineForward(robotHandle, jointpos1, pose1)
    jointpos2 = (60, 50, -70, 60, 60, 60)
    pose2 = [0, 0, 0, 0, 0, 0]
    cgxiapi.cr_kineForward(robotHandle, jointpos2, pose2)
    pointControlParaList = basestruct.PointControlParaList()
    index = 0
    while index < basestruct.ROB_AXIS_NUM:
        pointControlParaList.pointcontrolpara[0].pose[index] = pose1[index]
        pointControlParaList.pointcontrolpara[0].jointpos[index] = jointpos1[index]
        pointControlParaList.pointcontrolpara[0].tcpOffset[index] = 0
        pointControlParaList.pointcontrolpara[0].coordinatePose[index] = 0
        pointControlParaList.pointcontrolpara[0].speed[index] = 30
        pointControlParaList.pointcontrolpara[0].acc[index] = 30
        pointControlParaList.pointcontrolpara[0].jerk[index] = 60
        pointControlParaList.pointcontrolpara[1].pose[index] = pose2[index]
        pointControlParaList.pointcontrolpara[1].jointpos[index] = jointpos2[index]
        pointControlParaList.pointcontrolpara[1].tcpOffset[index] = 0
        pointControlParaList.pointcontrolpara[1].coordinatePose[index] = 0
        pointControlParaList.pointcontrolpara[1].speed[index] = 30
        pointControlParaList.pointcontrolpara[1].acc[index] = 30
        pointControlParaList.pointcontrolpara[1].jerk[index] = 60
        index += 1
    pointControlParaList.pointcontrolpara[0].tcpID = -1
    pointControlParaList.pointcontrolpara[0].coordinateType = \
        basestruct.CoordinateType.jointCoordinate
    pointControlParaList.pointcontrolpara[0].pointTransType = \
        basestruct.PointTransType.pointTransStop
    pointControlParaList.pointcontrolpara[0].pointTransRadius = 0
    pointControlParaList.pointcontrolpara[0].poseTranType = \
        basestruct.PoseTranType.poseTranMoveToTargetPose
    pointControlParaList.pointcontrolpara[0].motiontriggerMode = \
        basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    pointControlParaList.pointcontrolpara[1].tcpID = -1
    pointControlParaList.pointcontrolpara[1].coordinateType = \
        basestruct.CoordinateType.jointCoordinate
    pointControlParaList.pointcontrolpara[1].pointTransType = \
        basestruct.PointTransType.pointTransStop
    pointControlParaList.pointcontrolpara[1].pointTransRadius = 0
    pointControlParaList.pointcontrolpara[1].poseTranType = \
        basestruct.PoseTranType.poseTranMoveToTargetPose
    pointControlParaList.pointcontrolpara[1].motiontriggerMode = \
        basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    pointControlParaList.fixedrot = 0
    pointControlParaList.centralangle = 0
    result2 = cgxiapi.cr_move_circle(robotHandle, pointControlParaList, 1)
    assert (result2.value == 0)


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_move_circle()
    # 机械臂断开连接
    re0=cgxiapi.cr_destroy_robot(robotHandle)
    if re0.value != 0:
        print("断开失败")
        exit()

if __name__ == "__main__":
    main()
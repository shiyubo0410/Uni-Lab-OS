import cgxiapi
from ctypes import *
import time
import basestruct
import inspect

# 机械臂创建连接
robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
# re0=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接

if re0[0].value == 0:
    robotHandle = re0[1].value
    pointControlPara = basestruct.PointControlPara()
    pointControlParaSimple = basestruct.PointControlParaSimple()
    speed = 30
    acc = 60
    jointpos = ( 0, 0, 90, 0, -90, 0)
    pointControlPara.jointpos = (jointpos[0],jointpos[1],jointpos[2],jointpos[3],jointpos[4],jointpos[5])  #目标点示例数据
    pointControlPara.pose = (0, 0, 0, 0, 0, 0)  #在MoveJ中无影响
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
    result_movej = cgxiapi.cr_moveJ(robotHandle, pointControlPara) #轴空间运动
    print("返回结果:", result_movej.value)
    if result_movej.value == 0:
        time.sleep(0.5)
        result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
        while result_moveStatus[0].value==0:  #读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
            result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
            if result_moveStatus[1].value==0:
                break
        pose = [0, 0, 0, 0, 0, 0]
        result_get = cgxiapi.cr_get_tcpActualPose(robotHandle, pose)  # 读实际TCP位置
        pose[2] = pose[2]-150
        if result_get.value == 0:
            pointControlPara.coordinateType = basestruct.CoordinateType.baseCoordinate
            pointControlPara.pose = (pose[0],pose[1],pose[2],pose[3],pose[4],pose[5])
            pointControlPara.jointpos = (jointpos[0],jointpos[1],jointpos[2],jointpos[3],jointpos[4],jointpos[5])
            result_movel = cgxiapi.cr_moveL(robotHandle, pointControlPara)
            if result_movel.value == 0:
                time.sleep(0.05)
                result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
                while result_moveStatus[0].value == 0:  # 读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
                    result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
                    if result_moveStatus[1].value == 0:
                        break
                pose[2] = pose[2] + 150
                pointControlParaSimple.pose = (pose[0], pose[1], pose[2], pose[3], pose[4], pose[5])
                pointControlParaSimple.jointpos = (jointpos[0], jointpos[1], jointpos[2], jointpos[3], jointpos[4], jointpos[5])
                pointControlParaSimple.speed = (speed, speed, speed, speed, speed, speed)
                pointControlParaSimple.acc = (acc, acc, acc, acc, acc, acc)
                pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
                pointControlParaSimple.tcpID = -1
                pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
                pointControlParaSimple.coordinateType = basestruct.CoordinateType.baseCoordinate
                pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
                pointControlParaSimple.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
                result_trans = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple,pointControlPara)  # PointControlParaSimple数据转换为PointControlPara
                isBlock = 1
                result_moveline = cgxiapi.cr_move_line(robotHandle, pointControlPara, isBlock)  #阻塞直线运动
                if result_moveline.value == 0:
                    jointpos2 = (90, 0, 90, 0, -90, 0)
                    pointControlParaSimple.jointpos = (jointpos2[0], jointpos2[1], jointpos2[2], jointpos2[3], jointpos2[4], jointpos2[5])
                    pointControlParaSimple.pose = (0, 0, 0, 0, 0, 0)
                    pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
                    pointControlParaSimple.tcpID = -1
                    pointControlParaSimple.speed = (speed, speed, speed, speed, speed, speed)
                    pointControlParaSimple.acc = (acc, acc, acc, acc, acc, acc)
                    pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
                    pointControlParaSimple.coordinateType = basestruct.CoordinateType.jointCoordinate
                    pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
                    pointControlParaSimple.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
                    result_trans = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple,pointControlPara)   #PointControlParaSimple数据转换为PointControlPara
                    isBlock = 1
                    result_movejoint = cgxiapi.cr_move_joint(robotHandle, pointControlPara, isBlock)   #阻塞式的轴空间运动，由于是阻塞的轴空间运动，则运动会在运动到位后在进行后续的程序运行，因此不用像之前做判断
                    if result_movejoint.value==0:
                        result = cgxiapi.cr_get_tcpActualPose(robotHandle, pose)   #读实际TCP位置
                        pose[2] = pose[2]-150
                        pointControlParaSimple.coordinateType = basestruct.CoordinateType.baseCoordinate
                        pointControlParaSimple.pose = (pose[0], pose[1], pose[2], pose[3], pose[4], pose[5])
                        pointControlParaSimple.jointpos = (jointpos2[0], jointpos2[1], jointpos2[2], jointpos2[3], jointpos2[4], jointpos2[5])
                        result_trans = cgxiapi.cr_move_pointControlPara_transfer(robotHandle,pointControlParaSimple,pointControlPara)   #PointControlParaSimple数据转换为PointControlPara
                        result_movel = cgxiapi.cr_moveL(robotHandle, pointControlPara)   #直线运动
                        if result_movel.value == 0:
                            time.sleep(0.05)
                            result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
                            while result_moveStatus[0].value == 0:  # 读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
                                result_moveStatus = cgxiapi.cr_get_robotMoveStatus(robotHandle)
                                if result_moveStatus[1].value == 0:
                                    break
                            pose[2] = pose[2] + 150
                            pointControlParaSimple.pose = (pose[0], pose[1], pose[2], pose[3], pose[4], pose[5])
                            pointControlParaSimple.jointpos = (jointpos2[0], jointpos2[1], jointpos2[2], jointpos2[3], jointpos2[4], jointpos2[5])
                            result_trans = cgxiapi.cr_move_pointControlPara_transfer(robotHandle,pointControlParaSimple,pointControlPara)   #PointControlParaSimple数据转换为PointControlPara
                            isBlock = 0
                            result = cgxiapi.cr_move_line(robotHandle, pointControlPara, isBlock)   #非阻塞式直线运动，下发运动后会立刻执行下一条指令
                            if result.value == 0:
                                print("运动已完成")
                            else:
                                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result.value)
                        else:
                            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_movel.value)
                    else:
                        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_movejoint.value)
                else:
                    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_moveline.value)
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_movel.value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_get.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_movej.value)
else:
    print("行数：",inspect.currentframe().f_lineno,"  ","结果：",re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
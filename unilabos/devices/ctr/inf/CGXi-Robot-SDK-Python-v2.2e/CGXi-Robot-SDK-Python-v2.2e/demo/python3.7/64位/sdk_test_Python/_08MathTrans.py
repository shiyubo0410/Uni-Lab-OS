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
    pointCSNode = basestruct.PointCSNode()
    pointCSNode.name = b'point523'
    pointCSNode.point.toolAxisAngle = (30, 30, 30, 30, 30, 30)
    pointCSNode.point.toolPosition = (0, 0, 0, 0, 0, 0)
    result_count = cgxiapi.cr_cfg_cs_point_count(robotHandle)  # 读取点坐标系个数
    Pcount = result_count[1].value
    if result_count[0].value == 0:
        if Pcount>0:
            i=0
            while i<Pcount:
                pointCS = basestruct.PointCSNode()
                result_get = cgxiapi.cr_cfg_cs_point_get(robotHandle, i, pointCS)
                if pointCS.name==pointCSNode.name:
                    result_kineF = cgxiapi.cr_kineForward(robotHandle, pointCSNode.point.toolAxisAngle, pointCSNode.point.toolPosition)  #正解求点的位姿
                    if result_kineF.value==0:
                        pointCSNode.isValid = 1
                        pointCSNode.id = 8
                        result_set = cgxiapi.cr_cfg_cs_point_set(robotHandle, i, pointCSNode)  #设置点坐标系
                        if result_set.value==0:
                            print("行数：", inspect.currentframe().f_lineno, "  修改成功")
                        else:
                            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_set.value)
                    else:
                        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_kineF.value)
                if i==Pcount-1 :
                    result_kineF = cgxiapi.cr_kineForward(robotHandle, pointCSNode.point.toolAxisAngle,pointCSNode.point.toolPosition)  #正解求点的位姿
                    if result_kineF.value==0:
                        pointCSNode.isValid = 1
                        pointCSNode.id = 8
                        result_add = cgxiapi.cr_cfg_cs_point_add(robotHandle, pointCSNode)  # 增加点坐标系数据
                        if result_add.value == 0:
                            print("行数：", inspect.currentframe().f_lineno, "  增加成功")
                        else:
                            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_add.value)
                i+=1
        else:
            pointCSNode.isValid = 1
            pointCSNode.id = 1
            result_kineF = cgxiapi.cr_kineForward(robotHandle, pointCSNode.point.toolAxisAngle,pointCSNode.point.toolPosition)  # 正解求点的位姿
            result_add = cgxiapi.cr_cfg_cs_point_add(robotHandle, pointCSNode)   #增加点坐标系数据
            if result_add.value==0:
                print("行数：", inspect.currentframe().f_lineno, "  增加成功")
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_add[0].value)
        pose = [0, 0, 0, 0, 0, 0]
        result_getTcp = cgxiapi.cr_get_tcpActualPose(robotHandle, pose)  # 读实际TCP位置
        if result_getTcp.value == 0:
            basePoseLen = 6
            userPoseLen = 6
            poseInUserLen = 6
            basePose = [0, 0, 0, 0, 0, 0]
            userPose = [0, 0, 0, 0, 0, 0]
            i = 0
            while i < 6:
                basePose[i] = pose[i]
                userPose[i] = pointCSNode.point.toolPosition[i]  # 将点坐标系设置为用户坐标系
                i += 1
            poseInUser = [0, 0, 0, 0, 0, 0]
            result_compute = cgxiapi.cr_compute_pose_base_to_user(basePose, basePoseLen, userPose, userPoseLen,
                                                                  poseInUser, poseInUserLen)  # 基坐标系下位姿转移到用户坐标系下
            if result_compute.value == 0:
                print(poseInUser)
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_compute.value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_getTcp.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_count[0].value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
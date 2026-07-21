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
    pointControlParaSimple = basestruct.PointControlParaSimple()
    pointControlPara = basestruct.PointControlPara()
    speed = 90
    acc = 200
    pointControlParaSimple.jointpos = (0, 0, 90, 0, -90, 0)
    pointControlParaSimple.pose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.tcpID = -1
    pointControlParaSimple.speed = (speed, speed, speed, speed, speed, speed)
    pointControlParaSimple.acc = (acc, acc, acc, acc, acc, acc)
    pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.coordinateType = basestruct.CoordinateType.jointCoordinate
    pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlParaSimple.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    result_trans1 = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, pointControlPara)   #PointControlParaSimple数据转换为PointControlPara
    isBlock = 1
    re1 = cgxiapi.cr_move_joint(robotHandle, pointControlPara, isBlock)   #轴空间运动
    #轨迹
    recordPathPara = basestruct.RecordPathPara()
    recordPathPara.recordControl = 1  # 记录控制，0-停止，1-启动，2-暂停
    recordPathPara.sampleTime = 2
    result_set = cgxiapi.cr_path_recordPara_set(robotHandle, recordPathPara)   #设置轨迹记录参数，开启轨迹记录
    time.sleep(0.5)
    pointControlParaSimple.jointpos = (90, 0, 90, 0, -90, 0)
    result_trans2 = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple,pointControlPara)  # PointControlParaSimple数据转换为PointControlPara
    isBlock = 1
    if result_set.value==0:
        re2 = cgxiapi.cr_move_joint(robotHandle, pointControlPara, isBlock)  # 轴空间运动
        if re2.value==0:
            recordPathPara.recordControl = 1  # 记录控制，0-停止，1-启动，2-暂停
            result_set = cgxiapi.cr_path_recordPara_set(robotHandle, recordPathPara)  # 结束轨迹记录
            if result_set.value==0:
                index = -1  # 轨迹索引
                pathData = basestruct.PathData()
                stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
                pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
                result_upload = cgxiapi.cr_path_upload(robotHandle, index, pathData)   #上传轨迹
                if result_upload.value==0:
                    result_get = cgxiapi.cr_path_all_index_get(robotHandle)   #读取控制柜当前存在的轨迹索引
                    i=0
                    while i<result_get[2].value:
                        if(result_get[1][i] == 2):   #将下载的轨迹索引设置为2，故需要判断其是否已经存在
                            print("行数：", inspect.currentframe().f_lineno, "存在轨迹索引为2的轨迹")
                            pathDownloadData = basestruct.PathDownloadData()
                            pathDownloadData.pathData = pathData
                            pathDownloadData.pathPara.index = 2
                            pathDownloadData.pathPara.moveType = 1
                            result_download = cgxiapi.cr_path_download(robotHandle, pathDownloadData)   #下载轨迹到索引2
                            if result_download.value==0:
                                print("行数：", inspect.currentframe().f_lineno, "  已成功下载索引为2的轨迹")
                            else:
                                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_download.value)
                            break
                        if(i==result_get[2].value-1):
                            pathDownloadData = basestruct.PathDownloadData()
                            pathDownloadData.pathData = pathData
                            pathDownloadData.pathPara.index = 2
                            pathDownloadData.pathPara.moveType = 1
                            result_download = cgxiapi.cr_path_download(robotHandle, pathDownloadData)  # 下载轨迹到索引2
                            if result_download.value == 0:
                                print("行数：", inspect.currentframe().f_lineno, "  已成功下载索引为2的轨迹")
                            else:
                                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_download.value)
                        i += 1
                else:
                    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_upload.value)
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_set.value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re2.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_set.value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
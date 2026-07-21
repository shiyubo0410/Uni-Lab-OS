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
    pointCSNode.name = b'point3'
    pointCSNode.point.toolAxisAngle = (30, 30, 30, 30, 30, 30)
    pointCSNode.point.toolPosition = (0, 0, 0, 0, 0, 0)
    result_count = cgxiapi.cr_cfg_cs_point_count(robotHandle)   #读取点坐标系个数
    Pcount = result_count[1].value
    if result_count[0].value==0:
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
                    break
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
        index = 0
        result_get = cgxiapi.cr_cfg_cs_point_get(robotHandle, index, pointCSNode)   #读取索引号为0的点坐标系数据,可能不存在该坐标系
        if result_get.value==0:
            print(pointCSNode.name)
            index = 0
            result_delete = cgxiapi.cr_cfg_cs_point_delete(robotHandle, index)   #删除索引号为0的点坐标系
            if result_delete.value==0:
                print("行数：", inspect.currentframe().f_lineno, "  已成功删除索引号为0的坐标系")
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_delete.value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_get.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_count[0].value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
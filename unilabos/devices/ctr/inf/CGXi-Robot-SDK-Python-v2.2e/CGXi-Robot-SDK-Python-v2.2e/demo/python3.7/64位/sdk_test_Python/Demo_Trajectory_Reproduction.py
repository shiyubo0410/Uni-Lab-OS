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





#3.2.5 轨迹复现
#读取控制器当前存在的轨迹索引
def api_demo_cr_path_all_index_get():
    result = cgxiapi.cr_path_all_index_get(robotHandle)
    print("上传程序结果：", result[0].value)
    assert (result[0].value == 0)
    print("所有轨迹索引:",result[1][0:result[2].value],"轨迹索引数组有效长度:",result[2].value)

#上传轨迹
def api_demo_cr_path_upload():
    index = 7  #轨迹索引
    pathData = basestruct.PathData()
    stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
    pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
    result = cgxiapi.cr_path_upload(robotHandle, index, pathData)
    print(pathData.pathPoints[5].pose[0:])
    assert (result.value == 0)
    print("上传轨迹结果：",result.value)

#下载轨迹
def api_demo_cr_path_download():
    pathDownloadData = basestruct.PathDownloadData()
    stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
    pathDownloadData.pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
    filePath = b"D:/trait.crpath"
    result = cgxiapi.cr_path_file2pathData(filePath, pathDownloadData.pathData)
    print(pathDownloadData.pathData.pathPoints[5].pose[0:])
    pathDownloadData.pathPara.index = 8
    pathDownloadData.pathPara.moveType = 1
    pathDownloadData.pathData.moveTime = 100
    result = cgxiapi.cr_path_download(robotHandle,pathDownloadData)
    assert (result.value == 0)
    print("下载轨迹结果：",result.value)

#轨迹控制
def api_demo_cr_path_action():
    index = 7  # 轨迹索引
    pathData = basestruct.PathData()
    stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
    pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
    result = cgxiapi.cr_path_upload(robotHandle, index, pathData)

    pointControlParaSimple = basestruct.PointControlParaSimple()
    pointControlPara = basestruct.PointControlPara()
    speed = 10
    acc = 250
    i = 0
    while i<6:
        pointControlParaSimple.jointpos[i] = pathData.pathPoints[0].jointpos[i]
        pointControlParaSimple.pose[i] = pathData.pathPoints[0].pose[i]
        i = i+1
    pointControlParaSimple.tcpOffset = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.tcpID = -1
    pointControlParaSimple.speed = (speed, speed, speed, speed, speed, speed)
    pointControlParaSimple.acc = (acc, acc, acc, acc, acc, acc)
    pointControlParaSimple.coordinatePose = (0, 0, 0, 0, 0, 0)
    pointControlParaSimple.coordinateType = basestruct.CoordinateType.jointCoordinate
    pointControlParaSimple.pointTransType = basestruct.PointTransType.pointTransStop
    pointControlParaSimple.motiontriggerMode = basestruct.MotiontriggerMode.MovetriggerbyOnlyRpc
    result = cgxiapi.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, pointControlPara)
    isBlock = 1
    result = cgxiapi.cr_move_joint(robotHandle, pointControlPara, isBlock)

    index = 7
    runControl = 1
    result = cgxiapi.cr_path_action(robotHandle,index,runControl)
    assert (result.value == 0)
    print("轨迹控制结果：",result.value)

#轨迹数据转换为轨迹文件
def api_demo_cr_path_pathData2file():
    pathData = basestruct.PathData()
    stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
    pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
    index = 7
    result = cgxiapi.cr_path_upload(robotHandle, index, pathData)
    print(pathData.pathPoints[5].pose[0:])
    filePath = b"D:/path11.crpath"
    result = cgxiapi.cr_path_pathData2file(pathData,filePath)
    assert (result.value == 0)
    print("轨迹数据转换为轨迹文件结果：",result.value)

#轨迹文件转换为轨迹数据
def api_demo_cr_path_file2pathData():
    pathData = basestruct.PathData()
    stru_info = create_string_buffer(sizeof(basestruct.PathPoint) * 10000)
    pathData.pathPoints = POINTER(basestruct.PathPoint)(stru_info)
    filePath = b"D:/trait.crpath"
    result = cgxiapi.cr_path_file2pathData(filePath,pathData)
    print(pathData.pathPoints[5].pose[0:])
    assert (result.value == 0)
    print("轨迹文件转换为轨迹数据结果：", result.value)

#设置轨迹记录参数
def api_demo_cr_path_recordPara_set():
    recordPathPara = basestruct.RecordPathPara()
    recordPathPara.recordControl = 1   #记录控制，0-停止，1-启动，2-暂停
    recordPathPara.sampleTime = 100
    result = cgxiapi.cr_path_recordPara_set(robotHandle, recordPathPara)
    assert (result.value == 0)
    print("设置轨迹记录参数结果：", result.value)

#获取当前轨迹记录状态
def api_demo_cr_path_recordStatus_get():
    pathRecordStatus = basestruct.PathRecordStatus()
    result = cgxiapi.cr_path_recordStatus_get(robotHandle, pathRecordStatus)
    assert (result.value == 0)
    print("获取当前轨迹记录状态结果：", result.value)
    print("轨迹记录状态：", pathRecordStatus.recordStatus, "已记录点数：", pathRecordStatus.waypointNumber)

#获取当前轨迹运行状态
def api_demo_cr_path_currentRunStatus_get():
    pathRunMsg = basestruct.PathRunMsg()
    result = cgxiapi.cr_path_currentRunStatus_get(robotHandle, pathRunMsg)
    assert (result.value == 0)
    print("获取当前轨迹运行状态结果：", result.value)
    print("当前轨迹运行状态：", pathRunMsg.pathrunstatus, "当前运行轨迹点数：", pathRunMsg.pointIndex)



#主函数
def main():
    #####在此处调用函数
    # api_demo_cr_path_all_index_get()
    # api_demo_cr_path_action()
    # api_demo_cr_path_download()
    api_demo_cr_path_recordPara_set()


    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()

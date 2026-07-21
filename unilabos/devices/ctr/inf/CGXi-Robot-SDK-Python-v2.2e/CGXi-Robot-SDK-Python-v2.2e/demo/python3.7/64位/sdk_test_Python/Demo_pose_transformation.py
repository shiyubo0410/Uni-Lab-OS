import cgxiapi
from ctypes import *
import time
import basestruct



##3.5.1位姿变换
#位姿转换
def api_demo_cr_poseTrans():
    poseFrom = [0, 0, 0, 10, 10, 10]
    poseTrans = [1, 1, 1, 20, 20, 20]
    poseTo = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_poseTrans(poseFrom, poseTrans, poseTo)
    assert (result.value == 0)
    print("位姿转换结果：", result.value, poseTo)


#位姿求逆
def api_demo_cr_compute_pose_inv():
    poseLen = 6
    poseInvLen = 6
    pose = [-66, -438, 887, -57, 0, -148]
    poseInv = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_compute_pose_inv(pose, poseLen, poseInv, poseInvLen)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("计算结果：")
    i = 0
    while i < 6:
        print(poseInv[i])
        i += 1


#轴角转欧拉角
def api_demo_cr_AxisAngle2Eule():
    axisAnglePose = [1, 1, 1, 20, 20, 20]
    eulePose = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_AxisAngle2Eule(axisAnglePose, eulePose)
    print("轴角转欧拉角：", result.value)
    assert (result.value == 0)
    print(eulePose)


#欧拉角转轴角
def api_demo_cr_Eule2AxisAngle():
    eulePose = [1, 1, 1, 20, 20, 20]
    axisAnglePose = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_Eule2AxisAngle(eulePose, axisAnglePose)
    print("位姿变换：", result.value)
    assert (result.value == 0)
    print(axisAnglePose)


#TCP位姿转法兰位姿
def api_demo_cr_TcpToFlangePose():
    tcpPose = [1, 1, 1, 20, 20, 20]
    toolPose = [14, 14, 14, 10, 10, 10]
    flangePose = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_TcpToFlangePose(tcpPose, toolPose, flangePose)
    print("位姿变换：", result.value)
    assert (result.value == 0)
    print(flangePose)


#基坐标系下位姿转移到用户坐标系下
def api_demo_cr_compute_pose_base_to_user():
    basePoseLen = 6
    userPoseLen = 6
    poseInUserLen = 6
    basePose = [-66, -438, 887, -57, 0, -148]
    userPose = [1, 2, 3, 10, 10, 10]
    poseInUser = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_compute_pose_base_to_user(basePose, basePoseLen, userPose, userPoseLen, poseInUser,
                                                  poseInUserLen)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：")
    i = 0
    while i < 6:
        print(poseInUser[i])
        i += 1



#主函数
def main():
    #####在此处调用函数
    api_demo_cr_compute_pose_base_to_user()



if __name__ == "__main__":
    main()

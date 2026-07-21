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



##3.2.1（实际机械臂运动的接口已单独列出Demo，见Demo_moveJ,Demo_moveL,Demo_moveJog,Demo_moveC）
#运动控制
def api_demo_cr_moveControl():
    moveType = 1  # 0-减速停止  1-立即停止  2-运动
    result = cgxiapi.cr_moveControl(robotHandle, moveType)
    print("运动控制结果：", result.value)
    assert (result.value == 0)


#设置阻塞移动中参数阈值
def api_demo_cr_move_block_threshold_set():
    poseDelt = 0.1
    jointDelt = 0.1
    result = cgxiapi.cr_move_block_threshold_set(robotHandle, poseDelt, jointDelt)
    print("设置阻塞移动中参数阈值结果：", result.value)
    assert (result.value == 0)

#设置软件自由驱动启动
def api_demo_cr_set_softFreeDriveEnabled():
    softFreeDriveEnabled = 0    #1为进入拖拽模式，0为退出拖拽模式
    result = cgxiapi.cr_set_softFreeDriveEnabled(robotHandle, softFreeDriveEnabled)
    print("返回结果：", result.value)
    assert (result.value == 0)

#读机械臂运动状态
def api_demo_cr_get_robotMoveStatus():
    result = cgxiapi.cr_get_robotMoveStatus(robotHandle)
    print("读机械臂运动结果：", result[0].value, "目前是否运动：", result[1].value)
    assert (result[0].value == 0)

#读取移动缓存区中移动指令的数量
def api_demo_cr_move_cache_num_get():
    result = cgxiapi.cr_move_cache_num_get(robotHandle)
    print("读取移动缓存区中移动指令的数量结果：", result[0].value, "移动缓存区中移动指令的数量：", result[1].value)
    assert (result[0].value == 0)


#主函数
def main():
    #####在此处调用函数
    # api_demo_cr_moveControl()
    api_demo_cr_move_block_threshold_set()

    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()



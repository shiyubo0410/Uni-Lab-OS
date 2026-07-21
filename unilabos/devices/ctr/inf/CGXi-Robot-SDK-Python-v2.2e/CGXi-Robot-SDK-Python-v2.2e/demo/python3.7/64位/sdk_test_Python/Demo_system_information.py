import cgxiapi
from ctypes import *
import time
import basestruct
import threading


# #cr_log_enable和cr_log_set_size需要在机械臂连接之前调用
# #日志功能是否开启
# enable = 1
# result1 = cgxiapi.cr_log_enable(enable)
# print("返回结果:",result1.value)
#
# #日志大小设置
# size = 1024*1024
# num = 10
# result2 = cgxiapi.cr_log_set_size(size, num)
# print("返回结果:",result2.value)

# 机械臂创建连接
robotHandle = 1
re1 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
# re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：", re1[0].value)
if re1[0].value != 0:
    print("连接失败")
    exit()
robotHandle = re1[1].value


##3.3.2系统信息
#读机械臂当前状态
def api_demo_cr_get_robotMode():
    result = cgxiapi.cr_get_robotMode(robotHandle)
    print("读当前机械臂状态结果：", result[0].value)
    assert (result[0].value == 0)
    print("当前状态为：", result[1].value)



#获取机械臂日志
def api_demo_cr_get_logMsgs():
    stru_info = create_string_buffer(sizeof(basestruct.RobotLogMsg) * 10)
    logmsgs = POINTER(basestruct.RobotLogMsg)(stru_info)
    while 1:
        result = cgxiapi.cr_get_logMsgs(robotHandle, logmsgs)
        print("获取机械臂日志结果：", result[0].value)
        assert (result[0].value == 0)
        print("日志个数为：", result[1].value)
        if result[1].value > 0:
            msg = logmsgs[0].textMessage
            str_msg = str(msg, 'utf-8')
            print(logmsgs[0].robotMessageCode, str_msg)
        time.sleep(2)


#获取机械臂历史所有日志
def api_demo_cr_sys_history_log_get():
    stru_info = create_string_buffer(sizeof(basestruct.RobotLogMsg) * 3000)
    logmsgs = POINTER(basestruct.RobotLogMsg)(stru_info)
    result = cgxiapi.cr_sys_history_log_get(robotHandle, logmsgs)
    assert (result[0].value == 0)
    if result[1].value > 0:
        msg = logmsgs[0].textMessage
        str_msg = str(msg, 'utf-8')
        print(logmsgs[0].robotMessageCode, str_msg)



#读系统时间
def api_demo_cr_get_SystemDateTime():
    result = cgxiapi.cr_get_SystemDateTime(robotHandle)
    print("读系统时间结果：", result[0].value)
    assert (result[0].value == 0)
    print("系统时间为：", result[1].value)

#读取机型型号
def api_demo_cr_sys_robotModel_get():
    robotModel = b'eee'
    result = cgxiapi.cr_sys_robotModel_get(robotHandle, robotModel, 10)
    print("读机型型号结果：", result[0].value)
    assert (result[0].value == 0)
    print("机型型号为：", result[1].value)

#读取控制器型号
def api_demo_cr_get_controllerType():
    controllerType = b'eee'
    result = cgxiapi.cr_get_controllerType(robotHandle, controllerType)
    print("读控制器型号结果：", result[0].value)
    assert (result[0].value == 0)
    print("控制器型号为：", result[1].value)

# 触发黑匣子数据
def api_demo_cr_sys_blackBoxData_trigger():
    result = cgxiapi.cr_sys_blackBoxData_trigger(robotHandle)  #触发黑匣子数据
    print("触发黑匣子数据结果:", result.value)
    assert (result.value == 0)

#主函数
def main():
    #####在此处调用函数
    api_demo_cr_sys_robotModel_get()
    # api_demo_cr_get_logMsgs()

    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()






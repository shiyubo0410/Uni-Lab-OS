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
    re1 = cgxiapi.cr_get_robotMode(robotHandle)  #读机械臂当前状态
    if re1[0].value==0 and re1[1].value==6 :  #判断状态,robotMode为6时是本体未上电状态才可以进行上电
        result = cgxiapi.cr_poweron(robotHandle)   #机械臂上电
        if result.value == 0:
            while result.value == 0:
                re1 = cgxiapi.cr_get_robotMode(robotHandle)  # 读机械臂当前状态
                time.sleep(0.05)
                if re1[1].value == 8:
                    break
            result = cgxiapi.cr_enable(robotHandle)
            if result.value == 0:
                while result.value == 0:
                    re1 = cgxiapi.cr_get_robotMode(robotHandle)  # 读机械臂当前状态
                    time.sleep(0.05)
                    if re1[1].value == 103:
                        break
                print("使能完成")
            else:
                print("行数：",inspect.currentframe().f_lineno,"  ","结果：",re1[0].value)
        else:
            print("行数：",inspect.currentframe().f_lineno,"  ","结果：",result.value)
    else:
        print("行数：",inspect.currentframe().f_lineno,"  ","结果：",re1[0].value)
else:
    print("行数：",inspect.currentframe().f_lineno,"  ","结果：",re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
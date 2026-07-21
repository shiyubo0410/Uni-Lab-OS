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
    scriptstatus = basestruct.Lua_ScriptStatus
    re1 = cgxiapi.cr_get_lua_scriptstatus(robotHandle)  # 读脚本运行状态
    if re1[0].value==0 and re1[1].value==1:  #当脚本运行状态处于脚本程序停止时才可进行程序下载
        # crpFilepathname = b"D:/v1.6c/teachpendant_x64/program/test.crp"
        # crscriptFilepathname = b"D:/v1.6c/teachpendant_x64/program/test.crscript"
        crpFilepathname = b"./program/demo.crp"
        crscriptFilepathname = b"./program/demo.crscript"
        re2 = cgxiapi.cr_downloadProject(robotHandle, crpFilepathname, crscriptFilepathname)  #下载程序
        if re2.value==0:
            re3=cgxiapi.cr_play(robotHandle)   #运行程序
            while re3.value==0:
                result = cgxiapi.cr_get_robotMode(robotHandle)
                if result[1].value == 103:  #读机械臂当前状态,程序停止状态下才可以上传程序
                    break
            if result[0].value==0:
                FilePath = b"./program/"
                filename = b"test"   #crp和脚本程序的文件名
                re4 = cgxiapi.cr_uploadProject(robotHandle, FilePath, filename)   #工程文件上传
                if re4.value==0:
                    print("行数：", inspect.currentframe().f_lineno, "已成功上传工程文件")
                else:
                    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re4.value)
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result[0].value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re2.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re1[0].value)
        print("脚本运行状态：",re1[1].value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
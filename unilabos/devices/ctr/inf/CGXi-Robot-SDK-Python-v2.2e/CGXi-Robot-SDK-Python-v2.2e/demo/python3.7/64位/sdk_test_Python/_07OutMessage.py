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
    programfile = ("function mainFuncProgram()\n"
                   "--start robotConfig\n"
                   "TCP_1 = { 0,0,0,0,0,0 }\n"
                   "Payload_1= { 0,{0,0,0} }\n"
                   "set_tcp_payload(Payload_1[1], Payload_1[2])\n"
                   "--end robotConfig\n"
                   "function RobotProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "--popup_out:text\n"
                   "popup_message(\"hello\", \"message\", false, false, true)\n"
                   "wait(1)  --sync\n"
                   "end\n"
                   "end\n"
                   "RobotProgram_Result = task_create(RobotProgram)\n"
                   "function PauseFuncProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "wait(100)  --sync\n"
                   "end\n"
                   "end\n"
                   "PauseFuncProgram_Result = task_create(PauseFuncProgram)\n"
                   "end\n"
                   "mainFuncProgram_Result = task_create(mainFuncProgram)")
    result_download = cgxiapi.cr_downloadProgram(robotHandle, programfile)  #加载程序
    if result_download.value==0:
        result_play = cgxiapi.cr_play(robotHandle)   #运行程序
        if result_play.value==0:
            result_existPop = cgxiapi.cr_script_popup_exist(robotHandle)   #是否存在弹窗：1-是，0-否
            if result_existPop[0].value==0:
                if result_existPop[1].value==1:  #有弹窗信息
                    popupMsg = basestruct.PopUpMsg()
                    result_getPop = cgxiapi.cr_script_popup_msg_get(robotHandle, popupMsg)
                    if result_getPop.value==0:
                        print("行数：", inspect.currentframe().f_lineno, "  读取弹窗信息成功")
                        print("行数：", inspect.currentframe().f_lineno, "  ", popupMsg.popupType)
                        str_popupMsg = str(popupMsg.var_data, 'utf-8')
                        print("弹窗内容", str_popupMsg)
                        result = cgxiapi.cr_stop(robotHandle)
                    else:
                        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_getPop.value)
                else:
                    print("行数：", inspect.currentframe().f_lineno, "  没有弹窗信息")
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_existPop[0].value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_play.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_download.value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
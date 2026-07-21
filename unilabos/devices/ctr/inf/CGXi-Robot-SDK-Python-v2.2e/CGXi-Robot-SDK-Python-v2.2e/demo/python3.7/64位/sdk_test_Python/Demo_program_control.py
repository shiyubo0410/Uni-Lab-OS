import cgxiapi
from ctypes import *
import time
import basestruct


# 机械臂创建连接
robotHandle = 1
# re1 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：", re1[0].value)
if re1[0].value != 0:
    print("连接失败")
    exit()
robotHandle = re1[1].value




##3.1.2程序控制
#加载程序
def api_demo_cr_downloadProgram():
    programfile = ("function mainFuncProgram()\n"
                   "--start robotConfig\n"
                   "TCP_1 = { 10,0,0,0,0,0 }\n"
                   "Payload_1= { 5,{0,0,0} }\n"
                   "set_tcp_payload(Payload_1[1], Payload_1[2])\n"
                   "--end robotConfig\n"
                   "function RobotProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "--output: CDO_0 = true\n"
                   "set_standard_digital_out(0, true)\n"
                   "wait(1)  --sync\n"
                   "end\n"
                   "end\n"
                   "RobotProgram_result=task_create(RobotProgram)\n"
                   "function PauseFuncProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "wait(100)  --sync\n"
                   "end\n"
                   "end\n"
                   "PauseFuncProgram_result=task_create(PauseFuncProgram)\n"
                   "end\n"
                   "mainFuncProgram_result=task_create(mainFuncProgram)")
    re2 = cgxiapi.cr_downloadProgram(robotHandle, programfile)
    print("加载程序结果：", re2.value)
    # assert (re2.value == 0)

#加载程序（加密）
def api_demo_cr_downloadProgram_encryption():
    programfile = ("function mainFuncProgram()\n"
                   "--start robotConfig\n"
                   "TCP_1 = { 10,0,0,0,0,0 }\n"
                   "Payload_1= { 5,{0,0,0} }\n"
                   "set_tcp_payload(Payload_1[1], Payload_1[2])\n"
                   "--end robotConfig\n"
                   "function RobotProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "--output: CDO_0 = true\n"
                   "set_standard_digital_out(0, true)\n"
                   "wait(1)  --sync\n"
                   "end\n"
                   "end\n"
                   "RobotProgram_result=task_create(RobotProgram)\n"
                   "function PauseFuncProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "wait(100)  --sync\n"
                   "end\n"
                   "end\n"
                   "PauseFuncProgram_result=task_create(PauseFuncProgram)\n"
                   "end\n"
                   "mainFuncProgram_result=task_create(mainFuncProgram)")
    re2 = cgxiapi.cr_downloadProgram_encryption(robotHandle, programfile)
    print("加载程序结果（加密）：", re2.value)
    # assert (re2.value == 0)

#上传程序
def api_demo_cr_uploadProgram():
    re2 = cgxiapi.cr_uploadProgram(robotHandle)
    print("上传程序结果：", re2.value)
    assert (re2.value == 0)


#运行程序
def api_demo_cr_play():
    programfile = ("function mainFuncProgram()\n"
                   "--start robotConfig\n"
                   "TCP_1 = { 10,0,0,0,0,0 }\n"
                   "Payload_1= { 5,{0,0,0} }\n"
                   "set_tcp_payload(Payload_1[1], Payload_1[2])\n"
                   "--end robotConfig\n"
                   "function RobotProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "--output: CDO_0 = true\n"
                   "set_standard_digital_out(0, true)\n"
                   "wait(1)  --sync\n"
                   "end\n"
                   "end\n"
                   "RobotProgram_result=task_create(RobotProgram)\n"
                   "function PauseFuncProgram()\n"
                   "while (true)\n"
                   "do\n"
                   "wait(100)  --sync\n"
                   "end\n"
                   "end\n"
                   "PauseFuncProgram_result=task_create(PauseFuncProgram)\n"
                   "end\n"
                   "mainFuncProgram_result=task_create(mainFuncProgram)")
    re2 = cgxiapi.cr_downloadProgram(robotHandle, programfile)
    print("加载程序结果：", re2.value)
    re2 = cgxiapi.cr_play(robotHandle)
    print("运行程序结果：", re2.value)
    assert (re2.value == 0)


#停止程序运行
def api_demo_cr_stop():
    re2 = cgxiapi.cr_stop(robotHandle)
    print("返回结果：", re2.value)
    assert (re2.value == 0)


#暂停程序运行
def api_demo_cr_pause():
    re2 = cgxiapi.cr_pause(robotHandle)
    print("返回结果：", re2.value)
    assert (re2.value == 0)


#读取脚本当前运行行号
def api_demo_cr_script_current_line_get():
    result = cgxiapi.cr_script_current_line_get(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("脚本当前行号：", result[1][0])
    print("脚本行号数组长度：", result[2].value)


#读脚本运行状态
def api_demo_cr_get_lua_scriptstatus():
    result = cgxiapi.cr_get_lua_scriptstatus(robotHandle)
    print("返回结果：", result[0].value)
    print("读取结果：", result[1].value)
    assert (result[0].value == 0)


#工程文件上传
def api_demo_cr_uploadProject():
    FilePath = b"D:/v1.6c/teachpendant_x64/program/"
    filename = b"test"
    result = cgxiapi.cr_uploadProject(robotHandle, FilePath, filename)
    print("返回结果：", result.value)
    assert (result.value == 0)


#工程文件下载
def api_demo_cr_downloadProject():
    crpFilepathname = b"D:/v1.6c/teachpendant_x64/program/test.crp"
    crscriptFilepathname = b"D:/v1.6c/teachpendant_x64/program/test.crscript"
    result = cgxiapi.cr_downloadProject(robotHandle, crpFilepathname, crscriptFilepathname)
    print("返回结果：", result.value)
    assert (result.value == 0)


#是否存在弹窗
def api_demo_cr_script_popup_exist():
    result = cgxiapi.cr_script_popup_exist(robotHandle)
    print("返回结果:", result[0].value, "是否存在弹窗:", result[1].value)
    assert (result[0].value == 0)


#读取弹窗信息
def api_demo_cr_script_popup_msg_get():
    popupMsg = basestruct.PopUpMsg()
    result = cgxiapi.cr_script_popup_msg_get(robotHandle, popupMsg)
    print("返回结果：", result.value)
    print("读取结果:", popupMsg.popupType)
    str_popupMsg = str(popupMsg.var_data ,'utf-8')
    print("弹窗内容",str_popupMsg)
    assert (result.value == 0)


#设置输入弹窗信息
def api_demo_cr_script_popup_msg_set():
    invarMsg = basestruct.VariableMsg()
    invarMsg.variableName = b'var_1'
    invarMsg.variableType = 3
    invarMsg.variableID = 3
    invarMsg.numberValue = 1
    result = cgxiapi.cr_script_popup_msg_set(robotHandle, invarMsg)
    print("返回结果:", result.value)
    assert (result.value == 0)


#关闭弹窗
def api_demo_cr_script_popup_close():
    result = cgxiapi.cr_script_popup_close(robotHandle)
    print("返回结果:", result.value)
    assert (result.value == 0)



#主函数
def main():
    #####在此处调用函数
    api_demo_cr_script_popup_msg_get()


    # api_demo_cr_play()
    # api_demo_cr_script_current_line_get()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()








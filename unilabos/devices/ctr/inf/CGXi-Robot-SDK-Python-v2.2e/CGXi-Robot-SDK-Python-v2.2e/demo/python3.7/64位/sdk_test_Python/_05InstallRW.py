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
    variableMsg = basestruct.VariableMsg()
    variableMsg.variableName = b'var_11'
    variableMsg.variableType = 3  #number
    variableMsg.numberValue = 22
    variableMsg.variableID = 8
    result_count = cgxiapi.cr_cfg_var_install_count(robotHandle)
    if result_count[0].value==0:
        if result_count[1].value>0:
            i=0
            while i<result_count[1].value:
                variable_get = basestruct.VariableMsg()
                result = cgxiapi.cr_cfg_var_install_get(robotHandle, i, variable_get)
                if variable_get.variableName==variableMsg.variableName:   #判断是否存在我想添加的同名安装变量，如果有就修改，没有就增加
                    result_set = cgxiapi.cr_cfg_var_install_set(robotHandle, i, variableMsg)
                    if result_set.value==0:
                        print("行数：", inspect.currentframe().f_lineno, "  已成功修改安装变量")
                    else:
                        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_set.value)
                    break
                if i==(result_count[1].value-1):
                    result_add = cgxiapi.cr_cfg_var_install_add(robotHandle, variableMsg)
                    if result_add.value == 0:
                        print("行数：", inspect.currentframe().f_lineno, "  已成功增加安装变量")
                    else:
                        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_add.value)
                i+=1
        else:
            result_add = cgxiapi.cr_cfg_var_install_add(robotHandle, variableMsg)
            if result_add.value==0:
                print("行数：", inspect.currentframe().f_lineno, "  已成功增加安装变量")
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_add.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_count[0].value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
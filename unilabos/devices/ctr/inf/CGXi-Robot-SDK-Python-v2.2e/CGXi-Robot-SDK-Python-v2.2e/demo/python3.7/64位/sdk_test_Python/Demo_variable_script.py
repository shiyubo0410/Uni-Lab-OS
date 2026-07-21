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


##3.4.4脚本变量

#读安装变量
def api_demo_cr_get_intallVarValue():
    installVarName = "bfbfbb"
    installVar = basestruct.VariableMsg()
    result = cgxiapi.cr_get_intallVarValue(robotHandle, installVarName, installVar)
    print("读安装变量结果：", result.value)
    assert (result.value == 0)
    print("变量类型：", installVar.variableType.value)

#修改安装变量
def api_demo_cr_set_installVarValue():
    installVarName = "i_var_1"
    installVar = basestruct.VariableMsg()
    installVar.variableType = 3
    installVar.numberValue = 1
    installVar.variableName = b"i_var_2"
    result = cgxiapi.cr_set_installVarValue(robotHandle, installVarName, installVar)
    print("修改安装变量结果：", result.value)
    assert (result.value == 0)
    print("变量类型：", installVar.variableType.value)

#读取程序变量数据
def api_demo_cr_script_var_get():
    varName = b'var_1'
    variableMsg = basestruct.VariableMsg()
    result = cgxiapi.cr_script_var_get(robotHandle, varName, variableMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", variableMsg.variableType.value)

#修改程序变量数据
def api_demo_cr_script_var_set():
    variableMsg = basestruct.VariableMsg()
    variableMsg.variableType = 3
    variableMsg.variableName = b'var_1'
    variableMsg.numberValue = 99
    result = cgxiapi.cr_script_var_set(robotHandle, variableMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果：", variableMsg.numberValue)


#主函数
def main():
    #####在此处调用函数
    # api_demo_cr_script_var_get()
    # api_demo_cr_script_var_set()
    api_demo_cr_set_installVarValue()
    # 机械臂断开连接
    re0=cgxiapi.cr_destroy_robot(robotHandle)
    if re0.value != 0:
        print("断开失败")
        exit()

if __name__ == "__main__":
    main()
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


##3.3.2本体参数
#读机械臂DH参数
def api_demo_cr_get_DhParmeter():
    dhparam = [0] * 100
    result = cgxiapi.cr_get_DhParmeter(robotHandle, dhparam)
    assert (result.value == 0)
    print("读取dh参数结果：", result.value)
    i = 0
    while i < 36:
        print(dhparam[i])
        i = i + 1

#读机械臂标准DH参数
def api_demo_cr_get_stdDhParmeter():
    dhparam = [0] * 100
    result = cgxiapi.cr_get_stdDhParmeter(robotHandle, dhparam)
    assert (result.value == 0)
    print("读取标准dh参数结果：", result.value)
    i = 0
    while i < 36:
        print(dhparam[i])
        i = i + 1


#读机械臂动力学参数
def api_demo_cr_get_DynamicParmeter():
    dynamicPara = [0] * 100
    result = cgxiapi.cr_get_DynamicParmeter(robotHandle, dynamicPara)
    assert (result.value == 0)
    print("读取动力学参数结果：", result.value)
    i = 0
    while i < 72:
        print(dynamicPara[i])
        i = i + 1


#读机械臂零位补偿值
def api_demo_cr_get_zeroCompensationOffset():
    zeroCompensationOffset = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_zeroCompensationOffset(robotHandle, zeroCompensationOffset)
    assert (result.value == 0)
    print("读取零位补偿值结果：", result.value)
    print("零位补偿值为：", zeroCompensationOffset)


#读机械臂减速比
def api_demo_cr_get_reducerRatio():
    reducerRatio = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_reducerRatio(robotHandle, reducerRatio)
    print("读取机械臂减速比结果：", result.value)
    assert (result.value == 0)
    print("机械臂减速比为：", reducerRatio)


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_reducerRatio()
    # 机械臂断开连接

    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()

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



##3.2.4读实际关节状态
#读实际关节位置
def api_demo_cr_get_jointActualPos():
    pos = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointActualPos(robotHandle, pos)
    print("读实际关节位置结果：", result.value)
    assert(result.value == 0)
    print("实际关节位置为：", pos)


#读目标关节位置
def api_demo_cr_get_jointTargetPos():
    pos = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointTargetPos(robotHandle, pos)
    print("读目标关节位置结果：", result.value)
    assert(result.value == 0)
    print("目标关节位置为：", pos)


#读实际关节速度
def api_demo_cr_get_jointActualVelocity():
    velocity = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointActualVelocity(robotHandle, velocity)
    print("读实际关节速度结果：", result.value)
    assert (result.value == 0)
    print("实际关节速度为：", velocity)


#读目标关节速度
def api_demo_cr_get_jointTargetVelocity():
    velocity = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointTargetVelocity(robotHandle, velocity)
    print("读目标关节速度结果：", result.value)
    assert (result.value == 0)
    print("目标关节速度为：", velocity)


#读实际关节加速度
def api_demo_cr_get_jointActualAcceleration():
    acceleration = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointActualAcceleration(robotHandle, acceleration)
    print("读实际关节加速度结果：", result.value)
    assert (result.value == 0)
    print("实际关节加速度为：", acceleration)


#读目标关节加速度
def api_demo_cr_get_jointTargetAcceleration():
    acceleration = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointTargetAcceleration(robotHandle, acceleration)
    print("读目标关节加速度结果：", result.value)
    assert (result.value == 0)
    print("目标关节加速度为：", acceleration)


#读实际关节电机电流
def api_demo_cr_get_jointActualCurrent():
    current = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointActualCurrent(robotHandle, current)
    print("读实际关节电机电流结果：", result.value)
    assert (result.value == 0)
    print("实际关节电机电流为：", current)


#读目标关节电机电流
def api_demo_cr_get_jointTargetCurrent():
    current = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointTargetCurrent(robotHandle, current)
    print("读目标关节电机电流结果：", result.value)
    assert (result.value == 0)
    print("目标关节电机电流为：", current)


#读目标关节转矩
def api_demo_cr_get_jointTargetTorque():
    moment = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointTargetTorque(robotHandle, moment)
    print("读目标关节扭矩结果：", result.value)
    assert (result.value == 0)
    print("目标关节扭矩为：", moment)


#读实际关节采集的母线电压
def api_demo_cr_get_jointActualVoltage():
    voltage = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointActualVoltage(robotHandle, voltage)
    print("读实际关节采集的母线电压结果：", result.value)
    assert (result.value == 0)
    print("实际关节采集的母线电压为：", voltage)


#读关节温度
def api_demo_cr_get_jointTemperature():
    temperature = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointTemperature(robotHandle, temperature)
    print("读各关节的温度结果：", result.value)
    assert (result.value == 0)
    print("各关节的温度为：", temperature)


#读关节模式
def api_demo_cr_get_jointMode():
    jointMode = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_get_jointMode(robotHandle, jointMode)
    print("读各关节模式结果：", result.value)
    assert (result.value == 0)
    print("各关节模式为：", jointMode[0].value, jointMode[1].value, jointMode[2].value, jointMode[3].value,
          jointMode[4].value, jointMode[5].value)


#主函数
def main():
    #####在此处调用函数
    api_demo_cr_get_jointActualCurrent()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()
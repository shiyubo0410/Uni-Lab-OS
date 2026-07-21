import cgxiapi
from ctypes import *
import time
import basestruct

# 机械臂创建连接
robotHandle = 1
re1 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123") #机器人连接
# re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：", re1[0].value)
if re1[0].value != 0: #判断机器人连接是否成功
    print("连接失败")
    exit()
robotHandle = re1[1].value

###3.6配置
##安装
#设置安装角度
def api_demo_cr_cfg_install_angle_set():
    installAngle = basestruct.InstallAngle()
    installAngle.tiltAngle = 90
    installAngle.baseAngle = 90
    result = cgxiapi.cr_cfg_install_angle_set(robotHandle, installAngle)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取安装角度
def api_demo_cr_cfg_install_angle_get():
    installAngle = basestruct.InstallAngle()
    result = cgxiapi.cr_cfg_install_angle_get(robotHandle, installAngle)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("安装角度为：", installAngle.tiltAngle, installAngle.baseAngle)



##TCP
#读取TCP个数
def api_demo_cr_cfg_tcp_count():
    result = cgxiapi.cr_cfg_tcp_count(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("tcp个数为：", result[1].value)


#读取TCP数据
def api_demo_cr_cfg_tcp_get():
    index = 0
    tcpMsg = basestruct.TCPMsg()
    result = cgxiapi.cr_cfg_tcp_get(robotHandle, index, tcpMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("tcp信息:", tcpMsg.tcpName)
    for i in range(0,6):
        print(tcpMsg.tcpOffset[i])


#增加TCP
def api_demo_cr_cfg_tcp_add():
    tcpMsg = basestruct.TCPMsg()
    tcpMsg.tcpName = b's'
    tcpMsg.tcpOffset[0] = 2
    result = cgxiapi.cr_cfg_tcp_add(robotHandle, tcpMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("tcp信息:", tcpMsg.tcpName, tcpMsg.tcpOffset[0])


#删除TCP
def api_demo_cr_cfg_tcp_delete():
    index = 0
    result = cgxiapi.cr_cfg_tcp_delete(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#编辑TCP数据
def api_demo_cr_cfg_tcp_set():
    tcpMsg = basestruct.TCPMsg()
    tcpMsg.tcpName = b'a'
    tcpMsg.tcpOffset[0] = 10
    index = 2
    result = cgxiapi.cr_cfg_tcp_set(robotHandle, index, tcpMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("tcp信息:", tcpMsg.tcpName, tcpMsg.tcpOffset[0])


#读取当前激活的TCP索引
def api_demo_cr_cfg_tcp_active_get():
    result = cgxiapi.cr_cfg_tcp_active_get(robotHandle)
    print("返回结果：", result[0].value, "激活的TCP索引：", result[1].value)
    assert (result[0].value == 0)


#激活TCP
def api_demo_cr_cfg_tcp_active_set():
    index = 1
    result = cgxiapi.cr_cfg_tcp_active_set(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#计算TCP位置
def api_demo_cr_compute_tcp_position():
    poses = [[4.31, -66.66, 934.53, 20.30, -121.50, -73.277],
             [-3.71, -68.75, 926.57, 12.589, -124.54, -77.42],
             [13.98, -65.98, 934.53, 20.30, -121.5, -73.27],
             [4.2558, -66.66, 934.53, 8.77, -107.15, -71.457]]
    poseLen = 4
    position = [0, 0, 0]
    positionLen = 3
    result = cgxiapi.cr_compute_tcp_position(poses, poseLen, position, positionLen)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("计算结果:")
    i = 0
    while i < 3:
        print(position[i])
        i += 1
    print("误差为：", result[1].value)


#计算TCP角度
def api_demo_cr_compute_tcp_orientation():
    csPose = [0, 0, 0, 0, 0, 0]
    pointPose = [-36.10, -4.42, 32.62, 13.54, -91.33, 39.52]
    orientation = [0, 0, 0]
    csLen = 6
    pointLen = 6
    orientationLen = 3
    result = cgxiapi.cr_compute_tcp_orientation(csPose, csLen, pointPose, pointLen, orientation, orientationLen)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while i < 3:
        print("计算结果：", orientation[i])
        i += 1



##负载
#读取负载个数
def api_demo_cr_cfg_payload_count():
    result = cgxiapi.cr_cfg_payload_count(robotHandle)
    print("返回结果：", result[0].value, "负载个数为：", result[1].value)
    assert (result[0].value == 0)


#读取负载数据
def api_demo_cr_cfg_payload_get():
    index = 0
    payLoad = basestruct.PayLoad()
    result = cgxiapi.cr_cfg_payload_get(robotHandle, index, payLoad)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("负载数据：", payLoad.toolPayload)


#增加负载
def api_demo_cr_cfg_payload_add():
    payLoad = basestruct.PayLoad()
    payLoad.payloadName = b'aa'
    payLoad.centerOfGravity[0] = 10
    result = cgxiapi.cr_cfg_payload_add(robotHandle, payLoad)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("负载数据：", payLoad.toolPayload, payLoad.payloadName)


#删除负载
def api_demo_cr_cfg_payload_delete():
    index = 3
    result = cgxiapi.cr_cfg_payload_delete(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#编辑负载
def api_demo_cr_cfg_payload_set():
    payLoad = basestruct.PayLoad()
    payLoad.payloadName = b'cc'
    payLoad.toolPayload = 3
    payLoad.centerOfGravity[0] = 10
    payLoad.centerOfGravity[1] = 20
    index = 3
    result = cgxiapi.cr_cfg_payload_set(robotHandle, index, payLoad)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("负载数据：", payLoad.toolPayload, payLoad.payloadName)


#读取当前激活的负载索引
def api_demo_cr_cfg_payload_active_get():
    result = cgxiapi.cr_cfg_payload_active_get(robotHandle)
    print("返回结果：", result[0].value, "激活的负载索引：", result[1].value)
    assert (result[0].value == 0)


#激活负载
def api_demo_cr_cfg_payload_active_set():
    index = 3
    result = cgxiapi.cr_cfg_payload_active_set(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)



##初始位/包装位
#设置初始位
def api_demo_cr_cfg_home_pose_set():
    homePose = [20, 10, 10, 10, 10, 10]
    result = cgxiapi.cr_cfg_home_pose_set(robotHandle, homePose, 6)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while (i < 6):
        print(homePose[i])
        i = i + 1


#读取初始位
def api_demo_cr_cfg_home_pose_get():
    homePose = [10, 10, 10, 10, 10, 10]
    len = 6
    result = cgxiapi.cr_cfg_home_pose_get(robotHandle, homePose, len)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while (i < 6):
        print(homePose[i])
        i = i + 1


#删除初始位
def api_demo_cr_cfg_home_pose_delete():
    result = cgxiapi.cr_cfg_home_pose_delete(robotHandle)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取包装位
def api_demo_cr_cfg_pack_pose_get():
    packPose = [0, 0, 0, 0, 0, 0]
    result = cgxiapi.cr_cfg_pack_pose_get(robotHandle, packPose, 6)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while (i < 6):
        print(packPose[i])
        i = i + 1



##启动
#设置机器人是否自动上电使能
def api_demo_cr_cfg_poweron_auto_set():
    isAuto = 1
    result = cgxiapi.cr_cfg_poweron_auto_set(robotHandle, isAuto)
    assert (result.value == 0)


#读取机器人自动上电状态
def api_demo_cr_cfg_poweron_auto_get():
    result = cgxiapi.cr_cfg_poweron_auto_get(robotHandle)
    print("返回结果：", result[0].value)
    print("读取结果：", result[1].value)



##机器人拖动阻尼
#设置机器人拖动阻尼
def api_demo_cr_cfg_joint_drag_damping_set():
    jointDargDamping = (c_int * 6)(50, 50, 50, 50, 50, 50)
    arrSize = 6
    result = cgxiapi.cr_cfg_joint_drag_damping_set(robotHandle, jointDargDamping, arrSize)
    assert (result.value == 0)


#读取机器人拖动阻尼
def api_demo_cr_cfg_joint_drag_damping_get():
    jointDargDamping = (c_int * 6)(0, 0, 0, 0, 0, 0)
    arrSize = 6
    result = cgxiapi.cr_cfg_joint_drag_damping_get(robotHandle, jointDargDamping, arrSize)
    print("返回结果：", result.value)
    for i in range(0, arrSize):
        print("读取结果：", jointDargDamping[i])



##机器人限值
#设置限制模式
def api_demo_cr_cfg_safety_limit_type_set():
    safetyLimitsValuesType = basestruct.SafetyLimitsValuesType.LimitLevel_2
    result = cgxiapi.cr_cfg_safety_limit_type_set(robotHandle, safetyLimitsValuesType)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyLimitsValuesType)


#读取限制模式
def api_demo_cr_cfg_safety_limit_type_get():
    safetyLimitsValuesType = basestruct.SafetyLimitsValuesType()
    result = cgxiapi.cr_cfg_safety_limit_type_get(robotHandle, safetyLimitsValuesType)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyLimitsValuesType.value)


#设置自定义模式下参数
def api_demo_cr_cfg_safety_limit_para_set():
    mode = basestruct.SafetyLimitsMode.mode_Reduced
    safetyLimitsValues = basestruct.SafetyLimitsValues()
    safetyLimitsValues.maxTcpSpeed = 100
    result = cgxiapi.cr_cfg_safety_limit_para_set(robotHandle, mode, safetyLimitsValues)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取自定义模式下参数
def api_demo_cr_cfg_safety_limit_para_get():
    mode = basestruct.SafetyLimitsMode.mode_Reduced
    safetyLimitsValues = basestruct.SafetyLimitsValues()
    result = cgxiapi.cr_cfg_safety_limit_para_get(robotHandle, mode, safetyLimitsValues)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyLimitsValues.maxTcpSpeed)


#设置碰撞后处理方式
def api_demo_cr_cfg_safety_collihandle_type_set():
    safetyCollisionHandleMode = basestruct.SafetyCollisionHandleMode.Collision_EnterReboundMode
    result = cgxiapi.cr_cfg_safety_collihandle_type_set(robotHandle, safetyCollisionHandleMode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取碰撞后处理方式
def api_demo_cr_cfg_safety_collihandle_type_get():
    safetyCollisionHandleMode = basestruct.SafetyCollisionHandleMode()
    result = cgxiapi.cr_cfg_safety_collihandle_type_get(robotHandle, safetyCollisionHandleMode)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("碰撞后处理方式:", safetyCollisionHandleMode.value)


##关节限值
#设置关节限值
def api_demo_cr_cfg_safety_joint_limit_set():
    mode = basestruct.SafetyLimitsMode.mode_Reduced
    safetyLimitJoint = basestruct.SafetyLimitsJointAngle()
    safetyLimitJoint.maxJointPosition = 200
    safetyLimitJoint.minJointPosition = -200
    safetyLimitJoint.maxJointSpeed = 150
    result = cgxiapi.cr_cfg_safety_joint_limit_set(robotHandle, mode, 1, safetyLimitJoint)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果：", safetyLimitJoint.maxJointPosition, safetyLimitJoint.minJointPosition,
          safetyLimitJoint.maxJointSpeed)


#读取关节限值
def api_demo_cr_cfg_safety_joint_limit_get():
    mode = basestruct.SafetyLimitsMode.mode_Normal
    safetyLimitJoint = basestruct.SafetyLimitsJointAngle()
    result = cgxiapi.cr_cfg_safety_joint_limit_get(robotHandle, mode, 2, safetyLimitJoint)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果：", safetyLimitJoint.maxJointPosition, safetyLimitJoint.minJointPosition,
          safetyLimitJoint.maxJointSpeed)


##安全平面
#读取安全平面个数
def api_demo_cr_cfg_safety_plane_count():
    result = cgxiapi.cr_cfg_safety_plane_count(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果：", result[1].value)


#读取安全平面信息
def api_demo_cr_cfg_safety_plane_get():
    safetyLimitsBoundaryPlane = basestruct.SafetyLimitsBoundaryPlane()
    result = cgxiapi.cr_cfg_safety_plane_get(robotHandle, 1, safetyLimitsBoundaryPlane)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyLimitsBoundaryPlane.id, safetyLimitsBoundaryPlane.name)


#增加安全平面
def api_demo_cr_cfg_safety_plane_add():
    safetyLimitsBoundaryPlane = basestruct.SafetyLimitsBoundaryPlane()
    safetyLimitsBoundaryPlane.name = b'aa'
    safetyLimitsBoundaryPlane.id = 2
    result = cgxiapi.cr_cfg_safety_plane_add(robotHandle, safetyLimitsBoundaryPlane)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyLimitsBoundaryPlane.id, safetyLimitsBoundaryPlane.name)


#删除安全平面
def api_demo_cr_cfg_safety_plane_delete():
    result = cgxiapi.cr_cfg_safety_plane_delete(robotHandle, 2)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改安全平面数据
def api_demo_cr_cfg_safety_plane_set():
    safetyLimitsBoundaryPlane = basestruct.SafetyLimitsBoundaryPlane()
    safetyLimitsBoundaryPlane.name = b'123'
    safetyLimitsBoundaryPlane.id = 2
    safetyLimitsBoundaryPlane.displacement = 50
    result = cgxiapi.cr_cfg_safety_plane_set(robotHandle, 1, safetyLimitsBoundaryPlane)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyLimitsBoundaryPlane.id, safetyLimitsBoundaryPlane.name)



##安全I/O
#设置可配置输入信号
def api_demo_cr_cfg_safety_io_input_set():
    safetyinput = basestruct.SafetyIOInput.emergencyStop
    result = cgxiapi.cr_cfg_safety_io_input_set(robotHandle, 1, safetyinput)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyinput)


#读取可配置输入信号
def api_demo_cr_cfg_safety_io_input_get():
    safetyinput = basestruct.SafetyIOInput()
    result = cgxiapi.cr_cfg_safety_io_input_get(robotHandle, 1, safetyinput)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyinput.value)


#设置可配置输出信号
def api_demo_cr_cfg_safety_io_output_set():
    safetyoutput = basestruct.SafetyIOOutput.robotMoving
    result = cgxiapi.cr_cfg_safety_io_output_set(robotHandle, 1, safetyoutput)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyoutput)


#读取可配置输出信号
def api_demo_cr_cfg_safety_io_output_get():
    safetyoutput = basestruct.SafetyIOOutput()
    result = cgxiapi.cr_cfg_safety_io_output_get(robotHandle, 1, safetyoutput)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", safetyoutput.value)



##示教器控制
#设置是否启用示教器
def api_demo_cr_cfg_safety_tp_use_set():
    isUse = True
    result = cgxiapi.cr_cfg_safety_tp_use_set(robotHandle, isUse)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", isUse)


#读取当前是否启用示教器
def api_demo_cr_cfg_safety_tp_use_get():
    result = cgxiapi.cr_cfg_safety_tp_use_get(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果：", result[1].value)



##IO变量
#设置数字输入信号配置
def api_demo_cr_cfg_var_di_set():
    inputConfiguration = basestruct.IOInputConfiguration()
    type = basestruct.VarDigitialIOType.Digitial
    inputActions = basestruct.InputAction.InputAction_NONE
    inputConfiguration.inputActions = inputActions
    inputConfiguration.inputFilteringTime = 10
    inputConfiguration.inputName = b'addd'
    index = 1
    result = cgxiapi.cr_cfg_var_di_set(robotHandle, type, index, inputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", inputConfiguration.inputFilteringTime)


#读取数字输入信号配置
def api_demo_cr_cfg_var_di_get():
    inputConfiguration = basestruct.IOInputConfiguration()
    type = basestruct.VarDigitialIOType.Digitial
    inputConfiguration.inputActions = basestruct.InputAction.InputAction_NONE
    index = 1
    result = cgxiapi.cr_cfg_var_di_get(robotHandle, type, index, inputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", inputConfiguration.inputFilteringTime)


#设置数字输出信号配置
def api_demo_cr_cfg_var_do_set():
    outputConfiguration = basestruct.IOOutputConfiguration()
    type = basestruct.VarDigitialIOType.Digitial
    outputConfiguration.outputActions = basestruct.OutputAction.OutputAction_RobotON_LOW
    outputConfiguration.outputOptions = basestruct.OutputOptions.OutputOptions_Enable
    outputConfiguration.outputRule = basestruct.OutputRule.OutputRule_Disable
    outputConfiguration.outputName = b'af'
    index = 1
    result = cgxiapi.cr_cfg_var_do_set(robotHandle, type, index, outputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", outputConfiguration.outputName)


#读取数字输出信号配置
def api_demo_cr_cfg_var_do_get():
    outputConfiguration = basestruct.IOOutputConfiguration()
    type = basestruct.VarDigitialIOType.Digitial
    index = 1
    result = cgxiapi.cr_cfg_var_do_get(robotHandle, type, index, outputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", outputConfiguration.outputName)


#设置模拟量输入信号类型
def api_demo_cr_cfg_var_ai_set():
    analogInputConfiguration = basestruct.AnalogInputConfiguration()
    analogInputType = basestruct.AnalogType.Current
    type = basestruct.VarDigitialIOType.Analog
    analogInputConfiguration.analogInputType = analogInputType
    analogInputConfiguration.analogInputName = b'an'
    index = 1
    result = cgxiapi.cr_cfg_var_ai_set(robotHandle, type, index, analogInputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", analogInputConfiguration.analogInputName)


#读取模拟量输入信号类型
def api_demo_cr_cfg_var_ai_get():
    analogInputConfiguration = basestruct.AnalogInputConfiguration()
    type = basestruct.VarDigitialIOType.Analog
    index = 1
    result = cgxiapi.cr_cfg_var_ai_get(robotHandle, type, index, analogInputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", analogInputConfiguration.analogInputName)


#设置模拟量输出信号类型
def api_demo_cr_cfg_var_ao_set():
    analogOutputConfiguration = basestruct.AnalogOutputConfiguration()
    analogOutputConfiguration.analogOutputType = basestruct.AnalogType.Current
    analogOutputConfiguration.analogOutputName = b'afo'
    index = 0
    result = cgxiapi.cr_cfg_var_ao_set(robotHandle, index, analogOutputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", analogOutputConfiguration.analogOutputName)


#读取模拟量输出信号类型
def api_demo_cr_cfg_var_ao_get():
    analogOutputConfiguration = basestruct.AnalogOutputConfiguration()
    index = 0
    result = cgxiapi.cr_cfg_var_ao_get(robotHandle, index, analogOutputConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", analogOutputConfiguration.analogOutputName)


#设置工具电压输出值
def api_demo_cr_cfg_var_to_set():
    toolPower = basestruct.ToolPower.Power_on
    result = cgxiapi.cr_cfg_var_to_set(robotHandle, toolPower)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", toolPower)


#读取工具电压输出值
def api_demo_cr_cfg_var_to_get():
    toolPower = basestruct.ToolPower()
    result = cgxiapi.cr_cfg_var_to_get(robotHandle, toolPower)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", toolPower.value)


##通讯变量
#设置位寄存器配置
def api_demo_cr_cfg_var_bit_reg_set():
    bitRegisterConfiguration = basestruct.BitRegisterConfiguration()
    GeneralPurposeBOOLeanRegisterInputActions = basestruct.InputAction.InputAction_NONE
    GeneralPurposeBOOLeanRegisterOutputActions = basestruct.OutputAction.OutputAction_RobotON_HIGH
    GeneralPurposeBOOLeanRegisterOutputOutputRule = basestruct.OutputRule.OutputRule_Disable
    bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterInputActions = GeneralPurposeBOOLeanRegisterInputActions
    bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputActions = GeneralPurposeBOOLeanRegisterOutputActions
    bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputRule = GeneralPurposeBOOLeanRegisterOutputOutputRule
    bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName = b'aa'
    index = 2
    result = cgxiapi.cr_cfg_var_bit_reg_set(robotHandle, index, bitRegisterConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName,
          bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputActions.value)


#读取位寄存器配置
def api_demo_cr_cfg_var_bit_reg_get():
    bitRegisterConfiguration = basestruct.BitRegisterConfiguration()
    index = 2
    result = cgxiapi.cr_cfg_var_bit_reg_get(robotHandle, index, bitRegisterConfiguration)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName,
          bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputActions.value)


#设置16位整数寄存器变量名
def api_demo_cr_cfg_var_int16_reg_name_set():
    name = b'iii'
    index = 999
    len = 6
    result = cgxiapi.cr_cfg_var_int16_reg_name_set(robotHandle, index, name, len)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", name)


#读取16位整数寄存器变量名
def api_demo_cr_cfg_var_int16_reg_name_get():
    name = b'ee'
    index = 4
    len = 20
    result = cgxiapi.cr_cfg_var_int16_reg_name_get(robotHandle, index, name, len)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#设置32位整数寄存器变量名
def api_demo_cr_cfg_var_int32_reg_name_set():
    name = b'de'
    index = 1
    len = 6
    result = cgxiapi.cr_cfg_var_int32_reg_name_set(robotHandle, index, name, len)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", name)


#读取32位整数寄存器变量名
def api_demo_cr_cfg_var_int32_reg_name_get():
    name = b'qw'
    index = 2
    len = 6
    result = cgxiapi.cr_cfg_var_int32_reg_name_get(robotHandle, index, name, len)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#设置浮点寄存器变量名
def api_demo_cr_cfg_var_float_reg_name_set():
    name = b'ff'
    index = 2
    len = 6
    result = cgxiapi.cr_cfg_var_float_reg_name_set(robotHandle, index, name, len)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", name)


#读取浮点寄存器变量名
def api_demo_cr_cfg_var_float_reg_name_get():
    name = b'qq'
    index = 2
    len = 6
    result = cgxiapi.cr_cfg_var_float_reg_name_get(robotHandle, index, name, len)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)



##安装变量
#读取安装变量个数
def api_demo_cr_cfg_var_install_count():
    result = cgxiapi.cr_cfg_var_install_count(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#读取安装变量数据
def api_demo_cr_cfg_var_install_get():
    index = 1
    variableMsg = basestruct.VariableMsg()
    result = cgxiapi.cr_cfg_var_install_get(robotHandle, index, variableMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", variableMsg.variableName)


#增加安装变量
def api_demo_cr_cfg_var_install_add():
    variableMsg = basestruct.VariableMsg()
    variableMsg.variableName = b'aa'
    variableMsg.variableType = 3
    variableMsg.numberValue = 6
    variableMsg.variableID = 8
    result = cgxiapi.cr_cfg_var_install_add(robotHandle, variableMsg)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("增加结果:", variableMsg.variableName, variableMsg.variableID)


#删除安装变量
def api_demo_cr_cfg_var_install_delete():
    index = 1
    result = cgxiapi.cr_cfg_var_install_delete(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改安装变量
def api_demo_cr_cfg_var_install_set():
    variableMsg = basestruct.VariableMsg()
    variableMsg.variableName = b'sdf'
    variableMsg.variableType = 3
    variableMsg.numberValue = 12
    variableMsg.variableID = 3
    index = 1
    result = cgxiapi.cr_cfg_var_install_set(robotHandle, index, variableMsg)
    print("返回结果：", result.value)
    # assert (result.value == 0)
    print("设置结果:", variableMsg.variableName)



##坐标系
#读取点坐标系个数
def api_demo_cr_cfg_cs_point_count():
    result = cgxiapi.cr_cfg_cs_point_count(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#读取点坐标系数据
def api_demo_cr_cfg_cs_point_get():
    pointCSNode = basestruct.PointCSNode()
    index = 1
    result = cgxiapi.cr_cfg_cs_point_get(robotHandle, index, pointCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", pointCSNode.name)


#增加点坐标系
def api_demo_cr_cfg_cs_point_add():
    pointCSNode = basestruct.PointCSNode()
    pointCSNode.name = b'c0'
    pointCSNode.id = 1
    pointCSNode.point.toolAxisAngle = (30, 30, 30, 30, 30, 30)
    pointCSNode.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, pointCSNode.point.toolAxisAngle, pointCSNode.point.toolPosition)
    pointCSNode.isValid = 1
    result = cgxiapi.cr_cfg_cs_point_add(robotHandle, pointCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#删除点坐标系
def api_demo_cr_cfg_cs_point_delete():
    index = 1
    result = cgxiapi.cr_cfg_cs_point_delete(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改点坐标系数据
def api_demo_cr_cfg_cs_point_set():
    pointCSNode = basestruct.PointCSNode()
    pointCSNode.name = b'c2'
    pointCSNode.id = 2
    pointCSNode.point.toolAxisAngle = (30, 30, 30, 30, 30, 30)
    pointCSNode.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, pointCSNode.point.toolAxisAngle,
                           pointCSNode.point.toolPosition)
    pointCSNode.isValid = 1
    index = 0
    result = cgxiapi.cr_cfg_cs_point_set(robotHandle, index, pointCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取线坐标系个数
def api_demo_cr_cfg_cs_line_count():
    result = cgxiapi.cr_cfg_cs_line_count(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#读取线坐标系数据
def api_demo_cr_cfg_cs_line_get():
    lineCSNode = basestruct.LineCSNode()
    index = 1
    result = cgxiapi.cr_cfg_cs_line_get(robotHandle, index, lineCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", lineCSNode.name)


#增加线坐标系
def api_demo_cr_cfg_cs_line_add():
    lineCSNode = basestruct.LineCSNode()
    lineCSNode.name = b'line'
    lineCSNode.id = 4
    lineCSNode.firstPoint.name = b'p1'
    lineCSNode.firstPoint.id = 1
    lineCSNode.secondPoint.name = b'p2'
    lineCSNode.secondPoint.id = 2
    lineCSNode.firstPoint.point.toolAxisAngle = (0, 0, 90, 0, -90, 0)
    lineCSNode.firstPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, lineCSNode.firstPoint.point.toolAxisAngle,
                           lineCSNode.firstPoint.point.toolPosition)
    lineCSNode.firstPoint.isValid = 1
    lineCSNode.secondPoint.point.toolAxisAngle = (9.29, 3.39, 86.49, 0.08, -89.91, 9.29)
    lineCSNode.secondPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, lineCSNode.secondPoint.point.toolAxisAngle,
                           lineCSNode.secondPoint.point.toolPosition)
    lineCSNode.secondPoint.isValid = 1
    lineCSNode.coordinateJointPos = (0, 0, 0, 0, 0, 0)
    lineCSNode.coordinatePose = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_compute_cs_line(lineCSNode.firstPoint.point.toolPosition, 6,
                               lineCSNode.secondPoint.point.toolPosition, 6, lineCSNode.coordinatePose, 6)
    res = cgxiapi.cr_kineInverse(robotHandle, lineCSNode.coordinatePose,
                                 lineCSNode.coordinateJointPos, lineCSNode.coordinateJointPos)
    if res.value == 0:
        lineCSNode.isValid = 1
    else:
        lineCSNode.isValid = 0
    result = cgxiapi.cr_cfg_cs_line_add(robotHandle, lineCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#删除线坐标系
def api_demo_cr_cfg_cs_line_delete():
    index = 1
    result = cgxiapi.cr_cfg_cs_line_delete(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改线坐标系数据
def api_demo_cr_cfg_cs_line_set():
    lineCSNode = basestruct.LineCSNode()
    lineCSNode.name = b'line'
    lineCSNode.id = 4
    lineCSNode.firstPoint.name = b'llp1'
    lineCSNode.firstPoint.id = 1
    lineCSNode.secondPoint.name = b'lp2'
    lineCSNode.secondPoint.id = 2
    lineCSNode.firstPoint.point.toolAxisAngle = (0, 0, 90, 0, -90, 0)
    lineCSNode.firstPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, lineCSNode.firstPoint.point.toolAxisAngle,
                           lineCSNode.firstPoint.point.toolPosition)
    lineCSNode.firstPoint.isValid = 1
    lineCSNode.secondPoint.point.toolAxisAngle = (9.29, 3.39, 86.49, 0.08, -89.91, 9.29)
    lineCSNode.secondPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, lineCSNode.secondPoint.point.toolAxisAngle,
                           lineCSNode.secondPoint.point.toolPosition)
    lineCSNode.secondPoint.isValid = 1
    lineCSNode.coordinateJointPos = (0, 0, 0, 0, 0, 0)
    lineCSNode.coordinatePose = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_compute_cs_line(lineCSNode.firstPoint.point.toolPosition, 6,
                               lineCSNode.secondPoint.point.toolPosition, 6, lineCSNode.coordinatePose, 6)
    res = cgxiapi.cr_kineInverse(robotHandle, lineCSNode.coordinatePose,
                                 lineCSNode.coordinateJointPos, lineCSNode.coordinateJointPos)
    if res.value == 0:
        lineCSNode.isValid = 1
    else:
        lineCSNode.isValid = 0
    index = 1
    result = cgxiapi.cr_cfg_cs_line_set(robotHandle, index, lineCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取面坐标系个数
def api_demo_cr_cfg_cs_plane_count():
    result = cgxiapi.cr_cfg_cs_plane_count(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#读取面坐标系数据
def api_demo_cr_cfg_cs_plane_get():
    planeCSNode = basestruct.PlaneCSNode()
    index = 1
    result = cgxiapi.cr_cfg_cs_plane_get(robotHandle, index, planeCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", planeCSNode.name)


#增加面坐标系
def api_demo_cr_cfg_cs_plane_add():
    planeCSNode = basestruct.PlaneCSNode()
    planeCSNode.firstPoint.name = b'pp1'
    planeCSNode.firstPoint.id = 1
    planeCSNode.firstPoint.isValid = 1
    planeCSNode.secondPoint.name = b'pp2'
    planeCSNode.secondPoint.id = 2
    planeCSNode.secondPoint.isValid = 1
    planeCSNode.thirdPoint.name = b'pp3'
    planeCSNode.thirdPoint.id = 3
    planeCSNode.thirdPoint.isValid = 1
    planeCSNode.name = b'plane'
    planeCSNode.firstPoint.point.toolAxisAngle = (0, 0, 90, 0, -90, 0)
    planeCSNode.firstPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, planeCSNode.firstPoint.point.toolAxisAngle,
                           planeCSNode.firstPoint.point.toolPosition)
    planeCSNode.secondPoint.point.toolAxisAngle = (0, 4.84, 84.91, 0.25, -89.99, 0)
    planeCSNode.secondPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, planeCSNode.secondPoint.point.toolAxisAngle,
                           planeCSNode.secondPoint.point.toolPosition)
    planeCSNode.thirdPoint.point.toolAxisAngle = (-8.1, -1.5, 91.48, 0.04, -90.07, -8.1)
    planeCSNode.thirdPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, planeCSNode.thirdPoint.point.toolAxisAngle,
                           planeCSNode.thirdPoint.point.toolPosition)
    planeCSNode.coordinateJointPos = (0, 0, 0, 0, 0, 0)
    planeCSNode.coordinatePose = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_compute_cs_plane(planeCSNode.firstPoint.point.toolPosition, 6,
                                planeCSNode.secondPoint.point.toolPosition, 6,
                                planeCSNode.thirdPoint.point.toolPosition,
                                6, planeCSNode.coordinatePose, 6)
    res = cgxiapi.cr_kineInverse(robotHandle, planeCSNode.coordinatePose,
                                 planeCSNode.coordinateJointPos, planeCSNode.coordinateJointPos)
    if res.value == 0:
        planeCSNode.isValid = 1
    else:
        planeCSNode.isValid = 0
    result = cgxiapi.cr_cfg_cs_plane_add(robotHandle, planeCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#删除面坐标系
def api_demo_cr_cfg_cs_plane_delete():
    index = 1
    result = cgxiapi.cr_cfg_cs_plane_delete(robotHandle, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改面坐标系数据
def api_demo_cr_cfg_cs_plane_set():
    planeCSNode = basestruct.PlaneCSNode()
    planeCSNode.firstPoint.name = b'pp1'
    planeCSNode.firstPoint.id = 1
    planeCSNode.firstPoint.isValid = 1
    planeCSNode.secondPoint.name = b'pp2'
    planeCSNode.secondPoint.id = 2
    planeCSNode.secondPoint.isValid = 1
    planeCSNode.thirdPoint.name = b'pp3'
    planeCSNode.thirdPoint.id = 3
    planeCSNode.thirdPoint.isValid = 1
    planeCSNode.name = b'plane1'
    planeCSNode.firstPoint.point.toolAxisAngle = (0, 0, 90, 0, -90, 0)
    planeCSNode.firstPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, planeCSNode.firstPoint.point.toolAxisAngle,
                           planeCSNode.firstPoint.point.toolPosition)
    planeCSNode.secondPoint.point.toolAxisAngle = (0, 4.84, 84.91, 0.25, -89.99, 0)
    planeCSNode.secondPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, planeCSNode.secondPoint.point.toolAxisAngle,
                           planeCSNode.secondPoint.point.toolPosition)
    planeCSNode.thirdPoint.point.toolAxisAngle = (-8.1, -1.5, 91.48, 0.04, -90.07, -8.1)
    planeCSNode.thirdPoint.point.toolPosition = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_kineForward(robotHandle, planeCSNode.thirdPoint.point.toolAxisAngle,
                           planeCSNode.thirdPoint.point.toolPosition)
    planeCSNode.coordinateJointPos = (0, 0, 0, 0, 0, 0)
    planeCSNode.coordinatePose = (0, 0, 0, 0, 0, 0)
    cgxiapi.cr_compute_cs_plane(planeCSNode.firstPoint.point.toolPosition, 6,
                                planeCSNode.secondPoint.point.toolPosition, 6,
                                planeCSNode.thirdPoint.point.toolPosition, 6, planeCSNode.coordinatePose, 6)
    res = cgxiapi.cr_kineInverse(robotHandle, planeCSNode.coordinatePose,
                                 planeCSNode.coordinateJointPos, planeCSNode.coordinateJointPos)
    if res.value == 0:
        planeCSNode.isValid = 1
    else:
        planeCSNode.isValid = 0
    index = 0
    result = cgxiapi.cr_cfg_cs_plane_set(robotHandle, index, planeCSNode)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取基坐标系数据
def api_demo_cr_cfg_cs_base_get():
    csPose = [1,1,0,0,1,1]
    len = 6
    result = cgxiapi.cr_cfg_cs_base_get(robotHandle, csPose, len)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", csPose[0], csPose[1], csPose[2], csPose[3], csPose[4], csPose[5])


#读取工具坐标系数据
def api_demo_cr_cfg_cs_tool_get():
    csPose = [1,1,0,1,0,1]
    result = cgxiapi.cr_cfg_cs_tool_get(robotHandle, csPose, 6)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果：", csPose[0], csPose[1], csPose[2], csPose[3], csPose[4], csPose[5])


#计算点坐标系
def api_demo_cr_compute_cs_point():
    pointPose = [-36.10, -4.42, 32.62, 13.54, -91.33, 39.52]
    pointCS = [0, 0, 0, 0, 0, 0]
    csLen = 6
    pLen = 6
    result = cgxiapi.cr_compute_cs_point(pointPose, pLen, pointCS, csLen)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while i < 6:
        print("计算结果：", pointCS[i])
        i += 1


#计算线坐标系
def api_demo_cr_compute_cs_line():
    point1Pose = [-66, -438, 887, -57, 0, -148]
    point2Pose = [-76, -438, 887, -57, 0, -148]
    lineCS = [0, 0, 0, 0, 0, 0]
    csLen = 6
    p1Len = 6
    p2Len = 6
    result = cgxiapi.cr_compute_cs_line(point1Pose, p1Len, point2Pose, p2Len, lineCS, csLen)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while i < 6:
        print("计算结果：", lineCS[i])
        i += 1


#计算面坐标系
def api_demo_cr_compute_cs_plane():
    point1Pose = [-70, -436.75, 893, 27.15, 22, 150.76]
    point2Pose = [-75, -436.75, 893, 27.15, 22, 150.76]
    point3Pose = [-75, -440, 893, 27.15, 22, 150.76]
    planeCS = [0, 0, 0, 0, 0, 0]
    csLen = 6
    p1Len = 6
    p2Len = 6
    p3Len = 6
    result = cgxiapi.cr_compute_cs_plane(point1Pose, p1Len, point2Pose, p2Len, point3Pose, p3Len, planeCS, csLen)
    print("返回结果：", result.value)
    assert (result.value == 0)
    i = 0
    while i < 6:
        print("计算结果：", planeCS[i])
        i += 1



##串口通讯
#设置串口配置
def api_demo_cr_cfg_comm_serial_setting_set():
    serialType = basestruct.SerialType.rs485_1_CommSettings
    serialCommSettings = basestruct.SerialCommSettings()
    serialCommSettings.baudRate = basestruct.BaudRate.BaudRate115200
    serialCommSettings.parity = basestruct.ParityCheck.odd
    serialCommSettings.serialCommType = basestruct.SerialCommuType.Modbus_ASCII
    serialCommSettings.dataBits = 7
    serialCommSettings.retryNumber = 2
    serialCommSettings.timeout = 1000
    serialCommSettings.modbusSlaveNo = 1
    result = cgxiapi.cr_cfg_comm_serial_setting_set(robotHandle, serialType, serialCommSettings)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", serialType)


#读取串口配置
def api_demo_cr_cfg_comm_serial_setting_get():
    serialType = basestruct.SerialType.rs485_1_CommSettings
    serialCommSettings = basestruct.SerialCommSettings()
    result = cgxiapi.cr_cfg_comm_serial_setting_get(robotHandle, serialType, serialCommSettings)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", serialType)



##网络
#设置控制柜网络配置
def api_demo_cr_cfg_comm_ethernet_ip_set():
    ipconfig = basestruct.IPConfig()
    ipconfig.ipAddr[0] = 192
    ipconfig.ipAddr[1] = 168
    ipconfig.ipAddr[2] = 6
    ipconfig.ipAddr[3] = 7
    ipconfig.subnetMask[0] = 255
    ipconfig.subnetMask[1] = 255
    ipconfig.subnetMask[2] = 255
    ipconfig.subnetMask[3] = 0
    result = cgxiapi.cr_cfg_comm_ethernet_ip_set(robotHandle, ipconfig)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取控制柜网络配置
def api_demo_cr_cfg_comm_ethernet_ip_get():
    ipconfig = basestruct.IPConfig()
    result = cgxiapi.cr_cfg_comm_ethernet_ip_get(robotHandle, ipconfig)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", ipconfig.ipAddr[3])


#设置控制柜从站配置
def api_demo_cr_cfg_comm_ethernet_modbus_slave_num_set():
    modbusSlaveNo = 1
    result = cgxiapi.cr_cfg_comm_ethernet_modbus_slave_num_set(robotHandle, modbusSlaveNo)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", modbusSlaveNo)


#读取控制柜从站配置
def api_demo_cr_cfg_comm_ethernet_modbus_slave_num_get():
    result = cgxiapi.cr_cfg_comm_ethernet_modbus_slave_num_get(robotHandle)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)



##modbus主站
#读取从站个数
def api_demo_cr_cfg_comm_modbus_slave_count():
    type = basestruct.SerialType.rs232_CommSettings
    result = cgxiapi.cr_cfg_comm_modbus_slave_count(robotHandle, type)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)


#读取从站数据
def api_demo_cr_cfg_comm_modbus_slave_get():
    index = 1
    type = basestruct.SerialType.rs485_1_CommSettings
    modbusConfig = basestruct.ModbusMasterConfig()
    result = cgxiapi.cr_cfg_comm_modbus_slave_get(robotHandle, type, index, modbusConfig)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("读取结果:", modbusConfig.id)


#添加从站
def api_demo_cr_cfg_comm_modbus_slave_add():
    type = basestruct.SerialType.rs485_1_CommSettings
    modbusConfig = basestruct.ModbusMasterConfig()
    modbusConfig.autoConnect = 0
    modbusConfig.id = 2
    modbusConfig.modbusMasterOperate = basestruct.ModbusMasterOperate.Stop
    modbusConfig.scanTime = 10
    modbusConfig.slaveNo = 1
    result = cgxiapi.cr_cfg_comm_modbus_slave_add(robotHandle, type, modbusConfig)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("增加结果:", modbusConfig.id)


#删除从站
def api_demo_cr_cfg_comm_modbus_slave_delete():
    index = 0
    type = basestruct.SerialType.rs232_CommSettings
    result = cgxiapi.cr_cfg_comm_modbus_slave_delete(robotHandle, type, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改从站数据
def api_demo_cr_cfg_comm_modbus_slave_set():
    type = basestruct.SerialType.rs485_1_CommSettings
    modbusConfig = basestruct.ModbusMasterConfig()
    modbusConfig.autoConnect = 0
    modbusConfig.id = 1
    modbusConfig.modbusMasterOperate = basestruct.ModbusMasterOperate.Stop
    modbusConfig.scanTime = 5
    modbusConfig.slaveIP[0] = 192
    modbusConfig.slaveNo = 1
    index = 1
    result = cgxiapi.cr_cfg_comm_modbus_slave_set(robotHandle, type, index, modbusConfig)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", modbusConfig.scanTime)


#从站连接/断开
def api_demo_cr_cfg_comm_modbus_slave_operate():
    type = basestruct.SerialType.rs485_1_CommSettings
    modbusConfig = basestruct.ModbusMasterConfig()
    modbusOperate = basestruct.ModbusMasterOperate.Start
    index = 1
    result = cgxiapi.cr_cfg_comm_modbus_slave_operate(robotHandle, type, index, modbusOperate)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读取地址映射数量
def api_demo_cr_cfg_comm_modbus_addr_map_count():
    type = basestruct.SerialType.rs485_1_CommSettings
    serialIndex = 1
    result = cgxiapi.cr_cfg_comm_modbus_addr_map_count(robotHandle, type, serialIndex)
    print("返回结果：", result[0].value)
    assert (result[0].value == 0)
    print("读取结果:", result[1].value)



#读取地址映射数据
def api_demo_cr_cfg_comm_modbus_addr_map_get():
    type = basestruct.SerialType.rs232_CommSettings
    addrMap = basestruct.ModbusAddrMap()
    index = 1
    serialIndex = 1
    result = cgxiapi.cr_cfg_comm_modbus_addr_map_get(robotHandle, type, serialIndex, index, addrMap)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print(addrMap.masterRegType.value)


#添加地址映射
def api_demo_cr_cfg_comm_modbus_addr_map_add():
    type = basestruct.SerialType.rs232_CommSettings
    addrMap = basestruct.ModbusAddrMap()
    addrMap.functionNo = basestruct.ModbusMasterFunctionNo.ReadInt16
    addrMap.masterOffsetNo = 1
    addrMap.masterRegType = basestruct.CommuVarType.CommuVarType_Int16
    addrMap.masterStartAddr = 1
    addrMap.slaveStartAddr = 234
    index = 1
    result = cgxiapi.cr_cfg_comm_modbus_addr_map_add(robotHandle, type, index, addrMap)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("添加结果:", addrMap.slaveStartAddr)


#删除地址映射
def api_demo_cr_cfg_comm_modbus_addr_map_delete():
    type = basestruct.SerialType.rs485_1_CommSettings
    index = 1
    serialIndex = 1
    result = cgxiapi.cr_cfg_comm_modbus_addr_map_delete(robotHandle, type, serialIndex, index)
    print("返回结果：", result.value)
    assert (result.value == 0)


#修改地址映射数据
def api_demo_cr_cfg_comm_modbus_addr_map_set():
    type = basestruct.SerialType.rs485_1_CommSettings
    addrMap = basestruct.ModbusAddrMap()
    addrMap.functionNo = basestruct.ModbusMasterFunctionNo.ReadInt16
    addrMap.masterOffsetNo = 1
    addrMap.masterRegType = basestruct.CommuVarType.CommuVarType_Float
    addrMap.masterStartAddr = 2
    addrMap.slaveStartAddr = 234
    index = 1
    serialIndex = 1
    result = cgxiapi.cr_cfg_comm_modbus_addr_map_set(robotHandle, type, serialIndex, index, addrMap)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print("设置结果:", addrMap.slaveStartAddr)


#设置力控配置
def api_demo_cr_force_cfg_set():
    forceConfig = basestruct.ForceConfig()
    forceConfig.forceCtrlTcpImpl.activeForceTCP_name = b'TCP_4'
    forceConfig.forceCtrlTcpImpl.activeForcePayload_name = b'ForcePayload7'

    forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpName = b'TCP_4'
    forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpId = 0
    forceConfig.forceCtrlTcpImpl.availableForceTCP[1].forceTcpName = b'TCP_8'
    forceConfig.forceCtrlTcpImpl.availableForceTCP[1].forceTcpId = 1
    forceTcpOffset = [0, 0, 0, 0, 0, -110]
    for i in range(0, 6):
        forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpOffset[i] = forceTcpOffset[i]
    forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forcePayloadName = b'ForcePayload7'
    forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forcePayloadId = 0
    forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forceToolPayload = 1.3
    forceCenterOfGravity = [1, 2, 3]
    for i in range(0, 3):
        forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forceCenterOfGravity[i] = forceCenterOfGravity[i]
    forceConfig.forceCtrlTcpImpl.availableForceTCPLen = 2
    forceConfig.forceCtrlTcpImpl.availableForcePayLoadLen = 1
    forceConfig.commuConfig.autoConnect = 1
    forceConfig.commuConfig.mannaulOperate = 0
    forceConfig.commuConfig.paraBuf = 0
    forceConfig.sensorMessage.venderNo = 0  ##
    forceConfig.sensorMessage.productNo = 1
    forceConfig.sensorMessage.sequenceNo = 0
    result = cgxiapi.cr_force_cfg_set(robotHandle, forceConfig)
    print("返回结果：", result.value)
    assert (result.value == 0)


#读力控配置
def api_demo_cr_force_cfg_get():
    forceConfig = basestruct.ForceConfig()
    result = cgxiapi.cr_force_cfg_get(robotHandle, forceConfig)
    print("返回结果：", result.value)
    assert (result.value == 0)
    print(forceConfig.commuConfig.autoConnect)


#开启力控并下发相关设置
def api_demo_cr_force_open():
    forceSetting = basestruct.ForceSetting()
    forceSetting.forceBaseType = 0
    forceSetting.forceCtrlType = 1
    flexibleAxis = [0, 0, 1, 0, 0, 0]
    i=0
    while i<6:
        forceSetting.flexibleAxis[i] = flexibleAxis[i]
        i+=1
    result = cgxiapi.cr_force_open(robotHandle, forceSetting)

    print("返回结果：", result.value)
    assert (result.value == 0)


#关闭力控
def api_demo_cr_force_close():
    result = cgxiapi.cr_force_close(robotHandle)
    print("返回结果：", result.value)
    assert (result.value == 0)


#设置力控控制参数
def api_demo_cr_force_para_set():
    forceCtlPara = basestruct.ForceCtlPara()
    taskFrame = [0, 0, 0, 0, 0, 0]
    wrench = [0, 0, -10, 0, 0, 0]
    limits = [0.1,0.1,0.005,0.002,0.002,0.002]
    mass = [1, 1, 0.5, 1, 1, 1]
    damping = [1, 1, 0.1, 1, 1, 1 ]
    stiffness = [1, 1, 0.1, 1, 1, 1]
    forceCtlPara.limitsLen = 6
    forceCtlPara.massLen = 6
    forceCtlPara.dampingLen = 6
    forceCtlPara.stiffnessLen = 6
    i=0
    while i<6:
        forceCtlPara.taskFrame[i] = taskFrame[i]
        forceCtlPara.limits[i] = limits[i]
        forceCtlPara.mass[i] = mass[i]
        forceCtlPara.damping[i] = damping[i]
        forceCtlPara.stiffness[i] = stiffness[i]
        i+=1
    result = cgxiapi.cr_force_para_set(robotHandle,forceCtlPara)
    print("返回结果：", result.value)
    assert (result.value == 0)


# 读力控控制参数
def api_demo_cr_force_para_get():
    forceCtlPara = basestruct.ForceCtlPara()
    result = cgxiapi.cr_force_para_get(robotHandle, forceCtlPara)
    print("返回结果：", result.value)
    i=0
    while i < 6:
        print(forceCtlPara.limits[i])
        i += 1
    assert (result.value == 0)


# 读力控数据
def api_demo_cr_force_data_get():
    forceData = basestruct.ForceData()
    result = cgxiapi.cr_force_data_get(robotHandle, forceData)
    print("返回结果：", result.value)
    i = 0
    while i < 6:
        print(forceData.ftCtrl[i])
    assert (result.value == 0)


#主函数
def main():
    #####在此处调用函数
    # api_demo_cr_cfg_tcp_set()
    # api_demo_cr_cfg_payload_get()
    # api_demo_cr_cfg_var_do_set()
    # api_demo_cr_cfg_var_int16_reg_name_get()
    # api_demo_cr_cfg_var_install_get()
    # api_demo_cr_cfg_comm_modbus_addr_map_add()
    # api_demo_cr_cfg_var_install_add()
    # api_demo_cr_cfg_var_install_set()
    # api_demo_cr_force_cfg_set()

    api_demo_cr_cfg_joint_drag_damping_set()
    # 机械臂断开连接
    re0=cgxiapi.cr_destroy_robot(robotHandle)
    if re0.value != 0:
        print("断开失败")
        exit()

if __name__ == "__main__":
    main()
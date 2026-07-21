#!/usr/bin/python3
import sys
import types

from ctypes import *
from typing import NewType

ROB_AXIS_NUM = 6
CR6_DI_NUM = 8                              #数字输入，digital input
CR6_DO_NUM = 8
CR6_CI_NUM = 8                              #
CR6_CO_NUM = 8
CR6_AI_NUM = 3                              #模拟输入，Analog = signal
CR6_AO_NUM = 1
CR6_TOOL_DI_NUM = 2                         #工具数字信号输入
CR6_TOOL_DO_NUM = 2                         #工具数字信号输出
CR6_TOOL_AI_NUM = 2                         #工具模拟信号输入
CR6_COM_NUM = 4

ModbusMasterConfigNumber = 20
ModbusAddrMapNumber = 100
CR6_BOOL_REG_NUM = 1000
CR6_INT16_REG_NUM = 1000
CR6_INT32_REG_NUM = 1000
CR6_FLOAT_REG_NUM = 1000

RtInterfaceData_Max_Num = 20

ENCODER_TICK_NUM = 2

COR_MAX_NUM = 50

DH_PARA_MAX_NUM = 100
DY_PARA_MAX_NUM = 100

CR6_ISTALL_VAR_NUM = 100
CR6_ISTALL_VAR_NAME_LENGTH = 100
CR6_INSTALL_VAR_MAX_LENGTH = 100
CR6_INSTALL_VAE_TABLE_MAX_LENGTH = 10000
Script_MAX_TableElement = 500
Script_MAX_DataLen = 100

TCP_MAX_NUM = 20
NAMELENTH = 32
MOVECPOINT_NUM = 2
PATHMAXPOINTS = 10000
PATHMINTIME = 2

VERSION_MAX_LENGTH = 50

crRobotHandle =NewType("crRobotHandle",c_int)

# c=crRobotHandle(10)

BOOL = bool
TRUE = 1
FALSE = 0


class CRresult(c_int):
    sucess = 0                 #<成功
    error = 1                  #<一般错误
    thread_running = 2         #<通讯连接重复建立
    operate_timeout = 3        #<操作超时，无返回值
    result_invalid = 4         #<返回结果无效
    out_of_range = 5           #<输入数值越界
    mutex_invalid = 6          #<内部错误
    para_error = 7             #<参数无效
    no_result = 8              #<无对应数值
    no_assignTCPindex = 9      #<未找到指定索引号TCP偏移量
    no_handle = 10             #<未创建相关句柄
    handle_repeat = 11         #<重复建立相同的句柄
    repeat_name = 12           #<重命名
    delete_invalid = 13        #<删除唯一的TCP或者负载
    set_bit_reg_invalid = 14   #<同时设置位寄存器输入与输出
    repeat_id = 15             #<id重复
    file_encryption = 16       #<文件加密
    robotmode_error = 17       #<当前状态不能执行该操作
    move_error = 18            #<移动阻塞运动时,返回的移动状态错误
    forcectrl_wrongpara = 19    #<力控SDK参数设置错误：包括参数长度错误、payload为负数
    forcectrl_invaildcmd = 20   #<力控SDK无效的指令：包括forceEna等于1,0以外的值forcebasetype除0以外的值 forcectrltype除1,0以外  auto/mannual 1,0以外的值
    forcectrl_parablocked = 21   #<力控SDK freedrive模式下部分参数失效被屏蔽
    forcectrl_cmdblocked = 22   #<力控SDK 已在力控模式下时禁止再打开力控
    forcectrl_configblocked = 23  #<力控SDK 机器人运动时或已在力控模式下时禁止下发配置
    forcectrl_notenable = 24    #<力控SDK 机器人使能之前不能打开传感器
    forcectrl_wrongsensor = 25  #<力控SDK 传感器型号选择错误
    outputrule_error = 26       #<未设置系统输出，禁止启用自复位
    analoginputtype_error = 27  #<模拟量输入类型错误：注：工具端模拟量输入类型只有电压

class RtInterfaceCmd(c_int):
    noOperate=0
    open=1
    close=2
    start=3
    stop=4


class CommuVarType(c_int):
    CommuVarType_Bool=0         #<bool类型
    CommuVarType_Int16=1        #<16bit整数类型
    CommuVarType_Int32=2        #<32bit整数类型
    CommuVarType_Float=3        #<32bit浮点类型


class CoordinateType(c_int):
    baseCoordinate = 0          #<基坐标系
    jointCoordinate =1          #<关节坐标系
    PointCoordinate =2          #<点坐标系
    LineCoordinate  =3          #<线坐标系
    PlaneCoordinate =4          #<面坐标系
    ToolBaseCoordinate  =5      #<工具坐标系
    visionCoordinate    =6      #<视角坐标系


class PointTransType(c_int):
    pointTransStop =0             #<过渡点停止
    pointTransConstantSpeed=1     #<匀速过渡
    pointTransSmooth =2           #<柔顺过渡（不匀速，不停止）


class PoseTranType(c_int):
    poseTranMoveToTargetPose=0
    poseTranKeepStartPose=1

class MotiontriggerMode(c_int):
    MovetriggerbySafetySingnal = 0     #<安全同步信号触发
    MovetriggerbyOnlyRpc       = 1     #<指令直接触发
    MovetriggerbyMoveCache     = 2     #<移动指令会进入缓存区


class TCPMsg(Structure):
    _fields_ = [('tcpName', c_char*20),                     #tcp名称
                ('tcpOffset', c_double*ROB_AXIS_NUM)]        #<tcp偏移量, double tcpOffset[ROB_AXIS_NUM];

class PayLoad(Structure):
    _fields_ = [('payloadName',c_char*20),
                ('toolPayload',c_double),
                ('centerOfGravity',c_double*3)]

class PointControlPara(Structure):
    _fields_ = [('pose',c_double*ROB_AXIS_NUM),                 #<坐标点向量  double pose[ROB_AXIS_NUM]
                ('jointpos',c_double*ROB_AXIS_NUM),             #<关节角度   double jointpos[ROB_AXIS_NUM]
                ('tcpOffset',c_double*ROB_AXIS_NUM),            #<tcp偏移量  double tcpOffset[ROB_AXIS_NUM]
                ('tcpID',c_int),                         #<tcp的ID号,当tcpID为非负数时，使用tcpID对应的TCP偏移量作为输入；当tcpID为负数时，使用tcpoffset数据作为TCP偏移量输入；int  tcpID
                ('coordinateType',CoordinateType),             #<坐标系类型  c_int CoordinateType  coordinateType
                ('coordinatePose',c_double*ROB_AXIS_NUM),       #<参考坐标系位姿 double coordinatePose[ROB_AXIS_NUM]
                ('speed',c_double*ROB_AXIS_NUM),                #<速度  double speed[ROB_AXIS_NUM]
                ('acc',c_double*ROB_AXIS_NUM),                  #<加速度  double acc[ROB_AXIS_NUM]
                ('jerk',c_double*ROB_AXIS_NUM),                 #<加加速度  double jerk[ROB_AXIS_NUM]
                ('pointTransType',PointTransType),             #<位置过渡方式  c_int PointTransType pointTransType
                ('pointTransRadius',c_double),                  #<过渡半径  double pointTransRadius
                ('poseTranType',PoseTranType),                 #<姿态变换方式  c_int PoseTranType poseTranType
                ('motiontriggerMode',MotiontriggerMode)        #<运动轨迹触发方式  c_int MotiontriggerMode motiontriggerMode
                ]

class PointControlParaList (Structure):
    _fields_ = [('pointcontrolpara',PointControlPara*MOVECPOINT_NUM),   #过渡点和终点
                ('fixedrot',c_int),                                    #方向模式 0-无约束 1-固定
                ('centralangle',c_double)]                             #圆弧角

class PointControlParaSimple(Structure):
    _fields_ = [('pose', c_double * ROB_AXIS_NUM),  # <坐标点向量  double pose[ROB_AXIS_NUM]
                ('jointpos', c_double * ROB_AXIS_NUM),  # <关节角度   double jointpos[ROB_AXIS_NUM]
                ('tcpOffset', c_double * ROB_AXIS_NUM),  # <tcp偏移量  double tcpOffset[ROB_AXIS_NUM]
                ('coordinateType', CoordinateType),  # <坐标系类型  c_int CoordinateType  coordinateType
                ('coordinatePose', c_double * ROB_AXIS_NUM),  # <参考坐标系位姿 double coordinatePose[ROB_AXIS_NUM]
                ('speed', c_double * ROB_AXIS_NUM),  # <速度  double speed[ROB_AXIS_NUM]
                ('acc', c_double * ROB_AXIS_NUM),  # <加速度  double acc[ROB_AXIS_NUM]
                ('pointTransType', PointTransType),  # <位置过渡方式  c_int PointTransType pointTransType
                ('motiontriggerMode', MotiontriggerMode)  # <运动轨迹触发方式  c_int MotiontriggerMode motiontriggerMode
                ]

class MoveType(c_int):
    DecStop = 0     #<减速停止
    ImdStop = 1	    #<立即停止
    Run = 2  		#<运动


class JointModes(c_int):
    JOINT_MODE_POWER_OFF = 1					#<断电
    JOINT_MODE_BOOTING = 2			  			#<机械臂上电至空闲状态下
    JOINT_MODE_IDLE = 3						    #<上电完成,空闲状态（ethercat——>op）
    JOINT_MODE_BACK_DRIVE = 4					#<反向驱动状态
    JOINT_MODE_RELEASE_BRAKE = 5				#<机械臂使能，松抱闸过程中
    JOINT_MODE_CSP_STOP = 7					    #<关节使能静止(位置模式)
    JOINT_MODE_CSP_MOVING = 8					#<关节使能运动(位置模式)
    JOINT_MODE_CST_STOP = 9					    #<关节使能静止(转矩模式)
    JOINT_MODE_CST_MOVING = 10					#<关节使能运动(转矩模式)
    JOINT_MODE_FAULT = 11			    		#<错误状态
    JOINT_MODE_READY_FOR_POWER_OFF = 12 		#<准备断电




class RequestState(c_int):
    EC_INT_REQUEST_INIT = 0
    EC_INT_REQUEST_QUEUED = 1
    EC_INT_REQUEST_BUSY = 2
    EC_INT_REQUEST_SUCCESS = 3
    EC_INT_REQUEST_FAILURE = 4

class RobotModes(c_int):
    #初始化
    Closed = 0
    Disconnect = 1                       #< 断开连接状态
    ConfirmSafty = 2                     #< 安全确认状态
    Booting = 3                          #< 控制器正在启动
    ControlerIdle = 4                    #< 控制器启动完成，空闲状态
    ControlerUpdataFirmWare = 5          #< 固件更新
    JointPowerOff = 6                    #< 控制器启动完成，本体未上电
    JointPowerOn = 7                     #< 机器人上电过程
    JointIdle = 8                        #< 机器人上电完成，空闲
    BackDrive = 9                        #< 空闲状态下，按下示教按钮，会松开将仅释放在施加有显著压力的关节中的制动器。当使用反向驱动时，机器人感觉移动起来很沉重。
    ReleaseBrake = 10                    #< 机器人使能、松抱闸中
    Enable = 11                          #< 机器人使能完成，并已完全松开抱闸
    CloseBrake = 12                      #< 机器人断使能、关抱闸中
    #运动
    Jog = 100                            #< 点动
    Teach = 101                          #< 拖动示教
    ForceControlTest = 102               #< 力控测试
    ProgramStop = 103                    #< 使能完成，程序停止
    ProgramPause = 104                   #< 使能完成，程序暂停
    ProgramStopping = 105                #< 使能完成，程序和运动正在停止
    ProgramPauseing = 106                #< 使能完成，程序和运动正在暂停
    ProgramRun_MotionStop = 107          #< 程序运行，运动停止
    ProgramRun_MotionReducing = 108      #< 程序运行，运动减速中
    ProgramRun_MotionMoving  = 109
    ProgramRun_MotionCanBlend = 110      #< 程序运行，机器人进入到可交融区域
    Imdstop = 111                        #< 紧急停止
    ProtectiveStop = 112                 #< 防护停止


class ControlModes(c_int):
    CONTROL_MODE_POSITION = 0					#< 控制器启动后的各种RobotModes
    CONTROL_MODE_TEACH = 1						#< ROBOT_MODE_RUNNING下，按下示教按钮或者执行teach_mode()，在此模式下手动使机器人来回移动
    CONTROL_MODE_FORCE = 2						#< 力控命令内
    CONTROL_MODE_TORQUE = 3						#< 自由驱动模式


class SafetyModes(c_int):
    SAFETY_MODE_UNDEFINED_SAFETY_MODE = 1
    SAFETY_MODE_VALIDATE_JOINT_ID = 2		    #< 验证关节的ID
    SAFETY_MODE_FAULT = 3                       #< 安全错误，其他错误出现一段时间后，最终保持的错误状态
    SAFETY_MODE_VIOLATION = 4                   #< 在安全平面处越界
    SAFETY_MODE_ROBOT_EMERGENCY_STOP = 5	    #< 急停按钮按下
    SAFETY_MODE_SYSTEM_EMERGENCY_STOP = 6	    #< 可配置IO输入任意两路设置为紧急停机，断开后出现的错误状态
    SAFETY_MODE_SAFEGUARD_STOP = 7              #< 安全IO断开
    SAFETY_MODE_RECOVERY = 8                    #< 在违反安全限制后，机器人停止，重启后，进入恢复模式
    SAFETY_MODE_PROTECTIVE_STOP = 9             #< 保护性停止，运动过程中，外部强力推动机械手
    SAFETY_MODE_REDUCED	= 10                    #< 限制模式
    SAFETY_MODE_NORMAL = 11                     #< 正常运行模式

class ToolModes(c_int):
    TOOL_MODE_POWER_OFF	 = 1
    TOOL_MODE_BOOTING = 2
    TOOL_MODE_IDLE = 3
    TOOL_MODE_RUNNING = 4
    TOOL_MODE_FAULT = 5

#程序状态
class ProgramState(c_int):
    PROGRAM_STATE_STOP = 0		    #< 程序停止
    PROGRAM_STATE_PAUSE =1          #< 程序暂停
    PROGRAM_STATE_RUN   =2          #< 程序运行




class Version(Structure):
    _fields_ = [('deviceType',c_ubyte*VERSION_MAX_LENGTH),           #< 机器人类型  unsigned char deviceType[20];
               ('versionNo',c_ubyte*VERSION_MAX_LENGTH),            #< 版本信息    unsigned char versionNo[20];
               ('bugfix',c_int),                    #< bug修正    int bugfix;
               ('buildDate',c_longlong),            #< 编译日期    long long buildDate;
               ('hardwareID',c_ubyte*VERSION_MAX_LENGTH),           #< 硬件id     unsigned char hardwareID[20];
               ('bootVersionNo',c_ubyte*VERSION_MAX_LENGTH)]

#机器人状态
class RobotState_Data(Structure):
    _fields_ = [('timestamp',c_ulonglong),               #< 时间戳    unsigned long long	timestamp;
               ('controllerTimer',c_ulonglong),         #< 自控制器启动以来的时间   unsigned long long	controllerTimer;
               ('isRealRobotConnected',c_bool),         #< 是否连接实际机械臂    BOOL isRealRobotConnected;
               ('isRealRobotEnabled',c_bool),           #< 是否机械臂使能     BOOL isRealRobotEnabled;
               ('isRobotPowerOn',c_bool),               #< 是否机械臂上电     BOOL isRobotPowerOn;
               ('isEmergencyStopped',c_bool),           #< 是否紧急停止       BOOL isEmergencyStopped;
               ('isProtectiveStopped',c_bool),          #< 是否保护停止       BOOL isProtectiveStopped;
               ('isRobotMoving',c_bool),                #< 是否机械臂运动     BOOL isRobotMoving;
               ('programState',ProgramState),           #< 程序状态          ProgramState programState;
               ('robotMode',RobotModes),                #< 机械臂模式        RobotModes	robotMode;
               ('controlMode',c_int),                   #< 控制模式          int	controlMode;
               ('safetyMode',SafetyModes),              #< 安全模式          SafetyModes safetyMode;
               ('inReducedMode',c_bool),                #< 是否在限制模式     BOOL inReducedMode;
               ('percentVelocity',c_uint),              #< 速度百分比        unsigned int percentVelocity;
               ('linearMomentumNorm',c_double),         #< 直线动力值        double linearMomentumNorm;
               ('targetSpeedFractionLimit',c_double),   #< 目标速度分数限制   double targetSpeedFractionLimit;
               ('version',Version)                      #< 版本信息          Version
               ]

#关节数据
class Joint_Data(Structure):
    _fields_ = [('actualJointPositions',c_float*ROB_AXIS_NUM),  #< 实际关节位置    double
                ('targetJointPositions', c_float * ROB_AXIS_NUM),  # < 目标关节位置    double
                ('actualJointVelocitys', c_float * ROB_AXIS_NUM),  # < 实际关节速度    double
                ('targetJointVelocitys', c_float * ROB_AXIS_NUM),  # < 目标关节速度    double
                ('actualJointAccelerations', c_float * ROB_AXIS_NUM),  # < 实际关节加速度  double
                ('targetJointAccelerations', c_float * ROB_AXIS_NUM),  # < 目标关节加速度  double
                ('jointRevolutionCounts', c_float * ROB_AXIS_NUM),  # < 关节旋转圈数    double
                ('actualJointCurrents', c_float * ROB_AXIS_NUM),  # < 实际关节电机电流 double
                ('targetJointCurrents',c_float * ROB_AXIS_NUM),#< 目标关节电机电流 double
                ('targetJointMoments',c_float * ROB_AXIS_NUM),#< 目标关节扭矩    double
                ('actualJointVoltages',c_float * ROB_AXIS_NUM),#< 实际关节采集的母线电压double
                ('jointTemperature',c_float * ROB_AXIS_NUM),#< 关节温度       double
                ('jointMode',JointModes*ROB_AXIS_NUM),#< 关节模式  JointModes jointMode[ROB_AXIS_NUM]
                ('jointVersion',Version*ROB_AXIS_NUM)#< 版本信息  Version jointVersion[ROB_AXIS_NUM]
                ]

#末端工具接口数据
class Tool_Data(Structure):
    _fields_=[('toolAnalogInput',c_float*CR6_TOOL_AI_NUM),  #< 模拟量输入         double toolAnalogInput[CR6_TOOL_AI_NUM];
              ('toolVoltage',c_double),                     #< 工具输入电压       double toolVoltage;
              ('toolCurrent',c_double),                     #< 工具电流          double toolCurrent;
              ('toolTemperature',c_double),                 #< 工具温度          double toolTemperature;
              ('toolMode',ToolModes),                       #< 工具模式          ToolModes toolMode;
              ('toolDigitalInput',c_bool*CR6_TOOL_DI_NUM),  #< 工具数字输入       BOOL toolDigitalInput[CR6_TOOL_DI_NUM];
              ('toolDigitalOutput',c_bool*CR6_TOOL_DO_NUM),] #< 工具数字输出       BOOL toolDigitalOutput[CR6_TOOL_DO_NUM];

#控制器IO板数据
class Masterboard_Data(Structure):
    _fields_ = [('digitalInput',c_bool*CR6_DI_NUM),                 #< 数字输入  BOOL digitalInput[CR6_DI_NUM];
                ('digitalOutput',c_bool*CR6_DO_NUM),                #< 数字输出  BOOL digitalOutput[CR6_DO_NUM];
                ('configurableDigitalInput',c_bool*CR6_DI_NUM),     #< 可配置数字输入  BOOL configurableDigitalInput[CR6_CI_NUM];
                ('configurableDigitalOutput',c_bool*CR6_CO_NUM),    #< 可配置数字输出  BOOL configurableDigitalOutput[CR6_CO_NUM];
                ('analogInput',c_double*CR6_AI_NUM),                #< 模拟量输入     double analogInput[CR6_AI_NUM];
                ('analogOutput',c_double*CR6_AO_NUM),               #< 模拟量输出     double
                ('masterboardTemperature',c_double),                #< 主板温度       double
                ('safetyboardTemperature',c_double),                #< 安全板温度     double
                ('masterboardVoltage',c_double),                    #< 主板电压       double
                ('robotVoltage',c_double),                          #< 本体母线电压    double
                ('robotCurrent',c_double),                          #< 本体电流       double
                ('masterIOCurrent',c_double),                       #< IO口电流       double
                ('operationalModeSelectorInput',c_bool),            #< 操作模式选择输入限制模式BOOL
                ('threePositionEnablingDeviceInput',c_int),         #< 三态模式按钮       int
                ('encoderTickCount',c_longlong*ENCODER_TICK_NUM)    #< 编码器计数值       long long []
                ]

#tcp数据
class Cartesian_Data(Structure):
    _fields_ = [('tcpVectorActual',c_double*ROB_AXIS_NUM),          #< 实际tcp位置 double
                ('tcpVectorTarget',c_double*ROB_AXIS_NUM),          #< 目标tcp位置double
                ('tcpSpeedActual',c_double*ROB_AXIS_NUM),           #< 实际tcp速度double
                ('tcpSpeedTarget',c_double*ROB_AXIS_NUM),           #< 目标tcp速度double
                ('tcpAccelerometer',c_double*ROB_AXIS_NUM),         #< 实际tcp加速度double
                ('tcpIDValid',c_int),                               #<当前tcpid int
                ('tcpoffsetValid',c_double*ROB_AXIS_NUM)            #<当前tcp偏移量 double
                ]

#力控制模式数据
class ForceMode_Data(Structure):                                    #< tcp力矩反馈向量double
    _fields_ = [('tcp_F_Vector',c_double*ROB_AXIS_NUM),             #< tcp力度量程double
                ('tcpForceScalar',c_double),
                ('robotDexterity',c_double)                         #< 力控灵敏度double
                ]

#示教器数据
class TeachPanel_Data(Structure):
    _fields_ = [('freeDriveButtonPressed',c_bool),		            #< 自由驱动按钮按住 BOOL
                ('freeDriveButtonEnabled',c_bool),		            #< 自由驱动按钮使能BOOL
                ('powerButtonPressed',c_bool),		                #< 电源按钮按住BOOL
                ('IOEnabledFreedrive',c_bool)			            #< IO使能自由驱动BOOL
                ]

#脚本程序状态
class Lua_ScriptStatus(c_int):
    lua_Script_NoneOP = 0		#< 空
    lua_Script_stop = 1		    #< 脚本程序停止
    lua_Script_pause = 2		#< 脚本程序暂停
    lua_Script_run = 3			#< 脚本程序运行
    lua_Script_load = 4			#< 脚本程序正在加载


#脚本数据
class Script_Data(Structure):
    _fields_ = [('currentLine',c_uint*(COR_MAX_NUM+1)),             #< 当前运行到第几行     unsigned int
                ('lua_ScriptStatus',Lua_ScriptStatus)               #< 脚本程序状态
                ]



class RtInterfaceData(Structure):
    _fields_=[('robotState',RobotState_Data),
              ('jointData',Joint_Data),
              ('toolData',Tool_Data),
              ('masterboardData',Masterboard_Data),
              ('cartesianData',Cartesian_Data),
              ('forceModeData',ForceMode_Data),
              ('teachPanelData',TeachPanel_Data),
              ('scriptData',Script_Data)
              ]

class Mult_RtInterfaceData(Structure):
    _fields_ =[('rtInterfaceData',POINTER(RtInterfaceData)),         #指向RtInterfaceData的指针，怎么写？？
               ('validNum_rtInterfaceData',c_int)                   #int
               ]

class VariableType(c_int):
    LUA_TNIL = 0
    LUA_TBOOLEAN = 1
    LUA_TLIGHTUSERDATA = 2
    LUA_TNUMBER = 3
    LUA_TSTRING = 4
    LUA_TTABLE = 5
    LUA_TFUNCTION = 6
    LUA_TUSERDATA = 7
    LUA_TTHREAD = 8
    LUA_NUMTAGS = 9

##元素数据结构体
class VarItemData(Structure):
    _fields_=[('varItemType',VariableType),                             #< 数据类型 c_int
              ('boolValue',c_bool),                                     #< bool类型数据值
              ('numberValue',c_double),                                 #< number类型数据值double
              ('stringValue',c_char*(CR6_INSTALL_VAR_MAX_LENGTH))       #< char类型字符串数据值
              ]

class VariableMsg(Structure):
    _fields_=[('variableName',c_char*CR6_ISTALL_VAR_NAME_LENGTH),  #< 变量名   char
              ('variableType',VariableType),  #< 数据类型  c_int
              ('variableID', c_int),  # 变量名称
              ('boolValue',c_bool),  #< bool类型数据值 BOOL
              ('numberValue',c_double),  #< number类型数据值 double
              ('stringValue',c_char*CR6_ISTALL_VAR_NAME_LENGTH),  #< char类型字符串数据值 char
              ('tableValueCount',c_int),  #< table类型元素个数  int
              ('tableValue',VarItemData*Script_MAX_TableElement),  #< table类型元素值  #这个没见过
              ('tableValueStr', c_char*CR6_INSTALL_VAE_TABLE_MAX_LENGTH) #<table值
              ]

class PopUpMsg(Structure):
    _fields_ = [('popupType',c_int),               #弹窗类型，0-输出弹窗，1-输入弹窗
                ('var_data',c_char*1024),          #弹窗显示的字符串，字符串类型
                ('var_title',c_char*128),          #弹窗标题，字符串类型
                ('iswarning',c_int),              #是否是警告信息，bool类型
                ('iserror',c_int),                #是否是报警信息，bool类型
                ('isblocking',c_int),             #是否暂停程序运行，bool类型
                ('inVarType',VariableType),        #输入弹窗时，变量类型
                ('inVarMinValue',c_double),        #输入弹窗时，变量数值范围最小值
                ('inVarMaxValue',c_double)]        #输入弹窗时，变量数值范围最大值

###消息来源
class CommMessageSource(c_int):
    Base = 0               #<基座关节
    Shoulder = 1           #<肩部关节
    Elbow = 2              #<肘部关节
    Wrist1 = 3             #<腕关节1（4号关节）
    Wrist2 = 4             #<腕关节2（5号关节）
    Wrist3 = 5             #<腕关节3（6号关节）
    Tool = 6               #<工具模块
    Controller = 100       #<主控制器
    SafetyProcessorB = 101 #<协处理器
    TeachPendant = 200      #<示教器

##警告等级
class WarningLevel(c_int):
    MESSAGE_WARNING_LEVEL_INFO = 1         #<正常消息
    MESSAGE_WARNING_LEVEL_WARNING = 2      #<警告不停机
    MESSAGE_WARNING_LEVEL_VIOLATION = 3    #<违反限制停机
    MESSAGE_WARNING_LEVEL_FAULT = 4        #<系统故障，紧急停止
    MESSAGE_WARNING_LEVEL_USER = 5         #<用户打印输出


class WorldTime(Structure):
    _fields_=[('year',c_uint),               #unsigned int
              ('month', c_uint),
              ('day', c_uint),
              ('week', c_uint),
              ('hour', c_uint),
              ('minute', c_uint),
              ('second', c_uint),
              ('milliSecond', c_uint), ]



class RobotLogMsg(Structure):
    _fields_ = [('robotMessageCode', c_uint),       #<消息代码 unsigned int
              ('robotMessageType', c_uint),      # <消息类型 unsigned int
              ('source', CommMessageSource),     # <消息来源 c_int
              ('textMessage', c_char * 100),     # <消息信息 char
              ('worldTime', WorldTime),          # <时间戳
              ('warningLevel', WarningLevel),    # <警告等级 c_int
              ('robotMode', RobotModes),         # <机器人状态
              ('timeStamp_us', c_ulonglong),     # <精确时间戳 unsigned long long
              ('messageIndex', c_ulonglong)]     # <消息序号 unsigned long long

class BaudRate(c_int):
    BaudRate300 = 0
    BaudRate600 = 1
    BaudRate1200 = 2
    BaudRate2400 = 3
    BaudRate4800 = 4
    BaudRate9600 = 5
    BaudRate19200 = 6
    BaudRate28800 = 7
    BaudRate38400 = 8
    BaudRate57600 = 9
    BaudRate115200 = 10
    BaudRate192000 = 11
    BaudRate256000 = 12
    BaudRate288000 = 13
    BaudRate384000 = 14
    BaudRate512000 = 15
    BaudRate576000 = 16
    BaudRate768000 = 17
    BaudRate1000000 = 18
    BaudRate1200000 = 19
    BaudRate1500000 = 20
    BaudRate2400000 = 21
    BaudRate3000000 = 22

class ParityCheck(c_int):
    no = 0    #无校验
    odd = 1   #奇校验
    even = 2  #偶校验

class SerialCommuType(c_int):
    FreeComm = 0  #自由格式
    Modbus_RTU = 1
    Modbus_ASCII = 2

class SerialType(c_int):
    rs485_tool_CommSettings = 0 #工具485
    rs485_1_CommSettings = 1	#485-1
    rs485_2_CommSettings = 2	 #485-2
    rs232_CommSettings=3      #rs232
    ethernet_CommSettings = 4     #以太网

class SerialCommSettings(Structure):
    _fields_ = [('baudRate', BaudRate),
               ('parity', ParityCheck),
               ('dataBits', c_int),
               ('stopBits', c_double),
               ('retryNumber', c_int),
               ('timeout', c_int),
               ('serialCommType', SerialCommuType),
               ('modbusSlaveNo', c_int)]


class SysVersion(Structure):
    _fields_ =[('sjqVersion', Version),
              ('kzqVersion', Version),
              ('jpmVersion', Version),
              ('saftyCtrlVersion', Version),
              ('jointVersion', Version * ROB_AXIS_NUM),
              ('etfVersion', Version)]




## 配置接口
class VarDigitialIOType(c_int):
    Invaild = 0
    Digitial = 1 # 标准数字量
    ConfigureableDigitial = 2  #可配置数字量
    ToolDigitial = 3 #工具数字量
    Analog = 4   #模拟量
class InstallAngle(Structure):
    _fields_ =[
        ('baseAngle',c_double),
        ('tiltAngle',c_double)
    ]
class InputAction(c_int):
    InputAction_NONE = 0
    InputAction_RobotON = 1
    InputAction_MovetoHome = 2
    InputAction_RunProgram = 3
    InputAction_SuspendedProgram = 4
    InputAction_StopProgram = 5
    InputAction_FreeDrive = 6
    InputAction_DownEnable = 7
    InputAction_ClearFault = 8

class OutputAction(c_int):
    OutputAction_NONE = 0
    OutputAction_RobotON_HIGH = 1
    OutputAction_RobotON_LOW = 2
    OutputAction_RobotPowerOn_HIGH = 3
    OutputAction_RobotPowerOn_LOW = 4
    OutputAction_PowerOn_HIGH = 5
    OutputAction_PowerOn_LOW = 6
    OutputAction_WarnErr_HIGH = 7
    OutputAction_WarnErr_LOW = 8
    OutputAction_ProgramStatus_Stop_HIGH = 10
    OutputAction_ProgramStatus_Stop_LOW = 11
    OutputAction_Fault_Stop_HIGH = 12
    OutputAction_Fault_Stop_LOW = 13
    OutputAction_ProgramStatus_Pause_HIGH = 14  # 程序暂停输出为高
    OutputAction_ProgramStatus_Pause_LOW = 15  # 程序暂停输出为低
    OutputAction_MotionStatus_Moving_HIGH = 20
    OutputAction_MotionStatus_Moving_LOW = 21
    OutputAction_MovetoHome_HIGH = 22 # 回初始位到位信号，到位时为高

class OutputRule(c_int):
    OutputRule_Disable = 0
    OutputRule_Enable = 1

class OutputOptions(c_int):
    OutputOptions_Enable = 0
    OutputOptions_Manual = 1
    OutputOptions_Disable = 2
class IOInputConfiguration(Structure):
    _fields_ = [
        ('inputFilteringTime',c_int),
        ('inputName',c_char * NAMELENTH),
        ('inputActions',InputAction)
    ]
class IOOutputConfiguration(Structure):
    _fields_ = [
        ('outputName',c_char * NAMELENTH),
        ('outputActions',OutputAction),
        ('outputOptions',OutputOptions),
        ('outputRule', OutputRule)
    ]
class AnalogType(c_int):
    Current = 0
    Voltage = 1

class AnalogInputConfiguration(Structure):
    _fields_ =[
        ('analogInputName',c_char *NAMELENTH),
        ('analogInputType',AnalogType)
    ]
class AnalogOutputConfiguration(Structure):
    _fields_ =[
        ('analogOutputName',c_char *NAMELENTH),
        ('analogOutputType',AnalogType)
    ]
class ToolPower(c_int):
    Power_invaild = 0  #无效值
    Power_on = 1  #24V
    Power_off = 2  #0V
class BitRegisterConfiguration(Structure):
    _fields_ =[
        ('GeneralPurposeBOOLeanRegisterName',c_char *NAMELENTH),
        ('GeneralPurposeBOOLeanRegisterInputActions',InputAction),
        ('GeneralPurposeBOOLeanRegisterOutputActions',OutputAction),
        ('GeneralPurposeBOOLeanRegisterOutputRule', OutputRule)
    ]

class PoseMessage(Structure):
    _fields_ =[
        ('toolPosition', c_double * ROB_AXIS_NUM),
        ('toolAxisAngle', c_double * ROB_AXIS_NUM)
    ]

class PointCSNode(Structure):
    _fields_ =[
        ('isValid',c_int),
        ('id',c_int),
        ('name',c_char *NAMELENTH),
        ('point',PoseMessage)
    ]


class LineCSNode(Structure):
    _fields_ =[
        ('isValid',c_int),
        ('id',c_int),
        ('name',c_char *NAMELENTH),
        ('firstPoint',PointCSNode),
        ('secondPoint',PointCSNode),
        ('coordinatePose',c_double *ROB_AXIS_NUM),
        ('coordinateJointPos',c_double *ROB_AXIS_NUM)
    ]


class PlaneCSNode(Structure):
    _fields_ = [
        ('isValid', c_int),
        ('id', c_int),
        ('name', c_char * NAMELENTH),
        ('firstPoint', PointCSNode),
        ('secondPoint', PointCSNode),
        ('thirdPoint', PointCSNode),
        ('coordinatePose', c_double * ROB_AXIS_NUM),
        ('coordinateJointPos', c_double * ROB_AXIS_NUM)
    ]

class SafetyLimitsValuesType(c_int):
    Userdefined = 0
    LimitLevel_1 = 1
    LimitLevel_2 =2
    LimitLevel_3 = 3
    LimitLevel_4 = 4

class SafetyCollisionHandleMode(c_int):
    Collision_EnterReboundMode = 0
    Collision_ProgramPause = 1
    Collision_ProgramStop = 2

class LimitsBoundaryPlaneMode(c_int):
    Disabled = 0  	#禁用
    Normal = 1	   	#正常
    Reduced = 2  	#缩减
    Both = 3		#二者都是
    Trigger = 4  	#触发器缩减模式

class SafetyLimitsMode(c_int):
    invaild = 0 	#禁用
    mode_Normal = 1	   #正常
    mode_Reduced = 2	#缩减

class SafetyLimitsValues(Structure):
    _fields_ =[
        ('maxTcpSpeed',c_double),
        ('maxForce',c_double),
        ('maxElbowSpeed',c_double),
        ('maxElbowForce',c_double),
        ('maxStoppingDistance',c_double),
        ('maxStoppingTime',c_double),
        ('maxPower',c_double),
        ('maxMomentum',c_double),
        ('maxTcpAcc',c_double),
        ('maxTcpJerk',c_double)
    ]


class SafetyLimitsJointAngle(Structure):
    _fields_ =[
        ('maxJointSpeed',c_double),
        ('minJointPosition',c_double),
        ('maxJointPosition',c_double)
    ]

class SafetyLimitsBoundaryPlane(Structure):
    _fields_ =[
        ('name',c_char *NAMELENTH),
        ('id',c_int),
        ('displacement',c_double),
        ('mode',LimitsBoundaryPlaneMode),
        ('planeNormal',c_double),
        ('distanceToOrigin',c_double),
        ('elbowRestricted',c_int),
        ('sourceGeomFeatureType',CoordinateType),
        ('sourceGeomFeatureId',c_int)
    ]


class SafetyIOInput(c_int):
    input_invaild = 0
    emergencyStop = 1 #紧急停机
    reducedMode =2 #缩减模式
    safeguardStop =3  #安全停止
    safeguardReset =6  #安全重置

class  SafetyIOOutput(c_int):
    output_invaild = 0
    systemEmergencyStop =1  #紧急停止输出
    robotMoving =2 #机器人运动
    robotNotStopping =3 #机器人未停止


class IPConfig(Structure):
    _fields_ =[
        ('ipAddr',c_int *4),
        ('subnetMask',c_int *4)
    ]

class ModbusMasterFunctionNo(c_int):
    ReadBool = 0
    WriteBool = 1
    ReadInt16 = 2
    WriteInt16 = 3
    ReadInt32 = 4
    WriteInt32 = 5
    ReadFloat = 6
    WriteFloat = 7
    ReadWriteBool = 8
    ReadWriteInt16 = 9
    ReadWriteInt32 = 10
    ReadWriteFloat = 11


class ModbusAddrMap(Structure):
    _fields_ = [
        ('functionNo',ModbusMasterFunctionNo),
        ('slaveStartAddr',c_int),
        ('masterOffsetNo',c_int),
        ('masterStartAddr',c_int),
        ('masterRegType',CommuVarType)
    ]


class ModbusMasterOperate(c_int):
    Start = 0
    Stop = 1

class  ModbusMasterConfig(Structure):
    _fields_ =[
        ('id',c_int),
        ('slaveNo',c_int),
        ('slaveIP',c_int *4),
        ('scanTime',c_int),
        ('modbusMasterOperate',ModbusMasterOperate),
        ('autoConnect',c_int)
    ]

class PathPoint(Structure):
    _fields_ = [
        ('pose',c_double * ROB_AXIS_NUM),     #坐标点向量
        ('jointpos', c_double * ROB_AXIS_NUM)    #关节角度
    ]

class PathPara(Structure):
    _fields_ = [
        ('index', c_int),                       #轨迹索引 上传时：-1~9，下载时：0~9
        ('moveType', c_int),                    #运动类型，0-透传，1-样条
    ]

class PathData(Structure):
    _fields_ = [
        ('pathPoints', POINTER(PathPoint)),     #轨迹序列数据
        ('pathPointsNum', c_int),               #轨迹数量
        ('moveTime', c_int),                    #运动时间  moveType为1时有效 20~100000ms
    ]

class PathDownloadData(Structure):
    _fields_ = [
        ('pathData', PathData),                       #轨迹数据
        ('pathPara', PathPara),                    #轨迹参数
    ]

class RecordPathPara(Structure):   #轨迹记录参数
    _fields_ = [
        ('sampleTime',c_int),     #采样时间  recordControl为1时有效
        ('recordControl', c_int)    #记录控制，0-停止，1-启动，2-暂停
    ]

class PathRecordStatus(Structure):   #轨迹记录状态
    _fields_ = [
        ('recordStatus',c_int),     #0-记录完成，1-记录中，2-暂停记录
        ('waypointNumber', c_int)    #已记录点数
    ]

class PathRunMsg(Structure):   #轨迹运行状态
    _fields_ = [
        ('pathrunstatus',c_int),     #0或10001-轨迹控制停止 1-轨迹运行中
        ('pointIndex', c_int)    #当前运行轨迹索引
    ]
    
#ethercat从站信息
class EtherCATSlaveData(Structure):
    _fields_ = [
        ('index',c_int),
        ('venderID',c_int),
        ('productCode',c_int),
        ('revisionNo',c_int)
    ]

#Esc状态
class EscState(c_int):
    ECT_STATE_INIT = 1
    ECT_STATE_PREOP = 2
    ECT_STATE_BOOT = 3
    ECT_STATE_SAFEOP = 4
    ECT_STATE_OP = 8

#Ect数据
class Ect_DataType(c_int):               #参考ETG1020
    Ect_BOOL = 1		#0x0001;
    Ect_SINT = 2		#0x0002;
    Ect_INT = 3		    #0x0003;
    Ect_DINT = 4		#0x0004;
    Ect_USINT = 5		#0x0005;
    Ect_UINT = 6		#0x0006;
    Ect_UDINT = 7		#0x0007;
    Ect_REAL = 8		#0x0008;
    Ect_LREAL = 17		#0x0011;
    Ect_LINT = 21	    #0x0015;
    Ect_ULINT = 27		#0x001B;
    Ect_BYTE = 30		#0x001E;
    Ect_WORD = 31		#0x001F;
    Ect_DWORD = 32		#0x0020;


#pdo类型
class Ect_PdoType(c_int):
    Ect_TxPdo = 1
    Ect_RxPdo = 2

#pdo
class PdoTypeData(Structure):
    _fields_ = [
        ('offAddress',c_int),
        ('pdoData', c_ubyte * 8),
        ('pdoDataLen', c_int),
        ('pdoDataType', Ect_DataType),
        ('pdoType', Ect_PdoType)
    ]

# ///
# typedef struct ForceSetting
# {
#     int forceBaseType;		///力控类型:  0-基于TCP力传感器,1-基于动力学,2-基于底座力传感器
#     int forceCtrlType;	    ///力控用法:  0-运动力控,1-力控拖动
#     int flexibleAxis[6];    ///力控轴
# }ForceSetting;

class ForceSetting(Structure):
    _fields_ = [
        ('forceBaseType',c_int),
        ('forceCtrlType', c_int),
        ('flexibleAxis', c_int*6)
    ]

# typedef struct ForceTCPMsg
# {
#     char forceTcpName[20];
#     double forceTcpOffset[ROB_AXIS_NUM];             ///<tcp偏移量
# }ForceTCPMsg;

class ForceTCPMsg(Structure):
    _fields_ = [
        ('forceTcpName',c_char * 20),
        ('forceTcpId', c_int),
        ('forceTcpOffset', c_double * ROB_AXIS_NUM)
    ]


# typedef struct ForcePayLoad
# {
#     char forcePayloadName[20];                 ///负载名称
#     double forceToolPayload;                   ///负载重量
#     double forceCenterOfGravity[3];            ///负载中心（CX，CY，CZ）
# }ForcePayLoad;

class ForcePayLoad(Structure):
    _fields_ = [
        ('forcePayloadName',c_char * 20),
        ('forcePayloadId', c_int),
        ('forceToolPayload', c_double),
        ('forceCenterOfGravity', c_double*3)
    ]


# typedef struct SensorMessage
# {
#      int venderNo;             ///力传感器厂家号：0-CGX,1-蓝点,2-鑫精诚
#      int productNo;            ///力传感器产品号
#      int sequenceNo;           ///力传感器通讯拓扑顺序号
# }SensorMessage;

class SensorMessage(Structure):
    _fields_ = [
        ('venderNo',c_int),
        ('productNo', c_int),
        ('sequenceNo', c_int)
    ]


# typedef struct CommuConfig
# {
#     int  autoConnect;	     					///自动连接
#     int  mannaulOperate;	     					///手动连接-关闭：0-1
#     int  paraBuf;                                 ///预留参数
# }CommuConfig;

class CommuConfig(Structure):
    _fields_ = [
        ('autoConnect',c_int),
        ('mannaulOperate', c_int),
        ('paraBuf', c_int)
    ]


# typedef struct  ForceToolSetting    ///力控传感器工具设置
# {
#     char activeForceTCP_name[20];				///激活的力控tcp名称
#     char activeForcePayload_name[20];	      ///激活的力控负载名称
#     ForceTCPMsg availableForceTCP[20];		///可以使用的力控TCP
#     int availableForceTCPLen;                ///可以使用的力控TCP数量
#     ForcePayLoad availableForcePayLoad[20];   ///可以使用的力控负载
#     int availableForcePayLoadLen;  ///可以使用的力控负载数量
# }ForceToolSetting;
class ForceToolSetting(Structure):
    _fields_ = [
        ('activeForceTCP_name',c_char * 20),
        ('activeForcePayload_name', c_char * 20),
        ('availableForceTCP', ForceTCPMsg * 20),
        ('availableForceTCPLen', c_int),
        ('availableForcePayLoad', ForcePayLoad*20),
        ('availableForcePayLoadLen', c_int)
    ]


# typedef struct ForceConfig
# {
#     SensorMessage sensorMessage;
#     ForceTcpSetting forceCtrlTcpImpl;
#     CommuConfig commuConfig;
# }ForceConfig;

class ForceConfig(Structure):
    _fields_ = [
        ('sensorMessage',SensorMessage),
        ('forceCtrlTcpImpl', ForceToolSetting),
        ('commuConfig', CommuConfig)
    ]

# typedef struct ForceCtlPara   ///力控控制参数
# {
#     double taskFrame[6];                             ///力控坐标系
#     double wrench[6];                                ///力给定
#
#     double limits[6];                               ///力控保护限制
#     int limitsLen;    ///0或6
#
#     double mass[6];                                  ///力控虚拟质量
#     int massLen; ///0、1或6
#
#     double damping[6];                               ///力控虚拟阻尼
#     int dampingLen; ///0、1或6
#
#     double stiffness[6];                             ///力控虚拟刚度
#     int stiffnessLen; ///0、1或6
# }ForceCtlPara;

class ForceCtlPara(Structure):
    _fields_ = [
        ('taskFrame',c_double * 6),
        ('wrench',c_double * 6),
        ('limits',c_double * 6),
        ('limitsLen', c_int),
        ('mass',c_double * 6),
        ('massLen', c_int),
        ('damping', c_double * 6),
        ('dampingLen', c_int),
        ('stiffness', c_double * 6),
        ('stiffnessLen', c_int)
    ]

# typedef struct ForceData   ///力控数据
# {
#     double ftRaw[6];                                 ///力传感器原始值
#     double ftCtrl[6];                                ///力传感器控制值
#     ControlModes controlMode;                        ///力控模式
# }ForceData;

class ForceData(Structure):
    _fields_ = [
        ('ftRaw',c_double * 6),
        ('ftCtrl',c_double * 6),
        ('controlMode',ControlModes)
    ]

class RobotStateData(Structure):
    _fields_ = [
        ('tcpActualPose', c_double * ROB_AXIS_NUM),         #实际tcp位置  double tcpActualPose[ROB_AXIS_NUM]
        ('jointActualPos', c_double * ROB_AXIS_NUM),        #实际关节位置  double jointActualPos[ROB_AXIS_NUM]
        ('robotMode', RobotModes),                          #机械臂当前状态
        ('robotMoveStatus', c_bool),                        #机械臂运动状态
        ('robotSpeedPercent', c_uint),                      #机械臂速度百分比
        ('configurableDigitalOutput', c_int * CR6_CO_NUM)  #控制器可配置数字输出  bool configurableDigitalOutput[CR6_CO_NUM]
    ]
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Runtime.InteropServices;

namespace CGXi_Sdk
{
    public enum CRresult
    {
        sucess = 0,             ///成功
        success = 0,            ///成功
        error = 1,              ///一般错误
        thread_running = 2,     ///通讯连接重复建立
        operate_timeout = 3,    ///操作超时，无返回值
        result_invalid = 4,     ///返回结果无效
        out_of_range = 5,       ///输入数值越界
        mutex_invalid = 6,      ///内部错误
        para_error = 7,         ///参数无效
        no_result = 8,          ///无对应数值
        no_assignTCPindex = 9,   ///未找到指定索引号TCP偏移量
        no_handle = 10,          ///未创建相关句柄
        handle_repeat = 11,          ///重复建立相同的句柄
        repeat_name = 12,        ///重命名
        delete_invalid = 13,     ///删除唯一的TCP或者负载
        set_bit_reg_invalid = 14,   ///同时设置位寄存器输入与输出
        repeat_id = 15,         ///id重复
        file_encryption = 16,   ///文件加密
        robotmode_error = 17,    ///<当前状态不能执行该操作
        move_error = 18,   /// 移动阻塞运动时,返回的移动状态错误
        forcectrl_wrongpara = 19,    ///力控SDK参数设置错误：包括参数长度错误、payload为负数
        forcectrl_invaildcmd = 20,   ///力控SDK无效的指令：包括forceEna等于1,0以外的值forcebasetype除0以外的值 forcectrltype除1,0以外  auto/mannual 1,0以外的值
        forcectrl_parablocked = 21,   ///力控SDK freedrive模式下部分参数失效被屏蔽
        forcectrl_cmdblocked = 22,   ///力控SDK 已在力控模式下时禁止再打开力控
        forcectrl_configblocked = 23,   ///力控SDK 机器人运动时或已在力控模式下时禁止下发配置
        forcectrl_notenable = 24,   ///力控SDK 机器人使能之前不能打开传感器
        forcectrl_wrongsensor = 25,  ///力控SDK 传感器型号选择错误
        outputrule_error = 26,  ///未设置系统输出,禁止启用自复位
        analoginputtype_error = 27   ///模拟量输入类型错误,注：工具端模拟量输入类型只有电压
    }
    public enum RtInterfaceCmd
    {
        noOperate,
        open,
        close,
        start,
        stop
    }
    public enum CommuVarType
    {
        CommuVarType_Bool,      ///bool类型
        CommuVarType_Int16,     ///16bit整数类型
        CommuVarType_Int32,     ///32bit整数类型
        CommuVarType_Float      ///32bit浮点类型
    }
    public enum CoordinateType
    {
        baseCoordinate = 0,     ///基坐标系
        jointCoordinate,        ///关节坐标系
        PointCoordinate,        ///点坐标系
        LineCoordinate,         ///线坐标系
        PlaneCoordinate,        ///面坐标系
        ToolBaseCoordinate,     ///工具坐标系
        visionCoordinate        ///视角坐标系
    }
    public enum PointTransType
    {
        pointTransStop,             ///过渡点停止
        pointTransConstantSpeed,    ///匀速过渡
        pointTransSmooth            ///柔顺过渡（不匀速，不停止
    }
    public enum PoseTranType
    {
        poseTranMoveToTargetPose,
        poseTranKeepStartPose
    }
    public enum MotiontriggerMode
    {
        MovetriggerbySafetySingnal, //<安全同步信号触发
        MovetriggerbyOnlyRpc,   //<指令直接触发
        MovetriggerbyMoveCache  //<移动指令会进入缓存区
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct TCPMsg
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public char[] tcpName;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpOffset;             ///tcp偏移量
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PayLoad
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public char[] payloadName;
        public double toolPayload;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 3)]
        public double[] centerOfGravity;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PointControlPara
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] pose;//<坐标点向量
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jointpos;//关节角度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpOffset; //<tcp偏移量
        public int tcpID; //<tcp的ID号,当tcpID为非负数时，使用tcpID对应的TCP偏移量作为输入；当tcpID为负数时，使用tcpoffset数据作为TCP偏移量输入；
        public CoordinateType coordinateType; //<坐标系类型
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinatePose;//<参考坐标系位姿
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] speed; //<速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] acc; //<加速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jerk; //<加加速度
        public PointTransType pointTransType; //<位置过渡方式
        public double pointTransRadius;//<过渡半径
        public PoseTranType poseTranType; //<姿态变换方式
        public MotiontriggerMode motiontriggerMode; //<运动轨迹触发方式
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PointControlParaSimple
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] pose;//<坐标点向量
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jointpos;//关节角度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpOffset; //<tcp偏移量
        public CoordinateType coordinateType; //<坐标系类型
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinatePose;//<参考坐标系位姿
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] speed; //<速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] acc; //<加速度
        public PointTransType pointTransType; //<位置过渡方式
        public MotiontriggerMode motiontriggerMode; //<运动轨迹触发方式
    }

    ///< 圆弧运动参数
    [StructLayout(LayoutKind.Sequential)]
    public struct PointControlParaList
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 2)]
        public PointControlPara[] pointcontrolpara;  ///<过渡点和终点
        public int fixedrot;  ///<方向模式 0-无约束 1-固定
        public double centralangle; ///<圆弧角
    }


    public enum MoveType
    {
        DecStop = 0,    ///当前运功减速停止
        ImdStop = 1,    ///当前运动立即停止
        Run = 2         ///运动
    }
    public enum JointModes
    {
        JOINT_MODE_POWER_OFF = 1,                   ///断电
        JOINT_MODE_BOOTING = 2,                     ///机械臂上电至空闲状态下
        JOINT_MODE_IDLE = 3,                        ///上电完成,空闲状态（ethercat——>op）
        JOINT_MODE_BACK_DRIVE = 4,                  ///反向驱动状态
        JOINT_MODE_RELEASE_BRAKE = 5,               ///机械臂使能，松抱闸过程中
        JOINT_MODE_CSP_STOP = 7,                    ///关节使能静止(位置模式)
        JOINT_MODE_CSP_MOVING = 8,                  ///关节使能运动(位置模式)
        JOINT_MODE_CST_STOP = 9,                    ///关节使能静止(转矩模式)
        JOINT_MODE_CST_MOVING = 10,                 ///关节使能运动(转矩模式)
        JOINT_MODE_FAULT = 11,                      ///错误状态
        JOINT_MODE_READY_FOR_POWER_OFF = 12         ///准备断电
    }

    public enum RequestState
    {
        EC_INT_REQUEST_INIT = 0,
        EC_INT_REQUEST_QUEUED = 1,
        EC_INT_REQUEST_BUSY = 2,
        EC_INT_REQUEST_SUCCESS = 3,
        EC_INT_REQUEST_FAILURE = 4
    }
    public enum RobotModes
    {
        ///初始化
        Closed = 0,
        Disconnect = 1,                       /// 断开连接状态
        ConfirmSafty = 2,                     /// 安全确认状态
        Booting = 3,                          /// 控制器正在启动
        ControlerIdle = 4,                    /// 控制器启动完成，空闲状态
        ControlerUpdataFirmWare = 5,          /// 固件更新
        JointPowerOff = 6,                    /// 控制器启动完成，本体未上电
        JointPowerOn = 7,                     /// 机器人上电过程
        JointIdle = 8,                        /// 机器人上电完成，空闲
        BackDrive = 9,                        /// 空闲状态下，按下示教按钮，会松开将仅释放在施加有显著压力的关节中的制动器。当使用反向驱动时，机器人感觉移动起来很沉重。    
        ReleaseBrake = 10,                    /// 机器人使能、松抱闸中
        Enable = 11,                          /// 机器人使能完成，并已完全松开抱闸
        CloseBrake = 12,                      /// 机器人断使能、关抱闸中
                                              ///运动
        Jog = 100,                            /// 点动
        Teach = 101,                          /// 拖动示教
        ForceControlTest = 102,               /// 力控测试
        ProgramStop = 103,                    /// 使能完成，程序停止
        ProgramPause = 104,                   /// 使能完成，程序暂停
        ProgramStopping = 105,                /// 使能完成，程序和运动正在停止
        ProgramPausing = 106,                /// 使能完成，程序和运动正在暂停
        ProgramRun_MotionStop = 107,          /// 程序运行，运动停止
        ProgramRun_MotionReducing = 108,      /// 程序运行，运动减速中
        ProgramRun_MotionMoving = 109,
        ProgramRun_MotionCanBlend = 110,      /// 程序运行，机器人进入到可交融区域
        Imdstop = 111,                        /// 紧急停止
        ProtectiveStop = 112                  /// 防护停止
    }

    public enum ControlModes
    {
        CONTROL_MODE_POSITION = 0,                  /// 控制器启动后的各种RobotModes
        CONTROL_MODE_TEACH = 1,                     /// ROBOT_MODE_RUNNING下，按下示教按钮或者执行teach_mode()，在此模式下手动使机器人来回移动
        CONTROL_MODE_FORCE = 2,                     /// 力控命令内
        CONTROL_MODE_TORQUE = 3                     /// 自由驱动模式
    }

    public enum SafetyModes
    {
        SAFETY_MODE_UNDEFINED_SAFETY_MODE = 1,
        SAFETY_MODE_VALIDATE_JOINT_ID = 2,      /// 验证关节的ID
        SAFETY_MODE_FAULT = 3,                  /// 安全错误，其他错误出现一段时间后，最终保持的错误状态
        SAFETY_MODE_VIOLATION = 4,              /// 在安全平面处越界
        SAFETY_MODE_ROBOT_EMERGENCY_STOP = 5,   /// 急停按钮按下
        SAFETY_MODE_SYSTEM_EMERGENCY_STOP = 6,  /// 可配置IO输入任意两路设置为紧急停机，断开后出现的错误状态
        SAFETY_MODE_SAFEGUARD_STOP = 7,         /// 安全IO断开
        SAFETY_MODE_RECOVERY = 8,               /// 在违反安全限制后，机器人停止，重启后，进入恢复模式
        SAFETY_MODE_PROTECTIVE_STOP = 9,        /// 保护性停止，运动过程中，外部强力推动机械手
        SAFETY_MODE_REDUCED = 10,               /// 限制模式
        SAFETY_MODE_NORMAL = 11                 /// 正常运行模式
    }

    public enum ToolModes
    {
        TOOL_MODE_POWER_OFF = 1,
        TOOL_MODE_BOOTING = 2,
        TOOL_MODE_IDLE = 3,
        TOOL_MODE_RUNNING = 4,
        TOOL_MODE_FAULT = 5
    }

    ///程序状态
    public enum ProgramState
    {
        PROGRAM_STATE_STOP = 0,     /// 程序停止
        PROGRAM_STATE_PAUSE,        /// 程序暂停
        PROGRAM_STATE_RUN           /// 程序运行
    }
    public struct Version
    {
        //[MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 50)]
        public string deviceType;
        //[MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]/// 机器人类型
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 50)]
        public string versionNo;    /// 版本信息
        public int bugfix;                     /// bug修正
        public long buildDate;
        // [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]/// 编译日期
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 50)]
        public string hardwareID;   /// 硬件id
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 50)]
        public string bootVersionNo;   /// 硬件id

    }

    ///机器人状态
    [StructLayout(LayoutKind.Sequential)]
    public struct RobotState_Data
    {
        public ulong timestamp;               /// 时间戳
        public ulong controllerTimer;     /// 自控制器启动以来的时间
        public int isRealRobotConnected;                  /// 是否连接实际机械臂
        public int isRealRobotEnabled;                    /// 是否机械臂使能
        public int isRobotPowerOn;                        /// 是否机械臂上电
        public int isEmergencyStopped;                    /// 是否紧急停止
        public int isProtectiveStopped;                   /// 是否保护停止
        public int isRobotMoving;                         /// 是否机械臂运动
        public ProgramState programState;                  /// 程序状态
        public RobotModes robotMode;                       /// 机械臂模式
        public int controlMode;                            /// 控制模式
        public SafetyModes safetyMode;                     /// 安全模式
        public int inReducedMode;                         /// 是否在限制模式
        public uint percentVelocity;               /// 速度百分比
        public double linearMomentumNorm;                  /// 直线动力值
        public double targetSpeedFractionLimit;            /// 目标速度分数限制
        public Version version;                            /// 版本信息
    }

    ///关节数据
    [StructLayout(LayoutKind.Sequential)]
    public struct Joint_Data
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualJointPositions;          /// 实际关节位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] targetJointPositions;          /// 目标关节位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualJointVelocitys;          /// 实际关节速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] targetJointVelocitys;          /// 目标关节速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualJointAccelerations;      /// 实际关节加速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] targetJointAccelerations;      /// 目标关节加速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jointRevolutionCounts;         /// 关节旋转圈数
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualJointCurrents;           /// 实际关节电机电流
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] targetJointCurrents;           /// 目标关节电机电流
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] targetJointMoments;            /// 目标关节扭矩
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualJointVoltages;           /// 实际关节采集的母线电压
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jointTemperature;              /// 关节温度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public JointModes[] jointMode;                 /// 关节模式
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public Version[] jointVersion;                 /// 版本信息
    }

    ///末端工具接口数据
    [StructLayout(LayoutKind.Sequential)]
    public struct Tool_Data
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 2)]
        public double[] toolAnalogInput;      /// 模拟量输入
        public double toolVoltage;                                     /// 工具输入电压
        public double toolCurrent;                                     /// 工具电流
        public double toolTemperature;                                 /// 工具温度
        public ToolModes toolMode;                                     /// 工具模式
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 2)]
        public int[] toolDigitalInput;              /// 工具数字输入
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 2)]
        public int[] toolDigitalOutput;            /// 工具数字输出
    }

    ///控制器IO板数据
    [StructLayout(LayoutKind.Sequential)]
    public struct Masterboard_Data
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]
        public int[] digitalInput;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]/// 数字输入
        public int[] digitalOutput;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]/// 数字输出
        public int[] configurableDigitalInput;     /// 可配置数字输入
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]
        public int[] configurableDigitalOutput;   /// 可配置数字输出
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 3)]
        public double[] analogInput;                       /// 模拟量输入
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 1)]
        public double[] analogOutput;                     /// 模拟量输出
        public double masterboardTemperature;                                  /// 主板温度
        public double safetyboardTemperature;                                  /// 安全板温度
        public double masterboardVoltage;                                      /// 主板电压
        public double robotVoltage;                                            /// 本体母线电压
        public double robotCurrent;                                            /// 本体电流
        public double masterIOCurrent;                                         /// IO口电流
        public int[] operationalModeSelectorInput;                              /// 操作模式选择输入限制模式
        public int threePositionEnablingDeviceInput;                           /// 三态模式按钮
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 2)]
        public long[] encoderTickCount;                   /// 编码器计数值
    }

    ///tcp数据
    [StructLayout(LayoutKind.Sequential)]
    public struct Cartesian_Data
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpVectorActual;       /// 实际tcp位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpVectorTarget;       /// 目标tcp位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpSpeedActual;        /// 实际tcp速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpSpeedTarget;        /// 目标tcp速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpAccelerometer;      /// 实际tcp加速度
        public int tcpIDValid;                             ///当前tcpid
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpoffsetValid;        ///当前tcp偏移量
    }

    ///力控制模式数据
    [StructLayout(LayoutKind.Sequential)]
    public struct ForceMode_Data
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcp_F_Vector;      /// tcp力矩反馈向量
        public double tcpForceScalar;                  /// tcp力度量程
        public double robotDexterity;                  /// 力控灵敏度
    }

    ///示教器数据
    ///
    [StructLayout(LayoutKind.Sequential)]
    public struct TeachPanel_Data
    {
        public int freeDriveButtonPressed;        /// 自由驱动按钮按住
        public int freeDriveButtonEnabled;        /// 自由驱动按钮使能
        public int powerButtonPressed;            /// 电源按钮按住
        public int IOEnabledFreedrive;            /// IO使能自由驱动
    }

    ///脚本程序状态
    public enum Lua_ScriptStatus
    {
        lua_Script_NoneOP = 0,      /// 空
        lua_Script_stop = 1,        /// 脚本程序停止
        lua_Script_pause = 2,       /// 脚本程序暂停
        lua_Script_run = 3,         /// 脚本程序运行
        lua_Script_load = 4         /// 脚本程序正在加载
    }

    ///脚本数据
    ///
    [StructLayout(LayoutKind.Sequential)]
    public struct Script_Data
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 51)]
        public uint[] currentLine;  /// 当前运行到第几行
        public Lua_ScriptStatus lua_ScriptStatus;          /// 脚本程序状态
    }

    public struct RtInterfaceData
    {
        public RobotState_Data robotState;
        public Joint_Data jointData;
        public Tool_Data toolData;
        public Masterboard_Data masterboardData;
        public Cartesian_Data cartesianData;
        public ForceMode_Data forceModeData;
        public TeachPanel_Data teachPanelData;
        public Script_Data scriptData;
    }

    public struct Mult_RtInterfaceData
    {
        public RtInterfaceData rtInterfaceData;
        public int validNum_rtInterfaceData;
    }


    public enum VariableType
    {
        LUA_TNIL = 0,
        LUA_TBOOLEAN = 1,
        LUA_TLIGHTUSERDATA = 2,
        LUA_TNUMBER = 3,
        LUA_TSTRING = 4,
        LUA_TTABLE = 5,
        LUA_TFUNCTION = 6,
        LUA_TUSERDATA = 7,
        LUA_TTHREAD = 8,
        LUA_NUMTAGS = 9
    }

    //元素数据结构体
    [StructLayout(LayoutKind.Sequential)]
    public struct VarItemData
    {
        public VariableType varItemType;                 /// 数据类型
        public int boolValue;                                /// bool类型数据值
        public double numberValue;                            /// number类型数据值
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 100)]
        public string stringValue;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct VariableMsg
    {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 100)]
        public string variableName;
        public VariableType variableType;                 /// 数据类型
        public int variableID;
        public int boolValue;                                  /// bool类型数据值
        public double numberValue;                              /// number类型数据值
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 100)]
        public string stringValue;
        public int tableValueCount;                             /// table类型元素个数
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 500)]
        public VarItemData[] tableValue; /// table类型元素值
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 10000)]
        public string tableValueStr;///table值
    }

    //消息来源
    public enum CommMessageSource
    {
        Base = 0,               ///基座关节
        Shoulder = 1,           ///肩部关节
        Elbow = 2,              ///肘部关节
        Wrist1 = 3,             ///腕关节1（4号关节）
        Wrist2 = 4,             ///腕关节2（5号关节）
        Wrist3 = 5,             ///腕关节3（6号关节）
        Tool = 6,               ///工具模块
        Controller = 100,       ///主控制器
        SafetyProcessorB = 101, ///协处理器
        TeachPendant = 200      ///示教器
    }

    //警告等级
    public enum WarningLevel
    {
        MESSAGE_WARNING_LEVEL_INFO = 1,         ///正常消息
        MESSAGE_WARNING_LEVEL_WARNING = 2,      ///警告不停机
        MESSAGE_WARNING_LEVEL_VIOLATION = 3,    ///违反限制停机
        MESSAGE_WARNING_LEVEL_FAULT = 4,        ///系统故障，紧急停止
        MESSAGE_WARNING_LEVEL_USER = 5          ///用户打印输出
    }
    public struct WorldTime
    {
        public uint year;
        public uint month;
        public uint day;
        public uint week;
        public uint hour;
        public uint minute;
        public uint second;
        public uint milliSecond;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct RobotLogMsg
    {
        public uint robotMessageCode;      ///消息代码
        public uint robotMessageType;      ///消息类型
        public CommMessageSource source;      ///消息来源
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 100)]
        public byte[] textMessage;              ///消息信息
        public WorldTime worldTime;                ///时间戳
        public WarningLevel warningLevel;     ///警告等级
        public RobotModes robotMode;               ///机器人状态
        public ulong timeStamp_us;    ///精确时间戳
        public ulong messageIndex;    ///消息序号
    }

    ///RS485/232的结构体内容
    ///波特率
    public enum BaudRate
    {
        BaudRate300 = 0,
        BaudRate600,
        BaudRate1200,
        BaudRate2400,
        BaudRate4800,
        BaudRate9600,
        BaudRate19200,
        BaudRate28800,
        BaudRate38400,
        BaudRate57600,
        BaudRate115200,
        BaudRate192000,
        BaudRate256000,
        BaudRate288000,
        BaudRate384000,
        BaudRate512000,
        BaudRate576000,
        BaudRate768000,
        BaudRate1000000,
        BaudRate1200000,
        BaudRate1500000,
        BaudRate2400000,
        BaudRate3000000
    }
    public enum ParityCheck
    {
        no = 0,   ///无校验
        odd,  ///奇校验
        even  ///偶校验
    }
    public enum SerialCommuType
    {
        FreeComm = 0, ///自由格式
        Modbus_RTU,  ///modbus
        Modbus_ASCII     ///modbus
    }
    ///串口数据
    public struct SerialCommuStruct
    {
        public BaudRate baudRate;
        public ParityCheck parity;
        public int dataBits;
        public double stopBits;
        public int retryNumber;
        public int timeout;  //毫秒
        public SerialCommuType serialCommType;
        public int modbusSlaveNo;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public struct SysVersion
    {
        public Version sjqVersion;
        public Version kzqVersion;
        public Version jpmVersion;
        public Version saftyCtrlVersion;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public Version[] jointVersion;
        public Version etfVersion;
    }


    public enum VarDigitialIOType   //IO选项卡输出操作管理
    {
        Invaild = 0,
        Digitial = 1,               //标准数字量
        ConfigureableDigitial = 2,  //可配置数字量
        ToolDigitial = 3,           //工具数字量
        Analog = 4, // 模拟量
        ToolAnalog = 5     //工具模拟量
    }

    public struct InstallAngle
    {
        public double baseAngle;   //基座旋转角度
        public double tiltAngle;   //基座倾斜角
    }

    //本体上电使能、回初始点、运行程序、暂停程序、停止程序
    public enum InputAction
    {
        InputAction_NONE = 0,
        InputAction_RobotON = 1,
        InputAction_MovetoHome = 2,
        InputAction_RunProgram = 3,
        InputAction_SuspendedProgram = 4,
        InputAction_StopProgram = 5,
        InputAction_FreeDrive = 6,
        InputAction_DownEnable = 7,
        InputAction_ClearFault = 8
    }


    //系统功能输出：使能完成、到达初始点、程序运行状态、运动状态
    public enum OutputAction
    {
        OutputAction_NONE = 0,
        OutputAction_RobotON_HIGH = 1,
        OutputAction_RobotON_LOW = 2,
        OutputAction_RobotPowerOn_HIGH = 3,           
        OutputAction_RobotPowerOn_LOW = 4,           
        OutputAction_PowerOn_HIGH = 5,               
        OutputAction_PowerOn_LOW = 6,                
        OutputAction_WarnErr_HIGH = 7,                
        OutputAction_WarnErr_LOW = 8,                
        OutputAction_ProgramStatus_Stop_HIGH = 10,
        OutputAction_ProgramStatus_Stop_LOW = 11,
        OutputAction_Fault_Stop_HIGH = 12,
        OutputAction_Fault_Stop_LOW = 13,
        OutputAction_ProgramStatus_Pause_HIGH = 14,   //程序暂停输出为高
        OutputAction_ProgramStatus_Pause_LOW = 15,    //程序暂停输出为低
        OutputAction_MotionStatus_Moving_HIGH = 20,
        OutputAction_MotionStatus_Moving_LOW = 21,
        OutputAction_MovetoHome_HIGH = 22           //回初始位到位信号，到位时为高
    }

    public enum OutputOptions   //IO选项卡输出操作管理
    {
        OutputOptions_Enable = 0,
        OutputOptions_Manual = 1,
        OutputOptions_Disable = 2
    }

    public enum OutputRule   //输出信号状态（自动复位）
    {
        OutputRule_Disable = 0,         //禁用
        OutputRule_Enable = 1           //启用
    }

    public struct IOInputConfiguration
    {
        public int inputFilteringTime;    //输入信号滤波时间
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] inputName;          //输入信号名称
        public InputAction inputActions;   //输入信号操作
    }


    public struct IOOutputConfiguration
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] outputName;             //输出信号名称
        public OutputAction outputActions;     //输出信号条件
        public OutputOptions outputOptions;    //输出信号操作控制选项
        public OutputRule outputRule;          //输出信号状态（自动复位）
    }

    public enum ToolIoType   //输出信号状态（自动复位）
    {
        IO_OUTPUT = 0,         //输出
        IO_INPUT = 1           //输入
    }

    public enum AnalogType
    {
        Current = 0,
        Voltage = 1
    }


    public struct AnalogInputConfiguration
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] analogInputName;    //模拟量输入通道名称
        public AnalogType analogInputType; //模拟量输入类型
    }

    public struct AnalogOutputConfiguration
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] analogOutputName;    //模拟量输出通道名称
        public AnalogType analogOutputType; //模拟量输出类型
    }


    public enum ToolPower
    {
        Power_invaild, //无效值
        Power_on,      //24V
        Power_off,     //0V
    }

    public struct EncoderConfiguration
    {
        public int eqepType;       ///< 类型
        public int eqepCountMode;      ///< 模式
        public int strobeInputMode;    ///< 探针
        public int eqepEnabled;        ///< 控制
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct BitRegisterConfiguration
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] GeneralPurposeBOOLeanRegisterName;      //BOOL型寄存器名称
        public InputAction GeneralPurposeBOOLeanRegisterInputActions;   //BOOL型寄存器置位操作
        public OutputAction GeneralPurposeBOOLeanRegisterOutputActions;//BOOL型寄存器置位的条件
        public OutputRule GeneralPurposeBOOLeanRegisterOutputRule; //BOOL型寄存器自复位
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct RegisterConfiguration
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] GeneralPurposeRegisterName;      //寄存器名称
    }

    public struct PoseMessage
    {
        //double jointPositionVector[ROB_AXIS_NUM];
        //double tcpOffset[ROB_AXIS_NUM];
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] toolPosition;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] toolAxisAngle;
    }

    public struct PointCSNode
    {
        //BOOL showAxes;
        //BOOL joggable;
        public int isValid;
        public int id;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] name;
        public PoseMessage point;
    }
    //点坐标系

    public struct LineCSNode
    {
        //BOOL showAxes;
        //BOOL joggable;
        public int isValid;
        public int id;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] name;
        public PointCSNode firstPoint;
        public PointCSNode secondPoint;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinatePose;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinateJointPos;
    }
    //线坐标系

    public struct PlaneCSNode
    {
        //BOOL showAxes;
        //BOOL joggable;
        public int isValid;
        public int id;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] name;
        public PointCSNode firstPoint;
        public PointCSNode secondPoint;
        public PointCSNode thirdPoint;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinatePose;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinateJointPos;
    }
    //面坐标系

    public enum SafetyLimitsValuesType
    {
        Userdefined = 0,
        LimitLevel_1 = 1,
        LimitLevel_2 = 2,
        LimitLevel_3 = 3,
        LimitLevel_4 = 4
    }

    public enum SafetyCollisionHandleMode //碰撞后处理模式
    {
        Collision_EnterReboundMode = 0,     //进入反弹模式
        Collision_ProgramPause = 1,         //暂停
        Collision_ProgramStop = 2           //停止
    }


    public struct SafetyLimitsValues
    {
        public double maxTcpSpeed;     //tcp最高速度
        public double maxForce;            //tcp最大力
        public double maxElbowSpeed;       //肘部最高速度
        public double maxElbowForce;       //肘部最大力
        public double maxStoppingDistance;//最大停止距离
        public double maxStoppingTime; //最大停止时间
        public double maxPower;            //最高功率
        public double maxMomentum;     //最大动量
        public double maxTcpAcc;       //tcp最高加速度
        public double maxTcpJerk;      //tcp最高加加速度
    }



    public struct SafetyLimitsBoundaryPlane
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public char[] name;
        public int id;             //id号
        public double displacement;
        public LimitsBoundaryPlaneMode mode;
        public double planeNormal;
        public double distanceToOrigin;
        public int elbowRestricted;
        public CoordinateType sourceGeomFeatureType; //关联的坐标系类型
        public int sourceGeomFeatureId;            //关联的坐标系ID
    }

    public enum LimitsBoundaryPlaneMode
    {
        Disabled = 0,   //禁用
        Normal = 1,     //正常
        Reduced = 2,    //缩减
        Both = 3,       //二者都是
        Trigger = 4     //触发器缩减模式
    }

    public enum SafetyIOInput
    {
        input_invaild = 0,
        emergencyStop = 1, //紧急停机
        reducedMode = 2, //缩减模式
        safeguardStop = 3,//安全停止
        safeguardReset = 6  //安全重置
    }

    public enum SafetyIOOutput
    {
        output_invaild = 0,
        systemEmergencyStop = 1,  //紧急停止输出
        robotMoving = 2, //机器人运动
        robotNotStopping = 3 //机器人未停止
    }

    public struct IPConfig
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]
        public int[] ipAddr;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]
        public int[] subnetMask;
    }

    public enum SerialType
    {
        rs485_tool_CommSettings = 0, //工具485
        rs485_1_CommSettings = 1,    //485-1
        rs485_2_CommSettings = 2,    //485-2
        rs232_CommSettings = 3,       //rs232
        ethernet_CommSettings = 4	//<以太网
    }

    public struct SerialCommSettings
    {
        public BaudRate baudRate;
        public ParityCheck parity;
        public int dataBits;
        public double stopBits;
        public int retryNumber;
        public int timeout;  //毫秒
        public SerialCommuType serialCommType;
        public int modbusSlaveNo;
    }

    public enum SafetyLimitsMode
    {
        invaild = 0,    //禁用
        mode_Normal = 1,        //正常
        mode_Reduced = 2    //缩减
    }

    public struct SafetyLimitsJointAngle
    {
        public double maxJointSpeed;       //最大角速度
        public double minJointPosition;    //最小位置
        public double maxJointPosition;    //最大位置
    }

    public struct ModbusAddrMap
    {
        public ModbusMasterFunctionNo functionNo;
        public int slaveStartAddr;
        public int masterOffsetNo;
        public int masterStartAddr;
        public CommuVarType masterRegType;         //寄存器类型
    }

    public struct ModbusMasterConfig
    {
        public int id;
        public int slaveNo;        //从站站号
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]
        public int[] slaveIP;     //modbus-tcp时，从站ip
        public int scanTime;       //扫描周期

        public ModbusMasterOperate modbusMasterOperate;
        public int autoConnect;    //自动连接
    }

    public enum ModbusMasterFunctionNo
    {
        ReadBool = 0,
        WriteBool = 1,
        ReadInt16 = 2,
        WriteInt16 = 3,
        ReadInt32 = 4,
        WriteInt32 = 5,
        ReadFloat = 6,
        WriteFloat = 7,

        ReadWriteBool = 8,
        ReadWriteInt16 = 9,
        ReadWriteInt32 = 10,
        ReadWriteFloat = 11
    }


    public enum ModbusMasterOperate
    {
        Start = 0,
        Stop = 1
    }

    public struct PopUpMsg
    {
        public int popupType;              ///弹窗类型，0-输出弹窗，1-输入弹窗
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 1024)]
        public byte[] var_data;        ///弹窗显示的字符串，字符串类型
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 128)]
        public byte[] var_title;        ///弹窗标题，字符串类型
        public int iswarning;             ///是否是警告信息，bool类型
        public int iserror;               ///是否是报警信息，bool类型
        public int isblocking;            ///是否暂停程序运行，bool类型
        public VariableType inVarType; 	///输入弹窗时，变量类型
        public double inVarMinValue;       ///输入弹窗时，变量数值范围最小值
        public double inVarMaxValue;       ///输入弹窗时，变量数值范围最大值
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PathPoint
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] pose;                  /// 坐标点向量
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jointpos;              /// 关节角度
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PathPara
    {
        public int index;          /// 轨迹索引 上传时：-1~9，下载时：0~9
        public int moveType;       /// 运动类型，0-透传，1-样条，3-movex
        public double speed;       /// 速度  moveType为3时有效
        public double acc;         /// 加速度 moveType为3时有效
        public double blendRadius; /// 过渡半径 moveType为3时有效
    }

    public struct PathData     ///<轨迹数据
    {
        public IntPtr pathPoints;  ///<轨迹序列数据
        public int pathPointsNum;      ///<轨迹数量
        public int moveTime;           ///<运动时间  moveType为1时有效 20~10000ms
    }

    public struct PathDownloadData  ///<下载轨迹数据
    {
        public PathData pathData;     ///< 轨迹数据
        public PathPara pathPara;     ///<轨迹参数
    }

    public struct RecordPathPara
    {
        public int sampleTime;  ///采样时间  recordControl为1时有效
        public int recordControl;   ///记录控制，0-停止，1-启动，2-暂停
    }

    public struct PathRecordStatus
    {
        public int recordStatus;    ///0-记录完成，1-记录中，2-暂停记录
        public int waypointNumber;  ///已记录点数
    }

    public struct PathRunMsg
    {
        public int pathrunstatus;   ///0或10001-轨迹控制停止 1-轨迹运行中
        public int pointIndex;  ///当前运行轨迹索引
    }

    public struct PdoTypeData
    {
        public int offAddress;  //映射地址
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]
        public byte[] pdoData; //读出的数据
        public int pdoDataLen;   //读出的数据字节长度
        public Ect_DataType pdoDataType; //数据类型
        public Ect_PdoType pdoType; //pdo类型
    }

    ///
    public struct ForceSetting  ///力控设置
    {
        public int forceBaseType;      ///力控类型:  0-基于TCP力传感器,1-基于动力学,2-基于底座力传感器
        public int forceCtrlType;      ///力控用法:  0-运动力控,1-力控拖动
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public int[] flexibleAxis;    ///力控轴
    }

    public struct ForceTCPMsg ///力控传感器tcp
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public byte[] forceTcpName;   ///力控传感器tcp的名称
        public int forceTcpId;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] forceTcpOffset;             ///力控传感器tcp偏移量
    }

    public struct ForcePayLoad  ///力控传感器负载
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public byte[] forcePayloadName;                 ///力控传感器负载名称
        public int forcePayloadId;
        public double forceToolPayload;                   ///力控传感器负载重量
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 3)]
        public double[] forceCenterOfGravity;            ///负载中心（CX，CY，CZ）
    }
    public struct SensorMessage ///力控传感器信息
    {
        public int venderNo;             ///力传感器厂家号：0-CGX,1-蓝点,2-鑫精诚
        public int productNo;            ///力传感器产品号
        public int sequenceNo;           ///力传感器通讯拓扑顺序号
    }
    public struct CommuConfig  ///通讯配置
    {
        public int autoConnect;                            ///自动连接
        public int mannaulOperate;                         ///手动连接-关闭：0-1
        public int paraBuf;                                 ///预留参数
    }
    public struct ForceToolSetting    ///力控传感器工具设置
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public byte[] activeForceTCP_name;               ///激活的力控tcp名称

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public byte[] activeForcePayload_name;         ///激活的力控负载名称

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public ForceTCPMsg[] availableForceTCP;      ///可以使用的力控TCP
        public int availableForceTCPLen;                ///可以使用的力控TCP数量

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 20)]
        public ForcePayLoad[] availableForcePayLoad;   ///可以使用的力控负载
        public int availableForcePayLoadLen;  ///可以使用的力控负载数量
    }

    public struct ForceConfig  ///力控配置
    {
        public SensorMessage sensorMessage;  ///传感器信息
        public ForceToolSetting forceCtrlTcpImpl; ///力控工具设置
        public CommuConfig commuConfig;  ///力控通讯配置
    }

    public struct ForceCtlPara   ///力控控制参数
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] taskFrame;                             ///力控坐标系
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] wrench;                                ///力给定

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] limits;                               ///力控保护限制
        public int limitsLen;    ///力控保护限制长度0或6

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] mass;                                  ///力控虚拟质量
        public int massLen; ///力控虚拟质量长度 0、1或6

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] damping;                               ///<力控虚拟阻尼
        public int dampingLen; ///力控虚拟阻尼长度 0、1或6

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] stiffness;                             ///力控虚拟刚度
        public int stiffnessLen; ///力控虚拟刚度长度 0、1或6
    }

    public struct ForceData   ///力控数据
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] ftRaw;                                 ///力传感器原始值
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] ftCtrl;                                ///力传感器控制值
        public ControlModes controlMode;                        ///力控模式
    }
	
	///ethercat从站信息
	public struct EtherCATSlaveData
    {
        public int index;                       
        public int venderID;                  
        public int productCode;                       
        public int revisionNo; 
    }

    public enum EscState
    {
        ECT_STATE_INIT = 1,
        ECT_STATE_PREOP = 2,
        ECT_STATE_BOOT = 3,
        ECT_STATE_SAFEOP = 4,
        ECT_STATE_OP = 8
    }
    public enum Ect_DataType  //参考ETG1020
    {
        Ect_BOOL = 1,       //0x0001;
        Ect_SINT = 2,       //0x0002;
        Ect_INT = 3,        //0x0003;
        Ect_DINT = 4,       //0x0004;
        Ect_USINT = 5,      //0x0005;
        Ect_UINT = 6,       //0x0006;
        Ect_UDINT = 7,      //0x0007;
        Ect_REAL = 8,       //0x0008;
        Ect_LREAL = 17,     //0x0011;
        Ect_LINT = 21,      //0x0015;
        Ect_ULINT = 27,     //0x001B;
        Ect_BYTE = 30,      //0x001E;
        Ect_WORD = 31,      //0x001F;
        Ect_DWORD = 32      //0x0020;
    }

    ///pdo类型
    public enum Ect_PdoType
    {
        Ect_TxPdo = 1,
        Ect_RxPdo = 2
    }

    public struct RobotStateData
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpActualPose;                          /// 实际tcp位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] jointActualPos;                         /// 实际关节位置
        public RobotModes robotMode;                            /// 机械臂当前状态
        public int robotMoveStatus;                             /// 机械臂运动状态
        public int robotSpeedPercent;                           /// 机械臂速度百分比
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)]
        public int[] configurableDigitalOutput;              /// 控制器可配置数字输出
    }

    //扩展轴数据
    public struct RobotExjData
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public double[] actualExjointPos;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualJointPos;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] actualTcpVector;
    }

    public struct MoveExjPara
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 12)]
        public double[] pose;                           ///< 前六个代表关节姿态（x,y,z（单位：mm）;Rx,Ry,Rz（单位：°）），后六个代表扩展轴位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 12)]
        public double[] jointPos;                       ///< 前六个代表关节1~6关节角度，后六个代表扩展轴位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 12)]
        public double[] speed;                          ///< 前六个代表机械臂速度，当坐标系类型为关节坐标系时，分别代表一到六关节的速度 °/s，其他时候代表tcp速度 mm/s，第七个代表扩展轴直线速度 mm/s，第八个代表扩展轴旋转速度 °/s
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 12)]
        public double[] acc;                            ///< 前六个代表关节加速度，后六个无效
                                                        ///< acc可以是tcp加速度或者是关节加速度,当coordinateType设置为jointCoordinate时，该速度为关节加速度，其它情况是tcp加速度
                                                        ///< 作为tcp加速度时，单位为：mm/s²; 作为关节加速度时，单位为：°/s²
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] tcpOffset;                      ///< tcp偏移量:x,y,z（单位：mm）;Rx,Ry,Rz（单位：°）
        public int tcpId;                               ///< tcp的ID号
        public CoordinateType coordinateType;           ///< 坐标系类型
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] coordinatePose;                 ///< 参考坐标系位姿:x,y,z（单位：mm）;Rx,Ry,Rz（单位：°）
        public double pointTransRadius;                 ///< 过渡半径
        public MotiontriggerMode motiontriggerMode;     ///< 运动轨迹触发方式
    }

    //扩展轴点动运动参数
    public struct MoveJogExjPara
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public double[] jointPos;          ///< 扩展轴位置
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public double[] speed;             ///< 扩展轴速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public double[] acc;               ///< 扩展轴加速度
    }
    

    //扩展轴运动参数
    public struct ExjMovePara
    {
        public int exjCount;                             ///< 扩展轴数量
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public int[] index;                             ///< 扩展轴索引
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public double[] speed;                          ///< 扩展轴速度
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 10)]
        public double[] position;                       ///< 扩展轴位置
        public double acctime;                          ///< 扩展轴加速时间
        public MotiontriggerMode motiontriggerMode;     ///< 运动轨迹触发方式
    }

    //扩展轴类型
    public enum ExternalJointType
    {
        line_externalJoint = 0,  //直线
        rotation_externalJoint = 1 //旋转
    }

    //扩展轴配置
    public struct ExjConfig
    {
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public byte[] name;                             ///< 扩展轴名称
        public ExternalJointType type;                  ///< 扩展轴类型
        public double ratio;                            ///< 传动比
        public double minlimit;                         ///< 最小值
        public double maxlimit;                         ///< 最大值
        public long zeroPosition;                       ///< 零位(pulse)
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
        public double[] exjToRef;                       ///< 扩展轴相对于参考系的关系
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 50)]
        public byte[] masterExjName;                    ///< 主轴名称
        public double masterSlaveRate;                  ///< 主从比
    }

    public enum CoPdoType
    {
        CO_TX_PDO = 1,
        CO_RX_PDO = 2
    };

    public enum CoDataType
    {
        EDS_DT_BOOL = 1,   //0x0001;
        EDS_DT_S8 = 2,     //0x0002;
        EDS_DT_S16 = 3,    //0x0003;
        EDS_DT_S32 = 4,    //0x0004;
        EDS_DT_U8 = 5,     //0x0005;
        EDS_DT_U16 = 6,    //0x0006;
        EDS_DT_U32 = 7,    //0x0007;
        EDS_DT_FLOAT = 8,  //0x0008;
        EDS_DT_STRING = 9, //0x0009;  一个字符占8位
        EDS_DT_OCTET_STRING = 0xA,   //0x000A; 一个字符占8位
        EDS_DT_UNICODE_STRING = 0xB, //0x000B; 一个字符占16位
        EDS_DT_DOMAIN = 0xF,  //0x000F
        EDS_DT_DOUBLE = 0x11, //0x0011
        EDS_DT_INT64 = 0x15,  //0x0015
        EDS_DT_UINT64 = 0x1B  //0x001B
    };
}

"""
PGEA系列驱控一体式工业平行电爪 - 常量定义

适用型号:
- PGEA-15-26 (15N, 26mm)
- PGEA-15-40 (15N, 40mm)
- PGEA-50-26 (50N, 26mm)
- PGEA-50-40 (50N, 40mm)
- PGEA-100-26 (100N, 26mm)
- PGEA-100-40 (100N, 40mm)

通信协议: Modbus-RTU over RS485
默认配置: 波特率115200, 数据位8, 停止位1, 无校验
"""

# ==================== 默认通信配置 ====================
DEFAULT_BAUDRATE = 115200
DEFAULT_SLAVE_ID = 1
DEFAULT_DATA_BITS = 8
DEFAULT_STOP_BITS = 1
DEFAULT_PARITY = 'N'  # N:无校验, O:奇校验, E:偶校验

# ==================== Modbus功能码 ====================
FUNCTION_CODE_READ_HOLDING = 0x03      # 读取保持寄存器
FUNCTION_CODE_READ_INPUT = 0x04        # 读取输入寄存器
FUNCTION_CODE_WRITE_SINGLE = 0x06      # 写入单个寄存器
FUNCTION_CODE_WRITE_MULTIPLE = 0x10    # 写入多个寄存器

# ==================== 基础控制寄存器地址 ====================
# 控制类寄存器 (0x0100 - 0x01FF)
REG_INIT_GRIPPER = 0x0100              # 初始化夹爪
REG_FORCE = 0x0101                     # 力值设置 (20-100%)
REG_POSITION = 0x0103                  # 位置设置 (0-1000‰)
REG_SPEED = 0x0104                     # 速度设置 (1-100%)
REG_JOG = 0x010A                       # 点动控制 (-1:反向, 0:停止, 1:正向)

# 反馈类寄存器 (0x0200 - 0x02FF)
REG_INIT_STATUS = 0x0200               # 初始化状态反馈
REG_GRIP_STATUS = 0x0201               # 夹持状态反馈
REG_POSITION_FEEDBACK = 0x0202         # 位置反馈
REG_SPEED_FEEDBACK = 0x0203            # 速度反馈
REG_CURRENT_FEEDBACK = 0x0204          # 电流反馈
REG_ERROR_FEEDBACK = 0x0205            # 错误码反馈
REG_RESET_STATUS = 0x0206              # 复位状态反馈
REG_MOTOR_TEMP = 0x020F                # 电机温度反馈

# ==================== 参数配置寄存器地址 ====================
# 用户参数配置 (0x0300 - 0x03FF)
REG_SAVE_FLASH = 0x0300                # 写入保存到Flash
REG_INIT_DIRECTION = 0x0301            # 初始化方向
REG_DEVICE_ID = 0x0302                 # 设备ID (1-247)
REG_BAUDRATE = 0x0303                  # 波特率配置
REG_STOP_BITS = 0x0304                 # 停止位配置
REG_PARITY = 0x0305                    # 校验位配置

# ==================== IO控制寄存器地址 ====================
# IO配置 (0x0400 - 0x04FF)
REG_IO_TEST = 0x0400                   # IO参数测试 (1-4组)
REG_IO_PIN_CONFIG = 0x0401             # IO引脚配置
REG_IO_MODE_SWITCH = 0x0402            # IO模式开关 (0:关闭, 1:开启)
REG_IO_INPUT_LEVEL = 0x0403            # IO输入高低电平选择
REG_IO_OUTPUT_LEVEL = 0x0404           # IO输出高低电平选择
# 4组IO参数配置 (位置, 力值, 速度)
REG_IO_GROUP1_POS = 0x0405             # 第1组位置
REG_IO_GROUP1_FORCE = 0x0406           # 第1组力值
REG_IO_GROUP1_SPEED = 0x0407           # 第1组速度
REG_IO_GROUP2_POS = 0x0408             # 第2组位置
REG_IO_GROUP2_FORCE = 0x0409           # 第2组力值
REG_IO_GROUP2_SPEED = 0x040A           # 第2组速度
REG_IO_GROUP3_POS = 0x040B             # 第3组位置
REG_IO_GROUP3_FORCE = 0x040C           # 第3组力值
REG_IO_GROUP3_SPEED = 0x040D           # 第3组速度
REG_IO_GROUP4_POS = 0x040E             # 第4组位置
REG_IO_GROUP4_FORCE = 0x040F           # 第4组力值
REG_IO_GROUP4_SPEED = 0x0410           # 第4组速度
REG_IO_INPUT_FILTER = 0x0411           # IO输入滤波 (ms)
REG_IO_INPUT_STATE = 0x0412            # IO输入状态反馈
REG_IO_OUTPUT_STATE = 0x0413           # IO输出状态反馈

# ==================== 特殊功能寄存器地址 ====================
# 特殊功能 (0x0500 - 0x05FF)
REG_DIRECTION_SWITCH = 0x0500          # 方向切换
REG_UNIT_SWITCH = 0x0501               # 单位切换 (0:千分比, 1:0.01mm)
REG_MOTOR_BRAKE = 0x0502               # 停转/刹车
REG_CLEAR_ERROR = 0x0503               # 清除错误
REG_AUTO_INIT = 0x0504                 # 上电自动初始化
REG_STROKE_CHECK = 0x0505              # 行程校验阈值
REG_BRAKE_CONTROL = 0x0506             # 抱闸释放控制
REG_SYSTEM_RESTART = 0x050E            # 系统重启
REG_SYSTEM_ENABLE = 0x050F             # 系统使能/失能
REG_INIT_CLOSE_GAP = 0x0510            # 初始化闭合间隙
REG_INIT_OPEN_GAP = 0x0511             # 初始化张开间隙
REG_SET_INIT_POS = 0x0512              # 设置初始位置
REG_INIT_POS_ENABLE = 0x0513           # 初始位置功能开关

# ==================== 电气信息寄存器地址 ====================
# 电气信息 (0x0600 - 0x06FF)
REG_BUS_VOLTAGE = 0x0600               # 母线电压
REG_BUS_VOLTAGE_COMP = 0x0601          # 母线电压补偿

# ==================== 历史错误码寄存器地址 ====================
# 历史错误信息 (0x1700 - 0x17FF)
REG_HISTORY_ERROR_1 = 0x1700           # 历史错误码1
REG_HISTORY_ERROR_1_TIME_L = 0x1701    # 错误码1发生时刻低位
REG_HISTORY_ERROR_1_TIME_H = 0x1702    # 错误码1发生时刻高位
REG_HISTORY_ERROR_START = 0x1700       # 历史错误码起始地址
REG_HISTORY_ERROR_END = 0x172F         # 历史错误码结束地址
REG_CLEAR_HISTORY_ERROR = 0x1730       # 清除历史错误码

# ==================== 初始化命令值 ====================
INIT_COMMAND_NORMAL = 0x01             # 正常初始化(单向回零)
INIT_COMMAND_FULL = 0xA5               # 完全初始化(重新标定行程)

# ==================== 初始化状态值 ====================
INIT_STATUS_NOT_INIT = 0               # 未初始化
INIT_STATUS_SUCCESS = 1                # 初始化成功
INIT_STATUS_IN_PROGRESS = 2            # 初始化中
INIT_STATUS_STROKE_ERROR = 0xFFFF      # 行程标定异常

# ==================== 夹持状态值 ====================
GRIP_STATUS_MOVING = 0                 # 运动中
GRIP_STATUS_IN_POSITION = 1            # 到达位置(未夹到物体)
GRIP_STATUS_GRIPPED = 2                # 夹住物体
GRIP_STATUS_DROPPED = 3                # 物体掉落
GRIP_STATUS_NOT_INIT = 0xFFFF          # 初始化未完成

# ==================== IO输入状态值 ====================
IO_INPUT_NONE = 0                      # Input1无信号, Input2无信号
IO_INPUT_1_ON = 1                      # Input1有信号, Input2无信号
IO_INPUT_2_ON = 2                      # Input1无信号, Input2有信号
IO_INPUT_BOTH_ON = 3                   # Input1有信号, Input2有信号

# ==================== IO输出状态值 ====================
IO_OUTPUT_MOVING = 0                   # 运动中
IO_OUTPUT_IN_POSITION = 1              # 到位
IO_OUTPUT_GRIPPED = 2                  # 夹住物体(堵转)
IO_OUTPUT_DROPPED = 3                  # 物体掉落

# ==================== 错误码定义 ====================
ERROR_NONE = 0                         # 无错误
ERROR_UNDERVOLTAGE = 1                 # 欠压 (低于15V)
ERROR_OVERVOLTAGE = 2                  # 过压 (高于28V)
ERROR_OVERCURRENT = 3                  # 过流
ERROR_OVERTEMP = 4                     # 过热
ERROR_MOTOR_PHASE_LOSS = 5             # 电机缺相
ERROR_OVERLOAD = 8                     # 过载
ERROR_OVERSPEED = 11                   # 过速
ERROR_STARTUP = 15                     # 启动异常
ERROR_ENCODER = 32                     # 编码器异常
ERROR_ENCODER_COMM = 33                # 编码器通讯异常
ERROR_SAMPLE_CIRCUIT = 34              # 采样电路异常
ERROR_DRIVER_IC = 35                   # 驱动IC异常
ERROR_FLASH = 36                       # Flash芯片异常
ERROR_PARAMS = 37                      # 参数异常

# 错误码解释字典
ERROR_DESCRIPTIONS = {
    ERROR_NONE: "无错误",
    ERROR_UNDERVOLTAGE: "欠压错误: 电源电压低于15V,请检查电源",
    ERROR_OVERVOLTAGE: "过压错误: 电源电压高于28V,请检查电源",
    ERROR_OVERCURRENT: "过流错误: 电流超过额定值1.5倍,请检查负载",
    ERROR_OVERTEMP: "过热错误: 电机温度超过90℃,请降低负载或等待冷却",
    ERROR_MOTOR_PHASE_LOSS: "电机缺相: 请检查电机接线",
    ERROR_OVERLOAD: "过载错误: 负载过大,请减小夹持力",
    ERROR_OVERSPEED: "过速错误: 速度超过额定值1.5倍",
    ERROR_STARTUP: "启动异常: 请检查编码器和电机",
    ERROR_ENCODER: "编码器异常: 请检查编码器连接",
    ERROR_ENCODER_COMM: "编码器通讯异常: 请检查编码器线缆",
    ERROR_SAMPLE_CIRCUIT: "采样电路异常: 请检查硬件",
    ERROR_DRIVER_IC: "驱动IC异常: 请重启设备",
    ERROR_FLASH: "Flash芯片异常: 请重启设备",
    ERROR_PARAMS: "参数异常: 请重启设备",
}

# ==================== 波特率配置值 ====================
BAUDRATE_115200 = 0
BAUDRATE_57600 = 1
BAUDRATE_38400 = 2
BAUDRATE_19200 = 3
BAUDRATE_9600 = 4
BAUDRATE_4800 = 5
BAUDRATE_230400 = 6
BAUDRATE_460800 = 7
BAUDRATE_921600 = 8

BAUDRATE_MAP = {
    BAUDRATE_115200: 115200,
    BAUDRATE_57600: 57600,
    BAUDRATE_38400: 38400,
    BAUDRATE_19200: 19200,
    BAUDRATE_9600: 9600,
    BAUDRATE_4800: 4800,
    BAUDRATE_230400: 230400,
    BAUDRATE_460800: 460800,
    BAUDRATE_921600: 921600,
}

# ==================== 校验位配置值 ====================
PARITY_NONE = 0
PARITY_ODD = 1
PARITY_EVEN = 2

# ==================== 停止位配置值 ====================
STOP_BITS_1 = 0
STOP_BITS_2 = 1

# ==================== 初始化方向配置值 ====================
INIT_DIRECTION_OPEN = 0                # 张开方向归零
INIT_DIRECTION_CLOSE = 1               # 闭合方向归零

# ==================== 单位配置值 ====================
UNIT_PERCENTAGE = 0                    # 千分比 (0-1000)
UNIT_MM = 1                            # 0.01mm

# ==================== 点动控制值 ====================
JOG_BACKWARD = -1                      # 反向
JOG_STOP = 0                           # 停止
JOG_FORWARD = 1                        # 正向

# ==================== 自动初始化配置值 ====================
AUTO_INIT_OFF = 0                      # 上电不初始化
AUTO_INIT_NORMAL = 1                   # 上电自动单向初始化
AUTO_INIT_FULL = 165                   # 上电自动完全初始化

# ==================== 指示灯状态 ====================
LED_NOT_INITIALIZED = "red_blink"      # 未初始化: 红灯闪烁
LED_INITIALIZED = "blue_on"            # 初始化完成: 蓝灯常亮
LED_COMMAND_RECEIVED = "purple_flash"  # 接收到命令: 偏紫色闪烁
LED_GRIPPED = "green_on"               # 夹住物体: 绿灯常亮
LED_DROPPED = "green_blink"            # 物体掉落: 绿灯闪烁

# ==================== 数值范围限制 ====================
FORCE_MIN = 20                         # 最小力值 (%)
FORCE_MAX = 100                        # 最大力值 (%)
POSITION_MIN = 0                       # 最小位置 (‰)
POSITION_MAX = 1000                    # 最大位置 (‰)
SPEED_MIN = 1                          # 最小速度 (%)
SPEED_MAX = 100                        # 最大速度 (%)
DEVICE_ID_MIN = 1                      # 最小设备ID
DEVICE_ID_MAX = 247                    # 最大设备ID
IO_FILTER_MIN = 0                      # 最小IO滤波 (ms)
IO_FILTER_MAX = 32767                  # 最大IO滤波 (ms)
IO_FILTER_DEFAULT = 10                 # 默认IO滤波 (ms)

# ==================== 线缆颜色定义 ====================
# 线序定义 (8芯线 + 屏蔽)
WIRE_485_A = "绿色"                     # RS485 A (T/R+)
WIRE_485_B = "橙色"                     # RS485 B (T/R-)
WIRE_OUTPUT_2 = "黄色"                  # IO输出2
WIRE_OUTPUT_1 = "黑色"                  # IO输出1
WIRE_24V = "红色"                       # 24V电源正极
WIRE_GND = "蓝色"                       # GND电源负极
WIRE_INPUT_2 = "棕色"                   # IO输入2
WIRE_INPUT_1 = "白色"                   # IO输入1
WIRE_PE = "编织线"                      # 外壳接地

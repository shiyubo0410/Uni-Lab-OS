# -*- coding: utf-8 -*-
"""
PRCXI 标机 Python SDK
版本:V1.0
作者:Prcxi-xuhailin
适用设备:PRCXI 系列标机
适用 Python 版本:3.8.0
创建时间:2025-11-27
最后更新时间:2025-11-27
"""

import socket
import json
import time
from datetime import datetime
from enum import Enum, auto
from typing import List, Dict, Optional, Any


# ------------------------------ 核心数据模型 (仅列出主要,其他请根据接口返回自行定义；部分枚举是以项的名称处理业务逻辑，因此下面列出的枚举的项名称切勿随意更改！！！)------------------------------
class MaterialEnum(Enum):
    Other = 0  # 其它
    Tips = 1  # 吸头
    DeepWellPlate = 2  # 深孔板
    PCRPlate = 3  # PCR板
    ELISAPlate = 4  # 酶标板
    Reservoir = 5  # 储液槽
    WasteBox = 6  # 废弃盒


class MaterialEntity:
    """耗材实体类:描述吸头、试剂管等耗材的属性"""

    def __init__(
        self,
        uuid: str,
        code: str,
        name: Optional[str] = None,
        summary_name: Optional[str] = None,
        supply_type: Optional[int] = 1,
        factory: Optional[str] = None,
        length_num: Optional[float] = 0.0,
        width_num: Optional[float] = 0.0,
        height_num: Optional[float] = 0.0,
        depth_num: Optional[float] = 0.0,
        pipette_height: Optional[float] = 0.0,
        hole_diameter: Optional[float] = 0.0,
        margins_x: Optional[float] = 0.0,
        margins_y: Optional[float] = 0.0,
        hole_colum: Optional[int] = 0,
        hole_row: Optional[int] = 0,
        volume: Optional[int] = 0,
        x_spacing: Optional[float] = 0.0,
        y_spacing: Optional[float] = 0.0,
        material_enum: Optional[MaterialEnum] = MaterialEnum.Other,
        image_path: Optional[str] = None,
        create_time: Optional[datetime] = None,
        update_time: Optional[datetime] = None,
    ):
        """
        :param uuid: 耗材唯一ID uuid.uuid4()
        :param code: 型号
        :param name: 耗材名称
        :param summary_name: 概述名称
        :param supply_type: 类型(1 耗材 2 适配器)
        :param factory: 生产厂家
        :param length_num: 长度(mm)
        :param width_num: 宽度(mm)
        :param height_num: 高度(mm)
        :param depth_num: 深度(mm)
        :param pipette_height: 吸头高(mm)
        :param hole_diameter: 孔直径(mm)
        :param margins_x: X轴边距(mm)
        :param margins_y: Y轴边距(mm)
        :param hole_colum: 孔列
        :param hole_row: 孔行
        :param volume: 容积(ul)
        :param x_spacing: 列间距(mm)
        :param y_spacing: 行间距(mm)
        :param material_enum: 耗材类型
        :param image_path: 图片路径 可选
        :param create_time: 创建时间 可选
        :param update_time: 更新时间 可选
        """
        self.uuid = uuid
        self.code = code
        self.name = name
        self.summary_name = summary_name
        self.supply_type = supply_type
        self.factory = factory
        self.length_num = length_num
        self.width_num = width_num
        self.height_num = height_num
        self.depth_num = depth_num
        self.pipette_height = pipette_height
        self.hole_diameter = hole_diameter
        self.margins_x = margins_x
        self.margins_y = margins_y
        self.hole_colum = hole_colum
        self.hole_row = hole_row
        self.volume = volume
        self.x_spacing = x_spacing
        self.y_spacing = y_spacing
        self.material_enum = material_enum
        self.image_path = image_path
        self.create_time = create_time
        self.update_time = update_time

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典,用于JSON序列化"""
        return {
            "uuid": self.uuid,
            "Code": self.code,
            "Name": self.name,
            "SummaryName": self.summary_name,
            "SupplyType": self.supply_type,
            "Factory": self.factory,
            "LengthNum": self.length_num,
            "WidthNum": self.width_num,
            "HeightNum": self.height_num,
            "DepthNum": self.depth_num,
            "PipetteHeight": self.pipette_height,
            "HoleDiameter": self.hole_diameter,
            "Margins_X": self.margins_x,
            "Margins_Y": self.margins_y,
            "HoleColum": self.hole_colum,
            "HoleRow": self.hole_row,
            "Volume": self.volume,
            "XSpacing": self.x_spacing,
            "YSpacing": self.y_spacing,
            "materialEnum": self.material_enum,
            "ImagePath": self.image_path,
            "CreateTime": self.create_time.isoformat() if self.create_time else None,
            "UpdateTime": self.update_time.isoformat() if self.update_time else None,
        }


class WorkTablet:
    """工作板位实体类:描述板位位置、坐标及耗材/适配器"""

    def __init__(
        self,
        number: int,
        material: MaterialEntity,
        code: Optional[str] = None,
        row: Optional[int] = None,
        col: Optional[int] = None,
        x_pos: float = 0.0,
        y_pos: float = 0.0,
        z_pos: float = 0.0,
        z_gradient_pos: float = 0.0,
        x_center_pos: float = 0.0,
        y_center_pos: float = 0.0,
        x2_pos: float = 0.0,
        y2_pos: float = 0.0,
        z2_pos: float = 0.0,
        z2_gradient_pos: float = 0.0,
        z1_reverse_imbibition_pos: float = 0.0,
        z2_reverse_imbibition_pos: float = 0.0,
        x2_center_pos: float = 0.0,
        y2_center_pos: float = 0.0,
        adapter: Optional[MaterialEntity] = None,
    ):
        """
        :param code: 板位名称 T1-T6 可选
        :param number: 板位编号 必填
        :param row: 所在行 可选
        :param col: 所在列 可选
        :param x_pos: X位置 可选
        :param y_pos: Y位置 可选
        :param z_pos: Z位置 可选
        :param z_gradient_pos: 梯度Z 可选
        :param x_center_pos: 中心点X 可选
        :param y_center_pos: 中心点Y 可选
        :param x2_pos: X2位置 不填
        :param y2_pos: Y2位置 不填
        :param z2_pos: Z2位置 不填
        :param z2_gradient_pos: Z2梯度 可选
        :param z1_reverse_imbibition_pos: 反向吸液高度Z1 可选
        :param z2_reverse_imbibition_pos: 反向吸液高度Z2 可选
        :param x2_center_pos: X2中心点 可选
        :param y2_center_pos: Y2中心点 可选
        :param material: 耗材对象 必填
        :param adapter: 适配器对象 可选 有则必填
        """
        self.code = code
        self.number = number
        self.row = row
        self.col = col
        self.x_pos = x_pos
        self.y_pos = y_pos
        self.z_pos = z_pos
        self.z_gradient_pos = z_gradient_pos
        self.x_center_pos = x_center_pos
        self.y_center_pos = y_center_pos
        self.x2_pos = x2_pos
        self.y2_pos = y2_pos
        self.z2_pos = z2_pos
        self.z2_gradient_pos = z2_gradient_pos
        self.z1_reverse_imbibition_pos = z1_reverse_imbibition_pos
        self.z2_reverse_imbibition_pos = z2_reverse_imbibition_pos
        self.x2_center_pos = x2_center_pos
        self.y2_center_pos = y2_center_pos
        self.material = material
        self.adapter = adapter

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典,用于JSON序列化"""
        return {
            "Code": self.code,
            "Number": self.number,
            "Row": self.row,
            "Col": self.col,
            "XPos": self.x_pos,
            "YPos": self.y_pos,
            "ZPos": self.z_pos,
            "ZGradientPos": self.z_gradient_pos,
            "XCenterPos": self.x_center_pos,
            "YCenterPos": self.y_center_pos,
            "X2Pos": self.x2_pos,
            "Y2Pos": self.y2_pos,
            "Z2Pos": self.z2_pos,
            "Z2GradientPos": self.z2_gradient_pos,
            "Z1ReverseImbibitionPos": self.z1_reverse_imbibition_pos,
            "Z2ReverseImbibitionPos": self.z2_reverse_imbibition_pos,
            "X2CenterPos": self.x2_center_pos,
            "Y2CenterPos": self.y2_center_pos,
            "Material": self.material.to_dict() if self.material else None,
            "Adapter": self.adapter.to_dict() if self.adapter else None,
        }


class WorkTabletMatrix:
    """工作板位矩阵实体类:描述组合板位及布局信息"""

    def __init__(
        self,
        matrix_id: str,
        matrix_name: str,
        work_tablets: List[WorkTablet],
        length_two_edge: float = 139.0,
        width_two_edge: float = 95.8,
        baseplate_id: Optional[str] = None,
        matrix_count: int = 0,
        rows: int = 0,
        cols: int = 0,
        arm: int = 0,
        dosage: int = 0,
        arm2: int = 0,
        dosage2: int = 0,
    ):
        """
        :param matrix_id: 组合ID 必填
        :param matrix_name: 组合名称 必填
        :param work_tablets: 工作板位列表 必填
        :param length_two_edge: 两个板位间含边界长 X方向 默认139.0 可选
        :param width_two_edge: 两个板位宽 Y方向 默认95.8 可选
        :param baseplate_id: 底板布局编号 可选
        :param matrix_count: 组合板位数量 可选
        :param rows: 组合板位行数 可选
        :param cols: 组合板位列数 可选
        :param arm: 机械臂通道 可选
        :param dosage: 机械臂型号/剂量 可选
        :param arm2: 机械臂通道2 可选
        :param dosage2: 机械臂型号/剂量2 可选
        """
        self.matrix_id = matrix_id
        self.matrix_name = matrix_name
        self.work_tablets = work_tablets
        self.length_two_edge = length_two_edge
        self.width_two_edge = width_two_edge
        self.baseplate_id = baseplate_id
        self.matrix_count = matrix_count
        self.rows = rows
        self.cols = cols
        self.arm = arm
        self.dosage = dosage
        self.arm2 = arm2
        self.dosage2 = dosage2

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典,用于JSON序列化"""
        return {
            "LengthTwoEdge": self.length_two_edge,
            "WidthTwoEdge": self.width_two_edge,
            "BaseplateId": self.baseplate_id,
            "MatrixId": self.matrix_id,
            "MatrixName": self.matrix_name,
            "MatrixCount": self.matrix_count,
            "Rows": self.rows,
            "Cols": self.cols,
            "Arm": self.arm,
            "Dosage": self.dosage,
            "Arm2": self.arm2,
            "Dosage2": self.dosage2,
            "WorkTablets": [wt.to_dict() for wt in self.work_tablets],
        }


class AxisNum(Enum):
    Left = 1  # 左轴
    Right = 2  # 右轴
    ClampingJaw = 3 #


class MajorFun(Enum):
    Load = auto()  # 装载
    UnLoad = auto()  # 卸载
    Imbibing = auto()  # 吸液
    Tapping = auto()  # 放液
    Blending = auto()  # 混匀
    DefectiveLift = auto()  # 夹板
    PutDown = auto()  # 放板
    Shaking = auto()  # 振荡
    Incubation = auto()  # 孵育
    Magnetic = auto()  # 磁力架
    Shaking_Incubation = auto()  # 孵育+振荡


class MaterialType(Enum):
    BlankPipe = 0  # 空管
    Agentia = 1  # 试剂
    Used = 2  # 已编辑


class LiquidDispensingMethodEnum(Enum):
    NormalDispense = 0  # 正常放液
    WallContactAfterDispense_Left = 3  # 放液后靠左壁
    WallContactAfterDispense_Right = 4  # 放液后靠右壁


class StepData:
    """步骤数据实体类,描述装吸放卸等操作步骤"""

    def __init__(
        self,
        step_axis: AxisNum,
        function: MajorFun,
        dosage_num: float = 0.0,
        sequence_number: int = 0,
        plate_no: int = 0,
        hole_col: int = 0,
        hole_row: int = 0,
        is_whole_plate: bool = False,
        balance_height: int = 2,
        mate_type: MaterialType = MaterialType.BlankPipe,
        plate_or_hole_num: Optional[str] = None,
        assist_fun1: Optional[str] = None,
        assist_fun2: Optional[str] = None,
        assist_fun3: Optional[str] = None,
        assist_fun4: Optional[str] = None,
        assist_fun5: Optional[str] = None,
        hole_nums: List[int] = None,
        hole_numbers: str = None,
        liquid_dispensing_method: LiquidDispensingMethodEnum = LiquidDispensingMethodEnum.NormalDispense,
        dosage_speed: int = 1,
        blending_times: int = 0,
    ):
        """
        :param step_axis: 轴 - 左轴/右轴
        :param function: 动作类型
        :param dosage_num: 剂量,体积μL
        :param sequence_number: 序号
        :param plate_no: 当前板位号
        :param hole_col: 孔位列数,用于计算X方向偏移量
        :param hole_row: 孔位行数,用于计算Y方向偏移量
        :param is_whole_plate: 是否整块板位
        :param balance_height: 平衡高度,默认离底部2mm,可调10档,每档1mm
        :param mate_type: 放在板位上的物料类型:空管/试剂 不填
        :param plate_or_hole_num: 板位或孔位,外部绑定用
        :param assist_fun1: 辅助功能1
        :param assist_fun2: 辅助功能2
        :param assist_fun3: 辅助功能3
        :param assist_fun4: 辅助功能4
        :param assist_fun5: 辅助功能5
        :param hole_nums: 孔位编号集合
        :param hole_numbers: 孔号集
        :param liquid_dispensing_method: 排液方式
        :param dosage_speed: 移液速度 档位1-10
        :param blending_times: 混匀次数
        """
        """
        assist_fun1~5为辅助功能 根据动作类型的不同 有不同的含义：
                    assist_fun1    assist_fun2    assist_fun3    assist_fun4                assist_fun5
        振荡        时间            模块编号        振荡幅度
        孵育        时间            模块编号        温度
        磁力架      时间            模块编号        高度            是否等待('true'或'false')
        孵育+振荡   振荡时间         模块编号        振荡幅度        温度                       孵育时间
        """
        self.step_axis = step_axis
        self.function = function
        self.dosage_num = dosage_num
        self.sequence_number = sequence_number
        self.plate_no = plate_no
        self.hole_col = hole_col
        self.hole_row = hole_row
        self.is_whole_plate = is_whole_plate
        self.balance_height = balance_height
        self.mate_type = mate_type
        self.plate_or_hole_num = plate_or_hole_num
        self.assist_fun1 = assist_fun1
        self.assist_fun2 = assist_fun2
        self.assist_fun3 = assist_fun3
        self.assist_fun4 = assist_fun4
        self.assist_fun5 = assist_fun5
        self.hole_nums = hole_nums or []
        self.hole_numbers = hole_numbers
        self.liquid_dispensing_method = liquid_dispensing_method
        self.dosage_speed = dosage_speed
        self.blending_times = blending_times

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典,用于JSON序列化"""
        return {
            "StepAxis": self.step_axis.name if self.step_axis else None,
            "Function": self.function.name if self.function else None,
            "DosageNum": self.dosage_num,
            "SequenceNumber": self.sequence_number,
            "PlateNo": self.plate_no,
            "HoleCol": self.hole_col,
            "HoleRow": self.hole_row,
            "IsWholePlate": self.is_whole_plate,
            "BalanceHeight": self.balance_height,
            "MateType": self.mate_type.name if self.mate_type else None,
            "PlateOrHoleNum": self.plate_or_hole_num,
            "AssistFun1": self.assist_fun1,
            "AssistFun2": self.assist_fun2,
            "AssistFun3": self.assist_fun3,
            "AssistFun4": self.assist_fun4,
            "AssistFun5": self.assist_fun5,
            "HoleNums": self.hole_nums,
            "HoleNumbers": self.hole_numbers,
            "LiquidDispensingMethod": (
                self.liquid_dispensing_method.name
                if self.liquid_dispensing_method
                else None
            ),
            "DosageSpeed": self.dosage_speed,
            "BlendingTimes": self.blending_times,
        }


class Solution:
    """方案类:描述标机的完整方案"""

    def __init__(
        self,
        id: str,
        create_time: str,
        matrix_id: str,
        plan_code: str,
        plan_name: str,
        plan_targe: str,
        annotate: str,
    ):
        """
        :param id: 方案唯一ID
        :param create_time: 创建时间(格式:yyyy-MM-dd HH:mm:ss)
        :param matrix_id: 关联的板位组合ID
        :param plan_code: 方案编码(如"SOL-19970502-001")
        :param plan_name: 方案名称(如"20ul吸液-试剂A分液方案")
        :param plan_targe: 方案目标
        :param annotate: 方案备注
        """
        self.id = id
        self.create_time = create_time
        self.matrix_id = matrix_id
        self.plan_code = plan_code
        self.plan_name = plan_name
        self.plan_targe = plan_targe
        self.annotate = annotate

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典,用于JSON序列化"""
        return {
            "Id": self.id,
            "CreateTime": self.create_time,
            "MatrixId": self.matrix_id,
            "PlanCode": self.plan_code,
            "PlanName": self.plan_name,
            "PlanTarge": self.plan_targe,
            "Annotate": self.annotate,
        }


class DeviceErrorStatusFlags(Enum):
    """设备错误状态枚举:定义错误码与描述的映射"""

    DeviceNotConnected = 1  # 设备未连接
    XAxisOutOfRange = 17  # X轴超出限位
    YAxisOutOfRange = 18  # Y轴超出限位
    ZAxisOutOfRange = 19  # Z轴超出限位
    PipetteAxisOutOfRange = 20  # 移液轴超出限位
    CurrentPositionXZero = 33  # 当前板位X轴位置为零
    CurrentPositionYZero = 34  # 当前板位Y轴位置为零
    CurrentPositionZZero = 35  # 当前板位Z轴位置为零

    @staticmethod
    def get_description(error_code: int) -> str:
        """根据错误码获取描述信息"""
        error_map = {
            1: "设备未连接(检查IP、端口或设备电源)",
            17: "X轴运动超出其允许的限位范围(手动复位X轴)",
            18: "Y轴运动超出其允许的限位范围(手动复位Y轴)",
            19: "Z轴运动超出其允许的限位范围(手动复位Z轴)",
            20: "移液轴运动超出其允许的限位范围(手动复位移液轴)",
            33: "当前板位的X轴位置为零(重新校准X轴位置)",
            34: "当前板位的Y轴位置为零(重新校准Y轴位置)",
            35: "当前板位的Z轴位置为零(重新校准Z轴位置)",
        }
        return error_map.get(error_code, f"未知错误码: {error_code}")


class PositionData:
    """步骤数据实体类,描述装吸放卸等操作步骤"""

    def __init__(
        self,
        Number: int = 0,
        XPos: float = 0.0,
        YPos: float = 0.0,
        ZPos: float = 0.0,
    ):
        """
        :param Number: 板位
        :param XPos: x位置
        :param YPos: Y位置
        :param ZPos: Z位置
        """
        self.Number = Number
        self.XPos = XPos
        self.YPos = YPos
        self.ZPos = ZPos
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典,用于JSON序列化"""
        return {
            "Number": self.Number,
            "XPos": self.XPos,
            "YPos": self.YPos,
            "ZPos": self.ZPos,
        }


# ------------------------------ SDK 核心类 ------------------------------
class PRCXISDK:
    """PRCXI 标机Python SDK核心类,封装所有RPC接口"""

    def __init__(self, host: str = "127.0.0.1", port: int = 9999, timeout: int = 10):
        """
        初始化SDK连接配置
        :param host: 设备IP地址(默认:127.0.0.1)
        :param port: 设备端口号(默认:9999)
        :param timeout: 连接超时时间(默认:10秒)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None

    def _connect(self) -> None:
        """建立Socket连接(内部使用)"""
        if self.socket and self.socket.fileno() != -1:
            self._disconnect()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(self.timeout)
        self.socket.connect((self.host, self.port))

    def _disconnect(self) -> None:
        """关闭Socket连接(内部使用)"""
        if self.socket and self.socket.fileno() != -1:
            self.socket.close()
            self.socket = None

    def _number_to_hex(self, number: int) -> bytes:
        """将数字转换为16字节的十六进制字节流(内部使用)"""
        return bytes.fromhex(format(number, "016x"))

    def _send_command(
        self, service_name: str, method_name: str, parameters: List[Any]
    ) -> Dict[str, Any]:
        """
        发送RPC指令(内部使用)
        :param service_name: 服务名称
        :param method_name: 方法名称
        :param parameters: 参数列表
        :return: 设备返回结果字典
        """
        try:
            # 构建指令JSON
            cmd_dict = {
                "ServiceName": service_name,
                "MethodName": method_name,
                "Paramters": parameters,  # 保持与设备接口一致的参数键名(拼写为Paramters)
            }
            print(f"发送:{cmd_dict}")
            cmd_json = json.dumps(cmd_dict, separators=(",", ":"), ensure_ascii=False)
            cmd_bytes = cmd_json.encode("utf-8")

            # 构建指令头(16字节长度信息)
            cmd_header = self._number_to_hex(len(cmd_bytes))
            full_cmd = cmd_header + cmd_bytes

            # 发送指令并接收响应
            self._connect()
            self.socket.send(full_cmd)

            # 接收响应
            response = b""
            while True:
                data = self.socket.recv(4096)
                if not data:
                    break
                response += data[0:]

            # 解析响应
            if not response:
                return {"Success": False, "Message": "未收到设备响应", "Data": None}
            start = response.find(b"{")
            if start == -1:
                return {
                    "Success": False,
                    "Message": "未找到 JSON 起始符 '{'",
                    "Data": response,
                }

            json_bytes = response[start:]
            response_dict = json.loads(json_bytes.decode("utf-8"))
            return response_dict

        except socket.timeout:
            return {
                "Success": False,
                "Message": f"连接超时({self.timeout}秒)",
                "Data": None,
            }
        except ConnectionRefusedError:
            return {
                "Success": False,
                "Message": "设备拒绝连接,请检查IP和端口",
                "Data": None,
            }
        except json.JSONDecodeError:
            return {
                "Success": False,
                "Message": "响应数据解析失败",
                "Data": response.decode("utf-8", errors="ignore"),
            }
        except Exception as e:
            return {
                "Success": False,
                "Message": f"指令发送失败:{str(e)}",
                "Data": None,
            }
        finally:
            self._disconnect()

    # ------------------------------ 1. 设备控制接口(IAutomation)------------------------------

    def automation_start(self) -> Dict[str, Any]:
        """
        执行已加载的方案(需先调用solution_load)
        :return: 执行结果字典
        """
        return self._send_command("IAutomation", "Start", [])

    def automation_pause(self) -> Dict[str, Any]:
        """
        暂停当前运行的方案
        :return: 执行结果字典
        """
        return self._send_command("IAutomation", "Pause", [])

    def automation_resume(self) -> Dict[str, Any]:
        """
        继续已暂停的方案
        :return: 执行结果字典
        """
        return self._send_command("IAutomation", "Resume", [])

    def automation_reset(self) -> Dict[str, Any]:
        """
        设备复位(将各轴恢复到初始位置)
        :return: 执行结果字典
        """
        return self._send_command("IAutomation", "Reset", [])

    def automation_stop(self) -> Dict[str, Any]:
        """
        停止当前运行的方案(停止后自动复位)
        :return: 执行结果字典
        """
        return self._send_command("IAutomation", "Stop", [])

    def automation_get_error_code(self) -> Dict[str, Any]:
        """
        获取设备当前错误码
        :return: 执行结果字典(Data为错误码)
        """
        return self._send_command("IAutomation", "GetErrorCode", [])

    def automation_clear_error_code(self) -> Dict[str, Any]:
        """
        清空设备错误码
        :return: 执行结果字典
        """
        return self._send_command("IAutomation", "RemoveErrorCodet", [])

    # ------------------------------ 2. 方案管理接口(ISolution)------------------------------
    def solution_get_list(self) -> Dict[str, Any]:
        """
        获取所有方案列表
        :return: 执行结果字典(Data为方案列表)
        """
        return self._send_command("ISolution", "GetSolutionList", [])

    def solution_load(self, solution_id: str) -> Dict[str, Any]:
        """
        加载指定ID的方案
        :param solution_id: 方案ID
        :return: 执行结果字典
        """
        return self._send_command("ISolution", "LoadSolution", [solution_id])

    def solution_add(
        self, solution_name: str, matrix_id: str, solution_content: List[StepData]) -> Dict[str, Any]:
        """
        添加新方案
        :param solution_name: 方案名称
        :param matrix_id: 板位组合ID
        :param solution_content: 方案步骤列表(StepData对象列表)
        :return: 执行结果字典(Data为新方案ID)
        """
        # 转换为字典列表
        content_dict = [step.to_dict() for step in solution_content]
        return self._send_command(
            "ISolution", "AddSolution", [solution_name, matrix_id, content_dict]
        )

    # ------------------------------ 3. 设备状态接口(IMachineState)------------------------------
    def machine_state_get_step_list(self) -> Dict[str, Any]:
        """
        获取已加载方案的步骤状态列表(需先加载方案)
        :return: 执行结果字典
        """
        return self._send_command("IMachineState", "GetStepStateList", [])

    def machine_state_get_step_status(self, step_no: int) -> Dict[str, Any]:
        """
        获取指定步骤的详细状态(开始时间、结束时间)
        :param step_no: 步骤号
        :return: 执行结果字典
        """
        return self._send_command("IMachineState", "GetStepStatus", [step_no])

    def machine_state_get_step_state(self, step_no: int) -> Dict[str, Any]:
        """
        获取指定步骤的运行状态
        :param step_no: 步骤号
        :return: 执行结果字典
        """
        return self._send_command("IMachineState", "GetStepState", [step_no])

    def machine_state_get_axis_location(self, axis_no: int) -> Dict[str, Any]:
        """
        获取指定轴的当前位置
        :param axis_no: 轴编号(1左轴 0右轴)
        :return: 执行结果字典(Data为轴位置,单位mm)
        """
        return self._send_command("IMachineState", "GetLocation", [axis_no])

    # ------------------------------ 4. 板位组合接口(IMatrix)------------------------------
    def matrix_get_all(self) -> Dict[str, Any]:
        """
        获取所有板位组合列表
        :return: 执行结果字典
        """
        return self._send_command("IMatrix", "GetWorkTabletMatrices", [])

    def matrix_add(self, matrix: WorkTabletMatrix) -> Dict[str, Any]:
        """
        添加新的板位组合
        :param matrix: WorkTabletMatrix对象
        :return: 执行结果字典
        """
        return self._send_command("IMatrix", "AddWorkTabletMatrix2", [matrix])

    def matrix_get_by_id(self, matrix_id: str) -> Dict[str, Any]:
        """
        通过ID获取板位组合详情
        :param matrix_id: 板位组合ID
        :return: 执行结果字典
        """
        return self._send_command("IMatrix", "GetWorkTabletMatrixById", [matrix_id])

    def matrix_get_all_material(self) -> Dict[str, Any]:
        """
        获取所有耗材
        :return: 执行结果字典
        """
        return self._send_command("IMatrix", "GetAllMaterial", [])

    def matrix_Update_ClampJaw_Position(self, matrix: WorkTabletMatrix) -> Dict[str, Any]:
        """
        添加新的板位组合
        :param matrix: WorkTabletMatrix对象
        :return: 执行结果字典
        """
        return self._send_command("IMatrix", "UpdateClampJawPosition", [WorkTabletMatrix])
    def matrix_Update_Pipetting_Position(self, matrix: WorkTabletMatrix) -> Dict[str, Any]:
        """
        添加新的板位组合
        :param matrix: WorkTabletMatrix对象
        :return: 执行结果字典
        """
        return self._send_command("IMatrix", "UpdatePipettingPosition", [WorkTabletMatrix])


# ------------------------------ 使用示例 ------------------------------
if __name__ == "__main__":
    # 1. 初始化SDK
    sdk = PRCXISDK(host="10.142.209.190", port=9999, timeout=15)

    try:

        matrix_info = {
            "MatrixId": "11111",
            "MatrixName": "test002",
            "MatrixCount":16,
            "WorkTablets": [{"Number": i, "Material": {"uuid": "73bb9b10bc394978b70e027bf45ce2d3"}} for i in
                            range(1, 16)] +
                           [{"Number": 16,
                             "Material": {'uuid': '80652665f6a54402b2408d50b40398df', "Code": "ZX-001-1000", "Name": "1000μL Tip头",
                           "SummaryName": "1000μL Tip头", "PipetteHeight": 100, "materialEnum": 1}}]
        }
        # sdk.matrix_add(matrix=matrix_info)

        # 2. 设备复位
        # print("=== 设备复位 ===")
        # reset_result = sdk.automation_reset()
        # print(f"复位结果:{reset_result}")
        # time.sleep(60)  # 等待复位完成

        # 3. 获取所有方案
        print("\n=== 获取所有方案 ===")
        solution_result = sdk.solution_get_list()
        if solution_result["Success"]:
            # 取出 Data
            data = solution_result.get("Data", [])
            # 解析
            if isinstance(data, str):
                data = json.loads(data)
            # 转成 Solution 对象列表
            solutions = [
                Solution(
                    id=item.get("Id"),
                    create_time=item.get("CreateTime"),
                    matrix_id=item.get("MatrixId"),
                    plan_code=item.get("PlanCode"),
                    plan_name=item.get("PlanName"),
                    plan_targe=item.get("PlanTarge"),
                    annotate=item.get("Annotate"),
                )
                for item in data
            ]
        
            print(f"获取到 {len(solutions)} 个方案")
            for sol in solutions:
                print(f"方案ID: {sol.id}, 名称: {sol.plan_name}, 关联板位组合ID: {sol.matrix_id}, \n详细: {sol.to_dict()}")
        #
        # 4. 获取所有板位组合(用于创建方案时关联)
        print("\n=== 获取所有板位组合 ===")
        matrix_result = sdk.matrix_get_all()
        if matrix_result["Success"]:
            matrices_raw = matrix_result["Data"]
            # Data 是 JSON 字符串（常见问题） → 二次解析
            if isinstance(matrices_raw, str):
                matrices = json.loads(matrices_raw)
            else:
                matrices = matrices_raw
            print(f"获取到 {len(matrices)} 个板位组合")
            # print("板位组合列表:", matrices)
            if matrices:
                target_matrix_id = matrices[0]["MatrixId"]
                print("目标板位组合ID:", target_matrix_id)
        else:
            print("获取失败：", matrix_result["Message"])
        #
        # # 5. 创建新方案
        # print("\n=== 创建新方案 ===")
        # # 构建步骤列表
        # steps = [
        #     # 步骤1:左轴装载(1号板位，第一行 第一列)
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Load,
        #         dosage_num=20,
        #         plate_no=1,
        #         is_whole_plate=False,
        #         hole_row=1,
        #         hole_col=1,
        #         blending_times=0,
        #         balance_height=5,
        #         plate_or_hole_num="H1-8,T1",
        #         hole_nums=[1,2,3,4,5,6,7,8]
        #     ),
        #     # 步骤2:左轴吸液(2号板位,20ul)
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Imbibing,
        #         dosage_num=20,
        #         plate_no=2,
        #         is_whole_plate=False,
        #         hole_row=1,
        #         hole_col=1,
        #         blending_times=0,
        #         balance_height=5,
        #         plate_or_hole_num="H1-8,T2",
        #         hole_nums=[1,2,3,4,5,6,7,8]
        #     ),
        #     # 步骤3:左轴放液(3号板位,20ul)
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Tapping,
        #         dosage_num=20,
        #         plate_no=3,
        #         is_whole_plate=False,
        #         hole_row=1,
        #         hole_col=1,
        #         blending_times=0,
        #         balance_height=5,
        #         plate_or_hole_num="H1-8,T3",
        #         hole_nums=[1,2,3,4,5,6,7,8]
        #     ),
        #     # 步骤4:左轴混匀(3次)
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Blending,
        #         dosage_num=20,
        #         plate_no=3,
        #         is_whole_plate=False,
        #         hole_row=1,
        #         hole_col=1,
        #         blending_times=3,
        #         balance_height=5,
        #         plate_or_hole_num="H1-8,T3",
        #         hole_nums=[1,2,3,4,5,6,7,8]
        #     ),
        #     # 步骤5:右轴吸液(3号板位,10ul,整板操作)
        #     StepData(
        #         step_axis=AxisNum.Right,
        #         function=MajorFun.Imbibing,
        #         dosage_num=10,
        #         plate_no=3,
        #         is_whole_plate=False,
        #         hole_row=1,
        #         hole_col=1,
        #         blending_times=0,
        #         balance_height=5,
        #         plate_or_hole_num="H1-8,T3",
        #         hole_nums=[1,2,3,4,5,6,7,8],
        #         assist_fun1="反向吸液(1ul)",#吸液后吸空气
        #     ),
        #     # 步骤6:夹爪轴夹取(3号板位,整板操作)
        #     StepData(
        #         step_axis=AxisNum.ClampingJaw,
        #         function=MajorFun.DefectiveLift,
        #         plate_no=3,
        #         is_whole_plate=True,
        #         hole_row=1,
        #         hole_col=1,
        #         balance_height=2,
        #         plate_or_hole_num="T3",
        #     ),
        #     # 步骤7:夹爪轴放下(4号板位,整板操作)
        #     StepData(
        #         step_axis=AxisNum.ClampingJaw,
        #         function=MajorFun.PutDown,
        #         plate_no=4,
        #         is_whole_plate=True,
        #         hole_row=1,
        #         hole_col=1,
        #         balance_height=2,
        #         plate_or_hole_num="T4",
        #     ),
        #     # 步骤8:振荡
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Shaking,
        #         assist_fun1="10",# 时间（s）
        #         assist_fun2="1",# 模块编号
        #         assist_fun3="500",# 震荡幅度（300-1200）
        #         assist_fun4="True",# 是否等待
        #     ),
        #     # 步骤9:孵育
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Incubation,
        #         assist_fun1="10",# 时间（s）
        #         assist_fun2="1",# 模块编号
        #         assist_fun3="50",# 温度
        #         assist_fun4="True",# 是否等待
        #     ),
        #     # 步骤10:磁力架
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Magnetic,
        #         assist_fun1="10",# 时间（s）
        #         assist_fun2="1",# 模块编号
        #         assist_fun3="35",# 高度
        #         assist_fun4="True",# 是否等待
        #     ),
        #     # 步骤11:孵育+振荡
        #     StepData(
        #         step_axis=AxisNum.Left,
        #         function=MajorFun.Shaking_Incubation,
        #         assist_fun1="10",# 时间（s）
        #         assist_fun2="1",# 模块编号
        #         assist_fun3="500",# 震荡幅度（300-1200）
        #         assist_fun4="True",# 是否等待
        #         assist_fun5="50",# 温度
        #     )
        # ]
        # # 添加方案
        # add_solution_result = sdk.solution_add(
        #     solution_name="示例方案",
        #     matrix_id=target_matrix_id,
        #     solution_content=steps,
        # )
        # print(f"创建方案结果:{add_solution_result}")
        # if add_solution_result["Success"]:
        #     solution_id = add_solution_result["Data"].strip('"')
        #     print(f"新方案ID:{solution_id}")
        #     print('长度=', len(solution_id))
        #
        # # 6. 加载方案
        # print("\n=== 加载方案 ===")
        # load_result = sdk.solution_load(solution_id)
        # print(f"加载结果:{load_result}")
        # time.sleep(1)
        #
        # # 7. 启动方案
        # print("\n=== 启动方案 ===")
        # start_result = sdk.automation_start()
        # print(f"启动结果:{start_result}")
        # if start_result["Success"]:
        #
        #     # 8. 获取步骤状态
        #     print("\n=== 获取步骤状态 ===")
        #     step_list_result = sdk.machine_state_get_step_list()
        #     print(f"步骤列表状态:{step_list_result}")
        #
        #     # 9. 获取左轴位置
        #     print("\n=== 获取左轴位置 ===")
        #     x_axis_result = sdk.machine_state_get_axis_location(1)
        #     print(f"左轴位置:{x_axis_result}")
        #
        #
        # # 10.设置夹爪板位位置 Z2位置-ZPos_2
        # print("\n=== 设置夹爪板位位置 ===")
        # WorkTabletMatrix = {"MatrixId": target_matrix_id,  "WorkTablets":
        # [{"Number": 1,"XPos": 10.0,"YPos": 10.0,"ZPos": 10.0,"ZPos_2": 12.0},{"Number": 2,"XPos": 20.0,"YPos": 10.0,"ZPos": 10.0}]}
        # start_result = sdk.matrix_Update_ClampJaw_Position(WorkTabletMatrix)
        # print(f"设置夹爪板位位置:{start_result}")

         # 11.设置移液轴板位位置 X左靠壁-X_Left X右靠壁-X_Right Z靠壁-ZAgainstTheWall
        # print("\n=== 设置移液轴板位位置 ===")
        # WorkTabletMatrix = {"MatrixId": "334d0feb-8eed-4675-a72f-c711c53ad56d",  "WorkTablets":
        # [{"Number": 1,"XPos": 10.0,"YPos": 10.0,"ZPos": 10.0,"X_Left": 2.0,"X_Right": 1.0,"ZAgainstTheWall": 11.0
        #      ,"X2Pos": 11.0,"Y2Pos": 11.0,"Z2Pos": 11.0,"X2_Left": 1.0,"X2_Right": 3.0,"ZAgainstTheWall2": 4.0}]}
        # start_result = sdk.matrix_Update_Pipetting_Position(WorkTabletMatrix)
        # print(f"设置夹爪板位位置:{start_result}")

    except Exception as e:
        print(f"示例运行异常:{str(e)}")
        # 获取错误码并解析
        error_result = sdk.automation_get_error_code()
        if error_result["Success"] and error_result["Data"] != 0:
            error_desc = DeviceErrorStatusFlags.get_description(error_result["Data"])
            print(f"设备错误信息:{error_desc}")
        # 清空错误码
        sdk.automation_clear_error_code()

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using CGXi_Sdk;
using System.IO;
using System.Runtime.InteropServices;
using System.Collections;
using System.Diagnostics;
using System.Threading;

namespace sdk_test_Csharp
{
    class Program
    {
        public static int robotHandle = -1;

        static void Main(string[] args)
        {
            CRresult result;
            //机器人创建连接
            result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("cr_create_robot" + ":" + result.ToString() + "\r\n");


            //典型demo使用示例
            api_demo_cr_move_joint();
            api_demo_cr_move_line();
            api_demo_cr_moveJog();
            api_demo_cr_get_tcpActualPose();
            api_demo_cr_get_currentTCPmsg();
            api_demo_cr_get_jointActualPos();
            api_demo_cr_get_stdDigitalOut();
            api_demo_cr_set_stdDigitalOut();
            api_demo_cr_get_boolRegValue();
            api_demo_cr_set_boolRegValue();
            api_demo_cr_kineForward();
            api_demo_cr_kineInverse();
            api_demo_cr_cfg_tcp_get();
            api_demo_cr_cfg_payload_get();

            //机器人断开连接
            result = CS.cr_destroy_robot(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("cr_destroy_robot" + ":" + result.ToString() + "\r\n");

            Console.WriteLine($"按下任意键退出。");
            Console.ReadKey();
        }

        //机器人关机
        static void api_demo_cr_shutdown()
        {
            CRresult result = CS.cr_shutdown(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //机械臂上电
        static void api_demo_cr_poweron()
        {
            CRresult result = CS.cr_poweron(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //机械臂断电
        static void api_demo_cr_poweroff()
        {
            CRresult result = CS.cr_poweroff(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //机械臂使能
        static void api_demo_cr_enable()
        {
            CRresult result = CS.cr_enable(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //机械臂关使能
        static void api_demo_cr_disable()
        {
            CRresult result = CS.cr_disable(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //机械臂故障复位
        static void api_demo_cr_FaultReset()
        {
            CRresult result = CS.cr_FaultReset(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //获取控制柜状态
        static void api_demo_cr_get_controlMode()
        {
            int controlmode = -1;
            CRresult result = CS.cr_get_controlMode(robotHandle, ref controlmode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(controlmode.ToString());
        }

        //写机械臂速度百分比
        static void api_demo_cr_set_robotSpeedPercent()
        {
            uint speedPercent = 20;
            CRresult result = CS.cr_set_robotSpeedPercent(robotHandle, speedPercent);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(speedPercent.ToString());
        }

        //读机械臂速度百分比
        static void api_demo_cr_get_robotSpeedPercent()
        {
            uint speedPercent = 1;
            CRresult result = CS.cr_get_robotSpeedPercent(robotHandle, ref speedPercent);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(speedPercent.ToString());
        }

        //获取SDK版本号
        static void api_demo_cr_get_sdk_version()
        {
            byte[] version = new byte[20];
            CRresult result = CS.cr_get_sdk_version(version);
            Debug.Assert(result == CRresult.sucess);
            string str = Encoding.UTF8.GetString(version);
            Console.WriteLine(str);
        }

        //获取机械臂状态数据
        static void api_demo_cr_get_robotStateData()
        {
            RobotStateData robotStateData = new RobotStateData();
            CRresult result = CS.cr_get_robotStateData(robotHandle, ref robotStateData);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("实际tcp位置：");
            for (int i = 0; i < 6; i++)
            {
                Console.Write(robotStateData.tcpActualPose[i].ToString());
                if (i < 5)
                    Console.Write(",");
            }
            Console.WriteLine("\n");
            Console.WriteLine("实际关节位置：");
            for (int i = 0; i < 6; i++)
            {
                Console.Write(robotStateData.jointActualPos[i].ToString());
                if (i < 5)
                    Console.Write(",");
            }
            Console.WriteLine("\n");
            Console.WriteLine("机械臂当前状态：" + robotStateData.robotMode.ToString());
            Console.WriteLine("机械臂运动状态：" + robotStateData.robotMoveStatus.ToString());
            Console.WriteLine("机械臂速度百分比：" + robotStateData.robotSpeedPercent.ToString());
            Console.WriteLine("控制器可配置数字输出：");
            for (int i = 0; i < 8; i++)
            {
                Console.Write(robotStateData.configurableDigitalOutput[i].ToString());
                if (i < 7)
                    Console.Write(",");
            }
            Console.WriteLine("\n");
        }

        //下载脚本程序
        static void api_demo_cr_downloadProgram()
        {
            string programfile = @"function mainFuncProgram()
                       --start robotConfig
                       TCP_1 = { 0,0,0,0,0,0 }
                       Payload_1= { 0,{0,0,0} }
                       set_tcp_payload(Payload_1[1], Payload_1[2])
                       --end robotConfig
                       function RobotProgram()
                       while (true)
                       do
                       --output: CDO_0 = true
                       set_standard_digital_out(0, true)
                       wait(1)  --sync
                       end
                       end
                       RobotProgram_CRresult result = task_create(RobotProgram)
                       function PauseFuncProgram()
                       while (true)
                       do
                       wait(100)  --sync
                       end
                       end
                       PauseFuncProgram_CRresult result = task_create(PauseFuncProgram)
                       end
                       mainFuncProgram_CRresult result = task_create(mainFuncProgram)";
            CRresult result = CS.cr_downloadProgram(robotHandle, programfile);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());

        }

        //下载脚本程序（加密）
        static void cr_downloadProgram()
        {
            string programfile = @"function mainFuncProgram()
                       --start robotConfig
                       TCP_1 = { 0,0,0,0,0,0 }
                       Payload_1= { 0,{0,0,0} }
                       set_tcp_payload(Payload_1[1], Payload_1[2])
                       --end robotConfig
                       function RobotProgram()
                       while (true)
                       do
                       --output: CDO_0 = true
                       set_standard_digital_out(0, true)
                       wait(1)  --sync
                       end
                       end
                       RobotProgram_Result = task_create(RobotProgram)
                       function PauseFuncProgram()
                       while (true)
                       do
                       wait(100)  --sync
                       end
                       end
                       PauseFuncProgram_Result = task_create(PauseFuncProgram)
                       end
                       mainFuncProgram_Result = task_create(mainFuncProgram)";
            CRresult result = CS.cr_downloadProgram(robotHandle, programfile);
            //加载程序
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());

        }

        //上传程序
        static void api_demo_cr_uploadProgram()
        {       
            byte[] programfile = new byte[1024 * 75 * 10];
            string str = "";
            CRresult result = CS.cr_uploadProgram(robotHandle, programfile);
            str = Encoding.UTF8.GetString(programfile);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(Encoding.UTF8.GetString(programfile));
        }

        //运行程序
        static void api_demo_cr_play()
        {            
            CRresult result = CS.cr_play(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //停止程序运行
        static void api_demo_cr_stop()
        {
            CRresult result = CS.cr_stop(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //暂停程序运行
        static void api_demo_cr_pause()
        {
            CRresult result = CS.cr_pause(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //读取脚本当前运行行号
        static void api_demo_cr_script_current_line_get()
        {
            int[] currentLine = new int[20];
            int lineLen = 0;
            CRresult result = CS.cr_script_current_line_get(robotHandle, currentLine, ref lineLen);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(currentLine[0].ToString());
        }

        //读脚本运行状态
        static void api_demo_cr_get_lua_scriptstatus()
        {
            Lua_ScriptStatus scriptstatus = Lua_ScriptStatus.lua_Script_load;
            CRresult result = CS.cr_get_lua_scriptstatus(robotHandle, ref scriptstatus);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(scriptstatus.ToString());
        }


        //工程文件上传
        static void api_demo_cr_uploadProject()
        {
            string FilePath = "../";
            string filename = "test";
            CRresult result = CS.cr_uploadProject(robotHandle, FilePath, filename);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //工程文件下载
        static void api_demo_cr_downloadProject()
        {
            string crpFilepathname = "../test.crp";
            string crscriptFilepathname = "../test.crscript";
            CRresult result = CS.cr_downloadProject(robotHandle, crpFilepathname, crscriptFilepathname);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //是否存在弹窗
        static void api_demo_cr_script_popup_exist()
        {
            bool hasPopup = false;
            CRresult result = CS.cr_script_popup_exist(robotHandle, ref hasPopup);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(hasPopup.ToString());
        }

        //读取弹窗信息
        static void api_demo_cr_script_popup_msg_get()
        {
            PopUpMsg popupMsg = new PopUpMsg();
            CRresult result = CS.cr_script_popup_msg_get(robotHandle, ref popupMsg);
            Debug.Assert(result == CRresult.sucess);
            string utf8String = Encoding.UTF8.GetString(popupMsg.var_data);
            Console.WriteLine(utf8String);
        }


        //设置输入弹窗信息
        static void api_demo_cr_script_popup_msg_set()
        {
            VariableMsg invarMsg = new VariableMsg();
            invarMsg.variableType = VariableType.LUA_TSTRING;
            invarMsg.variableID = 4;
            invarMsg.variableName = "abc213";
            invarMsg.stringValue = "This is Message";
            int size = Marshal.SizeOf(invarMsg);
            IntPtr ptr = Marshal.AllocHGlobal(size);
            Marshal.StructureToPtr(invarMsg, ptr, true);
            CRresult result = CS.cr_script_popup_msg_set(robotHandle, ptr);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(invarMsg.variableName);
            Marshal.FreeHGlobal(ptr);
        }

        //关闭弹窗
        static void api_demo_cr_script_popup_close()
        {
            
            CRresult result = CS.cr_script_popup_close(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //轴空间运动
        static void api_demo_cr_moveJ()
        {
            PointControlPara pointControlPara = new PointControlPara();
            pointControlPara.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlPara.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlPara.pose = new double[6] { -66, -438, 887, -57.34, 0, -149 };
            //在MoveJ中无影响
            pointControlPara.jointpos = new double[6] { 60, 60, -60, 60, 60, 60 };
            //目标点示例数据
            pointControlPara.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlPara.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlPara.jerk = new double[6] { 60, 60, 60, 60, 60, 60 };
            pointControlPara.tcpID = -1;
            pointControlPara.coordinateType = CoordinateType.jointCoordinate;
            pointControlPara.pointTransType = PointTransType.pointTransStop;
            pointControlPara.pointTransRadius = 0;
            pointControlPara.poseTranType = PoseTranType.poseTranMoveToTargetPose;
            pointControlPara.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CRresult result = CS.cr_moveJ(robotHandle, pointControlPara);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointControlPara.tcpID.ToString());
        }

        //轴空间运动
        static void api_demo_cr_move_joint()
        {
            PointControlParaSimple pointControlParaSimple = new PointControlParaSimple();
            PointControlPara pointControlPara = new PointControlPara();

            bool isBlock = true;
            pointControlParaSimple.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple.pose = new double[6] { -66, -438, 887, -57.34, 0, -149 };
            //在MoveJ中无影响
            pointControlParaSimple.jointpos = new double[6] { 60, 60, -60, 60, 60, 60 };
            //目标点示例数据
            pointControlParaSimple.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinateType = CoordinateType.jointCoordinate;
            pointControlParaSimple.pointTransType = PointTransType.pointTransStop;
            pointControlParaSimple.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);

            CRresult result = CS.cr_move_joint(robotHandle, pointControlPara, isBlock);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointControlPara.speed[0].ToString());
        }

        //直线运动
        static void api_demo_cr_moveL()
        {
            PointControlPara pointControlPara = new PointControlPara();
            pointControlPara.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlPara.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlPara.jointpos = new double[6] { 60, 60, -60, 60, 60, 60 };
            //起始点示例数据
            pointControlPara.pose = new double[6] { 0, -437, 887, -57.34, 0, -149 };
            //目标点示例数据           
            pointControlPara.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlPara.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlPara.jerk = new double[6] { 60, 60, 60, 60, 60, 60 };
            pointControlPara.tcpID = -1;
            pointControlPara.coordinateType = CoordinateType.baseCoordinate;
            pointControlPara.pointTransType = PointTransType.pointTransStop;
            pointControlPara.pointTransRadius = 0;
            pointControlPara.poseTranType = PoseTranType.poseTranMoveToTargetPose;
            pointControlPara.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CRresult result = CS.cr_moveL(robotHandle, pointControlPara);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointControlPara.tcpID.ToString());
        }

        //直线运动
        static void api_demo_cr_move_line()
        {
            PointControlPara pointControlPara = new PointControlPara();
            PointControlParaSimple pointControlParaSimple = new PointControlParaSimple();

            bool isBlock = true;
            pointControlParaSimple.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple.jointpos = new double[6] { 60, 60, -60, 60, 60, 60 };
            //起始点示例数据
            pointControlParaSimple.pose = new double[6] { 0, -437, 887, -57.34, 0, -149 };
            //目标点示例数据
            pointControlParaSimple.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinateType = CoordinateType.baseCoordinate;
            pointControlParaSimple.pointTransType = PointTransType.pointTransStop;
            pointControlParaSimple.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;

            CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
            CRresult result = CS.cr_move_line(robotHandle, pointControlPara, isBlock);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointControlPara.tcpID.ToString());
        }

        //点动运动
        static void api_demo_cr_moveJog()
        {
            PointControlPara pointControlPara = new PointControlPara();
            pointControlPara.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlPara.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlPara.pose = new double[6] { 0, 5, 0, 0, 0, 0 };//沿坐标系y轴运动5mm
            pointControlPara.jointpos = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlPara.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlPara.coordinatePose = new double[6] { 114.3, -390.498, 215.347, -180, 0, 0 };//点坐标系
            pointControlPara.jerk = new double[6] { 60, 60, 60, 60, 60, 60 };
            pointControlPara.tcpID = -1;
            pointControlPara.coordinateType = CoordinateType.PointCoordinate;//基于点坐标系进行点动
            pointControlPara.pointTransType = PointTransType.pointTransStop;
            pointControlPara.pointTransRadius = 0;
            pointControlPara.poseTranType = PoseTranType.poseTranMoveToTargetPose;
            pointControlPara.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CRresult result = CS.cr_moveJog(robotHandle, pointControlPara);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointControlPara.tcpID.ToString());
        }

        //圆弧运动
        static void api_demo_cr_move_circle()
        {
            //初始点
            PointControlParaSimple pointControlParaSimple0 = new PointControlParaSimple();
            PointControlPara pointControlPara0 = new PointControlPara();
            pointControlParaSimple0.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple0.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple0.pose = new double[6] { 0, 0, 0, 0, 0, 0 };
            //在MoveJ中无影响
            pointControlParaSimple0.jointpos = new double[6] { 60, 60, -60, 60, 60, 60 };
            //目标点示例数据
            pointControlParaSimple0.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple0.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple0.coordinateType = CoordinateType.jointCoordinate;
            pointControlParaSimple0.pointTransType = PointTransType.pointTransStop;
            pointControlParaSimple0.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple0, ref pointControlPara0);
            //过渡点
            PointControlParaSimple pointControlParaSimple1 = new PointControlParaSimple();
            PointControlPara pointControlPara1 = new PointControlPara();
            pointControlParaSimple1.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple1.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple1.jointpos = new double[6] { 60, 55, -65, 60, 60, 60 };
            //过渡点示例数据
            pointControlParaSimple1.pose = new double[6] { 0, 0, 0, 0, 0, 0 };
            CS.cr_kineForward(robotHandle, pointControlParaSimple1.jointpos, pointControlParaSimple1.pose);
            pointControlParaSimple1.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple1.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple1.coordinateType = CoordinateType.jointCoordinate;
            pointControlParaSimple1.pointTransType = PointTransType.pointTransStop;
            pointControlParaSimple1.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple1, ref pointControlPara1);
            //终点
            PointControlParaSimple pointControlParaSimple2 = new PointControlParaSimple();
            PointControlPara pointControlPara2 = new PointControlPara();
            pointControlParaSimple2.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple2.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple2.jointpos = new double[6] { 60, 50, -70, 60, 60, 60 };
            //终点示例数据
            pointControlParaSimple2.pose = new double[6] { 0, 0, 0, 0, 0, 0 };
            CS.cr_kineForward(robotHandle, pointControlParaSimple2.jointpos, pointControlParaSimple2.pose);
            pointControlParaSimple2.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple2.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple2.coordinateType = CoordinateType.jointCoordinate;
            pointControlParaSimple2.pointTransType = PointTransType.pointTransStop;
            pointControlParaSimple2.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple2, ref pointControlPara2);

            bool isBlock = true;
            PointControlParaList pointControlParaList = new PointControlParaList();
            pointControlParaList.pointcontrolpara = new PointControlPara[] { pointControlPara1, pointControlPara2 };

            pointControlParaList.fixedrot = 0;
            pointControlParaList.centralangle = 0;
            CS.cr_move_joint(robotHandle, pointControlPara0, isBlock);//运动到起始点
            CS.cr_move_circle(robotHandle, pointControlParaList, isBlock);
        }

        //运动控制
        static void api_demo_cr_moveControl()
        {
            MoveType moveType = MoveType.ImdStop;
            CRresult result = CS.cr_moveControl(robotHandle, moveType);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //设置阻塞移动中参数阈值
        static void api_demo_cr_move_block_threshold_set()
        {
            CRresult result = CS.cr_move_block_threshold_set(robotHandle, 0.05, 0.05);
            //将阻塞移动中的位姿阈值设置为0.05，关节阈值设置为0.05
            Debug.Assert(result == CRresult.sucess);
        }

        //PointControlParaSimple数据转换
        static void api_demo_cr_move_pointControlPara_transfer()
        {
            PointControlParaSimple pointControlParaSimple = new PointControlParaSimple();
            pointControlParaSimple.acc = new double[6] { 10, 10, 10, 10, 10, 10 };
            pointControlParaSimple.speed = new double[6] { 10, 10, 10, 10, 10, 10 };
            pointControlParaSimple.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinateType = CoordinateType.jointCoordinate;
            pointControlParaSimple.pose = new double[6] { 60, 60, -60, 60, 60, 60 };
            PointControlPara pointControlPara = new PointControlPara();
            CRresult result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointControlPara.pose[2].ToString());
        }

        //设置软件自由驱动启动
        static void api_demo_cr_set_softFreeDriveEnabled()
        {
            CRresult result = CS.cr_set_softFreeDriveEnabled(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //读机械臂运动状态
        static void api_demo_cr_get_robotMoveStatus()
        {
            int isRobotMoving = 1;
            CRresult result = CS.cr_get_robotMoveStatus(robotHandle, ref isRobotMoving);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(isRobotMoving.ToString());
        }

        //读取移动缓存区中移动指令的数量
        static void api_demo_cr_move_cache_num_get()
        {
            int cacheNum = 0;
            CRresult result = CS.cr_move_cache_num_get(robotHandle, ref cacheNum);
            Debug.Assert(result == CRresult.sucess);
        }

        //读实际TCP位置
        static void api_demo_cr_get_tcpActualPose()
        {
            double[] pose = new double[6];
            CRresult result = CS.cr_get_tcpActualPose(robotHandle, pose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pose[0].ToString());
        }

        //读目标TCP位置
        static void api_demo_cr_get_tcpTargetPose()
        {
            double[] pose = new double[6];
            CRresult result = CS.cr_get_tcpTargetPose(robotHandle, pose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pose[0].ToString());
        }

        //读实际TCP速度
        static void api_demo_cr_get_tcpActualSpeed()
        {
            double[] speed = new double[6];
            CRresult result = CS.cr_get_tcpActualSpeed(robotHandle, speed);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(speed[0].ToString());
        }

        //读目标TCP速度
        static void api_demo_cr_get_tcpTargetSpeed()
        {
            double[] speed = new double[6];
            CRresult result = CS.cr_get_tcpTargetSpeed(robotHandle, speed);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(speed[0].ToString());
        }

        //读实际TCP加速度
        static void api_demo_cr_get_tcpActualAcceleration()
        {
            double[] acceleration = new double[6];
            CRresult result = CS.cr_get_tcpActualAcceleration(robotHandle, acceleration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(acceleration[0].ToString());
        }

        //读当前使用的TCP偏移信息
        static void api_demo_cr_get_currentTCPmsg()
        {
            TCPMsg tcpMsg = new TCPMsg();
            CRresult result = CS.cr_get_currentTCPmsg(robotHandle, ref tcpMsg);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(tcpMsg.tcpName[0].ToString());
        }

        //读取当前使用负载信息
        static void api_demo_cr_get_currentPayloadmsg()
        {
            PayLoad payloadMsg = new PayLoad();
            CRresult result = CS.cr_get_currentPayloadmsg(robotHandle, ref payloadMsg);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(payloadMsg.toolPayload.ToString());
        }

        //读所有TCP偏移信息列表
        static void api_demo_cr_get_allTCPmsg()
        {
            TCPMsg[] tcpMsgList = new TCPMsg[20];
            int size = Marshal.SizeOf(typeof(TCPMsg));
            IntPtr ptr = Marshal.AllocHGlobal(size * 20);
            int validNumber = 0;
            CRresult result = CS.cr_get_allTCPmsg(robotHandle, ptr, ref validNumber);
            Debug.Assert(result == CRresult.sucess);
            for (int i = 0; i < validNumber; i++)
            {
                IntPtr ptr_s = ptr + i * size;
                tcpMsgList[i] = (TCPMsg)Marshal.PtrToStructure(ptr_s, typeof(TCPMsg));
            }
            Marshal.FreeHGlobal(ptr);
            Console.WriteLine(tcpMsgList[0].tcpOffset[0].ToString());
        }

        //读取所有负载信息
        static void api_demo_cr_get_allPayloadmsg()
        {
            PayLoad[] payloadMsgList = new PayLoad[20];
            int size = Marshal.SizeOf(typeof(PayLoad));
            IntPtr ptr = Marshal.AllocHGlobal(size * 20);
            int validNumber = 0;
            CRresult result = CS.cr_get_allPayloadmsg(robotHandle, ptr, ref validNumber); ;
            Debug.Assert(result == CRresult.sucess);
            for (int i = 0; i < validNumber; i++)
            {
                IntPtr ptr_s = ptr + i * size;
                payloadMsgList[i] = (PayLoad)Marshal.PtrToStructure(ptr_s, typeof(PayLoad));
            }
            Marshal.FreeHGlobal(ptr);
            Console.WriteLine(payloadMsgList[0].toolPayload.ToString());
        }

        //获取指定TCPoffset的位姿
        static void api_demo_cr_get_AssignTCP_Pose()
        {
            double[] dstTCPoffset = new double[6];
            dstTCPoffset[0] = 10;
            double[] dstPose = new double[6];
            CRresult result = CS.cr_get_AssignTCP_Pose(robotHandle, dstTCPoffset, dstPose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(dstPose[0].ToString());
        }


        //读实际关节位置
        static void api_demo_cr_get_jointActualPos()
        {
            double[] actualpos = new double[6];
            CRresult result = CS.cr_get_jointActualPos(robotHandle, actualpos);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(actualpos[0].ToString());
        }


        //读目标关节位置
        static void api_demo_cr_get_jointTargetPos()
        {
            double[] pos = new double[6];
            CRresult result = CS.cr_get_jointTargetPos(robotHandle, pos);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pos[0].ToString());
        }


        //读实际关节速度
        static void api_demo_cr_get_jointActualVelocity()
        {
            double[] velocity = new double[6];
            CRresult result = CS.cr_get_jointActualVelocity(robotHandle, velocity);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(velocity[0].ToString());
        }


        //读目标关节速度
        static void api_demo_cr_get_jointTargetVelocity()
        {
            double[] velocity = new double[6];
            CRresult result = CS.cr_get_jointTargetVelocity(robotHandle, velocity);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(velocity[0].ToString());
        }


        //读实际关节加速度
        static void api_demo_cr_get_jointActualAcceleration()
        {
            double[] acceleration = new double[6];
            CRresult result = CS.cr_get_jointActualAcceleration(robotHandle, acceleration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(acceleration[0].ToString());
        }


        //读目标关节加速度
        static void api_demo_cr_get_jointTargetAcceleration()
        {
            double[] acceleration = new double[6];
            CRresult result = CS.cr_get_jointTargetAcceleration(robotHandle, acceleration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(acceleration[0].ToString());
        }


        //读实际关节电机电流
        static void api_demo_cr_get_jointActualCurrent()
        {
            double[] current = new double[6];
            CRresult result = CS.cr_get_jointActualCurrent(robotHandle, current);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(current[0].ToString());
        }


        //读目标关节电机电流
        static void api_demo_cr_get_jointTargetCurrent()
        {
            double[] current = new double[6];
            CRresult result = CS.cr_get_jointTargetCurrent(robotHandle, current);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(current[0].ToString());
        }


        //读目标关节转矩
        static void api_demo_cr_get_jointTargetTorque()
        {
            double[] torque = new double[6];
            CRresult result = CS.cr_get_jointTargetTorque(robotHandle, torque);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(torque[0].ToString());
        }


        //读实际关节采集的母线电压
        static void api_demo_cr_get_jointActualVoltage()
        {
            double[] voltage = new double[6];
            CRresult result = CS.cr_get_jointActualVoltage(robotHandle, voltage);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(voltage[0].ToString());
        }


        //读关节温度
        static void api_demo_cr_get_jointTemperature()
        {
            double[] temperature = new double[6];
            CRresult result = CS.cr_get_jointTemperature(robotHandle, temperature);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(temperature[0].ToString());
        }


        //读关节模式
        static void api_demo_cr_get_jointMode()
        {
            JointModes[] jointMode = new JointModes[6];
            CRresult result = CS.cr_get_jointMode(robotHandle, jointMode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(jointMode[0].ToString());
        }


        //读取控制柜当前存在的轨迹索引
        static void api_demo_cr_path_all_index_get()
        {
            int[] allPathIndex = new int[11];
            int pathIndexLen = -1;
            CRresult result = CS.cr_path_all_index_get(robotHandle, allPathIndex, ref pathIndexLen);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pathIndexLen + "\r\n");
        }


        //上传轨迹
        static void api_demo_cr_path_upload()
        {
            PathData pathData = new PathData();
            pathData.pathPoints = new IntPtr();
            int size = Marshal.SizeOf(typeof(PathPoint));
            pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);
            PathPoint[] pathPoints = new PathPoint[10000];

            CRresult result = CS.cr_path_upload(robotHandle, 4, ref pathData);
            //上传索引为4的轨迹，使用前需判断索引为4的轨迹是否存在
            Debug.Assert(result == CRresult.sucess);
            for (int points_count = 0; points_count < 10000; points_count++)
            {
                IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                Console.WriteLine($"{points_count}");
            }
            Marshal.FreeHGlobal(pathData.pathPoints);
            Console.WriteLine(result + "\r\n");
        }


        //下载轨迹
        static void api_demo_cr_path_download()
        {
            PathDownloadData pathDownloadData = new PathDownloadData();
            pathDownloadData.pathData = new PathData();
            pathDownloadData.pathPara = new PathPara();

            pathDownloadData.pathData.pathPoints = new IntPtr();
            int size = Marshal.SizeOf(typeof(PathPoint));
            pathDownloadData.pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);

            //轨迹文件转换为轨迹数据，为指针开辟大小
            PathData pathData = new PathData();
            pathData.pathPoints = new IntPtr();
            pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);
            PathPoint[] pathPoints = new PathPoint[10000];

            string filePath = "D:/file/path.crpath";
            CRresult result = CS.cr_path_file2pathData(filePath, ref pathData);  //轨迹文件转换为轨迹数据
            Debug.Assert(result == CRresult.sucess);
            for (int points_count = 0; points_count < 10000; points_count++)//轨迹点指针内容转化
            {
                IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                Console.WriteLine($"{points_count}");
            }

            pathDownloadData.pathData.moveTime = pathData.moveTime;
            pathDownloadData.pathData.pathPointsNum = pathData.pathPointsNum;
            pathDownloadData.pathPara.index = 1; //轨迹下载参数设置
            pathDownloadData.pathPara.moveType = 1;

            for (int points_count = 0; points_count < 10000; points_count++)//将新的轨迹点位转回指针
            {
                Marshal.StructureToPtr(pathPoints[points_count], IntPtr.Add(pathDownloadData.pathData.pathPoints, points_count * size), false);
            }

            result = CS.cr_path_download(robotHandle, pathDownloadData);  //下载轨迹到索引1
            Debug.Assert(result == CRresult.sucess);
            Marshal.FreeHGlobal(pathDownloadData.pathData.pathPoints);
            Marshal.FreeHGlobal(pathData.pathPoints);

            Console.WriteLine(result + "\r\n");
        }


        //轨迹控制
        static void api_demo_cr_path_action()
        {
            PathData pathData = new PathData();
            pathData.pathPoints = new IntPtr();
            int size = Marshal.SizeOf(typeof(PathPoint));
            pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);
            PathPoint[] pathPoints = new PathPoint[10000];

            CRresult result = CS.cr_path_upload(robotHandle, 4, ref pathData);
            //上传索引为4的轨迹，使用前需判断索引为4的轨迹是否存在
            Debug.Assert(result == CRresult.sucess);


            for (int points_count = 0; points_count < 10000; points_count++)
            {
                IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                Console.WriteLine($"{points_count}");
            }

            PointControlParaSimple pointControlParaSimple = new PointControlParaSimple();
            //初始点简化运动参数
            PointControlPara pointControlPara = new PointControlPara();
            //初始点运动参数
            pointControlParaSimple.speed = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple.acc = new double[6] { 30, 30, 30, 30, 30, 30 };
            pointControlParaSimple.pose = new double[6] { pathPoints[0].pose[0],
                                                pathPoints[0].pose[1],
                                                pathPoints[0].pose[2],
                                                pathPoints[0].pose[3],
                                                pathPoints[0].pose[4],
                                                pathPoints[0].pose[5]};
            //初始点，但在MoveJ中无影响
            pointControlParaSimple.jointpos = new double[6] { pathPoints[0].jointpos[0],
                                                    pathPoints[0].jointpos[1],
                                                    pathPoints[0].jointpos[2],
                                                    pathPoints[0].jointpos[3],
                                                    pathPoints[0].jointpos[4],
                                                    pathPoints[0].jointpos[5]};
            //初始点关节角
            pointControlParaSimple.tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 };
            pointControlParaSimple.coordinateType = CoordinateType.jointCoordinate;
            pointControlParaSimple.pointTransType = PointTransType.pointTransStop;
            pointControlParaSimple.motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc;
            result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
            //PointControlParaSimple数据转换为PointControlPara
            Debug.Assert(result == CRresult.sucess);


            result = CS.cr_move_joint(robotHandle, pointControlPara, true);  //移动至第一个点位
            Debug.Assert(result == CRresult.sucess);

            Thread.Sleep(200);
            result = CS.cr_path_action(robotHandle, 4, 1);
            //启动轨迹索引为4的轨迹，使用前需判断索引为4的轨迹是否存在
            Debug.Assert(result == CRresult.sucess);

            Marshal.FreeHGlobal(pathData.pathPoints);


            Console.WriteLine(result + "\r\n");
        }


        //轨迹数据转换为轨迹文件
        static void api_demo_cr_path_pathData2file()
        {
            PathData pathData = new PathData();
            pathData.pathPoints = new IntPtr();
            int size = Marshal.SizeOf(typeof(PathPoint));
            pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);
            PathPoint[] pathPoints = new PathPoint[10000];

            CRresult result = CS.cr_path_upload(robotHandle, 4, ref pathData);
            //上传索引为4的轨迹，使用前需判断索引为4的轨迹是否存在
            Debug.Assert(result == CRresult.sucess);
            for (int points_count = 0; points_count < 10000; points_count++)
            {
                IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                Console.WriteLine($"{points_count}");
            }

            string filePath = "D:/file/path.crpath";
            result = CS.cr_path_pathData2file(pathData, filePath);
            Debug.Assert(result == CRresult.sucess);
            Marshal.FreeHGlobal(pathData.pathPoints);
            Console.WriteLine(result + "\r\n");
        }


        //轨迹文件转换为轨迹数据
        static void api_demo_cr_path_file2pathData()
        {
            PathData pathData = new PathData();
            pathData.pathPoints = new IntPtr();
            int size = Marshal.SizeOf(typeof(PathPoint));
            pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);
            PathPoint[] pathPoints = new PathPoint[10000];

            string filePath = "D:/file/path.crpath";
            CRresult result = CS.cr_path_file2pathData(filePath, ref pathData);  //轨迹文件转换为轨迹数据
            Debug.Assert(result == CRresult.sucess);

            for (int points_count = 0; points_count < 10000; points_count++)//轨迹点指针内容转化
            {
                IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                Console.WriteLine($"{points_count}");
            }
            Marshal.FreeHGlobal(pathData.pathPoints);

            Console.WriteLine(result + "\r\n");
        }


        //设置轨迹记录参数
        static void api_demo_cr_path_recordPara_set()
        {
            RecordPathPara recordPathPara = new RecordPathPara();
            recordPathPara.sampleTime = 2;
            recordPathPara.recordControl = 1;
            CRresult result = CS.cr_path_recordPara_set(robotHandle, recordPathPara);  //设置轨迹记录参数
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result + "\r\n");
        }


        //获取当前轨迹记录状态
        static void api_demo_cr_path_recordStatus_get()
        {
            PathRecordStatus pathRecordStatus = new PathRecordStatus();
            CRresult result = CS.cr_path_recordStatus_get(robotHandle, ref pathRecordStatus);
            //获取当前轨迹记录状
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result + "\r\n");
        }


        //获取当前轨迹运行状态
        static void api_demo_cr_path_currentRunStatus_get()
        {
            PathRunMsg pathRunMsg = new PathRunMsg();
            CRresult result = CS.cr_path_currentRunStatus_get(robotHandle, ref pathRunMsg);
            //获取当前轨迹运行状态
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result + "\r\n");
        }


        //读取控制柜硬件序列号
        static void api_demo_cr_get_productInfo()
        {
            byte[] productSn = new byte[20];
            CRresult result = CS.cr_get_productInfo(robotHandle, productSn);
            Debug.Assert(result == CRresult.sucess);
            string str = Encoding.UTF8.GetString(productSn);
            Console.WriteLine(str);
        }


        //读取整臂序列号
        static void api_demo_cr_get_productSn()
        {
            byte[] Sn = new byte[20];
            CRresult result = CS.cr_get_productSn(robotHandle, Sn);
            Debug.Assert(result == CRresult.sucess);
            string str = Encoding.UTF8.GetString(Sn);
            Console.WriteLine(str);
        }


        //获取版本信息
        static void api_demo_cr_get_sysVersion()
        {
            SysVersion version = new SysVersion();
            CRresult result = CS.cr_get_sysVersion(robotHandle, ref version);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(version.kzqVersion.versionNo.ToString());
        }

        //读机械臂DH参数
        static void api_demo_cr_get_DhParmeter()
        {
            double[] dhPara = new double[100];
            CRresult result = CS.cr_get_DhParmeter(robotHandle, dhPara);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(dhPara[0].ToString());
        }

        //读机械臂标准DH参数
        static void cr_get_DhParmeter()
        {
            double[] dhPara = new double[100];
            CRresult result = CS.cr_get_stdDhParmeter(robotHandle, dhPara);//读机械臂标准DH参数
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(dhPara[0].ToString());
        }

        //读机械臂动力学参数
        static void api_demo_cr_get_DynamicParmeter()
        {
            double[] dynamicPara = new double[100];
            CRresult result = CS.cr_get_DynamicParmeter(robotHandle, dynamicPara);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(dynamicPara[0].ToString());
        }


        //读机械臂零位补偿值
        static void api_demo_cr_get_zeroCompensationOffset()
        {
            double[] zeroCompensationOffset = new double[6];
            CRresult result = CS.cr_get_zeroCompensationOffset(robotHandle, zeroCompensationOffset);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(zeroCompensationOffset[0].ToString());
        }


        //读机械臂减速比
        static void api_demo_cr_get_reducerRatio()
        {
            double[] reducerRatio = new double[6];
            CRresult result = CS.cr_get_reducerRatio(robotHandle, reducerRatio);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(reducerRatio[0].ToString());
        }

        //读机械臂当前状态
        static void api_demo_cr_get_robotMode()
        {
            RobotModes robotMode = RobotModes.BackDrive;
            CRresult result = CS.cr_get_robotMode(robotHandle, ref robotMode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(robotMode.ToString());
        }


        //获取机械臂日志
        static void api_demo_cr_get_logMsgs()
        {
            int logMsgNumber = 0;
            IntPtr ptr = IntPtr.Zero;
            int size = Marshal.SizeOf(typeof(RobotLogMsg));
            ptr = Marshal.AllocHGlobal(size * 100);
            CRresult result = CS.cr_get_logMsgs(robotHandle, ptr, ref logMsgNumber);
            Debug.Assert(result == CRresult.sucess);
            RobotLogMsg[] logMsgs = new RobotLogMsg[logMsgNumber];
            for (int i = 0; i < logMsgNumber; i++)
            {
                IntPtr ptr_s = ptr + i * size;
                logMsgs[i] = (RobotLogMsg)Marshal.PtrToStructure(ptr_s, typeof(RobotLogMsg));
            }
            if (logMsgs.Length > 0)
            {
                byte[] tmp = new byte[100];
                int indexOfZero = Array.IndexOf(logMsgs[0].textMessage, (byte)0);
                Array.Copy(logMsgs[0].textMessage, tmp, indexOfZero == -1 ? logMsgs[0].textMessage.Length : indexOfZero);

                Console.WriteLine(Encoding.UTF8.GetString(tmp));
            }
            Marshal.FreeHGlobal(ptr);
        }


        //获取机械臂历史所有日志
        static void api_demo_cr_sys_history_log_get()
        {
            int logMsgNumber = 0;
            IntPtr ptr = IntPtr.Zero;
            int size = Marshal.SizeOf(typeof(RobotLogMsg));
            ptr = Marshal.AllocHGlobal(size * 3000);
            CRresult result = CS.cr_sys_history_log_get(robotHandle, ptr, ref logMsgNumber);
            Debug.Assert(result == CRresult.sucess);
            RobotLogMsg[] logMsgs = new RobotLogMsg[logMsgNumber];
            for (int i = 0; i < logMsgNumber; i++)
            {
                IntPtr ptr_s = ptr + i * size;
                logMsgs[i] = (RobotLogMsg)Marshal.PtrToStructure(ptr_s, typeof(RobotLogMsg));
            }
            if (logMsgs.Length > 0)
            {
                byte[] tmp = new byte[100];
                int indexOfZero = Array.IndexOf(logMsgs[0].textMessage, (byte)0);
                Array.Copy(logMsgs[0].textMessage, tmp, indexOfZero == -1 ? logMsgs[0].textMessage.Length : indexOfZero);

                Console.WriteLine(Encoding.UTF8.GetString(tmp));
            }
            Marshal.FreeHGlobal(ptr);
        }


        //日志功能是否开启
        static void api_demo_cr_log_enable()
        {
            bool enable = true;
            CRresult result = CS.cr_log_enable(enable);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //日志大小设置
        static void api_demo_cr_log_set_size()
        {
            long size = 10 * 1024 * 1024;
            int num = 10;
            CRresult result = CS.cr_log_set_size(size, num);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //读系统时间
        static void api_demo_cr_get_SystemDateTime()
        {
            byte[] systemDateTime = new byte[20];
            CRresult result = CS.cr_get_SystemDateTime(robotHandle, systemDateTime);
            Debug.Assert(result == CRresult.sucess);
            string str = Encoding.UTF8.GetString(systemDateTime);
            Console.WriteLine(str);
        }


        //读取机型型号
        static void api_demo_cr_sys_robotModel_get()
        {
            byte[] robotModel = new byte[10];
            CRresult result = CS.cr_sys_robotModel_get(robotHandle, robotModel, 10); //读机型型号
            Debug.Assert(result == CRresult.sucess);
            string str = Encoding.UTF8.GetString(robotModel);
            Console.WriteLine(str + "\r\n");
        }

        //读取控制器型号
        static void cr_get_controllerType()
        {
            byte[] controllerType = new byte[10];
            CRresult result = CS.cr_get_controllerType(robotHandle, controllerType);//读取控制器型号
            Debug.Assert(result == CRresult.sucess);
            string str = Encoding.UTF8.GetString(controllerType);
            Console.WriteLine(str + "\r\n");
        }

        //触发黑匣子数据
        static void api_demo_cr_sys_blackBoxData_trigger()
        {
            CRresult result = CS.cr_sys_blackBoxData_trigger(robotHandle); //触发黑匣子数据
            Debug.Assert(result == CRresult.sucess);
        }


        //读控制柜标准数字输出
        static void api_demo_cr_get_stdDigitalOut()
        {
            int val = 0;
            CRresult result = CS.cr_get_stdDigitalOut(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("DO_0:" + val + "\r\n");
        }


        //写控制柜标准数字输出
        static void api_demo_cr_set_stdDigitalOut()
        {
            int val = 1;
            CRresult result = CS.cr_set_stdDigitalOut(robotHandle, 0, val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("DO_0:" + val + "\r\n");
        }


        //读控制柜可配置数字输出
        static void api_demo_cr_get_configDigitalOut()
        {
            int val = 0;
            CRresult result = CS.cr_get_configDigitalOut(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("CO_0:" + val + "\r\n");
        }


        //写控制柜可配置数字输出
        static void api_demo_cr_set_configDigitalOut()
        {
            int val = 1;
            CRresult result = CS.cr_set_configDigitalOut(robotHandle, 0, val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("CO_0:" + val + "\r\n");
        }


        //读工具端数字输出
        static void api_demo_cr_get_toolDigitalOut()
        {
            int val = 0;
            CRresult result = CS.cr_get_toolDigitalOut(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("toolDO_0:" + val + "\r\n");
        }


        //写工具端数字输出
        static void api_demo_cr_set_toolDigitalOut()
        {
            int val = 1;
            CRresult result = CS.cr_set_toolDigitalOut(robotHandle, 0, val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("toolDO_0:" + val + "\r\n");
        }


        //读控制柜标准数字输入
        static void api_demo_cr_get_stdDigitalIn()
        {
            int val = 0;
            CRresult result = CS.cr_get_stdDigitalIn(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("DI_0:" + val + "\r\n");
        }


        //读控制柜可配置数字输入
        static void api_demo_cr_get_configDigitalIn()
        {
            int val = 0;
            CRresult result = CS.cr_get_configDigitalIn(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("CI_0:" + val + "\r\n");
        }


        //读工具端数字输入
        static void api_demo_cr_get_toolDigitalIn()
        {
            int val = 0;
            CRresult result = CS.cr_get_toolDigitalIn(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("toolDI_0:" + val + "\r\n");
        }

        //读控制柜模拟量输出
        static void api_demo_cr_get_stdAnalogOut()
        {
            double val = 0;
            CRresult result = CS.cr_get_stdAnalogOut(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("AO_0:" + val + "\r\n");
        }


        //写控制柜模拟量输出
        static void api_demo_cr_set_stdAnalogOut()
        {
            double val = 7;
            CRresult result = CS.cr_set_stdAnalogOut(robotHandle, 0, val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("AO_0:" + val + "\r\n");
        }


        //读工具端模拟量输入
        static void api_demo_cr_get_toolAnalogIn()
        {
            double val = 0;
            CRresult result = CS.cr_get_toolAnalogIn(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("toolAI_0:" + val + "\r\n");
        }


        //读控制柜模拟量输入
        static void api_demo_cr_get_stdAnalogIn()
        {
            double val = 0;
            CRresult result = CS.cr_get_stdAnalogIn(robotHandle, 0, ref val);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("AI_0:" + val + "\r\n");
        }


        //读机械臂控制柜和工具端上所有输入数字量和模拟量
        static void api_demo_cr_get_allDAInput()
        {
            int[] controllerDI = new int[8];
            int[] controllerCI = new int[8];
            double[] controllerAI = new double[3];
            int[] toolDI = new int[2];
            double[] toolAI = new double[2];
            CRresult result = CS.cr_get_allDAInput(robotHandle, controllerDI, controllerCI, controllerAI, toolDI, toolAI);
            Debug.Assert(result == CRresult.sucess);
            string controldi = "";
            string contrci = "";
            string contrai = "";
            string tooldi = "";
            string toolai = "";
            for (int i = 0; i < 8; i++)
            {
                controldi += controllerDI[i].ToString() + ',';
                contrci += controllerCI[i].ToString() + ',';
            }
            for (int i = 0; i < 3; i++)
            {
                contrai += controllerAI[i].ToString() + ',';
            }
            for (int i = 0; i < 2; i++)
            {
                tooldi += toolDI[i].ToString() + ',';
                toolai += toolAI[i].ToString() + ',';
            }
            Console.WriteLine("控制柜标准数字输入量 :  " + controldi + "\r\n");
            Console.WriteLine("控制柜可配置数字输入量 :  " + contrci + "\r\n");
            Console.WriteLine("控制柜模拟输入量 :  " + contrai + "\r\n");
            Console.WriteLine("工具端标准数字输入量 :  " + tooldi + "\r\n");
            Console.WriteLine("工具端模拟输入量 :  " + toolai + "\r\n");
        }


        //读机械臂控制柜和工具端上所有输出数字量和模拟量
        static void api_demo_cr_get_allDAOutput()
        {
            int[] controllerDO = new int[8];
            int[] controllerCO = new int[8];
            double[] controllerAO = new double[1];
            int[] toolDO = new int[2];
            CRresult result = CS.cr_get_allDAOutput(robotHandle, controllerDO, controllerCO, controllerAO, toolDO);
            Debug.Assert(result == CRresult.sucess);
            string controldo = "";
            string contrco = "";
            string contrao = controllerAO[0].ToString();
            string tooldo = "";
            for (int i = 0; i < 8; i++)
            {
                controldo += controllerDO[i].ToString() + ',';
                contrco += controllerCO[i].ToString() + ',';
            }
            for (int i = 0; i < 2; i++)
            {
                tooldo += toolDO[i].ToString() + ',';
            }

            Console.WriteLine("控制柜标准数字输出量 :  " + controldo + "\r\n");
            Console.WriteLine("控制柜可配置数字输出量 :  " + contrco + "\r\n");
            Console.WriteLine("控制柜模拟输出量 :  " + contrao + "\r\n");
            Console.WriteLine("工具端标准数字输出量 :  " + tooldo + "\r\n");
        }

        //读bool寄存器
        static void api_demo_cr_get_boolRegValue()
        {
            int[] regDat = new int[10];
            CRresult result = CS.cr_get_boolRegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //写bool寄存器
        static void api_demo_cr_set_boolRegValue()
        {
            int[] regDat = new int[10];
            regDat[0] = 1;
            regDat[1] = 1;
            regDat[2] = 1;
            CRresult result = CS.cr_set_boolRegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //读int16寄存器
        static void api_demo_cr_get_int16RegValue()
        {
            int[] regDat = new int[10];
            CRresult result = CS.cr_get_int16RegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //写int16寄存器
        static void api_demo_cr_set_int16RegValue()
        {
            int[] regDat = new int[10];
            regDat[0] = 1;
            regDat[1] = 1;
            regDat[2] = 1;
            CRresult result = CS.cr_set_int16RegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //读int32寄存器
        static void api_demo_cr_get_int32RegValue()
        {
            int[] regDat = new int[10];
            CRresult result = CS.cr_get_int32RegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //写int32寄存器
        static void api_demo_cr_set_int32RegValue()
        {
            int[] regDat = new int[10];
            regDat[0] = 1;
            regDat[1] = 1;
            regDat[2] = 1;
            CRresult result = CS.cr_set_int32RegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //读float寄存器
        static void api_demo_cr_get_floatRegValue()
        {
            float[] regDat = new float[10];
            CRresult result = CS.cr_get_floatRegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }


        //写float寄存器
        static void api_demo_cr_set_floatRegValue()
        {
            float[] regDat = new float[10];
            regDat[0] = -0.1f;
            regDat[1] = 0.1f;
            regDat[2] = 0.1f;
            CRresult result = CS.cr_set_floatRegValue(robotHandle, 0, 10, regDat);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(regDat[0].ToString());
        }

        //读安装变量
        static void api_demo_cr_get_intallVarValue()
        {
            IntPtr ptr = IntPtr.Zero;
            int size = Marshal.SizeOf(typeof(VariableMsg));
            ptr = Marshal.AllocHGlobal(size);
            string installVarName = "var_1";
            CRresult result = CS.cr_get_intallVarValue(robotHandle, installVarName, ptr);
            Debug.Assert(result == CRresult.sucess);
            VariableMsg installVar = (VariableMsg)Marshal.PtrToStructure(ptr, typeof(VariableMsg));
            Console.WriteLine(installVar.variableName);
            Marshal.FreeHGlobal(ptr);
        }

        //修改安装变量
        static void cr_get_intallVarValue()
        {
            VariableMsg variableMsg = new VariableMsg();
            variableMsg.numberValue = 1;
            variableMsg.variableType = VariableType.LUA_TNUMBER;
            variableMsg.variableName = "i_var_2";
            string installVarName = "i_var_1";
            int size = Marshal.SizeOf(variableMsg);
            IntPtr ptr = Marshal.AllocHGlobal(size);
            Marshal.StructureToPtr(variableMsg, ptr, true);
            CRresult result = CS.cr_set_installVarValue(robotHandle, installVarName, ptr);//修改安装变量
            VariableMsg installVar = (VariableMsg)Marshal.PtrToStructure(ptr, typeof(VariableMsg));
            Console.WriteLine(installVar.variableName);
            Marshal.FreeHGlobal(ptr);
        }

        //读取程序变量数据
        static void api_demo_cr_script_var_get()
        {
            byte[] varName = new byte[32];
            string str = "var_1";
            varName = Encoding.Default.GetBytes(str);
            IntPtr ptr = IntPtr.Zero;
            int size = Marshal.SizeOf(typeof(VariableMsg));
            ptr = Marshal.AllocHGlobal(size);
            CRresult result = CS.cr_script_var_get(robotHandle, varName, ptr);
            Debug.Assert(result == CRresult.sucess);
            VariableMsg variableMsg = (VariableMsg)Marshal.PtrToStructure(ptr, typeof(VariableMsg));
            Console.WriteLine(variableMsg.variableName[0].ToString());
            Marshal.FreeHGlobal(ptr);
        }


        //修改程序变量数据
        static void api_demo_cr_script_var_set()
        {
            VariableMsg variableMsg = new VariableMsg();
            variableMsg.variableName = "var_1";
            variableMsg.variableID = 2;
            variableMsg.variableType = VariableType.LUA_TNUMBER;
            variableMsg.numberValue = 1;
            int size = Marshal.SizeOf(variableMsg);
            IntPtr ptr = Marshal.AllocHGlobal(size);
            Marshal.StructureToPtr(variableMsg, ptr, true);
            CRresult result = CS.cr_script_var_set(robotHandle, ptr);
            //修改名称为var_1的程序变量的数据
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result:" + result + "variableName:" + variableMsg.variableName + "variableID:" + variableMsg.variableID + "\r\n");
        }


        //获取编码器计数数量
        static void api_demo_cr_get_encoderTickCnt()
        {
            int encoderChannel = 0;
            long encoderTickCount = 0;
            CRresult result = CS.cr_get_encoderTickCnt(robotHandle, encoderChannel, ref encoderTickCount); //获取编码器通道0的计数数量
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(encoderTickCount.ToString());
        }

        //设置监控界面的工具输出电压
        static void cr_set_ToolOutputVoltage()
        {
            ToolPower toolPower = ToolPower.Power_on;
            CRresult result = CS.cr_set_ToolOutputVoltage(robotHandle, toolPower);//设置监控界面的工具输出电压为24V
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(toolPower.ToString());
        }

        //读取监控界面的工具输出电压
        static void cr_get_ToolOutputVoltage()
        {
            ToolPower toolPower = ToolPower.Power_invaild;
            CRresult result = CS.cr_get_ToolOutputVoltage(robotHandle, ref toolPower);//读取监控界面的工具输出电压
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(toolPower.ToString());
        }

        //位姿转换
        static void api_demo_cr_poseTrans()
        {
            double[] poseFrom = new double[6];
            double[] poseTrans = new double[6];
            double[] poseTo = new double[6];
            poseFrom[0] = 1;
            poseFrom[1] = 2;
            poseFrom[2] = 3;
            poseTrans[0] = 4;
            poseTrans[1] = 4;
            poseTrans[2] = 4;
            CRresult result = CS.cr_poseTrans(poseFrom, poseTrans, poseTo);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(poseTo[0].ToString());
        }


        //位姿求逆
        static void api_demo_cr_compute_pose_inv()
        {
            double[] pose = new double[6] { -66, -438, 887, -57, 0, -148 };
            double[] poseInv = new double[6];
            CRresult result = CS.cr_compute_pose_inv(pose, 6, poseInv, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(poseInv[0].ToString());
        }


        //轴角转欧拉角
        static void api_demo_cr_AxisAngle2Eule()
        {
            double[] axisAnglePose = new double[6];
            double[] eulePose = new double[6];
            axisAnglePose[3] = 86.44;
            axisAnglePose[4] = 29.52;
            axisAnglePose[5] = 29.52;
            CRresult result = CS.cr_AxisAngle2Eule(axisAnglePose, eulePose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(eulePose[3].ToString());
        }


        //欧拉角转轴角
        static void api_demo_cr_Eule2AxisAngle()
        {
            double[] axisAnglePose = new double[6];
            double[] eulePose = new double[6];
            eulePose[3] = 90.00;
            eulePose[4] = 0;
            eulePose[5] = 37.71;
            CRresult result = CS.cr_Eule2AxisAngle(eulePose, axisAnglePose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(axisAnglePose[3].ToString());
        }


        //TCP位姿转法兰位姿
        static void api_demo_cr_TcpToFlangePose()
        {
            double[] tcpPose = new double[6] { 223, 240, 550, 23, 24, 55 };
            double[] toolPose = new double[6] { 22, 44, 55, 66, 77, 88 };
            double[] flangePose = new double[6];
            CRresult result = CS.cr_TcpToFlangePose(tcpPose, toolPose, flangePose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(flangePose[3].ToString());
        }


        //基坐标系下的位姿转到用户坐标系下
        static void api_demo_cr_compute_pose_base_to_user()
        {
            double[] basePose = new double[6] { -66, -438, 887, -57, 0, -148 };
            double[] userPose = new double[6] { 0, 0, 0, 0, 0, 0 };
            double[] poseInUser = new double[6];
            CRresult result = CS.cr_compute_pose_base_to_user(basePose, 6, userPose, 6, poseInUser, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(poseInUser[0].ToString());
        }

        //正解
        static void api_demo_cr_kineForward()
        {
            double[] srcJointPose = new double[6] { 60, 60, -60, 60, 60, 60 };
            double[] tarPose = new double[6];
            CRresult result = CS.cr_kineForward(robotHandle, srcJointPose, tarPose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(tarPose[3].ToString());
        }


        //逆解
        static void api_demo_cr_kineInverse()
        {
            double[] srcPose = new double[6] { -66.01, -438.24, 887.68, -57.34, 0, -148.98 };
            double[] refJointPose = new double[6] { 0, 0, 0, 0, 0, 0 };
            double[] tarJointPose = new double[6];
            CRresult result = CS.cr_kineInverse(robotHandle, srcPose, refJointPose, tarJointPose);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(tarJointPose[3].ToString());
        }

        //设置安装角度
        static void api_demo_cr_cfg_install_angle_set()
        {
            InstallAngle installAngle = new InstallAngle();
            installAngle.tiltAngle = 1;
            installAngle.baseAngle = 1;
            CRresult result = CS.cr_cfg_install_angle_set(robotHandle, installAngle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //读取安装角度
        static void api_demo_cr_cfg_install_angle_get()
        {
            InstallAngle installAngle = new InstallAngle();
            CRresult result = CS.cr_cfg_install_angle_get(robotHandle, ref installAngle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(installAngle.baseAngle.ToString());
            Console.WriteLine(installAngle.tiltAngle.ToString());
        }


        //读取TCP个数
        static void api_demo_cr_cfg_tcp_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_tcp_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(count.ToString());
        }


        //读取TCP数据
        static void api_demo_cr_cfg_tcp_get()
        {
            TCPMsg tcpMsg = new TCPMsg();
            tcpMsg.tcpOffset = new double[6];
            tcpMsg.tcpName = new char[20];
            CRresult result = CS.cr_cfg_tcp_get(robotHandle, 0, ref tcpMsg);
            Debug.Assert(result == CRresult.sucess);
            string TcpName = new string(tcpMsg.tcpName);
            Console.WriteLine(TcpName);
            Console.WriteLine(tcpMsg.tcpOffset[0].ToString());
        }


        //增加TCP
        static void api_demo_cr_cfg_tcp_add()
        {
            TCPMsg tcpMsg = new TCPMsg();
            tcpMsg.tcpOffset = new double[6];
            tcpMsg.tcpName = new char[20];
            tcpMsg.tcpName[0] = 'a';
            tcpMsg.tcpName[1] = '2';
            tcpMsg.tcpOffset[0] = 5;
            tcpMsg.tcpOffset[1] = 7;
            CRresult result = CS.cr_cfg_tcp_add(robotHandle, tcpMsg);
            Debug.Assert(result == CRresult.sucess);
            string TcpName = new string(tcpMsg.tcpName);
            Console.WriteLine(result.ToString());
            Console.WriteLine(TcpName);
            Console.WriteLine(tcpMsg.tcpOffset[0].ToString());
        }


        //删除TCP
        static void api_demo_cr_cfg_tcp_delete()
        {
            CRresult result = CS.cr_cfg_tcp_delete(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //编辑TCP数据
        static void api_demo_cr_cfg_tcp_set()
        {
            TCPMsg tcpMsg = new TCPMsg();
            tcpMsg.tcpOffset = new double[6];
            tcpMsg.tcpName = new char[20];
            tcpMsg.tcpName[0] = 'y';
            tcpMsg.tcpName[1] = '2';
            tcpMsg.tcpOffset[0] = 5;
            tcpMsg.tcpOffset[1] = 7;
            CRresult result = CS.cr_cfg_tcp_set(robotHandle, 1, tcpMsg);
            Debug.Assert(result == CRresult.sucess);
            string TcpName = new string(tcpMsg.tcpName);
            Console.WriteLine(result.ToString());
            Console.WriteLine(TcpName);
            Console.WriteLine(tcpMsg.tcpOffset[0].ToString());
        }


        //读取当前激活的TCP索引
        static void api_demo_cr_cfg_tcp_active_get()
        {
            int index = -1;
            CRresult result = CS.cr_cfg_tcp_active_get(robotHandle, ref index);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(index.ToString());
            Console.WriteLine(result.ToString());
        }


        //激活TCP
        static void api_demo_cr_cfg_tcp_active_set()
        {
            CRresult result = CS.cr_cfg_tcp_active_set(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //计算TCP位置
        static void api_demo_cr_compute_tcp_position()
        {
            double[,] poses = new double[,] {{ -36.10, -4.42, 32.62, 13.54, -91.33, 39.52 },
                                             { -35.98, -11.94, 43.92, 5.07, -94.74, 39.53 },
                                             { -61.76, -16.04, 34.85, 18.68, -80.13, 39.52 },
                                             { -121.26, -33.49, 38.20, 19.91, -51.68, 39.31 }};
            double[] position = new double[3];
            double err = 0;
            CRresult result = CS.cr_compute_tcp_position(poses, 4, position, 3, ref err);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(err.ToString());
        }


        //计算TCP角度
        static void api_demo_cr_compute_tcp_orientation()
        {
            double[] csPose = new double[6] { 0, 0, 0, 0, 0, 0 };
            double[] pointPose = new double[6] { -36.10, -4.42, 32.62, 13.54, -91.33, 39.52 };
            double[] orientation = new double[3];
            CRresult result = CS.cr_compute_tcp_orientation(csPose, 6, pointPose, 6, orientation, 3);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(orientation[0].ToString());
        }


        //读取负载个数
        static void api_demo_cr_cfg_payload_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_payload_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(count.ToString());
        }


        //读取负载数据
        static void api_demo_cr_cfg_payload_get()
        {
            PayLoad payLoad = new PayLoad();
            CRresult result = CS.cr_cfg_payload_get(robotHandle, 0, ref payLoad);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(payLoad.toolPayload.ToString());
            Console.WriteLine(payLoad.payloadName[0].ToString());
        }


        //增加负载
        static void api_demo_cr_cfg_payload_add()
        {
            PayLoad payLoad = new PayLoad();
            payLoad.payloadName = new char[20];
            payLoad.centerOfGravity = new double[3];
            payLoad.payloadName[0] = 'c';
            payLoad.payloadName[1] = '2';
            payLoad.centerOfGravity[0] = 8;
            CRresult result = CS.cr_cfg_payload_add(robotHandle, payLoad);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(payLoad.toolPayload.ToString());
            Console.WriteLine(payLoad.payloadName[0].ToString());
        }


        //删除负载
        static void api_demo_cr_cfg_payload_delete()
        {
            CRresult result = CS.cr_cfg_payload_delete(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }


        //编辑负载
        static void api_demo_cr_cfg_payload_set()
        {
            PayLoad payLoad = new PayLoad();
            payLoad.payloadName = new char[20];
            payLoad.centerOfGravity = new double[3];
            payLoad.payloadName[0] = 'o';
            payLoad.payloadName[1] = '2';
            payLoad.centerOfGravity[0] = 8;
            CRresult result = CS.cr_cfg_payload_set(robotHandle, 2, payLoad);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(payLoad.toolPayload.ToString());
            Console.WriteLine(payLoad.payloadName[0].ToString());
        }


        //读取当前激活负载索引
        static void api_demo_cr_cfg_payload_active_get()
        {
            int index = -1;
            CRresult result = CS.cr_cfg_payload_active_get(robotHandle, ref index);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(index.ToString());
            Console.WriteLine(result.ToString());
        }


        //激活负载
        static void api_demo_cr_cfg_payload_active_set()
        {
            CRresult result = CS.cr_cfg_payload_active_set(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //设置初始位
        static void api_demo_cr_cfg_home_pose_set()
        {
            double[] homePose = new double[6];
            homePose[0] = 1;
            homePose[1] = 1;
            CRresult result = CS.cr_cfg_home_pose_set(robotHandle, homePose, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(homePose[0].ToString());
        }

        //读取初始位
        static void api_demo_cr_cfg_home_pose_get()
        {
            double[] homePose = new double[6];
            CRresult result = CS.cr_cfg_home_pose_get(robotHandle, homePose, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(homePose[0].ToString());
        }

        //删除初始位
        static void api_demo_cr_cfg_home_pose_delete()
        {
            CRresult result = CS.cr_cfg_home_pose_delete(robotHandle);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //读取包装位
        static void api_demo_cr_cfg_pack_pose_get()
        {
            double[] packPose = new double[6];
            CRresult result = CS.cr_cfg_pack_pose_get(robotHandle, packPose, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(packPose[0].ToString());
        }

        //设置机器人是否自动上电使能
        static void api_demo_cr_cfg_poweron_auto_set()
        {
            int isAuto = 1;
            CRresult result = CS.cr_cfg_poweron_auto_set(robotHandle, isAuto);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(isAuto.ToString());
        }

        //读取机器人自动上电状态
        static void api_demo_cr_cfg_poweron_auto_get()
        {
            int isAuto = -1;
            CRresult result = CS.cr_cfg_poweron_auto_get(robotHandle, ref isAuto);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(isAuto.ToString());
        }

        //设置机器人拖动阻尼
        static void cr_cfg_joint_drag_damping_set()
        {
            int[] doubjointDargDamping = new int[6] { 0, 0, 0, 0, 0, 0 };
            CRresult result = CS.cr_cfg_joint_drag_damping_set(robotHandle, doubjointDargDamping, 6); //读取机器人拖动阻尼
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(doubjointDargDamping.ToString());
        }

        //读取机器人拖动阻尼
        static void cr_cfg_joint_drag_damping_get()
        {
            int[] doubjointDargDamping = new int[6] { 100, 100, 100, 100, 100, 100 };
            CRresult result = CS.cr_cfg_joint_drag_damping_set(robotHandle, doubjointDargDamping, 6); //设置机器人拖动阻尼
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(doubjointDargDamping.ToString());
        }

        //设置限制模式
        static void api_demo_cr_cfg_safety_limit_type_set()
        {
            SafetyLimitsValuesType safetyLimitsValuesType = SafetyLimitsValuesType.LimitLevel_3;
            CRresult result = CS.cr_cfg_safety_limit_type_set(robotHandle, safetyLimitsValuesType);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(safetyLimitsValuesType.ToString());
        }

        //读取限制模式
        static void api_demo_cr_cfg_safety_limit_type_get()
        {
            SafetyLimitsValuesType safetyLimitsValuesType = SafetyLimitsValuesType.LimitLevel_2;
            CRresult result = CS.cr_cfg_safety_limit_type_get(robotHandle, ref safetyLimitsValuesType);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(safetyLimitsValuesType.ToString());
        }

        //设置自定义模式下参数
        static void api_demo_cr_cfg_safety_limit_para_set()
        {
            SafetyLimitsValues safetyLimitsValues = new SafetyLimitsValues();
            SafetyLimitsMode mode = SafetyLimitsMode.mode_Reduced;
            safetyLimitsValues.maxTcpSpeed = 100;
            CRresult result = CS.cr_cfg_safety_limit_para_set(robotHandle, mode, safetyLimitsValues);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //读取自定义模式下参数
        static void api_demo_cr_cfg_safety_limit_para_get()
        {
            SafetyLimitsValues safetyLimitsValues = new SafetyLimitsValues();
            SafetyLimitsMode mode = SafetyLimitsMode.mode_Reduced;
            CRresult result = CS.cr_cfg_safety_limit_para_get(robotHandle, mode, ref safetyLimitsValues);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyLimitsValues.maxTcpSpeed.ToString());
        }

        //设置碰撞后处理方式
        static void api_demo_cr_cfg_safety_collihandle_type_set()
        {
            SafetyCollisionHandleMode safetyCollisionHandleMode = new SafetyCollisionHandleMode();
            safetyCollisionHandleMode = SafetyCollisionHandleMode.Collision_EnterReboundMode;
            CRresult result = CS.cr_cfg_safety_collihandle_type_set(robotHandle, safetyCollisionHandleMode);
            Debug.Assert(result == CRresult.sucess);
        }

        //读取碰撞后处理方式
        static void api_demo_cr_cfg_safety_collihandle_type_get()
        {
            SafetyCollisionHandleMode safetyCollisionHandleMode = new SafetyCollisionHandleMode();
            CRresult result = CS.cr_cfg_safety_collihandle_type_get(robotHandle, ref safetyCollisionHandleMode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("碰撞后处理方式:" + safetyCollisionHandleMode.ToString());
        }

        //设置关节限值
        static void api_demo_cr_cfg_safety_joint_limit_set()
        {
            SafetyLimitsJointAngle safetyLimitJoint = new SafetyLimitsJointAngle();
            SafetyLimitsMode mode = SafetyLimitsMode.mode_Reduced;
            safetyLimitJoint.maxJointPosition = 200;
            safetyLimitJoint.minJointPosition = -200;
            safetyLimitJoint.maxJointSpeed = 150;
            CRresult result = CS.cr_cfg_safety_joint_limit_set(robotHandle, mode, 1, safetyLimitJoint);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyLimitJoint.maxJointPosition.ToString());
            Console.WriteLine(safetyLimitJoint.minJointPosition.ToString());
        }

        //读取关节限值
        static void api_demo_cr_cfg_safety_joint_limit_get()
        {
            SafetyLimitsJointAngle safetyLimitJoint = new SafetyLimitsJointAngle();
            SafetyLimitsMode mode = SafetyLimitsMode.mode_Normal;
            CRresult result = CS.cr_cfg_safety_joint_limit_get(robotHandle, mode, 3, ref safetyLimitJoint);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyLimitJoint.maxJointPosition.ToString());
            Console.WriteLine(safetyLimitJoint.maxJointSpeed.ToString());
        }

        //读取安全平面个数
        static void api_demo_cr_cfg_safety_plane_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_safety_plane_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(count.ToString());
        }

        //读取安全平面信息
        static void api_demo_cr_cfg_safety_plane_get()
        {
            SafetyLimitsBoundaryPlane safetyLimitsBoundaryPlane = new SafetyLimitsBoundaryPlane();
            CRresult result = CS.cr_cfg_safety_plane_get(robotHandle, 2, ref safetyLimitsBoundaryPlane);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyLimitsBoundaryPlane.id.ToString());
            Console.WriteLine(safetyLimitsBoundaryPlane.name[0].ToString());
        }

        //增加安全平面
        static void api_demo_cr_cfg_safety_plane_add()
        {
            SafetyLimitsBoundaryPlane safetyLimitsBoundaryPlane = new SafetyLimitsBoundaryPlane();
            safetyLimitsBoundaryPlane.name = new char[32];
            string name = "asdfv22";
            char[] str = name.ToCharArray();
            for (int i = 0; i < str.Length; i++)
            {
                safetyLimitsBoundaryPlane.name[i] = str[i];
            }
            safetyLimitsBoundaryPlane.id = 4;
            CRresult result = CS.cr_cfg_safety_plane_add(robotHandle, safetyLimitsBoundaryPlane);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyLimitsBoundaryPlane.id.ToString());
        }

        //删除安全平面
        static void api_demo_cr_cfg_safety_plane_delete()
        {
            CRresult result = CS.cr_cfg_safety_plane_delete(robotHandle, 5);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //修改安全平面数据
        static void api_demo_cr_cfg_safety_plane_set()
        {
            SafetyLimitsBoundaryPlane safetyLimitsBoundaryPlane = new SafetyLimitsBoundaryPlane();
            safetyLimitsBoundaryPlane.name = new char[32];
            string name = "yyyyyybafv22";
            char[] str = name.ToCharArray();
            for (int i = 0; i < str.Length; i++)
            {
                safetyLimitsBoundaryPlane.name[i] = str[i];
            }
            safetyLimitsBoundaryPlane.id = 0;
            CRresult result = CS.cr_cfg_safety_plane_set(robotHandle, 2, safetyLimitsBoundaryPlane);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyLimitsBoundaryPlane.id.ToString());
        }

        //设置可配置输入信号
        static void api_demo_cr_cfg_safety_io_input_set()
        {
            SafetyIOInput safetyinput = SafetyIOInput.emergencyStop;
            CRresult result = CS.cr_cfg_safety_io_input_set(robotHandle, 1, safetyinput);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyinput.ToString());
        }

        //读取可配置输入信号
        static void api_demo_cr_cfg_safety_io_input_get()
        {
            SafetyIOInput safetyinput = SafetyIOInput.emergencyStop;
            CRresult result = CS.cr_cfg_safety_io_input_get(robotHandle, 1, ref safetyinput);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyinput.ToString());
        }

        //设置可配置输出信号
        static void api_demo_cr_cfg_safety_io_output_set()
        {
            SafetyIOOutput safetyoutput = SafetyIOOutput.robotMoving;
            CRresult result = CS.cr_cfg_safety_io_output_set(robotHandle, 2, safetyoutput);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyoutput.ToString());
        }

        //读取可配置输出信号
        static void api_demo_cr_cfg_safety_io_output_get()
        {
            SafetyIOOutput safetyoutput = SafetyIOOutput.robotMoving;
            CRresult result = CS.cr_cfg_safety_io_output_get(robotHandle, 1, ref safetyoutput);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(safetyoutput.ToString());
        }

        //设置是否启用示教器
        static void api_demo_cr_cfg_safety_tp_use_set()
        {
            bool isUse = false;
            CRresult result = CS.cr_cfg_safety_tp_use_set(robotHandle, isUse);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(isUse.ToString());
        }

        //读取当前是否启用示教器
        static void api_demo_cr_cfg_safety_tp_use_get()
        {
            bool isUse = true;
            CRresult result = CS.cr_cfg_safety_tp_use_get(robotHandle, ref isUse);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(isUse.ToString());
        }

        //设置数字输入信号配置
        static void api_demo_cr_cfg_var_di_set()
        {
            IOInputConfiguration inputConfiguration = new IOInputConfiguration();
            VarDigitialIOType type = VarDigitialIOType.Digitial;
            InputAction inputActions = InputAction.InputAction_NONE;
            inputConfiguration.inputActions = inputActions;
            inputConfiguration.inputFilteringTime = 1;
            inputConfiguration.inputName = new char[32];
            inputConfiguration.inputName[0] = 'a';
            inputConfiguration.inputName[1] = '1';
            CRresult result = CS.cr_cfg_var_di_set(robotHandle, type, 1, inputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(inputConfiguration.inputFilteringTime.ToString());
        }

        //读取数字输入信号配置
        static void api_demo_cr_cfg_var_di_get()
        {
            IOInputConfiguration inputConfiguration = new IOInputConfiguration();
            VarDigitialIOType type = VarDigitialIOType.Digitial;
            CRresult result = CS.cr_cfg_var_di_get(robotHandle, type, 1, ref inputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(inputConfiguration.inputFilteringTime.ToString());
        }

        //设置数字输出信号配置
        static void api_demo_cr_cfg_var_do_set()
        {
            VarDigitialIOType type = VarDigitialIOType.Digitial;
            int index = 1;
            IOOutputConfiguration outputConfiguration = new IOOutputConfiguration();
            outputConfiguration.outputName = new char[32];
            outputConfiguration.outputActions = OutputAction.OutputAction_RobotON_LOW;
            string name = "digital";
            char[] str = name.ToCharArray();
            for (int i = 0; i < str.Length; i++)
            {
                outputConfiguration.outputName[i] = str[i];
            }
            outputConfiguration.outputOptions = OutputOptions.OutputOptions_Enable;
            outputConfiguration.outputRule = OutputRule.OutputRule_Disable;
            CRresult result = CS.cr_cfg_var_do_set(robotHandle, type, index, outputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(outputConfiguration.outputName[0].ToString());
        }

        //读取数字输出信号配置
        static void api_demo_cr_cfg_var_do_get()
        {
            IOOutputConfiguration outputConfiguration = new IOOutputConfiguration();
            VarDigitialIOType type = VarDigitialIOType.Digitial;
            CRresult result = CS.cr_cfg_var_do_get(robotHandle, type, 1, ref outputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(outputConfiguration.outputName[0].ToString());
            Console.WriteLine(type.ToString());
        }

        //设置模拟量输入信号类型
        static void api_demo_cr_cfg_var_ai_set()
        {
            AnalogInputConfiguration analogInputConfiguration = new AnalogInputConfiguration();
            AnalogType analogInputType = AnalogType.Current;
            VarDigitialIOType type = VarDigitialIOType.Analog;
            analogInputConfiguration.analogInputType = analogInputType;
            analogInputConfiguration.analogInputName = new char[32];
            analogInputConfiguration.analogInputName[0] = 'a';
            analogInputConfiguration.analogInputName[1] = '1';
            CRresult result = CS.cr_cfg_var_ai_set(robotHandle, type, 1, analogInputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(analogInputConfiguration.analogInputName[0].ToString());
            Console.WriteLine(type.ToString());
        }

        //读取模拟量输入信号类型
        static void api_demo_cr_cfg_var_ai_get()
        {
            AnalogInputConfiguration analogInputConfiguration = new AnalogInputConfiguration();
            VarDigitialIOType type = VarDigitialIOType.Analog;
            CRresult result = CS.cr_cfg_var_ai_get(robotHandle, type, 1, ref analogInputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(analogInputConfiguration.analogInputName[0].ToString());
            Console.WriteLine(type.ToString());
        }

        //设置模拟量输出信号类型
        static void api_demo_cr_cfg_var_ao_set()
        {
            AnalogOutputConfiguration analogOutputConfiguration = new AnalogOutputConfiguration();
            AnalogType analogOutputType = AnalogType.Voltage;
            analogOutputConfiguration.analogOutputType = analogOutputType;
            analogOutputConfiguration.analogOutputName = new char[32];
            analogOutputConfiguration.analogOutputName[0] = 'a';
            analogOutputConfiguration.analogOutputName[1] = '1';
            CRresult result = CS.cr_cfg_var_ao_set(robotHandle, 0, analogOutputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(analogOutputConfiguration.analogOutputName[0].ToString());
            Console.WriteLine(analogOutputConfiguration.analogOutputType.ToString());
        }

        //读取模拟量输出信号类型
        static void api_demo_cr_cfg_var_ao_get()
        {
            AnalogOutputConfiguration analogOutputConfiguration = new AnalogOutputConfiguration();
            CRresult result = CS.cr_cfg_var_ao_get(robotHandle, 0, ref analogOutputConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(analogOutputConfiguration.analogOutputName[0].ToString());
            Console.WriteLine(analogOutputConfiguration.analogOutputType.ToString());
        }

        //设置工具电压输出值
        static void api_demo_cr_cfg_var_to_set()
        {
            ToolPower toolPower = ToolPower.Power_on;
            CRresult result = CS.cr_cfg_var_to_set(robotHandle, toolPower);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(toolPower.ToString());
        }

        //读取工具电压输出值
        static void api_demo_cr_cfg_var_to_get()
        {
            ToolPower toolPower = ToolPower.Power_on;
            CRresult result = CS.cr_cfg_var_to_get(robotHandle, ref toolPower);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(toolPower.ToString());
        }

        //设置位寄存器配置
        static void api_demo_cr_cfg_var_bit_reg_set()
        {
            int index = 1;
            BitRegisterConfiguration bitRegisterConfiguration = new BitRegisterConfiguration();
            bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName = new char[32];
            bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterInputActions = InputAction.InputAction_NONE;
            bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputActions = OutputAction.OutputAction_RobotON_HIGH;
            bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputRule = OutputRule.OutputRule_Disable;
            string name = "WEI";
            char[] str = name.ToCharArray();
            for (int i = 0; i < str.Length; i++)
            {
                bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName[i] = str[i];
            }
            CRresult result = CS.cr_cfg_var_bit_reg_set(robotHandle, index, bitRegisterConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName[0].ToString());
            Console.WriteLine(bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputActions.ToString());
        }

        //读取位寄存器配置
        static void api_demo_cr_cfg_var_bit_reg_get()
        {
            BitRegisterConfiguration bitRegisterConfiguration = new BitRegisterConfiguration();
            CRresult result = CS.cr_cfg_var_bit_reg_get(robotHandle, 1, ref bitRegisterConfiguration);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterName[0].ToString());
            Console.WriteLine(bitRegisterConfiguration.GeneralPurposeBOOLeanRegisterOutputActions.ToString());
        }

        //设置16位整数寄存器变量名
        static void api_demo_cr_cfg_var_int16_reg_name_set()
        {
            byte[] name = new byte[32];
            string str = "a22";
            name = Encoding.Default.GetBytes(str);
            CRresult result = CS.cr_cfg_var_int16_reg_name_set(robotHandle, 5, name, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("int16：" + Encoding.UTF8.GetString(name) + "\r\n");
        }

        //读取16位整数寄存器变量名
        static void api_demo_cr_cfg_var_int16_reg_name_get()
        {
            byte[] name = new byte[32];
            CRresult result = CS.cr_cfg_var_int16_reg_name_get(robotHandle, 1, name, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("int16：" + Encoding.UTF8.GetString(name) + "\r\n");
        }

        //设置32位整数寄存器变量名
        static void api_demo_cr_cfg_var_int32_reg_name_set()
        {
            byte[] name = new byte[32];
            string str = "k22";
            name = Encoding.Default.GetBytes(str);
            CRresult result = CS.cr_cfg_var_int32_reg_name_set(robotHandle, 2, name, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("int32：" + Encoding.UTF8.GetString(name) + "\r\n");
        }

        //读取32位整数寄存器变量名
        static void api_demo_cr_cfg_var_int32_reg_name_get()
        {
            byte[] name = new byte[32];
            CRresult result = CS.cr_cfg_var_int32_reg_name_get(robotHandle, 1, name, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("int32：" + Encoding.UTF8.GetString(name) + "\r\n");
        }

        //设置浮点寄存器变量名
        static void api_demo_cr_cfg_var_float_reg_name_set()
        {
            byte[] name = new byte[32];
            string str = "asda342";
            name = Encoding.Default.GetBytes(str);
            CRresult result = CS.cr_cfg_var_float_reg_name_set(robotHandle, 2, name, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("float：" + Encoding.UTF8.GetString(name) + "\r\n");
        }

        //读取浮点寄存器变量名
        static void api_demo_cr_cfg_var_float_reg_name_get()
        {
            byte[] name = new byte[32];
            CRresult result = CS.cr_cfg_var_float_reg_name_get(robotHandle, 1, name, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("float：" + Encoding.UTF8.GetString(name) + "\r\n");
        }

        //读取安装变量个数
        static void api_demo_cr_cfg_var_install_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_var_install_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(count.ToString());
        }

        //读取安装变量数据
        static void api_demo_cr_cfg_var_install_get()
        {
            IntPtr ptr = IntPtr.Zero;
            int size = Marshal.SizeOf(typeof(VariableMsg));
            ptr = Marshal.AllocHGlobal(size);
            CRresult result = CS.cr_cfg_var_install_get(robotHandle, 1, ptr);
            Debug.Assert(result == CRresult.sucess);
            VariableMsg variableMsg = (VariableMsg)Marshal.PtrToStructure(ptr, typeof(VariableMsg));
            Console.WriteLine(variableMsg.variableName[0].ToString());
            Console.WriteLine(variableMsg.variableID.ToString());
        }

        //增加安装变量
        static void api_demo_cr_cfg_var_install_add()
        {
            VariableMsg variableMsg = new VariableMsg();
            variableMsg.variableName = "bbbbb";
            variableMsg.variableID = 3;
            variableMsg.variableType = VariableType.LUA_TNUMBER;
            variableMsg.numberValue = 1;
            int size = Marshal.SizeOf(variableMsg);
            IntPtr ptr = Marshal.AllocHGlobal(size);
            Marshal.StructureToPtr(variableMsg, ptr, true);
            CRresult result = CS.cr_cfg_var_install_add(robotHandle, ptr);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("cr_set_intallVarValue;" + "result:" + result + "variableName:" + variableMsg.variableName + "variableID:" + variableMsg.variableID + "\r\n");
            Marshal.FreeHGlobal(ptr);
        }

        //删除安装变量
        static void api_demo_cr_cfg_var_install_delete()
        {
            CRresult result = CS.cr_cfg_var_install_delete(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //修改安装变量
        static void api_demo_cr_cfg_var_install_set()
        {
            VariableMsg variableMsg = new VariableMsg();
            variableMsg.variableName = "yyyyyyyyb";
            variableMsg.variableID = 2;
            variableMsg.variableType = VariableType.LUA_TNUMBER;
            variableMsg.numberValue = 1;
            int size = Marshal.SizeOf(variableMsg);
            IntPtr ptr = Marshal.AllocHGlobal(size);
            Marshal.StructureToPtr(variableMsg, ptr, true);
            CRresult result = CS.cr_cfg_var_install_set(robotHandle, 1, ptr);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("cr_set_intallVarValue;" + "result:" + result + "variableName:" + variableMsg.variableName + "variableID:" + variableMsg.variableID + "\r\n");
            Marshal.FreeHGlobal(ptr);
        }

        //读取点坐标系个数
        static void api_demo_cr_cfg_cs_point_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_cs_point_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(count.ToString());
        }

        //读取点坐标系数据
        static void api_demo_cr_cfg_cs_point_get()
        {
            PointCSNode pointCSNode = new PointCSNode();
            CRresult result = CS.cr_cfg_cs_point_get(robotHandle, 2, ref pointCSNode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointCSNode.name[0].ToString());
        }

        //增加点坐标系
        static void api_demo_cr_cfg_cs_point_add()
        {
            PointCSNode pointcsnode;

            pointcsnode.point.toolAxisAngle = new double[6] { 1.8, 2.09, 90, 34.00, -90, 0 };
            pointcsnode.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolPosition);
            pointcsnode.id = 1;

            char[] str = ("point1").ToCharArray();
            pointcsnode.name = new char[32];
            for (int i = 0; i < str.Length; i++)
            {
                pointcsnode.name[i] = str[i];
            }

            int res = (int)CS.cr_compute_cs_point(pointcsnode.point.toolPosition, 6, pointcsnode.point.toolPosition, 6);
            if (res == 0)
            {
                pointcsnode.isValid = 1;
            }
            else
                pointcsnode.isValid = 0;

            CS.cr_kineInverse(robotHandle, pointcsnode.point.toolPosition, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolAxisAngle);

            CRresult result = CS.cr_cfg_cs_point_add(robotHandle, pointcsnode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
            Console.WriteLine("\r\n");
            Console.WriteLine(pointcsnode.name[2].ToString());
        }

        //删除点坐标系
        static void api_demo_cr_cfg_cs_point_delete()
        {
            CRresult result = CS.cr_cfg_cs_point_delete(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //修改点坐标系数据
        static void api_demo_cr_cfg_cs_point_set()
        {
            PointCSNode pointcsnode;

            pointcsnode.point.toolAxisAngle = new double[6] { 1.8, 2.09, 90, 34.00, -90, 0 };
            pointcsnode.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolPosition);
            pointcsnode.id = 1;

            char[] str = ("point1").ToCharArray();
            pointcsnode.name = new char[32];
            for (int i = 0; i < str.Length; i++)
            {
                pointcsnode.name[i] = str[i];
            }

            int res = (int)CS.cr_compute_cs_point(pointcsnode.point.toolPosition, 6, pointcsnode.point.toolPosition, 6);
            if (res == 0)
            {
                pointcsnode.isValid = 1;
            }
            else
                pointcsnode.isValid = 0;

            CS.cr_kineInverse(robotHandle, pointcsnode.point.toolPosition, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolAxisAngle);
            CRresult result = CS.cr_cfg_cs_point_set(robotHandle, 1, pointcsnode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
            Console.WriteLine("\r\n");
            Console.WriteLine(pointcsnode.name[2].ToString());
        }

        //读取线坐标系个数
        static void api_demo_cr_cfg_cs_line_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_cs_line_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(count.ToString());
        }

        //读取线坐标系数据
        static void api_demo_cr_cfg_cs_line_get()
        {
            LineCSNode lineCSNode = new LineCSNode();
            CRresult result = CS.cr_cfg_cs_line_get(robotHandle, 1, ref lineCSNode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(lineCSNode.name[0].ToString());
            Console.WriteLine(lineCSNode.coordinateJointPos[5].ToString());
        }

        //增加线坐标系
        static void api_demo_cr_cfg_cs_line_add()
        {
            LineCSNode linecsnode;

            linecsnode.firstPoint.point.toolAxisAngle = new double[6] { 1.8, 2.09, 90, 34.00, -90, 0 };
            linecsnode.firstPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, linecsnode.firstPoint.point.toolAxisAngle, linecsnode.firstPoint.point.toolPosition);
            linecsnode.firstPoint.id = 1;
            linecsnode.firstPoint.isValid = 1;
            char[] str = ("first").ToCharArray();
            linecsnode.firstPoint.name = new char[32];
            for (int i = 0; i < str.Length; i++)
            {
                linecsnode.firstPoint.name[i] = str[i];
            }
            linecsnode.secondPoint.point.toolAxisAngle = new double[6] { 5.96, 5.28, 90, 34.67, -90, 4.76 };
            linecsnode.secondPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, linecsnode.secondPoint.point.toolAxisAngle, linecsnode.secondPoint.point.toolPosition);
            linecsnode.secondPoint.id = 2;
            linecsnode.secondPoint.isValid = 1;
            char[] str1 = ("second").ToCharArray();
            linecsnode.secondPoint.name = new char[32];
            for (int i = 0; i < str1.Length; i++)
            {
                linecsnode.secondPoint.name[i] = str1[i];
            }

            //  public int isValid;
            linecsnode.id = 2;
            char[] str2 = ("line1").ToCharArray();
            linecsnode.name = new char[32];
            for (int i = 0; i < str2.Length; i++)
            {
                linecsnode.name[i] = str2[i];
            }
            linecsnode.coordinateJointPos = new double[6] { 0, 0, 0, 0, 0, 0 };
            linecsnode.coordinatePose = new double[6];
            int res = (int)CS.cr_compute_cs_line(linecsnode.firstPoint.point.toolPosition, 6, linecsnode.secondPoint.point.toolPosition, 6, linecsnode.coordinatePose, 6);
            if (res == 0)
            {
                linecsnode.isValid = 1;
            }
            else
                linecsnode.isValid = 0;

            CS.cr_kineInverse(robotHandle, linecsnode.coordinatePose, linecsnode.coordinateJointPos, linecsnode.coordinateJointPos);

            CRresult result = CS.cr_cfg_cs_line_add(robotHandle, linecsnode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
            Console.WriteLine("\r\n");
            Console.WriteLine(linecsnode.name[2].ToString());
        }

        //删除线坐标系
        static void api_demo_cr_cfg_cs_line_delete()
        {
            CRresult result = CS.cr_cfg_cs_line_delete(robotHandle, 2);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
        }

        //修改线坐标系数据
        static void api_demo_cr_cfg_cs_line_set()
        {
            LineCSNode linecsnode;

            linecsnode.firstPoint.point.toolAxisAngle = new double[6] { 1.8, 2.09, 90, 34.00, -90, 0 };
            linecsnode.firstPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, linecsnode.firstPoint.point.toolAxisAngle, linecsnode.firstPoint.point.toolPosition);
            linecsnode.firstPoint.id = 1;
            linecsnode.firstPoint.isValid = 1;
            char[] str = ("first").ToCharArray();
            linecsnode.firstPoint.name = new char[32];
            for (int i = 0; i < str.Length; i++)
            {
                linecsnode.firstPoint.name[i] = str[i];
            }
            linecsnode.secondPoint.point.toolAxisAngle = new double[6] { 5.96, 5.28, 90, 34.67, -90, 4.76 };
            linecsnode.secondPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, linecsnode.secondPoint.point.toolAxisAngle, linecsnode.secondPoint.point.toolPosition);
            linecsnode.secondPoint.id = 2;
            linecsnode.secondPoint.isValid = 1;
            char[] str1 = ("second").ToCharArray();
            linecsnode.secondPoint.name = new char[32];
            for (int i = 0; i < str1.Length; i++)
            {
                linecsnode.secondPoint.name[i] = str1[i];
            }

            //  public int isValid;
            linecsnode.id = 2;
            char[] str2 = ("line1").ToCharArray();
            linecsnode.name = new char[32];
            for (int i = 0; i < str2.Length; i++)
            {
                linecsnode.name[i] = str2[i];
            }
            linecsnode.coordinateJointPos = new double[6] { 0, 0, 0, 0, 0, 0 };
            linecsnode.coordinatePose = new double[6];
            int res = (int)CS.cr_compute_cs_line(linecsnode.firstPoint.point.toolPosition, 6, linecsnode.secondPoint.point.toolPosition, 6, linecsnode.coordinatePose, 6);
            if (res == 0)
            {
                linecsnode.isValid = 1;
            }
            else
                linecsnode.isValid = 0;

            CS.cr_kineInverse(robotHandle, linecsnode.coordinatePose, linecsnode.coordinateJointPos, linecsnode.coordinateJointPos);
            CRresult result = CS.cr_cfg_cs_line_set(robotHandle, 2, linecsnode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
            Console.WriteLine("\r\n");
            Console.WriteLine(linecsnode.name[1].ToString());
        }

        //读取面坐标系个数
        static void api_demo_cr_cfg_cs_plane_count()
        {
            int count = -1;
            CRresult result = CS.cr_cfg_cs_plane_count(robotHandle, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
            Console.WriteLine(count.ToString());
        }

        //读取面坐标系数据
        static void api_demo_cr_cfg_cs_plane_get()
        {
            PlaneCSNode planeCSNode = new PlaneCSNode();
            CRresult result = CS.cr_cfg_cs_plane_get(robotHandle, 1, ref planeCSNode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(planeCSNode.id.ToString());
        }

        //增加面坐标系
        static void api_demo_cr_cfg_cs_plane_add()
        {
            PlaneCSNode planecsnode;

            planecsnode.firstPoint.point.toolAxisAngle = new double[6] { 1.8, 2.09, 90, 34.00, -90, 0 };
            planecsnode.firstPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, planecsnode.firstPoint.point.toolAxisAngle, planecsnode.firstPoint.point.toolPosition);
            planecsnode.firstPoint.id = 1;
            planecsnode.firstPoint.isValid = 1;
            char[] str = ("first").ToCharArray();
            planecsnode.firstPoint.name = new char[32];
            for (int i = 0; i < str.Length; i++)
            {
                planecsnode.firstPoint.name[i] = str[i];
            }
            planecsnode.secondPoint.point.toolAxisAngle = new double[6] { 5.96, 5.28, 90, 34.67, -90, 4.76 };
            planecsnode.secondPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, planecsnode.secondPoint.point.toolAxisAngle, planecsnode.secondPoint.point.toolPosition);
            planecsnode.secondPoint.id = 2;
            planecsnode.secondPoint.isValid = 1;
            char[] str1 = ("second").ToCharArray();
            planecsnode.secondPoint.name = new char[32];
            for (int i = 0; i < str1.Length; i++)
            {
                planecsnode.secondPoint.name[i] = str1[i];
            }
            planecsnode.thirdPoint.point.toolAxisAngle = new double[6] { 7.80, 7.30, 86.45, 34.67, -92.46, 6.22 };
            planecsnode.thirdPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, planecsnode.thirdPoint.point.toolAxisAngle, planecsnode.thirdPoint.point.toolPosition);
            planecsnode.thirdPoint.id = 3;
            planecsnode.thirdPoint.isValid = 1;
            char[] str2 = ("third").ToCharArray();
            planecsnode.thirdPoint.name = new char[32];
            for (int i = 0; i < str2.Length; i++)
            {
                planecsnode.thirdPoint.name[i] = str2[i];
            }
            //  public int isValid;
            planecsnode.id = 2;
            char[] str3 = ("plane1").ToCharArray();
            planecsnode.name = new char[32];
            for (int i = 0; i < str3.Length; i++)
            {
                planecsnode.name[i] = str3[i];
            }
            planecsnode.coordinateJointPos = new double[6] { 0, 0, 0, 0, 0, 0 };
            planecsnode.coordinatePose = new double[6];
            int res = (int)CS.cr_compute_cs_plane(planecsnode.firstPoint.point.toolPosition, 6, planecsnode.secondPoint.point.toolPosition, 6, planecsnode.thirdPoint.point.toolPosition, 6, planecsnode.coordinatePose, 6);
            if (res == 0)
            {
                planecsnode.isValid = 1;
            }
            else
                planecsnode.isValid = 0;

            CS.cr_kineInverse(robotHandle, planecsnode.coordinatePose, planecsnode.coordinateJointPos, planecsnode.coordinateJointPos);

            CRresult result = CS.cr_cfg_cs_plane_add(robotHandle, planecsnode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
            Console.WriteLine("\r\n");
            Console.WriteLine(planecsnode.name[1].ToString());
        }

        //删除面坐标系
        static void api_demo_cr_cfg_cs_plane_delete()
        {
            CRresult result = CS.cr_cfg_cs_plane_delete(robotHandle, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
        }

        //修改面坐标系数据
        static void api_demo_cr_cfg_cs_plane_set()
        {
            PlaneCSNode planecsnode;

            planecsnode.firstPoint.point.toolAxisAngle = new double[6] { 1.8, 2.09, 90, 34.00, -90, 0 };
            planecsnode.firstPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, planecsnode.firstPoint.point.toolAxisAngle, planecsnode.firstPoint.point.toolPosition);
            planecsnode.firstPoint.id = 1;
            planecsnode.firstPoint.isValid = 1;
            char[] str = ("first").ToCharArray();
            planecsnode.firstPoint.name = new char[32];
            for (int i = 0; i < str.Length; i++)
            {
                planecsnode.firstPoint.name[i] = str[i];
            }
            planecsnode.secondPoint.point.toolAxisAngle = new double[6] { 5.96, 5.28, 90, 34.67, -90, 4.76 };
            planecsnode.secondPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, planecsnode.secondPoint.point.toolAxisAngle, planecsnode.secondPoint.point.toolPosition);
            planecsnode.secondPoint.id = 2;
            planecsnode.secondPoint.isValid = 1;
            char[] str1 = ("second").ToCharArray();
            planecsnode.secondPoint.name = new char[32];
            for (int i = 0; i < str1.Length; i++)
            {
                planecsnode.secondPoint.name[i] = str1[i];
            }
            planecsnode.thirdPoint.point.toolAxisAngle = new double[6] { 7.80, 7.30, 86.45, 34.67, -92.46, 6.22 };
            planecsnode.thirdPoint.point.toolPosition = new double[6];
            CS.cr_kineForward(robotHandle, planecsnode.thirdPoint.point.toolAxisAngle, planecsnode.thirdPoint.point.toolPosition);
            planecsnode.thirdPoint.id = 3;
            planecsnode.thirdPoint.isValid = 1;
            char[] str2 = ("third").ToCharArray();
            planecsnode.thirdPoint.name = new char[32];
            for (int i = 0; i < str2.Length; i++)
            {
                planecsnode.thirdPoint.name[i] = str2[i];
            }
            //  public int isValid;
            planecsnode.id = 2;
            char[] str3 = ("plane1").ToCharArray();
            planecsnode.name = new char[32];
            for (int i = 0; i < str3.Length; i++)
            {
                planecsnode.name[i] = str3[i];
            }
            planecsnode.coordinateJointPos = new double[6] { 0, 0, 0, 0, 0, 0 };
            planecsnode.coordinatePose = new double[6];
            int res = (int)CS.cr_compute_cs_plane(planecsnode.firstPoint.point.toolPosition, 6, planecsnode.secondPoint.point.toolPosition, 6, planecsnode.thirdPoint.point.toolPosition, 6, planecsnode.coordinatePose, 6);
            if (res == 0)
            {
                planecsnode.isValid = 1;
            }
            else
                planecsnode.isValid = 0;

            CS.cr_kineInverse(robotHandle, planecsnode.coordinatePose, planecsnode.coordinateJointPos, planecsnode.coordinateJointPos);

            CRresult result = CS.cr_cfg_cs_plane_set(robotHandle, 1, planecsnode);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("\r\n");
            Console.WriteLine(result.ToString());
            Console.WriteLine("\r\n");
            Console.WriteLine(planecsnode.name[1].ToString());
        }

        //读取基坐标系数据
        static void api_demo_cr_cfg_cs_base_get()
        {
            double[] csPose = new double[6];
            CRresult result = CS.cr_cfg_cs_base_get(robotHandle, csPose, 6);
            Debug.Assert(result == CRresult.sucess);
            for (int i = 0; i < 6; i++)
            {
                Console.WriteLine(csPose[i].ToString());
            }
        }

        //读取工具坐标系数据
        static void api_demo_cr_cfg_cs_tool_get()
        {
            double[] csPose = new double[6];
            CRresult result = CS.cr_cfg_cs_tool_get(robotHandle, csPose, 6);
            Debug.Assert(result == CRresult.sucess);
            for (int i = 0; i < 6; i++)
            {
                Console.WriteLine(csPose[i].ToString());
            }
        }

        //计算点坐标系
        static void api_demo_cr_compute_cs_point()
        {
            double[] pointPose = new double[6] { -66, -438, 887, -57, 0, -148 };
            double[] pointCS = new double[6];
            CRresult result = CS.cr_compute_cs_point(pointPose, 6, pointCS, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(pointCS[0].ToString());
        }

        //计算线坐标系
        static void api_demo_cr_compute_cs_line()
        {
            double[] point1Pose = new double[6] { -66, -438, 887, -57, 0, -148 };
            double[] point2Pose = new double[6] { -76, -438, 887, -57, 0, -148 };
            double[] lineCS = new double[6];
            CRresult result = CS.cr_compute_cs_line(point1Pose, 6, point2Pose, 6, lineCS, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(lineCS[0].ToString());
        }

        //计算面坐标系
        static void api_demo_cr_compute_cs_plane()
        {
            double[] point1Pose = new double[6] { -70, -436.75, 893, 27.15, 22, 150.76 };
            double[] point2Pose = new double[6] { -75, -436.75, 893, 27.15, 22, 150.76 };
            double[] point3Pose = new double[6] { -70, -440, 893, 27.15, 22, 150.76 };
            double[] planeCS = new double[6];
            CRresult result = CS.cr_compute_cs_plane(point1Pose, 6, point2Pose, 6, point3Pose, 6, planeCS, 6);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(planeCS[0].ToString());
        }

        //设置串口配置
        static void api_demo_cr_cfg_comm_serial_setting_set()
        {
            SerialType serialType = SerialType.rs485_1_CommSettings;
            SerialCommSettings serialCommSettings = new SerialCommSettings();
            serialCommSettings.baudRate = BaudRate.BaudRate115200;
            serialCommSettings.parity = ParityCheck.odd;
            serialCommSettings.serialCommType = SerialCommuType.Modbus_ASCII;
            serialCommSettings.dataBits = 7;
            serialCommSettings.retryNumber = 2;
            serialCommSettings.timeout = 1000;
            serialCommSettings.modbusSlaveNo = 1;
            CRresult result = CS.cr_cfg_comm_serial_setting_set(robotHandle, serialType, serialCommSettings);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(serialType.ToString());
        }

        //读取串口配置
        static void api_demo_cr_cfg_comm_serial_setting_get()
        {
            SerialType serialType = SerialType.rs485_1_CommSettings;
            SerialCommSettings serialCommSettings = new SerialCommSettings();
            CRresult result = CS.cr_cfg_comm_serial_setting_get(robotHandle, serialType, ref serialCommSettings);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(serialCommSettings.baudRate.ToString());
        }

        //设置控制柜网络配置
        static void api_demo_cr_cfg_comm_ethernet_ip_set()
        {
            IPConfig ipconfig = new IPConfig();
            ipconfig.ipAddr = new int[4] { 192, 168, 6, 7 };
            ipconfig.subnetMask = new int[4] { 255, 255, 255, 0 };
            CRresult result = CS.cr_cfg_comm_ethernet_ip_set(robotHandle, ipconfig);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(ipconfig.ipAddr[0].ToString());
        }

        //读取控制柜网络配置
        static void api_demo_cr_cfg_comm_ethernet_ip_get()
        {
            IPConfig ipconfig = new IPConfig();
            CRresult result = CS.cr_cfg_comm_ethernet_ip_get(robotHandle, ref ipconfig);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(ipconfig.ipAddr[0].ToString());
        }

        //设置控制柜从站配置
        static void api_demo_cr_cfg_comm_ethernet_modbus_slave_num_set()
        {
            int modbusSlaveNo = 1200;
            CRresult result = CS.cr_cfg_comm_ethernet_modbus_slave_num_set(robotHandle, modbusSlaveNo);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(modbusSlaveNo.ToString());
        }

        //读取控制柜从站配置
        static void api_demo_cr_cfg_comm_ethernet_modbus_slave_num_get()
        {
            int modbusSlaveNo = -1;
            CRresult result = CS.cr_cfg_comm_ethernet_modbus_slave_num_get(robotHandle, ref modbusSlaveNo);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(modbusSlaveNo.ToString());
        }

        //读取从站个数
        static void api_demo_cr_cfg_comm_modbus_slave_count()
        {
            SerialType type = SerialType.rs232_CommSettings;
            int count = -1;
            CRresult result = CS.cr_cfg_comm_modbus_slave_count(robotHandle, type, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(count.ToString());
        }

        //读取从站数据
        static void api_demo_cr_cfg_comm_modbus_slave_get()
        {
            SerialType type = SerialType.rs232_CommSettings;
            ModbusMasterConfig modbusConfig = new ModbusMasterConfig();
            CRresult result = CS.cr_cfg_comm_modbus_slave_get(robotHandle, type, 1, ref modbusConfig);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(modbusConfig.id.ToString());
        }

        //添加从站
        static void api_demo_cr_cfg_comm_modbus_slave_add()
        {
            SerialType type = SerialType.ethernet_CommSettings;
            ModbusMasterConfig modbusConfig = new ModbusMasterConfig();
            modbusConfig.autoConnect = 0;
            modbusConfig.id = 1;
            modbusConfig.modbusMasterOperate = ModbusMasterOperate.Stop;
            modbusConfig.scanTime = 10;
            int[] slaveIP = new int[4];
            slaveIP[0] = 192;
            modbusConfig.slaveIP = slaveIP;
            modbusConfig.slaveNo = 2;
            CRresult result = CS.cr_cfg_comm_modbus_slave_add(robotHandle, type, ref modbusConfig);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(modbusConfig.id.ToString());
        }

        //删除从站
        static void api_demo_cr_cfg_comm_modbus_slave_delete()
        {
            SerialType type = SerialType.rs232_CommSettings;
            CRresult result = CS.cr_cfg_comm_modbus_slave_delete(robotHandle, type, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //修改从站数据
        static void api_demo_cr_cfg_comm_modbus_slave_set()
        {
            SerialType type = SerialType.ethernet_CommSettings;
            ModbusMasterConfig modbusConfig = new ModbusMasterConfig();
            modbusConfig.autoConnect = 0;
            modbusConfig.id = 1;
            modbusConfig.modbusMasterOperate = ModbusMasterOperate.Stop;
            modbusConfig.scanTime = 10;
            int[] slaveIP = new int[4];
            slaveIP[0] = 192;
            modbusConfig.slaveIP = slaveIP;
            modbusConfig.slaveNo = 3;
            CRresult result = CS.cr_cfg_comm_modbus_slave_set(robotHandle, type, 1, modbusConfig);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(modbusConfig.id.ToString());
        }

        //从站连接/断开
        static void api_demo_cr_cfg_comm_modbus_slave_operate()
        {
            ModbusMasterOperate modbusOperate = ModbusMasterOperate.Start;
            SerialType type = SerialType.rs232_CommSettings;
            CRresult result = CS.cr_cfg_comm_modbus_slave_operate(robotHandle, type, 1, modbusOperate);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //读取地址映射数量
        static void api_demo_cr_cfg_comm_modbus_addr_map_count()
        {
            int count = -1;
            SerialType type = SerialType.rs232_CommSettings;
            CRresult result = CS.cr_cfg_comm_modbus_addr_map_count(robotHandle, type, 1, ref count);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(count.ToString());
        }

        //读取地址映射数据
        static void api_demo_cr_cfg_comm_modbus_addr_map_get()
        {
            SerialType type = SerialType.rs232_CommSettings;
            ModbusAddrMap addrMap = new ModbusAddrMap();
            CRresult result = CS.cr_cfg_comm_modbus_addr_map_get(robotHandle, type, 1, 1, ref addrMap);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(addrMap.slaveStartAddr.ToString());
        }

        //添加地址映射
        static void api_demo_cr_cfg_comm_modbus_addr_map_add()
        {
            SerialType type = SerialType.rs232_CommSettings;
            ModbusAddrMap addrMap = new ModbusAddrMap();
            addrMap.functionNo = ModbusMasterFunctionNo.ReadInt16;
            addrMap.masterOffsetNo = 1;
            addrMap.masterRegType = CommuVarType.CommuVarType_Float;
            addrMap.masterStartAddr = 2;
            addrMap.slaveStartAddr = 1;
            CRresult result = CS.cr_cfg_comm_modbus_addr_map_add(robotHandle, type, 2, addrMap);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(addrMap.slaveStartAddr.ToString());
        }

        //删除地址映射
        static void api_demo_cr_cfg_comm_modbus_addr_map_delete()
        {
            SerialType type = SerialType.rs232_CommSettings;
            CRresult result = CS.cr_cfg_comm_modbus_addr_map_delete(robotHandle, type, 1, 1);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(result.ToString());
        }

        //修改地址映射数据
        static void api_demo_cr_cfg_comm_modbus_addr_map_set()
        {
            SerialType type = SerialType.rs232_CommSettings;
            ModbusAddrMap addrMap = new ModbusAddrMap();
            addrMap.functionNo = ModbusMasterFunctionNo.ReadInt16;
            addrMap.masterOffsetNo = 1;
            addrMap.masterRegType = CommuVarType.CommuVarType_Float;
            addrMap.masterStartAddr = 2;
            addrMap.slaveStartAddr = 1;
            CRresult result = CS.cr_cfg_comm_modbus_addr_map_set(robotHandle, type, 1, 1, addrMap);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine(addrMap.slaveStartAddr.ToString());
        }

        
        //设置力控配置
        static void api_demo_cr_force_cfg_set()
        {
            ForceConfig forceConfig = new ForceConfig();

            forceConfig.commuConfig = new CommuConfig();
            forceConfig.commuConfig.autoConnect = 1;
            //自动与传感器通信，传感器开始接收数据
            forceConfig.commuConfig.mannaulOperate = 0;
            //自动与传感器通信，传感器开始接收数据
            forceConfig.commuConfig.paraBuf = 0;
            //预留参数

            forceConfig.forceCtrlTcpImpl = new ForceToolSetting();
            byte[] tmp_bytes = Encoding.UTF8.GetBytes("ForcePayload7");
            //激活的力控传感器负载的名称
            forceConfig.forceCtrlTcpImpl.activeForcePayload_name = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.activeForcePayload_name[i] = tmp_bytes[i];
            }
            tmp_bytes = Encoding.UTF8.GetBytes("TCP_4");
            //激活的力控传感器TCP的名称
            forceConfig.forceCtrlTcpImpl.activeForceTCP_name = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.activeForceTCP_name[i] = tmp_bytes[i];
            }

            forceConfig.forceCtrlTcpImpl.availableForcePayLoad = new ForcePayLoad[20];
            //当前待选的力控传感器的配置信息
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forceCenterOfGravity = new double[3] { 1, 2, 3 };
            tmp_bytes = Encoding.UTF8.GetBytes("ForcePayload7");
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forcePayloadName = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forcePayloadName[i] = tmp_bytes[i];
            }
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forceToolPayload = 1.3;
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[0].forcePayloadId = 0;
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[1].forceCenterOfGravity = new double[3] { 1, 2, 3 };
            tmp_bytes = Encoding.UTF8.GetBytes("ForcePayload6");
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[1].forcePayloadName = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.availableForcePayLoad[1].forcePayloadName[i] = tmp_bytes[i];
            }
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[1].forceToolPayload = 1.3;
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[1].forcePayloadId = 1;
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[2].forceCenterOfGravity = new double[3] { 0, 0, 0 };
            tmp_bytes = Encoding.UTF8.GetBytes("ForcePayload5");
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[2].forcePayloadName = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.availableForcePayLoad[2].forcePayloadName[i] = tmp_bytes[i];
            }
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[2].forceToolPayload = 0.5;
            forceConfig.forceCtrlTcpImpl.availableForcePayLoad[2].forcePayloadId = 2;

            forceConfig.forceCtrlTcpImpl.availableForcePayLoadLen = 3;
            //当前待选的力控传感器负载的配置信息的个数

            forceConfig.forceCtrlTcpImpl.availableForceTCP = new ForceTCPMsg[20];
            //当前待选的力控传感器TCP的配置信息
            forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpOffset = new double[6] { 0, 0, 0, 0, 0, -110 };
            forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpId = 0;
            tmp_bytes = Encoding.UTF8.GetBytes("TCP_4");
            forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpName = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.availableForceTCP[0].forceTcpName[i] = tmp_bytes[i];
            }

            forceConfig.forceCtrlTcpImpl.availableForceTCP[1].forceTcpOffset = new double[6] { 0, 0, 0, 180, 0, 0 };
            forceConfig.forceCtrlTcpImpl.availableForceTCP[1].forceTcpId = 1;
            tmp_bytes = Encoding.UTF8.GetBytes("ForceTcp5");
            forceConfig.forceCtrlTcpImpl.availableForceTCP[1].forceTcpName = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.availableForceTCP[1].forceTcpName[i] = tmp_bytes[i];
            }

            forceConfig.forceCtrlTcpImpl.availableForceTCP[2].forceTcpOffset = new double[6] { 0, 0, 0, 180, 0, 0 };
            forceConfig.forceCtrlTcpImpl.availableForceTCP[2].forceTcpId = 2;
            tmp_bytes = Encoding.UTF8.GetBytes("ForceTcp4");
            forceConfig.forceCtrlTcpImpl.availableForceTCP[2].forceTcpName = new byte[20];
            for (int i = 0; i < tmp_bytes.Length; i++)
            {
                forceConfig.forceCtrlTcpImpl.availableForceTCP[2].forceTcpName[i] = tmp_bytes[i];
            }

            forceConfig.forceCtrlTcpImpl.availableForceTCPLen = 3;
            //当前待选的力控传感器TCP的配置信息的个数

            forceConfig.sensorMessage = new SensorMessage();
            forceConfig.sensorMessage.productNo = 1;
            //传感器产品号，预留参数
            forceConfig.sensorMessage.sequenceNo = 0;
            //传感器序列号，预留参数
            forceConfig.sensorMessage.venderNo = 0;
            //传感器品牌
            CRresult result = CS.cr_force_cfg_set(robotHandle, forceConfig);
            //设置力控配置
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result);
        }

        //读力控配置
        static void api_demo_cr_force_cfg_get()
        {
            ForceConfig forceConfig = new ForceConfig();
            //读力控配置
            CRresult result = CS.cr_force_cfg_get(robotHandle, ref forceConfig);
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result);
        }

        //开启力控并下发相关设置
        static void api_demo_cr_force_open()
        {
            ForceSetting forceSetting = new ForceSetting
            {
                flexibleAxis = new int[6] { 0, 0, 1, 0, 0, 0 },
                //z轴可拖动
                forceBaseType = 0,
                //力控类型:  0-基于TCP力传感器,1-基于动力学,2-基于底座力传感器
                forceCtrlType = 1
                //力控用法:  0-运动力控,1-力控拖动
            };
            CRresult result = CS.cr_force_open(robotHandle, forceSetting);
            //开启力控并下发相关设置
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result);
        }

        //关闭力控
        static void api_demo_cr_force_close()
        {
            CRresult result = CS.cr_force_close(robotHandle);
            //关闭力控
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result);
        }

        //设置力控控制参数
        static void api_demo_cr_force_para_set()
        {
            ForceCtlPara forceCtlPara = new ForceCtlPara
            {
                damping = new double[6] { 1, 1, 0.1, 1, 1, 1 },
                //x,y,Rx,Ry,Rz阻尼系数均为1,z阻尼系数为0.1
                dampingLen = 6,
                //0、1或6
                limits = new double[6] { 0.1, 0.1, 0.005, 0.002, 0.002, 0.002 },
                //x,y方向速度保护为0.1m/s，z方向偏差保护为0.005m,Rx,Ry,Rz偏差保护为0.002rad
                limitsLen = 6,
                //0或6
                mass = new double[6] { 1, 1, 0.5, 1, 1, 1 },
                //x,y,Rx,Ry,Rz质量系数均为1,z质量系数为0.5
                massLen = 6,
                //0、1或6
                stiffness = new double[6] { 1, 1, 0.1, 1, 1, 1 },
                //x,y,Rx,Ry,Rz刚度均为1,z刚度为0.1
                stiffnessLen = 6,
                //0、1或6
                taskFrame = new double[6] { 0, 0, 0, 0, 0, 0 },
                //力控坐标系为基坐标系
                wrench = new double[6] { 0, 0, 10, 0, 0, 0 }
                //z轴正向施加10N的力
            };
            CRresult result = CS.cr_force_para_set(robotHandle, forceCtlPara);
            //设置力控控制参数
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result);
        }

        //读力控控制参数
        static void api_demo_cr_force_para_get()
        {
            ForceCtlPara forceCtlPara = new ForceCtlPara();
            CRresult result = CS.cr_force_para_get(robotHandle, ref forceCtlPara);
            //读力控控制参数
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result + "，massLen = " + forceCtlPara.massLen);
        }

        //读力控数据
        static void api_demo_cr_force_data_get()
        {
            ForceData forceData = new ForceData();
            CRresult result = CS.cr_force_data_get(robotHandle, ref forceData);
            //读力控数据
            Debug.Assert(result == CRresult.sucess);
            Console.WriteLine("result = " + result + "，controlMode = " + forceData.controlMode.ToString());
        }
    }
}

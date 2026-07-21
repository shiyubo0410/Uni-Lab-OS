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

namespace _03MotionInter
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
            {
                PointControlPara pointControlPara = new PointControlPara
                {
                    speed = new double[6] { 30, 30, 30, 30, 30, 30 },
                    acc = new double[6] { 30, 30, 30, 30, 30, 30 },
                    jerk = new double[6] { 60, 60, 60, 60, 60, 60 },
                    pose = new double[6] { 0, 0, 0, 0, 0, 0 },          //在MoveJ中无影响
                    jointpos = new double[6] { 0, 0, 90, 0, -90, 0 },   //目标点示例数据
                    tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 },
                    coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 },
                    tcpID = -1,
                    coordinateType = CoordinateType.jointCoordinate,
                    pointTransType = PointTransType.pointTransStop,
                    pointTransRadius = 0,
                    poseTranType = PoseTranType.poseTranMoveToTargetPose,
                    motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc
                };
                result = CS.cr_moveJ(robotHandle, pointControlPara);//轴空间运动
                if (result == CRresult.sucess)
                {
                    Thread.Sleep(50);
                    int isRobotMoving = 1;
                    while (result == CRresult.sucess)
                    {
                        result = CS.cr_get_robotMoveStatus(robotHandle, ref isRobotMoving);
                        //读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
                        Thread.Sleep(50);
                        if (isRobotMoving == 0)
                        {
                            break;
                        }
                    }
                    result = CS.cr_get_tcpActualPose(robotHandle, pointControlPara.pose);  //读实际TCP位置
                    if (result == CRresult.sucess)
                    {
                        pointControlPara.pose[2] = pointControlPara.pose[2] - 150;       //Z方向向下运动150mm
                        pointControlPara.coordinateType = CoordinateType.baseCoordinate;
                        result = CS.cr_moveL(robotHandle, pointControlPara);  //直线运动
                        if (result == CRresult.sucess)
                        {
                            Thread.Sleep(50);
                            while (result == CRresult.sucess)
                            {
                                result = CS.cr_get_robotMoveStatus(robotHandle, ref isRobotMoving);
                                //读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
                                Thread.Sleep(50);
                                if (isRobotMoving == 0)
                                {
                                    break;
                                }
                            }
                            pointControlPara.pose[2] = pointControlPara.pose[2] + 150;
                            PointControlParaSimple pointControlParaSimple = new PointControlParaSimple
                            {
                                speed = new double[6] { 30, 30, 30, 30, 30, 30 },
                                acc = new double[6] { 30, 30, 30, 30, 30, 30 },
                                pose = pointControlPara.pose,         
                                jointpos = new double[6] { 0, 0, 90, 0, -90, 0 },   //目标点示例数据
                                tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 },
                                coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 },
                                coordinateType = CoordinateType.baseCoordinate,
                                pointTransType = PointTransType.pointTransStop,
                                motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc
                            };
                            result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
                            //PointControlParaSimple数据转换为PointControlPara
                            result = CS.cr_move_line(robotHandle, pointControlPara, true);
                            //阻塞式的直线运动，由于是阻塞的直线运动，则运动会在运动到位后在进行后续的程序运行，因此不用像之前做判断
                            if (result == CRresult.sucess)
                            {
                                pointControlParaSimple.jointpos = new double[6] { 90, 0, 90, 0, -90, 0 };
                                pointControlParaSimple.coordinateType = CoordinateType.jointCoordinate;
                                result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
                                //PointControlParaSimple数据转换为PointControlPara
                                result = CS.cr_move_joint(robotHandle, pointControlPara, true);
                                //阻塞式的轴空间运动，由于是阻塞的直线运动，则运动会在运动到位后在进行后续的程序运行，因此不用像之前做判断
                                if (result == CRresult.sucess)
                                {
                                    result = CS.cr_get_tcpActualPose(robotHandle, pointControlPara.pose);  //读实际TCP位置
                                    pointControlPara.pose[2] = pointControlPara.pose[2] - 150;
                                    pointControlParaSimple.pose = pointControlPara.pose;
                                    pointControlParaSimple.coordinateType = CoordinateType.baseCoordinate;
                                    result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
                                    //PointControlParaSimple数据转换为PointControlPara
                                    result = CS.cr_moveL(robotHandle, pointControlPara);  //直线运动
                                    if (result == CRresult.sucess)
                                    {
                                        Thread.Sleep(50);
                                        while (result == CRresult.sucess)
                                        {
                                            result = CS.cr_get_robotMoveStatus(robotHandle, ref isRobotMoving);
                                            //读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
                                            Thread.Sleep(50);
                                            if (isRobotMoving == 0)
                                            {
                                                break;
                                            }
                                        }
                                        pointControlPara.pose[2] = pointControlPara.pose[2] + 150;
                                        //PointControlParaSimple数据转换为PointControlPara
                                        result = CS.cr_move_line(robotHandle, pointControlPara, false);
                                        //非阻塞式直线运动，下发运动后会立马执行下一条指令
                                        if (result == CRresult.sucess)
                                        {
                                            while (result == CRresult.sucess)
                                            {
                                                result = CS.cr_get_robotMoveStatus(robotHandle, ref isRobotMoving);
                                                //读机械臂运动状态,如果运动已经停止，代表上一次运动已经结束，则跳出循环进行下一次运动
                                                Thread.Sleep(50);
                                                if (isRobotMoving == 0)
                                                {
                                                    break;
                                                }
                                            }
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},运动已完成");
                                        }
                                        else
                                        {
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                        }
                                    }
                                    else
                                    {
                                        Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                    }
                                }
                                else
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                }
                            }
                            else
                            {
                                Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                            }
                        }
                        else
                        {
                            Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                        }
                    }
                    else
                    {
                        Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                    }
                }
                else
                {
                    Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                }
            }
            else
            {
                Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
            }

            result = CS.cr_destroy_robot(robotHandle);//机器人断开连接，释放句柄
            if (result != CRresult.sucess)
            {
                Console.WriteLine($"行号：{GetLineNum().ToString()},机器人断开连接失败");
            }
            Console.WriteLine($"按下任意键退出。");
            Console.ReadKey();
        }
        private static int GetLineNum()
        {
            StackTrace st = new StackTrace(1, true);

            return st.GetFrame(0).GetFileLineNumber();
        }
    }
}

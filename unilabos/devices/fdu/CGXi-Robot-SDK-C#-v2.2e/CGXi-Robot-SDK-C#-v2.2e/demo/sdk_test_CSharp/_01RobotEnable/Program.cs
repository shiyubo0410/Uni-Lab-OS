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


namespace _01RobotEnable
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
            {
                RobotModes robotMode = RobotModes.BackDrive;
                result = CS.cr_get_robotMode(robotHandle, ref robotMode); //读机械臂当前状态
                if (result == CRresult.sucess && robotMode == RobotModes.JointPowerOff) //判断状态,robotMode为6时是本体未上电状态才可以进行上电
                {
                    result = CS.cr_poweron(robotHandle); //机械臂上电
                    if (result == CRresult.sucess)
                    {
                        while(result == CRresult.sucess)
                        {
                            result = CS.cr_get_robotMode(robotHandle, ref robotMode);
                            Thread.Sleep(50);
                            if (robotMode == RobotModes.JointIdle)      //判断状态,robotMode为8时是机器人上电完成后再进行使能
                                break;
                        }
                        result = CS.cr_enable(robotHandle);  //机械臂使能
                        if (result == CRresult.sucess)
                        {
                            while (result == CRresult.sucess)
                            {
                                result = CS.cr_get_robotMode(robotHandle, ref robotMode);
                                Thread.Sleep(50);
                                if (robotMode == RobotModes.ProgramStop)      //判断状态,robotMode为103时机器人使能完成
                                    break;
                            }
                            Console.WriteLine($"行号：{GetLineNum().ToString()},使能完成");
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

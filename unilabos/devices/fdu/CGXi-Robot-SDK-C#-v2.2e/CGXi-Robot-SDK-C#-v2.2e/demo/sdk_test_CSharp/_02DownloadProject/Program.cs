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


namespace _02DownloadProject
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
            {
                Lua_ScriptStatus scriptstatus = Lua_ScriptStatus.lua_Script_load;
                result = CS.cr_get_lua_scriptstatus(robotHandle, ref scriptstatus); //读脚本运行状态
                if (result == CRresult.sucess && scriptstatus == Lua_ScriptStatus.lua_Script_stop) //当脚本运行状态处于脚本程序停止时才可进行程序下载
                {
                    string crpFilepathname = "../../../../program/demo.crp";//.crp文件路径
                    string crscriptFilepathname = "../../../../program/demo.crscript";//脚本程序路径
                    result = CS.cr_downloadProject(robotHandle, crpFilepathname, crscriptFilepathname);//下载程序
                    if (result == CRresult.sucess)
                    {
                        result = CS.cr_play(robotHandle);  //运行程序
                        if (result == CRresult.sucess)
                        {
                            while (result == CRresult.sucess)
                            {
                                RobotModes robotMode = RobotModes.BackDrive;
                                result = CS.cr_get_robotMode(robotHandle, ref robotMode);
                                Thread.Sleep(50);
                                if (robotMode == RobotModes.ProgramStop)      //读机械臂当前状态,程序停止状态下才可以上传程序
                                    break;
                            }
                            if (result == CRresult.sucess)
                            {
                                string FilePath = "../../../../program/"; //文件保存路径
                                string filename = "demo";  //.crp和脚本程序的文件名
                                result = CS.cr_uploadProject(robotHandle, FilePath, filename);//工程文件上传
                                if (result == CRresult.sucess)
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},已成功上传工程文件");
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
                    Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{scriptstatus.ToString()}");
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

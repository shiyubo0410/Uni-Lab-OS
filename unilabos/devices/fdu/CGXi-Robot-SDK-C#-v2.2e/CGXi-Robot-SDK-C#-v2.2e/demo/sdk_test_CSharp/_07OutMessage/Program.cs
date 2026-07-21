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


namespace _07OutMessage
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
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
                                    --popup_out:text
                                    popup_message(""hello"", ""message"", false, false, true)
                                    wait(1)--sync
                                    end
                                    end
                                    RobotProgram_Result = task_create(RobotProgram)
                                    function PauseFuncProgram()
                                    while (true)
                                    do
                                    wait(100)--sync
                                    end
                                    end
                                    PauseFuncProgram_Result = task_create(PauseFuncProgram)
                                    end
                                    mainFuncProgram_Result = task_create(mainFuncProgram)";
                result = CS.cr_downloadProgram(robotHandle, programfile);
                if (result == CRresult.sucess)
                {
                    result = CS.cr_play(robotHandle);//运行程序
                    if (result == CRresult.sucess)
                    {
                        bool hasPopup = false;
                        result = CS.cr_script_popup_exist(robotHandle, ref hasPopup);
                        if (result == CRresult.sucess)
                        {
                            if (hasPopup == true)
                            {
                                PopUpMsg popupMsg = new PopUpMsg();
                                result = CS.cr_script_popup_msg_get(robotHandle, ref popupMsg);
                                if (result == CRresult.sucess)
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},弹窗信息:{Encoding.UTF8.GetString(popupMsg.var_data)}");
                                    result = CS.cr_stop(robotHandle);  //停止程序运行
                                }
                                else
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                }
                            }
                            else
                            {
                                Console.WriteLine($"行号：{GetLineNum().ToString()},没有弹窗信息");
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

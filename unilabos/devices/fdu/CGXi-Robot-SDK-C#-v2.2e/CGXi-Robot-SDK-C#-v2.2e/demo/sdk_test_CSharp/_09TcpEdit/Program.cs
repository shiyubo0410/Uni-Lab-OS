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

namespace _09TcpEdit
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
            {
                int index = -1;
                result = CS.cr_cfg_tcp_active_get(robotHandle, ref index);//读取当前激活的TCP索引
                if (result == CRresult.sucess)
                {
                    TCPMsg tcpMsg = new TCPMsg
                    {
                        tcpOffset = new double[6],
                        tcpName = new char[20],
                    };
                    result = CS.cr_cfg_tcp_get(robotHandle, index, ref tcpMsg); //需要先存在索引号为0的TCP
                    if (result == CRresult.sucess)
                    {
                        tcpMsg.tcpOffset = new double[6] { 3, 10, 9, 90, 80, 70 };
                        result = CS.cr_cfg_tcp_set(robotHandle, index, tcpMsg);//编辑索引号为0的TCP数据
                        if (result == CRresult.sucess)
                        {
                            char[] str = ("TCP").ToCharArray();
                            TCPMsg tcpMsg1 = new TCPMsg
                            {
                                tcpOffset = new double[6] { 5, 10, 15, 10, 20, 30 },
                                tcpName = new char[20]
                            };
                            for (int i = 0; i < str.Length; i++)
                            {
                                tcpMsg1.tcpName[i] = str[i];
                            }
                            result = CS.cr_cfg_tcp_add(robotHandle, tcpMsg1);//增加TCP
                            if (result == CRresult.sucess)
                            {
                                index = 1;
                                result = CS.cr_cfg_tcp_active_set(robotHandle, index);  //激活索引号为1的TCP
                                if (result == CRresult.sucess)
                                {
                                    result = CS.cr_cfg_tcp_active_get(robotHandle,ref index);
                                    if (result == CRresult.sucess)
                                    {
                                        Console.WriteLine($"行号：{GetLineNum().ToString()},当前激活的TCP为：{index}");
                                        index = 0;
                                        result = CS.cr_cfg_tcp_delete(robotHandle, index);  //删除索引号为0的TCP
                                        if (result == CRresult.sucess)
                                        {
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},已成功删除索引号为{index}的TCP");
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

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

namespace _05InstallRW
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
            {
                int count = -1;
                result = CS.cr_cfg_var_install_count(robotHandle, ref count);//读取安装变量个数
                if (result == CRresult.sucess)
                {
                    VariableMsg variableMsg = new VariableMsg
                    {
                        variableName = "i_var_1",
                        variableID = 3,
                        variableType = VariableType.LUA_TBOOLEAN,
                        boolValue = 1
                    };
                    if (count > 0)
                    {
                        for (int i = 0; i < count; i++)
                        {
                            IntPtr ptr = IntPtr.Zero;
                            int size = Marshal.SizeOf(typeof(VariableMsg));
                            ptr = Marshal.AllocHGlobal(size);
                            result = CS.cr_cfg_var_install_get(robotHandle, i, ptr);
                            VariableMsg tmp_variableMsg = (VariableMsg)Marshal.PtrToStructure(ptr, typeof(VariableMsg));
                            if (tmp_variableMsg.stringValue == variableMsg.stringValue)//判断是否存在我想添加的同名安装变量，如果有就修改，没有就增加
                            {
                                int size1 = Marshal.SizeOf(variableMsg);
                                IntPtr ptr1 = Marshal.AllocHGlobal(size);
                                Marshal.StructureToPtr(variableMsg, ptr1, true);
                                result = CS.cr_cfg_var_install_set(robotHandle, i, ptr1);
                                if (result == CRresult.sucess)
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},已成功修改安装变量");
                                }
                                else
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                }
                            }
                            else
                            {
                                int size1 = Marshal.SizeOf(variableMsg);
                                IntPtr ptr1 = Marshal.AllocHGlobal(size);
                                Marshal.StructureToPtr(variableMsg, ptr1, true);
                                result = CS.cr_cfg_var_install_add(robotHandle, ptr1); //增加安装变量
                                if (result == CRresult.sucess)
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},已成功增加安装变量");
                                }
                                else
                                {
                                    Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                }
                            }
                        }
                    }
                    else
                    //如果不存在安装变量，则添加安装变量        
                    {
                        int size = Marshal.SizeOf(variableMsg);
                        IntPtr ptr = Marshal.AllocHGlobal(size);
                        Marshal.StructureToPtr(variableMsg, ptr, true);
                        result = CS.cr_cfg_var_install_add(robotHandle, ptr);
                        if (result == CRresult.sucess)
                        {
                            Console.WriteLine($"行号：{GetLineNum().ToString()},已成功增加安装变量");
                        }
                        else
                        {
                            Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                        }
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

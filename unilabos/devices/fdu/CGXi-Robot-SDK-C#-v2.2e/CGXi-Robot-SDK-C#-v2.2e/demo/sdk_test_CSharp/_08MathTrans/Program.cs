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


namespace _08MathTrans
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
                result = CS.cr_cfg_cs_point_count(robotHandle, ref count);//读取点坐标系个数
                if (result == CRresult.sucess)
                {
                    char[] str = ("point1").ToCharArray();
                    PointCSNode pointcsnode = new PointCSNode
                    {
                        point = new PoseMessage
                        {
                            toolAxisAngle = new double[6] { 30, 30, 30, 30, 30, 30 },
                            toolPosition = new double[6]
                        },
                        id = 1,
                        isValid = 0,
                        name = new char[32],
                    };
                    for (int i = 0; i < str.Length; i++)
                    {
                        pointcsnode.name[i] = str[i];
                    }
                    if (count > 0)
                    {
                        for (int i = 0; i < count; i++)
                        {
                            PointCSNode tmp_pointcsnode = new PointCSNode();
                            result = CS.cr_cfg_cs_point_get(robotHandle, i, ref tmp_pointcsnode);
                            if (result == CRresult.sucess)
                            {
                                if (tmp_pointcsnode.name == pointcsnode.name)
                                {
                                    result = CS.cr_kineForward(robotHandle, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolPosition);//正解求点的位姿
                                    if (result == CRresult.sucess)
                                    {
                                        result = CS.cr_compute_cs_point(pointcsnode.point.toolPosition, 6, pointcsnode.point.toolPosition, 6);
                                        if (result == CRresult.sucess)
                                        {
                                            pointcsnode.isValid = 1;
                                            result = CS.cr_cfg_cs_point_set(robotHandle, i, pointcsnode);//修改点坐标系成功
                                            if (result == CRresult.sucess)
                                            {
                                                Console.WriteLine($"行号：{GetLineNum().ToString()},修改点坐标系成功");
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
                                    break;
                                }
                                if (i == (count - 1))
                                {
                                    result = CS.cr_kineForward(robotHandle, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolPosition);//正解求点的位姿
                                    if (result == CRresult.sucess)
                                    {
                                        result = CS.cr_compute_cs_point(pointcsnode.point.toolPosition, 6, pointcsnode.point.toolPosition, 6);
                                        if (result == CRresult.sucess)
                                        {
                                            pointcsnode.isValid = 1;
                                            result = CS.cr_cfg_cs_point_add(robotHandle, pointcsnode);//增加点坐标系数据
                                            if (result == CRresult.sucess)
                                            {
                                                Console.WriteLine($"行号：{GetLineNum().ToString()},增加点坐标系成功");
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
                            }
                            else
                            {
                                Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                            }
                        }
                    }
                    else
                    {
                        result = CS.cr_kineForward(robotHandle, pointcsnode.point.toolAxisAngle, pointcsnode.point.toolPosition);//正解求点的位姿
                        if (result == CRresult.sucess)
                        {
                            result = CS.cr_compute_cs_point(pointcsnode.point.toolPosition, 6, pointcsnode.point.toolPosition, 6);
                            if (result == CRresult.sucess)
                            {
                                pointcsnode.isValid = 1;
                                result = CS.cr_cfg_cs_point_add(robotHandle, pointcsnode);//增加点坐标系数据
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
                    Thread.Sleep(500);
                    if (result == CRresult.sucess)
                    {
                        double[] pose = new double[6];
                        result = CS.cr_get_tcpActualPose(robotHandle, pose);
                        if (result == CRresult.sucess)
                        {
                            double[] basePose = pose;
                            double[] userPose = pointcsnode.point.toolPosition;
                            double[] poseInUser = new double[6];
                            result = CS.cr_compute_pose_base_to_user(basePose, 6, userPose, 6, poseInUser, 6);//将点坐标系设置为用户坐标系
                            if (result == CRresult.sucess)
                            {
                                Console.WriteLine($"行号：{GetLineNum().ToString()},将点坐标系设置为用户坐标系成功");
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

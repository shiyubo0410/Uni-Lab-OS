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

namespace _04TrajRetrace
{
    class Program
    {
        public static int robotHandle = -1;
        static void Main(string[] args)
        {
            CRresult result = CS.cr_create_robot(ref robotHandle, "192.168.6.6", 2323, "123");
            if (result == CRresult.sucess)
            {
                PointControlParaSimple pointControlParaSimple = new PointControlParaSimple
                {
                    speed = new double[6] { 30, 30, 30, 30, 30, 30 },
                    acc = new double[6] { 30, 30, 30, 30, 30, 30 },
                    pose = new double[6] { 0, 0, 0, 0, 0, 0 },
                    jointpos = new double[6] { 0, 0, 90, 0, -90, 0 },   //目标点示例数据
                    tcpOffset = new double[6] { 0, 0, 0, 0, 0, 0 },
                    coordinatePose = new double[6] { 0, 0, 0, 0, 0, 0 },
                    coordinateType = CoordinateType.jointCoordinate,
                    pointTransType = PointTransType.pointTransStop,
                    motiontriggerMode = MotiontriggerMode.MovetriggerbyOnlyRpc
                };
                PointControlPara pointControlPara = new PointControlPara();
                result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
                //PointControlParaSimple数据转换为PointControlPara
                result = CS.cr_move_joint(robotHandle, pointControlPara, true);//轴空间运动
                if (result == CRresult.sucess)
                {
                    RecordPathPara recordPathPara = new RecordPathPara
                    {
                        sampleTime = 2,
                        recordControl = 1
                    };
                    result = CS.cr_path_recordPara_set(robotHandle, recordPathPara);  //设置轨迹记录参数
                    Thread.Sleep(500);
                    pointControlParaSimple.jointpos = new double[6] { 90, 0, 90, 0, -90, 0 };
                    result = CS.cr_move_pointControlPara_transfer(robotHandle, pointControlParaSimple, ref pointControlPara);
                    //PointControlParaSimple数据转换为PointControlPara
                    result = CS.cr_move_joint(robotHandle, pointControlPara, true);//轴空间运动
                    if (result == CRresult.sucess)
                    {
                        recordPathPara.recordControl = 0;
                        result = CS.cr_path_recordPara_set(robotHandle, recordPathPara);  //设置轨迹记录参数
                        if (result == CRresult.sucess)
                        {
                            int index = -1;
                            PathData pathData = new PathData();
                            pathData.pathPoints = new IntPtr();
                            int size = Marshal.SizeOf(typeof(PathPoint));
                            pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);
                            PathPoint[] pathPoints = new PathPoint[10000];
                            result = CS.cr_path_upload(robotHandle, index, ref pathData);
                            if (result == CRresult.sucess)
                            {
                                int[] allPathIndex = new int[11];
                                int pathIndexLen = -1;
                                result = CS.cr_path_all_index_get(robotHandle, allPathIndex, ref pathIndexLen);
                                //读取控制柜当前存在的轨迹索引
                                for (int i = 0; i < pathIndexLen; i++)
                                {
                                    if (allPathIndex[i] == 2)  //将下载的轨迹索引设置为2，故需要判断其是否已经存在
                                    {
                                        Console.WriteLine($"行号：{GetLineNum().ToString()},存在轨迹索引为2的轨迹");
                                        PathDownloadData pathDownloadData = new PathDownloadData();
                                        pathDownloadData.pathData = new PathData();
                                        pathDownloadData.pathPara = new PathPara();

                                        pathDownloadData.pathData.pathPoints = new IntPtr();
                                        pathDownloadData.pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);

                                        for (int points_count = 0; points_count < 10000; points_count++)//轨迹点指针内容转化
                                        {
                                            IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                                            pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                                        }

                                        pathDownloadData.pathData.moveTime = pathData.moveTime;
                                        pathDownloadData.pathData.pathPointsNum = pathData.pathPointsNum;
                                        pathDownloadData.pathPara.index = 2; //轨迹下载参数设置
                                        pathDownloadData.pathPara.moveType = 1;

                                        for (int points_count = 0; points_count < 10000; points_count++)//将新的轨迹点位转回指针
                                        {
                                            Marshal.StructureToPtr(pathPoints[points_count], IntPtr.Add(pathDownloadData.pathData.pathPoints, points_count * size), false);
                                        }

                                        result = CS.cr_path_download(robotHandle, pathDownloadData);  //下载轨迹到索引2
                                        if (result == CRresult.sucess)
                                        {
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},已成功下载索引为2的轨迹");
                                        }
                                        else
                                        {
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                        }
                                        break;
                                    }
                                    if (i == (pathIndexLen - 1))
                                    {
                                        PathDownloadData pathDownloadData = new PathDownloadData();
                                        pathDownloadData.pathData = new PathData();
                                        pathDownloadData.pathPara = new PathPara();

                                        pathDownloadData.pathData.pathPoints = new IntPtr();
                                        pathDownloadData.pathData.pathPoints = Marshal.AllocHGlobal(size * 10000);

                                        for (int points_count = 0; points_count < 10000; points_count++)//轨迹点指针内容转化
                                        {
                                            IntPtr newPtr = IntPtr.Add(pathData.pathPoints, points_count * size);
                                            pathPoints[points_count] = (PathPoint)Marshal.PtrToStructure(newPtr, typeof(PathPoint));
                                        }

                                        pathDownloadData.pathData.moveTime = pathData.moveTime;
                                        pathDownloadData.pathData.pathPointsNum = pathData.pathPointsNum;
                                        pathDownloadData.pathPara.index = 2; //轨迹下载参数设置
                                        pathDownloadData.pathPara.moveType = 1;

                                        for (int points_count = 0; points_count < 10000; points_count++)//将新的轨迹点位转回指针
                                        {
                                            Marshal.StructureToPtr(pathPoints[points_count], IntPtr.Add(pathDownloadData.pathData.pathPoints, points_count * size), false);
                                        }

                                        result = CS.cr_path_download(robotHandle, pathDownloadData);  //下载轨迹到索引2
                                        if (result == CRresult.sucess)
                                        {
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},已成功下载索引为2的轨迹");
                                        }
                                        else
                                        {
                                            Console.WriteLine($"行号：{GetLineNum().ToString()},结果：{result}");
                                        }
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

import cgxiapi
from ctypes import *
import time
import basestruct
import inspect

# 机械臂创建连接
robotHandle = 1
re0 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
# re0=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接

if re0[0].value == 0:
    robotHandle = re0[1].value
    result_activeTcp = cgxiapi.cr_cfg_tcp_active_get(robotHandle)   #读取当前激活的TCP索引
    if result_activeTcp[0].value==0:
        index = 0
        tcpMsg = basestruct.TCPMsg()
        result_getTcp = cgxiapi.cr_cfg_tcp_get(robotHandle, index, tcpMsg)   #需要先存在索引号为0的TCP
        if result_getTcp.value==0:
            offset = [3,10,9,90,80,70]
            i=0
            while i<6:
                tcpMsg.tcpOffset[i] = offset[i]
                i+=1
            result_setTcp = cgxiapi.cr_cfg_tcp_set(robotHandle, index, tcpMsg)  #编辑索引号为0的TCP数据
            if result_setTcp.value==0:
                tcpMsg2 = basestruct.TCPMsg()
                tcpMsg2.tcpName = b'tcp_222'
                offset2 = [5,10,15,10,20,30]
                i = 0
                while i < 6:
                    tcpMsg2.tcpOffset[i] = offset2[i]
                    i += 1
                result_add = cgxiapi.cr_cfg_tcp_add(robotHandle, tcpMsg2)   #增加tcp
                if result_add.value==0:
                    index = 1
                    result_setActive = cgxiapi.cr_cfg_tcp_active_set(robotHandle, index)  #读取当前激活的TCP索引
                    if result_setActive.value==0:
                        result_activeTcp2 = cgxiapi.cr_cfg_tcp_active_get(robotHandle)  # 读取当前激活的TCP索引
                        if result_activeTcp2[0].value==0:
                            print("行数：", inspect.currentframe().f_lineno, "  当前激活的TCP索引为",result_activeTcp2[1].value)
                            index = 0
                            result_delete = cgxiapi.cr_cfg_tcp_delete(robotHandle, index)   #删除索引号为0的TCP
                            if result_delete.value==0:
                                print("行数：", inspect.currentframe().f_lineno, "  已成功删除索引号为0的TCP")
                            else:
                                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：",result_delete.value)
                        else:
                            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_activeTcp2[0].value)
                    else:
                        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_setActive.value)
                else:
                    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_add.value)
            else:
                print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_setTcp.value)
        else:
            print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_getTcp.value)
    else:
        print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", result_activeTcp[0].value)
else:
    print("行数：", inspect.currentframe().f_lineno, "  ", "结果：", re0[0].value)
result_destroy=cgxiapi.cr_destroy_robot(robotHandle)
if result_destroy.value!=0:
    print("断开失败")
    exit()
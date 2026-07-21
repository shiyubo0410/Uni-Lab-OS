import cgxiapi
from ctypes import *
import time
import basestruct
import sys
from pprint import pprint

# 机械臂创建连接
robotHandle = 1
re1 = cgxiapi.cr_create_robot(robotHandle, "192.168.6.6", 2323, "123")
# re1=cgxiapi.cr_create_robot(robotHandle, "127.0.0.1", 2325,"123")  #虚拟臂连接
print("机械臂建立连接返回值：", re1[0].value)
if re1[0].value != 0:
    print("连接失败")
    exit()
robotHandle = re1[1].value


##3.3.1硬件信息
#读取控制柜硬件序列号
def api_demo_cr_get_productInfo():
    result = cgxiapi.cr_get_productInfo(robotHandle)
    print("读取控制柜硬件序列号结果：", result[0].value)
    print("控制柜硬件序列号为：", result[1].value)
    assert (result[0].value == 0)


#读取整臂序列号
def api_demo_cr_get_productSn():
    result = cgxiapi.cr_get_productSn(robotHandle)
    print("读取整臂序列号结果：", result[0].value)
    print("整臂序列号为：", result[1].value)
    assert (result[0].value == 0)


#获取版本信息
def api_demo_cr_get_sysVersion():
    version = basestruct.SysVersion()
    result = cgxiapi.cr_get_sysVersion(robotHandle, version)
    print("获取版本信息结果：", result.value)

    # print("控制器", version.kzqVersion.deviceType[0:])
    # print("控制器",version.kzqVersion.versionNo[0:])
    # print("控制器", version.kzqVersion.bugfix)
    # print("控制器", version.kzqVersion.buildDate)
    # print("控制器", version.kzqVersion.hardwareID[0:])
    # print("控制器", version.kzqVersion.bootVersionNo[0:])

    print("\n")

    kzq_version = bytes(version.kzqVersion.versionNo)
    str_kzqversion = kzq_version.decode()
    print("获取控制柜版本结果",str_kzqversion)


#主函数
def main():
    #####在此处调用函数
    # api_demo_cr_get_sysVersion()
    api_demo_cr_get_sysVersion()
    # 机械臂断开连接
    cgxiapi.cr_destroy_robot(robotHandle)

if __name__ == "__main__":
    main()




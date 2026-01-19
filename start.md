
```bash
conda deactivate
conda activate unilab
```

D:\Uni-Lab\Uni-Lab-OS\test\experiments\prcxi_9320.json   修改IP
网络一致


# 云端控制，运行配置文件

```bash
unilab -g test\experiments\prcxi_9320.json --ak 911bc7f0-5ea6-4874-9fae-8e5cc0ecbce2 --sk 13bfedb0-4aed-43d7-bdbf-e8dd5e3d7b6a --upload_registry --addr test --disable_browser
```

浏览器打开 https://uni-lab.test.bohrium.com/uni-lab

仿真：
```python
"setup": false,
"debug": true,
"simulator": true,
```

真机：
```python
"setup": true,
"debug": false,
"simulator": false,
```


# 本地控制，运行Python程序

```bash
C:/Users/dp1/miniforge3/envs/unilab/python.exe d:/Uni-Lab/Uni-Lab-OS/unilabos/devices/liquid_handling/prcxi/prcxi.py
```


# 动作
```python
    asyncio.run(handler.create_protocol(protocol_name="Test Protocol"))
    asyncio.run(handler.pick_up_tips([plate5.get_item("C5")], [0]))
    asyncio.run(handler.aspirate([plate9.get_item("H12")], [5], [0]))
    asyncio.run(handler.dispense([plate10.get_item("H12")], [1], [0]))
    asyncio.run(handler.mix([plate10.get_item("H12")], mix_time=3, mix_vol=5))
    asyncio.run(handler.discard_tips([0]))
    asyncio.run(handler.run_protocol())
```

# Python环境选择

Ctrl + Shift + P
输入：Python: Select Interpreter
选择Unilab对应的Python环境


# 更新dev分支(pull)
```bash
git branch   #查看当前分支

git chechout dev  #如果当前分支不是dev,需要切换

git pull origin dev  #拉取最新远程代码

git log --online -5  #查看最近的5个提交记录，确认更新成功


git stash         #暂存再拉取，清理仓库工作树
git pull
git stash pop
```

# 上传修改分支(push)
    打开源代码管理(Ctrl+Shift+G)
    暂存文件(+)
    输入Message:
        feat	    新功能
        fix	        修复 bug
        docs	    文档更新
        style	    代码格式/风格/空格等，不影响功能
        refactor	重构代码，不改功能
        test	    添加或修改测试
        chore	    构建流程、工具配置等杂项
    推送到分支(Sync Changes)




# workshop 有机

```bash
unilab -g d:\Uni-Lab\Uni-Lab-OS\unilabos_data\workshop1.json --ak 3a836e8b-c58d-47c9-b96f-a1808a9ef844 --sk 50f8da19-8db4-4e02-a994-dca94fc9e52e --upload_registry --addr test
```

```bash
python unilabos/app/main.py -g workshop.graphml --ak 7c3eb977-e7eb-4dcd-91cb-ca2db8b203ec --sk 89ba4245-3486-4b40-b321-33c2c9dd9f75 --addr test --upload_registry
```


# 常量合成仿真

```bash
unilab -g test/experiments/comprehensive_protocol/comprehensive_station.json --ak 7c3eb977-e7eb-4dcd-91cb-ca2db8b203ec --sk 89ba4245-3486-4b40-b321-33c2c9dd9f75 --upload_registry --addr test
```


C:\Users\dp1\miniforge3\envs\unilab\Lib\site-packages\control_msgs\action\_single_joint_position.py


# Raman
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\devices\opsky_Raman\devices.json --ak 2b01d39c-dd22-4330-a9bf-481fa87335cf --sk 44074b78-2e0d-44d8-b66d-388a692a27b3 --upload_registry --addr test
```

unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\devices\opsky_Raman\devices.json --ak 9ad55416-5b44-4ed8-a109-1a530c3521c3 --sk 0a4f9e63-9e2e-44ea-8d66-4ba5fa61ff75 --upload_registry --addr test


# 过柱机测试

```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\guozhuji.json --ak 406dd4ed-f4ed-4e73-ad09-34eed8bf627f --sk 857d021c-da00-4bcc-aa02-9321ce1d1b2e --upload_registry --addr test --port 8003
```



# 实验室组网

1. 笔记本Host：

在终端1激活unilab环境后
```bash
fast-discovery-server -l 0.0.0.0 -p 11811 -i 0
```

在终端2激活unilab环境后
```bash
ros2 daemon stop
set RMW_IMPLEMENTATION=rmw_fastrtps_cpp
set ROS_DISCOVERY_SERVER=UDPv4:[172.16.9.134]:11811
set ROS_SUPER_CLIENT=1
set FASTDDS_BUILTIN_TRANSPORTS=UDPv4
```
启动unilab指令，主机需要启动一个空的json
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\test\experiments\start.json --ak b26253b3-6cc0-45a3-8d4a-103e5fd338f6 --sk 7c0ad7da-9234-4f50-a764-16eb5c5a1d2b --addr test --upload_registry
```

2. 台式机Slave：

激活unilab环境后
```bash
ros2 daemon stop
set RMW_IMPLEMENTATION=rmw_fastrtps_cpp
set ROS_DISCOVERY_SERVER=UDPv4:[172.16.9.134]:11811
set ROS_SUPER_CLIENT=1
set FASTDDS_BUILTIN_TRANSPORTS=UDPv4
```
启动unilab指令，加 --is_slave


检查主站从站是否在同一网络下
注意172.16.9.134为主机的ip，通过ipconfig查找



# XRD上传结果测试

```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\xrd_simulation.json --ak 11f255fc-c191-4132-9824-6ad11973693a --sk cee0e852-d98b-43b1-9384-6d76166323b2 --upload_registry --addr test
```
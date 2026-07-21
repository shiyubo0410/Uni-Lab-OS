
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

unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\devices\opsky_Raman\devices.json --ak 11f255fc-c191-4132-9824-6ad11973693a --sk cee0e852-d98b-43b1-9384-6d76166323b2 --upload_registry --addr test


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


# 单注射泵测试
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\runze.json --ak 64ad9e59-cc5c-45bf-96e8-e70182e64710 --sk 484e3498-06da-4790-a094-8471189d59e5 --upload_registry --addr test
```

# 双注射泵测试
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\pump_2.json --ak 567c9953-c34e-4fc7-8b49-2c62cf31be31 --sk 3d93504e-e016-4cc1-91ed-e4aa882ae97b --upload_registry --addr test
```


# 晶飞
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\jingfei.json --ak 4382c54e-175f-4695-8731-4c5bc17a3e4e --sk 2ccc0792-f5c0-44a4-95f0-6e67e4f77ae6 --upload_registry --addr test
```



# 北大附萃取测试
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\chinwe.json --ak 4f6fb55e-b3e1-4ef2-afd7-f89af60dd385 --sk 5dc92243-a7c3-4ec7-8f03-874a7203c3b7 --upload_registry --addr test
```

# 电导传感器
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\XKC.json --ak 8e173a67-a5b2-40fb-8f0a-8be22baece64 --sk e8fbf9b2-2387-4ddb-ba5a-a0b1ed237bd3 --upload_registry --addr test
```

# 泵和电导传感器合并
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\wxf.json --ak 91fa035e-6dc0-4497-a519-a3f82dca1a2c --sk 24e19620-8861-4515-847d-bf5471c5fa3d --upload_registry --addr test
```

# 石景山9300
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\prcxi_9300_slim.json --ak 3b8eac59-01a2-46aa-b5bc-575e4281da97 --sk e10aed07-0139-4b1b-8183-a3bbe354e76c --upload_registry --addr test
```

# 石景山铼羽
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\sjs_laiyu.json --ak 9e351848-6ab7-4d5c-8d51-2782d24b5ea2 --sk 6046ea9e-ed6e-4728-ad59-c2baf646565b --upload_registry --addr test
```

# 物联网注册设备
```bash
unilab --upload_registry --addr test --ak e6d14766-1782-4221-a4aa-4ae09be87f26 --sk 60f18e41-869f-49c6-ba38-660237091b9d
```

# 设备广场上报
```bash
unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\ika.json --ak d629d65b-0ccc-489b-9695-5979df6d9968 --sk 063f62dc-f8ed-4f05-9664-55da7476c983 --upload_registry --addr test --disable_browser
```




unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\ika.json --ak 15275e97-84d1-40f4-b897-684242495f4d --sk 8efdf5c4-d13c-4147-9ea8-dee2a8162249 --upload_registry --addr test --disable_browser


http://unilab-gateway.local/api/config/apply?ak=778fc077-eb18-4e85-bdbb-ec0cbef401db&sk=622a4cb1-5e78-4276-99d9-d7a763bd2a62&mount_uuid=07644cb0-74fd-42e3-8816-fc335b926457&ws_url=wss://leap-lab.test.bohrium.com/api/v1/ws/schedule&http_url=https://leap-lab.test.bohrium.com/api/v1




unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\danbai.json --ak 477e5aff-2e9b-44c2-8cbf-431bbd4085b9 --sk 156ac0fd-9e73-43d1-a746-bf921add7dc7 --upload_registry --addr test --disable_browser

unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\danbai.json --ak 7d087267-bb5a-4e74-8479-887d3978ea24 --sk 527fe662-a181-4922-972a-28f365bd7f29 --upload_registry --addr test --disable_browser


unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\test\experiments\danbai.json --ak 32363e9b-b60e-4e9c-a029-38daa0e81794 --sk 70a59624-daa9-43d7-be6c-a7384a79f39d --upload_registry --addr test --disable_browser

# 上海大学工站
```bash
unilab --ak 7d1d2ea0-5510-4ce2-a08c-d15672857ab8 --sk 83c9dde6-b023-4f66-a04c-4cc384f16594 --upload_registry --addr https://leap-lab.bohrium.com/api/v1 --disable_browser
```

unilab -g D:\Uni-Lab\Uni-Lab-OS\unilabos\devices\SHU\graph_combined_lab1.json --ak c6a32f93-fb47-4ab9-95a0-0256ce009530 --sk 50dfce27-171d-4d08-8844-2e34579e2713 --upload_registry --addr https://leap-lab.bohrium.com/api/v1 --disable_browser

# 🧠 ROS 2 常用命令速查表

适用于 ROS 2 Humble / Iron / Foxy 等版本

---

## 🚀 一、系统基础

```bash
# 启动 ROS 2 环境
source /opt/ros/<distro>/setup.bash

# 启动工作区环境
source install/setup.bash

# 查看 ROS 版本
ros2 --version

# 查看帮助
ros2 --help
ros2 <command> --help
```

---

## 🧩 二、节点（Node）

```bash
# 列出所有节点
ros2 node list

# 查看节点信息（发布/订阅/服务/动作）
ros2 node info <node_name>

# 启动节点
ros2 run <package_name> <executable>

# 启动节点并传入参数
ros2 run <pkg> <exe> --ros-args -p <param_name>:=<value>
```

---

## 🗣️ 三、话题（Topic）

```bash
# 列出所有话题
ros2 topic list

# 查看话题信息
ros2 topic info <topic_name>

# 查看话题类型
ros2 topic type <topic_name>

# 实时监听消息
ros2 topic echo <topic_name>

# 发布测试消息
ros2 topic pub <topic_name> <msg_type> '{data}'

# 示例
ros2 topic pub /chatter std_msgs/String "{data: 'hello'}"

# 查看消息发布频率
ros2 topic hz <topic_name>

# 查看带宽使用
ros2 topic bw <topic_name>
```

---

## ⚙️ 四、服务（Service）

```bash
# 列出所有服务
ros2 service list

# 查看服务类型
ros2 service type <service_name>

# 调用服务
ros2 service call <service_name> <srv_type> '{request}'

# 示例
ros2 service call /add_two_ints example_interfaces/srv/AddTwoInts "{a: 2, b: 3}"
```

---

## ⏱️ 五、动作（Action）

```bash
# 列出所有动作
ros2 action list

# 查看动作类型
ros2 action type <action_name>

# 查看动作详细信息
ros2 action info <action_name>

# 发送目标
ros2 action send_goal <action_name> <action_type> '{goal_data}'

# 示例
ros2 action send_goal /fibonacci action_tutorials_interfaces/action/Fibonacci "{order: 5}"
```

---

## 🔧 六、参数（Param）

```bash
# 查看所有参数
ros2 param list

# 查看指定节点参数
ros2 param list /node_name

# 获取参数值
ros2 param get /node_name param_name

# 设置参数值
ros2 param set /node_name param_name value

# 使用参数文件启动节点
ros2 run <pkg> <exe> --ros-args --params-file config.yaml
```

---

## 🧰 七、消息 / 服务 / 动作 定义查看

```bash
# 列出所有消息类型
ros2 msg list

# 查看消息定义
ros2 msg show <msg_type>

# 列出所有服务类型
ros2 srv list

# 查看服务定义
ros2 srv show <srv_type>

# 列出所有动作类型
ros2 action list

# 查看动作定义
ros2 interface show <action_type>
```

---

## 📦 八、包与构建（Package & Build）

```bash
# 列出所有包
ros2 pkg list

# 查看包路径
ros2 pkg prefix <package_name>

# 查看包内可执行文件
ros2 pkg executables <package_name>

# 构建工作区
colcon build

# 清理缓存重新构建
colcon build --symlink-install --cmake-clean-cache
```

---

## 🧾 九、Launch 文件

```bash
# 启动 launch 文件
ros2 launch <package> <launch_file>.py

# 启动并传参
ros2 launch <pkg> <launch>.py param:=value

# 查看包路径
ros2 pkg prefix <pkg> --share
```

---

## 🧭 十、可视化与调试工具

```bash
# 查看节点-话题通信图
rqt_graph

# 动态参数调整
rqt_reconfigure

# 查看日志
cd ~/.ros/log

# 清理日志
rm -rf ~/.ros/log
```

---

## 💡 常用组合示例

```bash
# 查看当前系统通信结构
ros2 node list && ros2 topic list && ros2 service list

# 监听并测试一个话题
ros2 topic echo /my_topic
ros2 topic pub /my_topic std_msgs/String "{data: 'test'}"

# 调用一个服务
ros2 service call /reset std_srvs/srv/Empty "{}"

# 快速调试节点
ros2 run demo_nodes_cpp talker
ros2 run demo_nodes_cpp listener
```

---

## 🧾 附录：常用消息类型

| 类型 | 描述 |
|------|------|
| std_msgs/String | 字符串消息 |
| std_msgs/Int32 | 整型消息 |
| geometry_msgs/Twist | 线速度 + 角速度 |
| sensor_msgs/Image | 图像数据 |
| sensor_msgs/LaserScan | 激光雷达数据 |
| nav_msgs/Odometry | 里程计数据 |

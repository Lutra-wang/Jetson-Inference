# Jetson Robot Vision Gateway 开发报告

日期：2026-08-05
项目目录：`/data/project/jetson_inference`
项目定位：基于 Jetson Nano 的机器人端侧视觉感知与控制网关
当前状态：Jetson Nano + USB 摄像头 + TensorRT 推理 + Web 可视化 + 运行时加速链路已跑通

发布态说明：GitHub 仓库不提交完整第三方源码、运行日志和本地缓存；`third_party/` 仅保留说明文件，`jetson-inference` 等外部仓库按部署文档在本地或 Jetson 上按需同步。

## 1. 项目背景

本项目面向机器人系统集成、嵌入式 Linux 和端侧部署场景。当前硬件条件为 Jetson Nano 开发板和 USB 摄像头，暂时没有真实移动底盘、机械臂或 ROS2 真机平台。因此第一阶段没有把目标设定为完整机器人运动控制，而是先实现一个稳定可演示、可扩展到机器人执行链路的端侧视觉网关。

项目核心闭环如下：

```text
USB Camera
  -> Jetson Nano 端侧推理
  -> 结构化感知 JSON
  -> 目标跟随状态机
  -> 速度指令 JSON
  -> Web Dashboard / HTTP API / 后续 ROS2 Bridge
```

这个定位更贴合当前硬件现实：先把“摄像头输入、端侧推理、控制决策、网络可视化、性能监控”打通，再把输出接入 `/cmd_vel` 或其他机器人中间件。

## 2. 开发目标

第一阶段目标包括：

- 在 Jetson Nano 上识别 USB 摄像头并完成真实视频采集。
- 接入 `dusty-nv/jetson-inference`，使用 TensorRT 后端完成目标检测。
- 将检测结果抽象为稳定的数据结构，输出检测框、类别、置信度、中心点和面积比例。
- 基于检测结果实现目标跟随状态机，生成 `linear_x` 和 `angular_z`。
- 提供 Flask Web 服务，展示实时 MJPEG 画面、检测结果、FPS、状态机和运行参数。
- 接入 `tegrastats`，在 Web 页面和 `/api/perf` 暴露 Jetson 运行状态。
- 参考 NVIDIA Jetson skills 完成可逆的运行时加速和回环测试。

暂缓目标包括：

- 不在第一阶段训练自定义模型。
- 不在 Jetson Nano 上强行部署 ROS2 Humble。
- 不修改 BSP、不重新刷机、不做不可逆系统调整。
- 不接真实底盘，先保留 JSON/UDP/ROS2 bridge 扩展口。

## 3. 硬件与系统环境

已验证平台信息：

```text
开发板: Jetson Nano / t210ref / aarch64
Jetson Linux: L4T R32.7.4
Kernel: 4.9.337-tegra
Ubuntu: 18.04
Python: 3.6.x
项目目录: /home/jetson/project 或 /data/project/jetson_inference
数据盘: /data
摄像头: /dev/video0
```

USB 摄像头能力：

```text
MJPG:
  1920x1080 @ 30 FPS
  1280x720  @ 30 FPS
  960x544   @ 30 FPS
  800x480   @ 30 FPS
  640x360   @ 30 FPS

YUYV:
  1920x1080 @ 10 FPS
  1280x720  @ 15 FPS
  960x544   @ 30 FPS
  800x480   @ 30 FPS
  640x360   @ 30 FPS
```

实际运行中优先选择 `MJPG`，原因是 USB 摄像头在 720p 和 960x544 下都能提供 30 FPS，且 Jetson 端 CPU 压力比 YUYV 更可控。当前加速版推荐配置为：

```text
config/jetson_usb_960x544.json
/dev/video0
960x544 @ 30 FPS
codec=mjpeg
```

## 4. 系统架构

项目按“输入、推理、策略、输出、展示”拆分模块：

```text
config/
  -> 保存 camera / detector / policy / web 配置

src/jrvg/model.py
  -> 定义 Detection、PerceptionFrame、VelocityCommand、PolicyOutput

src/jrvg/detector.py
  -> Detector 抽象
  -> MockDetector 本地开发后端
  -> JetsonInferenceDetector Jetson TensorRT 后端

src/jrvg/policy.py
  -> TargetTrackingPolicy 目标跟随状态机

src/jrvg/web_app.py
  -> Flask Web Dashboard
  -> /api/status
  -> /api/status.ndjson
  -> /api/perf
  -> /api/stream.mjpg

scripts/
  -> 环境探测、烟测、Web 启动、性能对比、回环测试
```

数据流：

```text
Camera frame
  -> Detector.detect()
  -> PerceptionFrame
  -> TargetTrackingPolicy.update()
  -> PolicyOutput
  -> HTTP JSON / MJPEG overlay / future robot command
```

这种拆分让本地开发和 Jetson 部署保持同一套上层接口。本地可以用 `MockDetector` 跑通状态机和 Web，Jetson 上只替换为 `JetsonInferenceDetector`。

## 5. 核心实现

### 5.1 数据模型

`src/jrvg/model.py` 定义了四类核心数据：

- `Detection`：单个目标检测结果，包含类别、置信度、边界框、中心点和面积占比。
- `PerceptionFrame`：单帧感知结果，包含时间戳、帧号、FPS、分辨率和检测列表。
- `VelocityCommand`：速度指令，目前包含 `linear_x` 和 `angular_z`。
- `PolicyOutput`：策略输出，包含状态、目标类别、速度指令和决策原因。

所有模型都提供 `to_dict()`，方便直接序列化为 JSON，减少 Web/API/日志之间的数据转换成本。

### 5.2 推理后端

`src/jrvg/detector.py` 使用抽象基类 `Detector` 统一推理接口。

本地开发阶段使用 `MockDetector`，它会生成一个周期性移动的 `person` 检测框，用于验证：

- JSON 输出格式是否稳定。
- 目标跟随策略是否能根据目标位置变化输出角速度。
- Web 页面是否能正常刷新检测框、FPS 和控制状态。

Jetson 部署阶段使用 `JetsonInferenceDetector`，它对 `jetson.inference.detectNet` 和 `jetson.utils.videoSource` 做封装：

- 通过惰性导入避免本地开发环境必须安装 Jetson 专有库。
- 使用 `ssd-mobilenet-v2` 作为第一阶段目标检测模型。
- 将 camera 的 `width / height / fps / codec` 从配置文件传入 `videoSource`。
- 在开启可视化时保存最近一帧图像，用于 Web MJPEG 叠加显示。

### 5.3 控制策略

`src/jrvg/policy.py` 实现 `TargetTrackingPolicy`。策略以 `person` 为默认目标，状态包括：

```text
TRACKING: 检测到目标，输出跟随速度
LOST: 短时丢失目标，速度清零但还未进入长期停止
STOP: 目标过近或连续丢失过久，停止运动
```

核心规则：

- 只从检测结果中选择目标类别，如 `person`。
- 多个目标出现时选择置信度最高的检测框。
- 使用目标中心点相对画面中心的水平误差生成 `angular_z`。
- 使用目标面积占比估计距离，面积越大线速度越小。
- 当面积超过 `stop_area_ratio` 时停止，避免靠得太近。
- 当连续丢失帧数超过 `lost_frames_to_stop` 时停止。

当前默认参数：

```text
center_deadband: 0.12
max_linear_x: 0.18
max_angular_z: 0.6
stop_area_ratio: 0.32
lost_frames_to_stop: 6
```

这些参数没有绑定真实底盘，因此现阶段以“可解释、可展示、可接入”为主，后续接底盘后再根据实际运动学和安全距离调参。

### 5.4 Web 服务

`src/jrvg/web_app.py` 使用 Flask 实现可视化和 API。服务启动后后台线程持续采集、推理和更新状态，前端页面周期性读取 JSON，并从 MJPEG 接口读取实时画面。

接口如下：

```text
GET /
  Web Dashboard

GET /api/status
  当前单帧感知、策略和运行配置快照

GET /api/status.ndjson
  连续 JSON Lines 状态流

GET /api/perf
  tegrastats 性能快照

GET /api/stream.mjpg
  带检测框和状态栏的实时 MJPEG 画面
```

Web 页面展示内容：

- 实时视频流。
- 检测框、类别、置信度、中心点。
- 当前 FPS 和帧号。
- 策略状态、线速度、角速度。
- 运行配置，如 backend、camera、network、stream FPS、JPEG quality。
- Jetson 性能数据，如 RAM、GPU、温度和功耗。

### 5.5 性能监控

Web 服务中新增了 `TegrastatsMonitor`，通过后台线程运行：

```bash
tegrastats --interval 1000
```

然后解析常用字段：

- `RAM used/total`
- `SWAP used/total`
- `GR3D_FREQ`
- `EMC_FREQ`
- `CPU [...]`
- 温度字段，如 `CPU@xxC`
- 功耗字段，如 `VDD_IN`

解析结果通过 `/api/perf` 返回，也合并进 `/api/status`，用于 Web 页面展示。

## 6. 实际开发过程

### 6.1 本地工程骨架

项目最初先在电脑端搭建 Python 包结构，使用 `MockDetector` 跑通端到端数据流。这样做的原因是 Jetson 侧依赖较重，直接在板子上边装环境边写业务逻辑风险较高。

本地阶段完成内容：

- 初始化 `src/jrvg` 模块。
- 定义数据模型。
- 实现 mock 推理。
- 实现状态机策略。
- 提供命令行主程序。
- 增加本地 benchmark 脚本。

本地验收命令：

```bash
PYTHONPATH=src python3 -m jrvg.main --backend mock --frames 30
bash scripts/benchmark_mock.sh
```

### 6.2 Jetson 硬件接入

硬件平台搭建完成后，先在 Jetson 上确认系统版本、数据盘和摄像头：

```bash
bash scripts/probe_jetson.sh
bash scripts/probe_camera.sh /dev/video0
```

这个阶段确认了：

- Jetson Nano 可以通过 SSH 登录。
- 系统为 L4T R32.7.4。
- `/data` 可作为项目、模型和日志目录。
- `/dev/video0` 能被识别。
- 摄像头支持 MJPG 720p/960x544/1080p。

### 6.3 Python 依赖问题

第一次启动 Web 服务时出现：

```text
ModuleNotFoundError: No module named 'flask'
```

说明项目代码已同步到 Jetson，但运行时依赖还没装。随后执行 `python3 -m pip install` 又遇到：

```text
/usr/bin/python3: No module named pip
```

处理方式是先通过系统包安装：

```bash
sudo apt-get install -y python3-pip python3-numpy
```

随后安装项目依赖。过程中还遇到 `numpy` 通过 pip 源码编译失败：

```text
RuntimeError: Running cythonize failed!
```

原因是 Jetson Nano 上 Python 3.6、Ubuntu 18.04 和 ARM64 环境下直接 pip 编译 NumPy 成本高且容易失败。最终处理方式：

- 使用 Ubuntu 源中的 `python3-numpy` 预编译包。
- 从 `requirements-jetson.txt` 移除裸 `numpy` 依赖，避免 pip 再次尝试源码编译。
- Flask 等 Python 依赖固定到兼容 Python 3.6 的版本。

还出现过一次 shell 换行错误，把 `--trusted-host` 单独作为命令执行：

```text
-bash: --trusted-host: command not found
```

修正方式是重新输入完整的 `python3 -m pip install ... -r requirements-jetson.txt` 命令，确保反斜杠换行没有中断。

### 6.4 jetson-inference 接入

基础依赖通过后，项目烟测卡在：

```text
missing: jetson.inference, jetson.utils
Install/build dusty-nv/jetson-inference, then rerun this script.
```

这说明项目依赖和摄像头都已经具备条件，缺的是 Jetson 侧 TensorRT 推理库的 Python 绑定。

实际开发中出现过两个典型错误。

第一，把 GitHub URL 当作 shell 命令直接执行：

```bash
https://github.com/dusty-nv/jetson-inference.git
```

正确做法应为：

```bash
git clone --recursive --depth=1 https://github.com/dusty-nv/jetson-inference.git
```

第二，在错误目录执行 CMake：

```bash
cd /data
mkdir -p build
cd build
cmake ../
```

报错原因是 `/data` 不是 `jetson-inference` 源码目录，没有 `CMakeLists.txt`。最终将第三方源码统一放进项目目录：

```text
third_party/jetson-inference
```

正确构建路径为：

```bash
cd ~/project/jetson_inference/third_party/jetson-inference
mkdir -p build
cd build
cmake -DBUILD_DEPS=NO -DBUILD_INTERACTIVE=NO ../
make -j1
sudo make install
sudo ldconfig
```

过程中还补齐了 CUDA Toolkit、TensorRT、cuDNN 和 Python 绑定相关依赖。最终验证：

```bash
python3 -c "import jetson.inference, jetson.utils; print('jetson-inference ok')"
```

### 6.5 真实推理烟测

`jetson-inference` 安装完成后，运行：

```bash
cd ~/project/jetson_inference
bash scripts/smoke_jetson_inference.sh /dev/video0
```

烟测脚本依次检查：

- Jetson 平台信息。
- 摄像头设备和格式。
- 项目 Python 依赖。
- `jetson.inference` 与 `jetson.utils` Python 绑定。
- 真实摄像头推理输出。

烟测通过后，项目从 mock 后端切换到真实 Jetson 后端。实测 720p/960x544 场景下，SSD-Mobilenet-v2 推理帧率约 20-21 FPS。

### 6.6 Web 可视化

真实推理跑通后，增加 Flask Web Dashboard。启动命令：

```bash
cd ~/project/jetson_inference
PYTHONPATH=src python3 -m jrvg.web_app \
  --config config/jetson_usb_720p.json \
  --backend jetson \
  --camera /dev/video0 \
  --host 0.0.0.0 \
  --port 5000
```

后续优化为加速版脚本：

```bash
CONFIG=config/jetson_usb_960x544.json bash scripts/run_web_jetson_maxperf.sh /dev/video0
```

Web 端最终可以展示：

- 摄像头实时画面。
- 目标检测框。
- 当前推理 FPS。
- `TRACKING / LOST / STOP` 状态。
- `linear_x / angular_z`。
- 当前运行配置。
- Jetson 性能状态。

### 6.7 网络和文件同步

开发过程经历过两种网络拓扑。

第一种是 Jetson 接墙壁网口、电脑接 Wi-Fi。该模式曾可 SSH 到 Jetson，但后续重启、网段变化和 DHCP 变化导致 IP 不稳定，需要按 MAC 查找。

第二种是电脑和 Jetson 网线直连，电脑通过 Wi-Fi 上网，并用 NetworkManager 给以太网口开启共享网络。最终直连状态为：

```text
电脑有线网口: 192.168.55.1/24
Jetson eth0: 192.168.55.109/24
Jetson MAC: 3C:6D:66:00:67:E1
Jetson hostname: ubuntu
SSH: ssh jetson@192.168.55.109
```

直连模式下，Jetson 默认路由指向电脑：

```text
default via 192.168.55.1 dev eth0
```

并已验证：

- 电脑可以 ping 通 Jetson。
- Jetson 可以 ping 通电脑网关。
- Jetson 可以 ping 通 `8.8.8.8`。
- Jetson 可以解析并 ping `github.com`，但稳定性一般。

由于 Jetson 直接下载 GitHub 经常只有约 10 KB/s，最终采用“电脑下载/克隆，rsync 同步到 Jetson”的方式：

```bash
cd /data/project/jetson_inference
rsync -av --progress \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'third_party/jetson-inference/build/' \
  ./ jetson@192.168.55.109:~/project/jetson_inference/
```

这种方式避免 Jetson 反复访问 GitHub，也便于把第三方源码、项目脚本和配置文件统一纳入项目目录管理。

## 7. 运行时加速

加速方案参考了 NVIDIA 的 `jetson-device-skills` 和 `jetson-bsp-skills`。本项目只采用可逆的运行时优化，不做 BSP 级改动。

实际使用的方向：

- 用 device skills 做设备信息、内存、服务和热状态诊断。
- 用 memory/headless 相关 skill 指导关闭图形界面和不必要后台服务。
- 用 `nvpmodel` 切换 MAXN 性能模式。
- 用 `jetson_clocks` 锁定 CPU/GPU/EMC 时钟。
- 用配置文件降低图像分辨率到 960x544。
- 限制 Web MJPEG 输出帧率到 10 FPS。
- 降低 JPEG 质量到 70，减少编码和网络压力。
- 开启 `/api/perf` 做运行时观测。

加速启动脚本：

```bash
cd ~/project/jetson_inference
CONFIG=config/jetson_usb_960x544.json bash scripts/run_web_jetson_maxperf.sh /dev/video0
```

脚本主要动作：

```text
sudo nvpmodel -m 0
sudo jetson_clocks
PYTHONPATH=src python3 -m jrvg.web_app
  --backend jetson
  --stream-fps 10
  --jpeg-quality 70
  --enable-tegrastats
```

Headless 优化结果：

```text
default_systemd_target: graphical.target -> multi-user.target
display-manager: active -> inactive
used memory: 725 MB -> 207 MB
free memory: 2652 MB -> 3384 MB
available memory: 3069 MB -> 3597 MB
used memory: -518 MB
free memory: +732 MB
available memory: +528 MB
idle tegrastats RAM avg: 806.4 MB -> 240.1 MB
```

实测 Web 加速版：

```text
camera runtime: /dev/video0 960x544@30 mjpeg
perception width/height: 960 x 544
detector fps: 约 21.4-21.6 FPS
target: person
policy state: STOP / TRACKING 随目标距离和画面变化切换
```

运行状态样例：

```text
RAM: 1584/3964 MB
SWAP: 0/6078 MB
GR3D_FREQ: 71%-99%, avg about 89.7%
CPU temp: up to about 39 C
GPU temp: about 36-37 C
```

## 8. 回环测试

为了验证端到端链路不是只在 Jetson 本机可用，项目增加：

```bash
scripts/loopback_jetson_web.sh
```

电脑端测试命令：

```bash
cd /data/project/jetson_inference
bash scripts/loopback_jetson_web.sh 192.168.55.109 5000
```

脚本检查：

- 局域网邻居 MAC。
- `/api/status` 是否返回 JSON。
- `/api/perf` 是否返回性能数据。
- `/api/stream.mjpg` 是否能拉取连续 MJPEG 数据。
- MJPEG multipart boundary 是否存在。

此前局域网模式实测结果：

```text
/api/status: 1218 bytes
/api/perf: 434 bytes
/api/stream.mjpg: 3 秒采样 911869 bytes
MJPEG boundary: OK
result: loopback ok
```

回环测试说明 Web 服务、JSON API、MJPEG 视频流和性能接口已经可以从局域网客户端访问，具备演示和后续远程调试基础。

## 9. 关键问题与解决方案

| 问题 | 现象 | 解决方案 |
| --- | --- | --- |
| Flask 缺失 | `ModuleNotFoundError: No module named 'flask'` | 安装 `python3-pip` 后按 `requirements-jetson.txt` 安装 Python 依赖 |
| pip 缺失 | `/usr/bin/python3: No module named pip` | `sudo apt-get install -y python3-pip` |
| NumPy 编译失败 | `Running cythonize failed` | 使用 `sudo apt-get install -y python3-numpy`，不走 pip 源码编译 |
| 命令换行错误 | `--trusted-host: command not found` | 重新输入完整 pip 命令，保证反斜杠换行正确 |
| Jetson 绑定缺失 | `missing: jetson.inference, jetson.utils` | 编译安装 `third_party/jetson-inference` |
| URL 被当成命令 | `No such file or directory` | 使用 `git clone ...`，不能直接输入 URL |
| CMake 目录错误 | `/data` 没有 `CMakeLists.txt` | 在 `third_party/jetson-inference/build` 中运行 `cmake ../` |
| Jetson 下载极慢 | GitHub 约 10 KB/s | 电脑端下载/clone 后通过 `rsync` 同步 |
| IP 不稳定 | 旧 IP 无法 SSH | 通过 MAC、`nmap`、`ip neigh` 查找，直连时使用共享网段 `192.168.55.0/24` |
| Web 负载偏高 | 推理和 MJPEG 编码同时占资源 | 降分辨率、限制 stream FPS、降低 JPEG quality、开启 maxperf |

## 10. 当前项目成果

已经完成：

- Jetson Nano 系统、摄像头和 Python 基础环境验收。
- USB 摄像头真实视频采集。
- `jetson-inference` TensorRT 推理后端接入。
- SSD-Mobilenet-v2 目标检测运行。
- 感知结果 JSON 化。
- 目标跟随状态机。
- Web Dashboard 和 HTTP API。
- `tegrastats` 性能监控接口。
- 960x544 加速运行配置。
- `nvpmodel + jetson_clocks + headless` 运行时优化。
- 局域网 HTTP/MJPEG 回环测试。
- 项目同步、烟测、性能对比和运行脚本。

当前最短启动路径：

```bash
ssh jetson@192.168.55.109
cd ~/project/jetson_inference
CONFIG=config/jetson_usb_960x544.json bash scripts/run_web_jetson_maxperf.sh /dev/video0
```

电脑端访问：

```text
http://192.168.55.109:5000
```

电脑端回环测试：

```bash
cd /data/project/jetson_inference
bash scripts/loopback_jetson_web.sh 192.168.55.109 5000
```

## 11. 项目局限

当前阶段仍有以下限制：

- 速度指令尚未发送给真实底盘，只停留在 JSON 层。
- 控制参数没有经过真实机器人运动学标定。
- 目标检测使用通用 SSD-Mobilenet-v2，没有针对具体机器人场景训练。
- 性能数据还需要补齐多分辨率长时间对比。
- Web 页面具备演示能力，但还没有做截图归档和完整演示视频。
- Jetson 下载外网仍不稳定，依赖电脑侧同步方案。

## 12. 后续计划

优先级从高到低：

1. 补齐三档分辨率性能对比：

```bash
cd ~/project/jetson_inference
bash scripts/perf_compare.sh
```

记录 `640x360 / 960x544 / 1280x720` 下的 FPS、RAM、GR3D、温度和功耗。

2. 增加 UDP 或 ROS2 Bridge：

```text
Jetson Nano -> UDP JSON -> PC ROS2 Humble -> /cmd_vel
```

这样可以规避 Jetson Nano Ubuntu 18.04 与 ROS2 Humble 的系统版本不匹配问题。

3. 做参数调优：

- `threshold`
- `center_deadband`
- `max_linear_x`
- `max_angular_z`
- `stop_area_ratio`
- `lost_frames_to_stop`
- `stream_fps`
- `jpeg_quality`
- camera resolution

4. 整理演示资产：

- Web Dashboard 截图。
- 摄像头识别目标截图。
- `/api/status` JSON 截图。
- `/api/perf` 性能截图。
- 回环测试终端截图。
- 架构图和数据流图。
- 30-60 秒演示视频。

5. 做服务化部署：

- systemd service 启动 Web 服务。
- 自动创建日志目录。
- 开机后自动进入加速配置。
- 保留一键回滚 headless 的说明。

## 13. 结论

本项目已经从本地 mock 验证推进到 Jetson Nano 真实端侧部署：USB 摄像头采集、TensorRT 目标检测、结构化 JSON、目标跟随策略、Web 可视化、性能监控和局域网回环测试均已完成。开发过程中遇到的 Python 依赖、NumPy 编译、Jetson 专有库、网络下载、CMake 目录和 IP 变化问题都已形成可复现处理方法。

当前成果可以作为机器人系统和端侧部署方向的项目展示基础。下一步重点不是继续扩大功能，而是补齐性能对比数据、演示截图和 ROS2 bridge 设计，使项目从“可运行 demo”进一步变成“可复现、可量化、可讲清楚工程取舍”的完整项目。

# Resume Summary

## Recommended Version

**Role**: Edge Deployment / System Integration

**Project Summary**:  
Built a Jetson Nano based robot vision gateway with USB camera capture, TensorRT object detection, structured perception JSON, target-tracking state machine, velocity command generation, Web dashboard, and runtime performance optimization. Verified about `21.4-21.6 FPS` detection loop under `960x544@30 MJPG`, with LAN HTTP/MJPEG loopback passing.

**Key Points**:

- Designed a `mock / jetson` dual-backend detector interface and unified `PerceptionFrame / PolicyOutput` data models to decouple local development from Jetson deployment.
- Built and deployed `jetson-inference` on Jetson Nano B01 / L4T R32.7.4, using SSD-Mobilenet-v2 + TensorRT for USB-camera object detection.
- Implemented a `TRACKING / LOST / STOP` target-tracking state machine that maps target center offset and bounding-box area into `angular_z / linear_x`, with deadband, close-range stop, and lost-frame stop protection.
- Applied Jetson runtime optimization with headless mode, `nvpmodel`, `jetson_clocks`, MJPEG stream limiting, JPEG quality tuning, `/api/perf`, and loopback validation.

## Chinese Resume Version

**项目角色**：端侧部署 / 系统集成

**项目简述**：  
基于 Jetson Nano + TensorRT 构建机器人端侧视觉感知与控制网关，完成 USB 摄像头采集、SSD-Mobilenet-v2 目标检测、结构化 JSON 输出、目标跟随状态机、速度指令生成、Web 可视化和运行时性能优化；实测 `960x544@30 MJPG` 输入下端侧检测约 `21.4-21.6 FPS`，局域网 HTTP/MJPEG 回环通过。

**项目要点**：

- 设计 `mock / jetson` 双后端检测框架，统一输出 `PerceptionFrame / PolicyOutput`，实现本地开发与 Jetson 部署解耦。
- 在 Jetson Nano B01 / L4T R32.7.4 上源码构建并部署 `jetson-inference`，使用 SSD-Mobilenet-v2 + TensorRT 完成端侧目标检测。
- 实现 `TRACKING / LOST / STOP` 目标跟随状态机，将检测框中心偏差和面积占比映射为 `angular_z / linear_x`。
- 基于 Jetson runtime tuning 完成 headless、`nvpmodel`、`jetson_clocks`、`/api/perf` 和局域网回环验证。

## Interview Boundaries

- Do not claim a full robot control system; no real chassis is connected yet.
- Do not claim ROS2 deployment until the bridge is implemented and tested.
- Do not claim custom model training; the current model is SSD-Mobilenet-v2.
- Do not describe Web stream FPS as inference FPS.

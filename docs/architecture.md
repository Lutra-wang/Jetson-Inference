# Architecture

Jetson Robot Vision Gateway is organized as an edge perception gateway. It turns camera frames into structured perception data and robot-style velocity commands, then exposes the result through Web and JSON interfaces.

## System Flow

```mermaid
flowchart LR
  A[USB Camera<br/>/dev/video0] --> B[Detector]
  B --> C[PerceptionFrame JSON]
  C --> D[TargetTrackingPolicy]
  D --> E[PolicyOutput<br/>linear_x / angular_z]
  C --> F[Web Dashboard]
  D --> F
  F --> G[/api/status<br/>/api/perf<br/>/api/stream.mjpg]
  E --> H[stdout / UDP JSON<br/>future ROS2 bridge]
```

## Modules

```text
src/jrvg/config.py     runtime config loading and CLI overrides
src/jrvg/model.py      perception and command dataclasses
src/jrvg/detector.py   mock detector and Jetson TensorRT detector
src/jrvg/policy.py     target tracking state machine
src/jrvg/transport.py  stdout and UDP JSON output
src/jrvg/main.py       CLI detection loop
src/jrvg/web_app.py    Flask dashboard, MJPEG stream, JSON APIs, tegrastats parser
```

## Runtime Modes

### Mock Mode

Used for local development without Jetson-specific libraries:

```text
MockDetector -> PerceptionFrame -> TargetTrackingPolicy -> stdout/Web
```

### Jetson Mode

Used on Jetson Nano after `jetson-inference` has been built and installed:

```text
USB Camera -> jetson.utils.videoSource -> detectNet -> PerceptionFrame -> TargetTrackingPolicy -> Web/API
```

## Data Model

`Detection`:

```text
class_name
confidence
bbox
center
area_ratio
```

`PerceptionFrame`:

```text
ts
frame_id
fps
width
height
detections[]
```

`PolicyOutput`:

```text
state
target
cmd.linear_x
cmd.angular_z
reason
```

## Policy Logic

```text
TRACKING: target detected, output velocity command
LOST: target missing for a short period, output zero velocity
STOP: target too close or missing for too long, output zero velocity
```

Velocity mapping:

```text
horizontal target center error -> angular_z
target bounding-box area ratio -> linear_x
area too large -> STOP
lost frames exceed threshold -> STOP
```

Default policy parameters:

```text
target_class: person
center_deadband: 0.12
max_linear_x: 0.18
max_angular_z: 0.6
stop_area_ratio: 0.32
lost_frames_to_stop: 6
```

## ROS2 Boundary

Jetson Nano with JetPack 4.x is based on Ubuntu 18.04, while ROS2 Humble is better aligned with Ubuntu 22.04. For this project stage, ROS2 is not a hard Jetson dependency.

Recommended next-stage integration:

```text
Jetson Nano:
  camera + detector + policy + UDP JSON sender

PC / robot computer:
  ROS2 Humble bridge -> /cmd_vel
```


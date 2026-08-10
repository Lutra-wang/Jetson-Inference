# Roadmap

## Completed

- Local Python project structure.
- Mock detector for local development.
- Jetson Nano system and USB camera bring-up.
- `jetson-inference` build and Python binding validation.
- SSD-Mobilenet-v2 TensorRT object detection.
- Structured perception and policy JSON data models.
- `TRACKING / LOST / STOP` target-tracking policy.
- Flask Web dashboard with MJPEG stream.
- `/api/status`, `/api/status.ndjson`, `/api/perf`, `/api/stream.mjpg`.
- Runtime acceleration with headless mode, `nvpmodel`, `jetson_clocks`, stream FPS limit, and JPEG quality tuning.
- LAN loopback validation.
- GitHub-ready documentation set.

## Next

- Capture final screenshots and a short demo video.
- Run `scripts/perf_compare.sh` and fill a three-resolution performance table.
- Add UDP JSON sender demo and PC-side ROS2 bridge proof of concept.
- Add systemd service for boot-time Web gateway startup.
- Add one command for project health check on Jetson.

## Optional

- Custom detection model export and TensorRT deployment.
- Better front-end controls for runtime tuning.
- Longer 30-60 minute stability run with temperature and throttling record.
- Real chassis integration and `/cmd_vel` closed-loop validation.

## Non-Goals For This Stage

- No claim of full robot control without real actuator validation.
- No ROS2 deployment claim until the bridge is implemented and tested.
- No custom model training claim.
- No BSP flashing or irreversible system customization in the default workflow.


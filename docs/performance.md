# Performance Notes

This document records the verified baseline and the commands used to collect repeatable metrics.

## Verified Baseline

| Metric | Result |
| --- | --- |
| Hardware | Jetson Nano Developer Kit, 4GB |
| System | L4T R32.7.4 / Ubuntu 18.04 / Python 3.6 |
| Camera | `/dev/video0`, MJPG `960x544@30` |
| Model | SSD-Mobilenet-v2 through `jetson-inference` / TensorRT |
| Detection loop FPS | about `21.4-21.6 FPS` |
| Web stream | MJPEG `10 FPS`, JPEG quality `70` |
| Multi-target RAM sample | `1584/3964 MB`, stable during sample |
| SWAP sample | `0/6078 MB` |
| GR3D sample | `71%-99%`, avg about `89.7%` |
| CPU/GPU temp sample | CPU up to about `39 C`, GPU about `36-37 C` |
| Loopback | `/api/status`, `/api/perf`, `/api/stream.mjpg` OK |

Headless optimization result:

```text
default systemd target: graphical.target -> multi-user.target
display-manager: active -> inactive
used memory: 725 MB -> 207 MB
free memory: 2652 MB -> 3384 MB
available memory: 3069 MB -> 3597 MB
used memory gain: -518 MB
free memory gain: +732 MB
available memory gain: +528 MB
idle tegrastats RAM avg: 806.4 MB -> 240.1 MB
```

Jetson Nano uses unified CPU/GPU memory. Treat `tegrastats` RAM as shared system memory, not independent discrete GPU VRAM.

## Tuning Choices

- Use MJPG camera input instead of raw YUYV for 720p and 960x544 modes.
- Prefer `960x544@30` for the default robot demo mode.
- Limit Web MJPEG output to `10 FPS`; this is separate from detection FPS.
- Set JPEG quality to `70` to reduce CPU encoding and network load.
- Enable MAXN mode with `nvpmodel -m 0`.
- Lock clocks with `jetson_clocks` during repeatable benchmarking.
- Run headless to reduce GUI and desktop service memory pressure.
- Use `/api/perf` and `tegrastats` snapshots for evidence.

## Collection Commands

Run accelerated Web demo on Jetson:

```bash
cd ~/project/jetson_inference
CONFIG=config/jetson_usb_960x544.json \
STREAM_FPS=10 \
JPEG_QUALITY=70 \
ENABLE_TEGRASTATS=1 \
bash scripts/run_web_jetson_maxperf.sh /dev/video0
```

Run loopback validation from PC:

```bash
bash scripts/loopback_jetson_web.sh <jetson-ip> 5000
```

Run three-resolution comparison on Jetson:

```bash
cd ~/project/jetson_inference
bash scripts/perf_compare.sh
```

Manual status samples:

```bash
for i in $(seq 1 10); do
  curl --noproxy '*' -s http://<jetson-ip>:5000/api/status
  echo
  sleep 1
done > logs/status_samples.ndjson
```

Manual performance samples:

```bash
for i in $(seq 1 10); do
  curl --noproxy '*' -s http://<jetson-ip>:5000/api/perf
  echo
  sleep 1
done > logs/perf_samples.ndjson
```

## Reporting Rule

Do not mix detection FPS and stream FPS:

```text
Detection FPS: camera capture + TensorRT inference + policy update loop
Stream FPS: Web MJPEG output limit
```

The current resume-safe statement is:

```text
Jetson Nano B01 上推荐配置 960x544@30 MJPG，SSD-Mobilenet-v2 TensorRT 检测闭环约 21.4-21.6 FPS，局域网 HTTP/MJPEG 回环通过。
```

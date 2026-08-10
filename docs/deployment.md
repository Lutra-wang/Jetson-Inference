# Jetson Deployment Guide

This guide covers the repeatable path from finding the Jetson on the LAN to running the accelerated Web demo and validating the loopback API.

## 1. Network Discovery

Known development baseline:

```text
Jetson user: jetson
Jetson MAC: 3C:6D:66:00:67:E1
Current direct-Ethernet IP observed: 192.168.55.109
Direct-Ethernet PC gateway: 192.168.55.1/24
```

Use the current IP if it is still valid:

```bash
ssh jetson@192.168.55.109
```

If the IP changed, scan the local subnet:

```bash
ip -br addr
ip route
nmap -n -sn 192.168.55.0/24
ip neigh | grep -i '3c:6d:66:00:67:e1'
```

For wall Ethernet or router-based LAN, replace `192.168.55.0/24` with the actual subnet shown by `ip route`.

## 2. Sync Project To Jetson

Run on the development computer from the repository root:

```bash
rsync -av --progress \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'logs/' \
  --exclude 'third_party/jetson-inference/build/' \
  ./ jetson@<jetson-ip>:~/project/jetson_inference/
```

The repository does not vendor large third-party source trees. `scripts/sync_jetson_inference.sh` can clone `jetson-inference` on the computer and sync it to Jetson when needed:

```bash
bash scripts/sync_jetson_inference.sh jetson@<jetson-ip> ~/project/jetson_inference
```

If GitHub download is slow on Jetson, keep downloads on the computer and sync by `rsync`.

## 3. Install Jetson Runtime Dependencies

Run on Jetson:

```bash
cd ~/project/jetson_inference
sudo apt-get update
sudo apt-get install -y \
  python3-pip \
  python3-numpy \
  python3-opencv \
  v4l-utils \
  git \
  cmake \
  build-essential \
  libpython3-dev
```

Install project Python dependencies:

```bash
python3 -m pip install --user \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --trusted-host pypi.tuna.tsinghua.edu.cn \
  -r requirements-jetson.txt
```

Do not install NumPy from pip on this Jetson Nano baseline. Use `python3-numpy` from apt to avoid slow or failed source builds.

Verify:

```bash
python3 -c "import flask, cv2, numpy; print('project deps ok')"
```

## 4. Camera Check

Run on Jetson:

```bash
ls -l /dev/video0
v4l2-ctl --device=/dev/video0 --list-formats-ext
```

Recommended runtime mode:

```text
Config: config/jetson_usb_960x544.json
Input:  /dev/video0
Codec:  MJPG
Size:   960x544
FPS:    30
```

## 5. Build jetson-inference

First sync source from the development computer:

```bash
bash scripts/sync_jetson_inference.sh jetson@<jetson-ip> ~/project/jetson_inference
```

Then build on Jetson:

```bash
cd ~/project/jetson_inference/third_party/jetson-inference
test -f CMakeLists.txt
mkdir -p build
cd build
cmake -DBUILD_DEPS=NO -DBUILD_INTERACTIVE=NO ../
make -j1
sudo make install
sudo ldconfig
```

Validate Python bindings:

```bash
python3 -c "import jetson.inference, jetson.utils; print('jetson-inference ok')"
```

## 6. Smoke Test

Run on Jetson:

```bash
cd ~/project/jetson_inference
bash scripts/smoke_jetson_inference.sh /dev/video0
```

Expected result:

```text
jetson-inference bindings available
project runtime dependencies available
logs/jetson_smoke_*.ndjson generated
```

## 7. Run Accelerated Web Demo

Run on Jetson:

```bash
cd ~/project/jetson_inference
CONFIG=config/jetson_usb_960x544.json \
STREAM_FPS=10 \
JPEG_QUALITY=70 \
ENABLE_TEGRASTATS=1 \
bash scripts/run_web_jetson_maxperf.sh /dev/video0
```

The script applies:

```text
sudo nvpmodel -m 0
sudo jetson_clocks
web stream FPS limit = 10
JPEG quality = 70
/api/perf enabled
```

Open from PC:

```text
http://<jetson-ip>:5000
```

## 8. Loopback Validation

Run on the development computer:

```bash
bash scripts/loopback_jetson_web.sh <jetson-ip> 5000
```

The test passes when:

```text
/api/status returns JSON
/api/perf returns tegrastats data
/api/stream.mjpg returns multipart MJPEG
script prints loopback ok
```

## 9. Common Fixes

If Flask is missing:

```bash
python3 -m pip install --user -r requirements-jetson.txt
```

If pip is missing:

```bash
sudo apt-get install -y python3-pip
```

If NumPy tries to compile from source:

```bash
sudo apt-get install -y python3-numpy
```

If `jetson.inference` is missing, rebuild `third_party/jetson-inference` on Jetson and rerun `sudo ldconfig`.

If `cmake ../` fails with missing `CMakeLists.txt`, check that the current directory is:

```text
~/project/jetson_inference/third_party/jetson-inference/build
```


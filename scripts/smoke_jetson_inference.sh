#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CAMERA="${1:-/dev/video0}"
CONFIG="${CONFIG:-config/jetson_usb_720p.json}"
FRAMES="${FRAMES:-30}"
NETWORK="${NETWORK:-ssd-mobilenet-v2}"
THRESHOLD="${THRESHOLD:-0.5}"

echo "== Platform =="
uname -a
if [ -f /etc/nv_tegra_release ]; then
  cat /etc/nv_tegra_release
else
  echo "/etc/nv_tegra_release not found; this does not look like Jetson Linux"
fi

echo
echo "== Camera =="
ls -la "$CAMERA"
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --device="$CAMERA" --list-formats-ext || true
else
  echo "v4l2-ctl not installed"
fi

echo
echo "== Project Python dependencies =="
python3 - <<'PY'
import importlib.util
import sys


missing = []
for name in ("dataclasses",):
    try:
        found = importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        found = False
    if not found:
        missing.append(name)

if missing:
    print("missing:", ", ".join(missing))
    print("Install NumPy on Jetson with: sudo apt-get install -y python3-numpy")
    print("Run: python3 -m pip install --user -r requirements-jetson.txt")
    sys.exit(2)

print("project runtime dependencies available")
PY

echo
echo "== jetson-inference Python bindings =="
python3 - <<'PY'
import importlib.util
import sys


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


missing = [name for name in ("jetson.inference", "jetson.utils") if not has_module(name)]
if missing:
    print("missing:", ", ".join(missing))
    print("Install/build dusty-nv/jetson-inference, then rerun this script.")
    sys.exit(2)

import jetson.inference  # noqa: F401
import jetson.utils  # noqa: F401

print("jetson-inference bindings available")
PY

mkdir -p logs
OUT="logs/jetson_smoke_$(date +%Y%m%d_%H%M%S).ndjson"

echo
echo "== Project smoke test =="
echo "camera=$CAMERA config=$CONFIG network=$NETWORK threshold=$THRESHOLD frames=$FRAMES"
PYTHONPATH=src python3 -m jrvg.main \
  --config "$CONFIG" \
  --backend jetson \
  --camera "$CAMERA" \
  --network "$NETWORK" \
  --threshold "$THRESHOLD" \
  --frames "$FRAMES" | tee "$OUT"

echo
echo "wrote $OUT"
echo "last frames:"
tail -n 3 "$OUT"

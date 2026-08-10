#!/usr/bin/env bash
set -euo pipefail

CAMERA="${1:-/dev/video0}"

echo "== Camera device =="
ls -la "$CAMERA" || true

echo
echo "== v4l2 device list =="
if command -v v4l2-ctl >/dev/null 2>&1; then
  v4l2-ctl --list-devices || true
  echo
  v4l2-ctl --device="$CAMERA" --list-formats-ext || true
else
  echo "v4l2-ctl not installed"
fi

echo
echo "== OpenCV quick check =="
python3 -c "import importlib.util, sys; has=importlib.util.find_spec('cv2') is not None; print('cv2 installed=', has); sys.exit(0 if has else 2)" \
  && python3 -c "import cv2; cap=cv2.VideoCapture('$CAMERA'); ok, frame=cap.read(); print('opened=', cap.isOpened(), 'read=', ok, 'shape=', None if frame is None else frame.shape); cap.release()" \
  || true

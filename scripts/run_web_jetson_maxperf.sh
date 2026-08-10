#!/usr/bin/env bash
set -euo pipefail

CAMERA="${1:-${CAMERA:-/dev/video0}}"
CONFIG="${CONFIG:-config/jetson_usb_960x544.json}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"
STREAM_FPS="${STREAM_FPS:-10}"
JPEG_QUALITY="${JPEG_QUALITY:-70}"
NVPMODEL_MODE="${NVPMODEL_MODE:-0}"
ENABLE_TEGRASTATS="${ENABLE_TEGRASTATS:-1}"
DISABLE_VISUALIZATION="${DISABLE_VISUALIZATION:-0}"

if [[ "${MAX_PERF:-1}" == "1" ]]; then
  if command -v nvpmodel >/dev/null 2>&1; then
    echo "== nvpmodel before =="
    sudo nvpmodel -q || true
    echo "== set nvpmodel mode ${NVPMODEL_MODE} =="
    sudo nvpmodel -m "$NVPMODEL_MODE" || true
  fi

  if command -v jetson_clocks >/dev/null 2>&1; then
    echo "== lock Jetson clocks =="
    sudo jetson_clocks || true
    sudo jetson_clocks --show || true
  fi
fi

ARGS=(
  --config "$CONFIG"
  --backend jetson
  --camera "$CAMERA"
  --host "$HOST"
  --port "$PORT"
  --stream-fps "$STREAM_FPS"
  --jpeg-quality "$JPEG_QUALITY"
)

if [[ "$ENABLE_TEGRASTATS" == "1" ]]; then
  ARGS+=(--enable-tegrastats)
fi

if [[ "$DISABLE_VISUALIZATION" == "1" ]]; then
  ARGS+=(--disable-visualization)
fi

echo "== start web app =="
echo "config=$CONFIG camera=$CAMERA host=$HOST port=$PORT stream_fps=$STREAM_FPS jpeg_quality=$JPEG_QUALITY"
PYTHONPATH=src python3 -m jrvg.web_app "${ARGS[@]}"

#!/usr/bin/env bash
set -euo pipefail

CAMERA="${CAMERA:-/dev/video0}"
PORT="${PORT:-5050}"
STREAM_FPS="${STREAM_FPS:-10}"
JPEG_QUALITY="${JPEG_QUALITY:-70}"
DURATION="${DURATION:-20}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-logs/perf_compare/${STAMP}}"

CONFIGS=(
  "config/jetson_usb_720p.json"
  "config/jetson_usb_960x544.json"
  "config/jetson_usb_640x360.json"
)

mkdir -p "$OUT_DIR"

PID=""
stop_server() {
  if [[ -n "$PID" ]] && kill -0 "$PID" >/dev/null 2>&1; then
    kill "$PID" >/dev/null 2>&1 || true
    wait "$PID" >/dev/null 2>&1 || true
  fi
  PID=""
}
trap stop_server EXIT

for CONFIG in "${CONFIGS[@]}"; do
  NAME="$(basename "$CONFIG" .json)"
  RUN_DIR="${OUT_DIR}/${NAME}"
  mkdir -p "$RUN_DIR"

  echo "== ${NAME} =="
  PYTHONPATH=src python3 -m jrvg.web_app \
    --config "$CONFIG" \
    --backend jetson \
    --camera "$CAMERA" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --stream-fps "$STREAM_FPS" \
    --jpeg-quality "$JPEG_QUALITY" \
    --enable-tegrastats \
    > "${RUN_DIR}/server.log" 2>&1 &
  PID="$!"

  READY=0
  for _ in $(seq 1 30); do
    if curl --noproxy '*' -fsS -L --max-time 2 "http://127.0.0.1:${PORT}/api/status" -o "${RUN_DIR}/status_first.json"; then
      READY=1
      break
    fi
    sleep 1
  done

  if [[ "$READY" != "1" ]]; then
    echo "service did not become ready for ${NAME}" >&2
    stop_server
    continue
  fi

  for i in $(seq 1 "$DURATION"); do
    curl --noproxy '*' -fsS -L --max-time 2 "http://127.0.0.1:${PORT}/api/status" >> "${RUN_DIR}/status.ndjson"
    printf '\n' >> "${RUN_DIR}/status.ndjson"
    curl --noproxy '*' -fsS -L --max-time 2 "http://127.0.0.1:${PORT}/api/perf" >> "${RUN_DIR}/perf.ndjson"
    printf '\n' >> "${RUN_DIR}/perf.ndjson"
    sleep 1
  done

  set +e
  curl --noproxy '*' -fsS -L --max-time 3 "http://127.0.0.1:${PORT}/api/stream.mjpg" -o "${RUN_DIR}/stream.mjpg"
  set -e

  stop_server
  echo "saved ${RUN_DIR}"
  sleep 2
done

echo "perf compare artifacts: ${OUT_DIR}"

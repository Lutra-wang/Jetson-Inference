#!/usr/bin/env bash
set -euo pipefail

JETSON_HOST="${1:-192.168.55.109}"
PORT="${2:-5000}"
EXPECTED_MAC="${EXPECTED_MAC:-3C:6D:66:00:67:E1}"
BASE_URL="http://${JETSON_HOST}:${PORT}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-logs/loopback/${STAMP}}"

mkdir -p "$OUT_DIR"

echo "== LAN peer =="
echo "host=$JETSON_HOST port=$PORT expected_mac=$EXPECTED_MAC"
if command -v ip >/dev/null 2>&1; then
  NEIGH="$(ip neigh show "$JETSON_HOST" 2>/dev/null || true)"
  if [[ -n "$NEIGH" ]]; then
    echo "$NEIGH"
    if ! grep -qi "$EXPECTED_MAC" <<<"$NEIGH"; then
      echo "warning: neighbor MAC does not match expected_mac" >&2
    fi
  fi
fi

echo
echo "== HTTP status =="
curl --noproxy '*' -fsS -L --max-time 5 "${BASE_URL}/api/status" -o "${OUT_DIR}/status.json"
wc -c "${OUT_DIR}/status.json"

echo
echo "== Perf status =="
curl --noproxy '*' -fsS -L --max-time 5 "${BASE_URL}/api/perf" -o "${OUT_DIR}/perf.json"
wc -c "${OUT_DIR}/perf.json"

echo
echo "== MJPEG stream sample =="
set +e
curl --noproxy '*' -fsS -L --max-time 3 "${BASE_URL}/api/stream.mjpg" -o "${OUT_DIR}/stream.mjpg"
STREAM_RC=$?
set -e
if [[ "$STREAM_RC" != "0" && "$STREAM_RC" != "28" ]]; then
  echo "stream request failed with curl exit code $STREAM_RC" >&2
  exit "$STREAM_RC"
fi

STREAM_BYTES="$(wc -c < "${OUT_DIR}/stream.mjpg")"
echo "${STREAM_BYTES} ${OUT_DIR}/stream.mjpg"
if [[ "$STREAM_BYTES" -lt 10000 ]]; then
  echo "stream sample is too small" >&2
  exit 1
fi

if ! grep -aq -- "--frame" "${OUT_DIR}/stream.mjpg"; then
  echo "stream sample does not contain multipart frame boundary" >&2
  exit 1
fi

echo
echo "loopback ok: ${BASE_URL}"
echo "artifacts: ${OUT_DIR}"

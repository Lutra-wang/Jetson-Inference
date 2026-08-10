#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-logs/tegrastats.log}"
mkdir -p "$(dirname "$OUT")"

if ! command -v tegrastats >/dev/null 2>&1; then
  echo "tegrastats not found"
  exit 1
fi

echo "writing to $OUT"
tegrastats --interval 1000 | tee "$OUT"


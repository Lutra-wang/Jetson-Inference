#!/usr/bin/env bash
set -euo pipefail

CAMERA="${1:-/dev/video0}"
CONFIG="${CONFIG:-config/jetson_usb_720p.json}"

PYTHONPATH=src python3 -m jrvg.main --config "$CONFIG" --backend jetson --camera "$CAMERA"

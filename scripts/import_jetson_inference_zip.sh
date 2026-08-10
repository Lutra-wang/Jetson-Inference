#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZIP_PATH="${1:-}"
TARGET_DIR="$ROOT_DIR/third_party/jetson-inference"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if [[ -z "$ZIP_PATH" ]]; then
  echo "usage: $0 /path/to/jetson-inference-master.zip" >&2
  exit 2
fi

if [[ ! -f "$ZIP_PATH" ]]; then
  echo "zip not found: $ZIP_PATH" >&2
  exit 1
fi

mkdir -p "$ROOT_DIR/third_party"
unzip -oq "$ZIP_PATH" -d "$TMP_DIR"

SRC_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$SRC_DIR" || ! -f "$SRC_DIR/CMakeLists.txt" ]]; then
  echo "zip does not contain a jetson-inference source tree" >&2
  exit 1
fi

if [[ -e "$TARGET_DIR" ]]; then
  echo "target already exists: $TARGET_DIR" >&2
  echo "move it aside manually before importing a new zip" >&2
  exit 1
fi

mv "$SRC_DIR" "$TARGET_DIR"

echo "imported jetson-inference source to:"
echo "$TARGET_DIR"
echo
echo "next sync command:"
echo "  bash scripts/sync_jetson_inference.sh jetson@<Jetson-IP> ~/project/jetson_inference"

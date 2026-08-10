#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/third_party/jetson-inference"
REPO_URL="https://github.com/dusty-nv/jetson-inference.git"

JETSON_HOST="${1:-}"
REMOTE_PROJECT_DIR="${2:-~/project/jetson_inference}"
REMOTE_SOURCE_DIR="${REMOTE_PROJECT_DIR%/}/third_party/jetson-inference"

if [[ -z "$JETSON_HOST" ]]; then
  echo "usage: $0 jetson@<jetson-ip> [remote-project-dir]" >&2
  echo "example: $0 jetson@<jetson-ip> ~/project/jetson_inference" >&2
  exit 2
fi

command -v git >/dev/null 2>&1 || {
  echo "git is required on the computer" >&2
  exit 1
}
command -v rsync >/dev/null 2>&1 || {
  echo "rsync is required on the computer" >&2
  exit 1
}

mkdir -p "$ROOT_DIR/third_party"

if [[ -e "$SOURCE_DIR" ]]; then
  if [[ ! -f "$SOURCE_DIR/CMakeLists.txt" ]]; then
    echo "destination exists but is not a jetson-inference source tree: $SOURCE_DIR" >&2
    exit 1
  fi
  if [[ -d "$SOURCE_DIR/.git" && "${UPDATE_SUBMODULES:-0}" == "1" ]]; then
    git -C "$SOURCE_DIR" submodule update --init --recursive
  else
    echo "using existing source tree: $SOURCE_DIR"
  fi
else
  git clone --recursive --depth=1 "$REPO_URL" "$SOURCE_DIR"
fi

test -f "$SOURCE_DIR/CMakeLists.txt"
test -f "$SOURCE_DIR/utils/CMakeLists.txt"

echo "== Source =="
echo "$SOURCE_DIR"
echo
echo "== Jetson =="
echo "$JETSON_HOST:$REMOTE_SOURCE_DIR"

ssh "$JETSON_HOST" "mkdir -p $REMOTE_SOURCE_DIR"
rsync -av --progress "$SOURCE_DIR/" "$JETSON_HOST:$REMOTE_SOURCE_DIR/"
ssh "$JETSON_HOST" "test -f $REMOTE_SOURCE_DIR/CMakeLists.txt"

echo
echo "jetson-inference source synchronized"
echo "build on Jetson with:"
echo "  cd $REMOTE_SOURCE_DIR"
echo "  mkdir -p build && cd build"
echo "  cmake ../"
echo "  make -j1"

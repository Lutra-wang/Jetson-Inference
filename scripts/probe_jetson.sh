#!/usr/bin/env bash
set -euo pipefail

echo "== Jetson release =="
if [ -f /etc/nv_tegra_release ]; then
  cat /etc/nv_tegra_release
else
  echo "/etc/nv_tegra_release not found"
fi

echo
echo "== OS =="
if [ -f /etc/os-release ]; then
  cat /etc/os-release
fi

echo
echo "== Disk =="
df -h

echo
echo "== Memory =="
free -h

echo
echo "== Camera devices =="
ls -la /dev/video* 2>/dev/null || true

echo
echo "== tegrastats =="
which tegrastats || true


#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src python3 -m jrvg.web_app --backend mock

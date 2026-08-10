#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=src python3 -m jrvg.main --backend mock --frames 100 --period 0.02 >/tmp/jrvg_mock_output.ndjson
tail -n 3 /tmp/jrvg_mock_output.ndjson

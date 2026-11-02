#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
# Every check that needs no phone: the Python tests (pytest: protocol, profiles, core, adapters; mqtt against a
# Mosquitto started by the test, ros2 only where rclpy is), the Node-RED package's tests, and the scripts' syntax.
#   ./test.sh [--browser]     --browser: also scripts/browser_check.py (headless Chrome as the phone)
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q paho-mqtt==2.1.0 pytest; }
# a ROS environment on PYTHONPATH brings pytest plugins the venv cannot load
env -u PYTHONPATH .venv/bin/python -m pytest -q tests
(cd node-red/node-red-contrib-dhc-edge && { [ -d node_modules/ws ] || npm install --no-audit --no-fund -s; } && npm test --silent | grep -E '^# (pass|fail)')
bash -n start.sh scripts/*.sh
for f in web/*.js; do node --check "$f"; done
if [ "${1:-}" = "--browser" ]; then env -u PYTHONPATH .venv/bin/python scripts/browser_check.py; fi
echo "all checks passed"

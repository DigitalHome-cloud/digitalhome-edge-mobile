#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 DigitalHome.cloud
# ROS 2's environment, then the edge with the given options.
set -e
source /opt/ros/kilted/setup.bash
exec python3 -m dhc_edge "$@"

#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OVERRIDES_FILE="$ROOT_DIR/config/robot_overrides.yaml"

pixi run -e humble \
ros2 launch franka_meta_quest start.launch.py overrides_file:="$OVERRIDES_FILE" "$@"

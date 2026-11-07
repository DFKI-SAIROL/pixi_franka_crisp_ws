#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

pixi run -e humble \
ros2 launch franka_data_collection start.launch.py config_path:="$ROOT_DIR/config/data_collector.yaml" "$@"

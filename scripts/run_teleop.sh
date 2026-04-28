#!/bin/bash
pixi run -e humble \
ros2 launch franka_meta_quest start.launch.py spawn_franka_left:=false  spawn_franka_right:=true

#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OVERRIDES_FILE="$ROOT_DIR/config/robot_overrides.yaml"

pixi run -e humble python \
    "$ROOT_DIR/scripts/python/check_robot_config.py" "$OVERRIDES_FILE" || exit 1

if ! command -v tmux &> /dev/null
then
    echo "tmux is not installed. Running commands in background instead."
    ros2 launch franka_launch example.launch.py overrides_file:="$OVERRIDES_FILE" &
    ssh jetson "cd Projects/ros2_ws && bash launch_zed.sh" &
    ros2 launch zed_rig_aggregator_node aggregator.launch.py &
    ros2 launch robot_ik_layer start_ijk.launch.py overrides_file:="$OVERRIDES_FILE" &
    wait
    exit 0
fi

# Use tmux to open multiple terminals side-by-side
SESSION="robot_run"
tmux new-session -d -s $SESSION "pixi run -e humble ros2 launch franka_launch example.launch.py overrides_file:=$OVERRIDES_FILE ; exec bash"
tmux split-window -h -t $SESSION "env -i HOME=$HOME USER=$USER /usr/bin/ssh -t jetson 'cd Projects/ros2_ws && source install/setup.bash && export ROS_DOMAIN_ID=$ROS_DOMAIN_ID && bash launch_zed.sh csil'" # choose config csil|max|"custom"
tmux split-window -v -t $SESSION "pixi run -e humble ros2 launch zed_rig_aggregator_node aggregator.launch.py ; exec bash"
tmux split-window -v -t $SESSION "pixi run -e humble ros2 launch robot_ik_layer start_ijk.launch.py overrides_file:=$OVERRIDES_FILE ; exec bash"

echo "Started robot launch nodes in a tmux session."
tmux attach-session -t $SESSION

#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OVERRIDES_FILE="$ROOT_DIR/config/robot_overrides.yaml"
export FASTRTPS_DEFAULT_PROFILES_FILE="$ROOT_DIR/config/fastdds_config.xml"

pixi run -e humble python \
    "$ROOT_DIR/scripts/python/check_robot_config.py" "$OVERRIDES_FILE" || exit 1

# ZED cameras: started on the Jetson by config/zed/zed.launch.py (topics /zed_multi/<camera>/..., as launch_zed.sh csil),
# which also publishes the hand-eye calibrations as TF.
ZED_CMD="ros2 launch $ROOT_DIR/config/zed/zed.launch.py"
# The aggregator's ~14 MB snapshots need a large shared memory segment (config/fastdds_camera.xml), otherwise most of
# them are lost on the way to the data collector.
AGGREGATOR_CMD="ros2 launch zed_rig_aggregator_node aggregator.launch.py"
AGGREGATOR_FASTDDS="$ROOT_DIR/config/fastdds_camera.xml"
# The spawners randomly leave controllers loaded but inactive (10 s load timeout vs. a ~11 s first load in the arm
# controller managers); this finishes starting them once the spawners are done, before the IK layer starts.
ENSURE_CONTROLLERS_CMD="python $ROOT_DIR/scripts/python/ensure_controllers.py $OVERRIDES_FILE"

if ! command -v tmux &> /dev/null
then
    echo "tmux is not installed. Running commands in background instead."
    ros2 launch franka_launch example.launch.py overrides_file:="$OVERRIDES_FILE" &
    $ZED_CMD &
    FASTRTPS_DEFAULT_PROFILES_FILE="$AGGREGATOR_FASTDDS" $AGGREGATOR_CMD &
    { $ENSURE_CONTROLLERS_CMD; ros2 launch robot_ik_layer start_ijk.launch.py overrides_file:="$OVERRIDES_FILE"; } &
    wait
    exit 0
fi

# Use tmux to open multiple terminals side-by-side
SESSION="robot_run"
tmux new-session -d -s $SESSION "FASTRTPS_DEFAULT_PROFILES_FILE=$FASTRTPS_DEFAULT_PROFILES_FILE pixi run -e humble ros2 launch franka_launch example.launch.py overrides_file:=$OVERRIDES_FILE ; exec bash"
tmux split-window -h -t $SESSION "FASTRTPS_DEFAULT_PROFILES_FILE=$FASTRTPS_DEFAULT_PROFILES_FILE pixi run -e humble $ZED_CMD ; exec bash"
tmux split-window -v -t $SESSION "FASTRTPS_DEFAULT_PROFILES_FILE=$AGGREGATOR_FASTDDS pixi run -e humble $AGGREGATOR_CMD ; exec bash"
tmux split-window -v -t $SESSION "FASTRTPS_DEFAULT_PROFILES_FILE=$FASTRTPS_DEFAULT_PROFILES_FILE pixi run -e humble $ENSURE_CONTROLLERS_CMD ; FASTRTPS_DEFAULT_PROFILES_FILE=$FASTRTPS_DEFAULT_PROFILES_FILE pixi run -e humble ros2 launch robot_ik_layer start_ijk.launch.py overrides_file:=$OVERRIDES_FILE ; exec bash"

echo "Started robot launch nodes in a tmux session."
tmux attach-session -t $SESSION

#!/bin/bash

# Set default ROS_DISTRO if not set (default to humble for this workspace)
ROS_DISTRO=${ROS_DISTRO:-humble}

# Move to the root of the project
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT_DIR/src"

mkdir -p "$SRC_DIR"
cd "$SRC_DIR"

echo "Using ROS_DISTRO: $ROS_DISTRO"
echo "Working in: $SRC_DIR"

# Helper function to clone OR pull
sync_repo() {
    local repo_url=$1
    local target_dir=$2
    local branch=$3

    if [ ! -d "$target_dir" ]; then
        echo "Cloning $target_dir..."
        if [ -n "$branch" ]; then
            git clone -b "$branch" "$repo_url" "$target_dir"
        else
            git clone "$repo_url" "$target_dir"
        fi
    else
        echo "$target_dir already exists, pulling latest changes..."
        cd "$target_dir"
        git pull
        cd ..
    fi
}

# 2. Franka ROS 2
if [ ! -d "franka_ros2" ]; then
    echo "Cloning franka_ros2 ($ROS_DISTRO)..."
    git clone -b "$ROS_DISTRO" https://github.com/frankarobotics/franka_ros2.git ./franka_ros2
    git -C ./franka_ros2 checkout 7ed0458
    
    # Remove nodes not used in this pipeline
    rm -rf ./franka_ros2/franka_gazebo ./franka_ros2/franka_fr3_moveit_config ./franka_ros2/franka_mobile_example_controllers ./franka_ros2/franka_mobile_sensors ./franka_ros2/franka_gazebo_bringup
    rm -rf ./franka_ros2/libfranka ./franka_ros2/franka_robot_state_broadcaster
    
    cd ./franka_ros2/ 
    git clone --recurse-submodules git@git.ias.informatik.tu-darmstadt.de:ros2/franka/libfranka.git
    git clone git@git.ias.informatik.tu-darmstadt.de:ros2/franka/franka_robot_state_broadcaster.git
    cd ..
    
    vcs import ./franka_ros2 < ./franka_ros2/dependency.repos --recursive --skip-existing
    rosdep install --from-paths ./franka_ros2 --ignore-src --rosdistro "$ROS_DISTRO" --skip-keys "ignition-plugin franka_ign_ros2_control" -y
else
    echo "franka_ros2 already exists, pulling changes for sub-repos..."
    cd franka_ros2
    git pull
    cd libfranka && git pull && git submodule update --init --recursive && cd ..
    cd franka_robot_state_broadcaster && git pull && cd ..
    cd ..
fi

cd "$SRC_DIR"

# 3. Dynamixel components (only needed if some arm actually uses a Dynamixel gripper)
OVERRIDES_FILE="$ROOT_DIR/config/robot_overrides.yaml"
eval "$(pixi run -e humble python3 "$ROOT_DIR/scripts/python/read_overrides.py" "$OVERRIDES_FILE")"
echo "config/robot_overrides.yaml: gripper_type_left=$gripper_type_left gripper_type_right=$gripper_type_right needs_dynamixel=$needs_dynamixel"

if [ "$needs_dynamixel" = "true" ]; then
    sync_repo "https://github.com/ROBOTIS-GIT/dynamixel_hardware_interface.git" "dynamixel_hardware_interface" "$ROS_DISTRO"
    sync_repo "https://github.com/ROBOTIS-GIT/DynamixelSDK.git" "DynamixelSDK" "$ROS_DISTRO"
    sync_repo "https://github.com/ROBOTIS-GIT/dynamixel_interfaces.git" "dynamixel_interfaces" "$ROS_DISTRO"
elif false; then
    # Placeholder for other hands/grippers
    echo "add custom hands/grippers"
else
    echo "No arm uses a Dynamixel gripper (config/robot_overrides.yaml), skipping Dynamixel repos."
fi

# 4. CRISP components
sync_repo "git@github.com:DFKI-SAIROL/crisp_py.git" "crisp_py"
sync_repo "git@github.com:DFKI-SAIROL/crisp_gym.git" "crisp_gym"
sync_repo "git@github.com:DFKI-SAIROL/crisp_controllers.git" "crisp_controllers"

# 5. Misc
sync_repo "git@github.com:DFKI-SAIROL/robot_ik_layer.git" "robot_ik_layer"
sync_repo "git@github.com:DFKI-SAIROL/robot_safety_layer.git" "robot_safety_layer"
sync_repo "git@github.com:DFKI-SAIROL/franka_robot_description.git" "franka_robot_description"
sync_repo "git@github.com:DFKI-SAIROL/franka_launch.git" "franka_launch"
sync_repo "git@github.com:DFKI-SAIROL/franka_py.git" "franka_py"
sync_repo "git@github.com:DFKI-SAIROL/franka_data_collection.git" "franka_data_collection"
sync_repo "git@github.com:DFKI-SAIROL/franka_custom_msgs.git" "franka_custom_msgs"
sync_repo "git@github.com:DFKI-SAIROL/bspline_controller.git" "bspline_controller"
sync_repo "git@github.com:DFKI-SAIROL/fake_effort_hardware.git" "fake_effort_hardware"

# System tools
if ! command -v scrcpy &> /dev/null || [ "$(scrcpy --version | head -n 1 | grep -o '1\.')" = "1." ]; then
    echo "Installing scrcpy from snap (v3.x required for audio)..."
    sudo apt remove -y scrcpy
    sudo snap install scrcpy
else
    echo "Modern scrcpy is already installed, skipping."
fi

echo "Setup and sync complete!"

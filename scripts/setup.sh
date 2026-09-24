#!/usr/bin/env bash

set -euo pipefail

ROS_DISTRO="${ROS_DISTRO:-humble}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRANKA_ROS2_DIR="$ROOT_DIR/src/franka_ros2"

echo "Initializing pinned source dependencies..."
git -C "$ROOT_DIR" submodule sync --recursive
git -C "$ROOT_DIR" submodule update --init --recursive

# These packages are replaced by sibling submodules or are not part of this
# workspace. COLCON_IGNORE keeps the franka_ros2 submodule pristine apart from
# untracked marker files and avoids maintaining a fork solely to delete them.
for package in \
    franka_fr3_moveit_config \
    franka_gazebo \
    franka_gazebo_bringup \
    franka_mobile_example_controllers \
    franka_mobile_sensors \
    franka_robot_state_broadcaster \
    libfranka; do
    if [[ -d "$FRANKA_ROS2_DIR/$package" ]]; then
        touch "$FRANKA_ROS2_DIR/$package/COLCON_IGNORE"
    fi
done

echo "Installing ROS dependencies for ROS $ROS_DISTRO..."

# RoboStack sets ROS_OS_OVERRIDE=conda:linux inside the Pixi environment.
# rosdep does not support Pixi as a Conda installer, so resolve the remaining
# system dependencies against the actual host OS instead.
if [[ ! -r /etc/os-release ]]; then
    echo "Unable to detect the host OS for rosdep: /etc/os-release is missing." >&2
    exit 1
fi
. /etc/os-release
ROSDEP_OS="${ID}:${VERSION_CODENAME:-${VERSION_ID}}"
ROSDEP_SKIP_KEYS="Eigen3 ignition-plugin franka_ign_ros2_control"
ROSDEP_SKIP_KEYS+=" franka_fr3_moveit_config franka_gazebo_bringup"

rosdep install \
    --from-paths "$ROOT_DIR/src" \
    --ignore-src \
    --os "$ROSDEP_OS" \
    --rosdistro "$ROS_DISTRO" \
    --skip-keys "$ROSDEP_SKIP_KEYS" \
    -y

if ! command -v scrcpy >/dev/null 2>&1; then
    echo "Note: scrcpy is not installed; install version 3.x separately if Quest audio is needed."
fi

echo "Submodules and ROS dependencies are ready."

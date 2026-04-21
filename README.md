- [1. Frankapy CRISP Workspace](#1-frankapy-crisp-workspace)
  - [1.1. Prerequisites](#11-prerequisites)
    - [1.1.1. Install Pixi](#111-install-pixi)
  - [1.2. Getting Started](#12-getting-started)
    - [1.2.1. Unified Setup \& Environment Initialization](#121-unified-setup--environment-initialization)
    - [1.2.2. Build the Workspace](#122-build-the-workspace)
  - [1.3. Running the Robot](#13-running-the-robot)
    - [1.3.1. Base Launch (with Safety Layer \& ZED)](#131-base-launch-with-safety-layer--zed)
    - [1.3.2. Teleoperation (Meta Quest VR)](#132-teleoperation-meta-quest-vr)
    - [1.3.3. Data Collection](#133-data-collection)
  - [1.4. Advanced Usage](#14-advanced-usage)
    - [1.4.1. Environments](#141-environments)
    - [1.4.2. Additional Tasks](#142-additional-tasks)
  - [1.5. Working with the Environment](#15-working-with-the-environment)
    - [1.5.1. Interactive Development (`pixi shell`)](#151-interactive-development-pixi-shell)


# 1. Frankapy CRISP Workspace

This repository provides a unified, **Pixi-managed** environment for the Franka Emika Panda robots, integrating the **CRISP** (C++ Real-time Impedance and Space Programming) ecosystem for high-performance, compliant control.

## 1.1. Prerequisites

### 1.1.1. Install Pixi
If you haven't installed Pixi yet, run the following command:
```bash
curl -fsSL https://pixi.sh/install.sh | bash
source ~/.bashrc
```

## 1.2. Getting Started

### 1.2.1. Unified Setup & Environment Initialization
Initialize the Pixi environment and clone all dependencies (CRISP, Franka ROS 2, Dynamixel, etc.):
```bash
pixi run setup
```
> [!NOTE]
> This command will automatically create the `.pixi` environment, clone repositories into `src/`, apply custom patches, and install dependencies via `rosdep` and `snap` (for `scrcpy`).

### 1.2.2. Build the Workspace
Compile all C++ and Python packages:
```bash
pixi run build
```

---

## 1.3. Running the Robot

### 1.3.1. Base Launch (with Safety Layer & ZED)
This command opens a tmux session with the Franka driver, the ZED aggregator, and the safety layer:
```bash
pixi run robot
```

### 1.3.2. Teleoperation (Meta Quest VR)
To start the VR teleoperation stack:
```bash
pixi run teleop
```

### 1.3.3. Data Collection
To start a data collection run:
```bash
pixi run data-collection
```

---

## 1.4. Advanced Usage

### 1.4.1. Environments
- **`humble`**: Default ROS 2 Humble environment.

### 1.4.2. Additional Tasks
- **`pixi run clean`**: Removes `build`, `install`, and `log` directories.
- **`pixi run test`**: Runs the `frankapy` test suite.
- **`pixi run client`**: Runs the frankapy client logic.

---

## 1.5. Working with the Environment

### 1.5.1. Interactive Development (`pixi shell`)
If you want to run arbitrary ROS 2 commands (`ros2 topic list`, `ros2 node info`, etc.), enter the Pixi shell:
```bash
pixi shell -e humble
```
---

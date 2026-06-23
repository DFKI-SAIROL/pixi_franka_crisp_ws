# Contribution Log

A running journal of changes so others can follow up. Newest entries on top. Format per entry: **Problem** -> **Solution**.

## 2026-06-23

### Stable gripper device names
- **Problem:** The Robotis RH-P12-RN-A grippers enumerate as `/dev/ttyUSB<N>` in kernel order, so the number is not tied to a physical gripper — power-cycling or replugging can swap left/right and break the launch.
- **Solution:** Added udev rules in `src/franka_launch/udev/99-dynamixel.rules` that pin each FTDI adapter's serial to a fixed symlink (`/dev/dynamixel_left`, `/dev/dynamixel_right`). Documented the install steps in the README under Prerequisites (§1.1.3).

# Backlog

Open tasks at the top, dated log of done/notable changes below. Newest first.

## Backlog / TODO
- [ ] **Check the RAM** — `pixi run build` intermittently crashes `cc1plus` (suspected faulty RAM). Run `memtest86+` (several passes), reseat/replace DIMMs. Workaround for now: re-run the build a few times until it passes.
- [ ] Remove rosdep from setup.sh
- [ ] joint trajectory controller interpolators (move Puze's code for linear and bspline interpolation)
- [?] remove two missing repos from IAS gitlab and move to DFKI
- [x] Move robot related configs to franka_launch
- [x] Option for installing the grippers in src/ 
- [x] move msgs to the correct repo
- [x] custom to aggregator from franka_py
- [x] data_collection is a standalone package
- [x] remove franka_ui
- [x] place the link to the crisp documnetation in the top of our


## Log

### 2026-09-07
 - **Problem:** remove mock_components/GenericSystem which doesn't work with effort (crisp_controllers/src/cartesian_controller.cpp uses effort command interface to communicate with the robot)
 - **Solution:** add fake_effort_hardware to handle the effort command interface and simulate the bimanual platform together with the real meta quest: https://github.com/DFKI-SAIROL/fake_effort_hardware

### 2026-07-07

#### cleaning/repos
 - add franka_data_collection, franka_custom_msgs
 - clean franka_py

#### Add a condiition to see if the gripper is turned on
  - **Problem:** The gripper is turned on separately, therefore an user might not notice that it's not turned on while launching the whole setup.
  - **Solution** Before launching the whole setup, ping the grippers (if specified).

### 2026-06-23

#### Intermittent build failures (suspected faulty RAM)
- **Problem:** `pixi run build` randomly crashes compiling `crisp_controllers` with `cc1plus: internal compiler error: Segmentation fault`. It is non-deterministic (different files/passes on identical source), so it points to a hardware fault — likely bad RAM, not a code bug.
- **Solution:** No code fix — just re-run `pixi run build` a few times until it succeeds. The RAM should be checked (`memtest86+`, reseat/replace DIMMs) in the future. See backlog above.

#### Stable gripper device names
- **Problem:** The Robotis RH-P12-RN-A grippers enumerate as `/dev/ttyUSB<N>` in kernel order, so the number is not tied to a physical gripper — power-cycling or replugging can swap left/right and break the launch.
- **Solution:** Added udev rules in `src/franka_launch/udev/99-dynamixel.rules` that pin each FTDI adapter's serial to a fixed symlink (`/dev/dynamixel_left`, `/dev/dynamixel_right`). Documented the install steps in the README under Prerequisites (§1.1.3).

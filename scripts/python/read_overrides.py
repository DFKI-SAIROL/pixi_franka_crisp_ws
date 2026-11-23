#!/usr/bin/env python3
"""Print config/robot_overrides.yaml as shell-sourceable KEY=VALUE lines.

Used by scripts/run_robot.sh and scripts/run_teleop.sh via:
    eval "$(pixi run -e humble python3 scripts/python/read_overrides.py "$OVERRIDES_FILE")"
"""
import sys

import yaml

def main():
    cfg = yaml.safe_load(open(sys.argv[1])) or {}

    def flag(key, default):
        return "true" if str(cfg.get(key, default)).lower() == "true" else "false"

    gripper_type_left = cfg.get("franka_left", {}).get("gripper_type", "rh_p12_rn_a")
    gripper_type_right = cfg.get("franka_right", {}).get("gripper_type", "rh_p12_rn_a")
    print(f"spawn_franka_left={flag('spawn_franka_left', True)}")
    print(f"spawn_franka_right={flag('spawn_franka_right', True)}")
    print(f"use_fake_hardware={flag('use_fake_hardware', False)}")
    print(f"bypass_safety={flag('bypass_safety', True)}")
    print(f"gripper_type_left={gripper_type_left}")
    print(f"gripper_type_right={gripper_type_right}")


if __name__ == "__main__":
    main()

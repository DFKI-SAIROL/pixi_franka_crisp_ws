#!/usr/bin/env python
"""Validate robot overrides and check all configured Dynamixel grippers."""

import sys
from pathlib import Path

import yaml

from check_gripper import check_gripper


DYNAMIXEL_GRIPPER_TYPES = {"rh_p12_rn_a", "dynamixel"}


def boolean(config, key, default):
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError(f"{key} must be true or false, got {value!r}")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <robot_overrides.yaml>", file=sys.stderr)
        return 1

    overrides_file = Path(sys.argv[1])
    with overrides_file.open() as stream:
        config = yaml.safe_load(stream) or {}
    if not isinstance(config, dict):
        raise ValueError(f"{overrides_file} must contain a YAML mapping")

    spawn = {
        side: boolean(config, f"spawn_franka_{side}", True)
        for side in ("left", "right")
    }
    use_fake_hardware = boolean(config, "use_fake_hardware", False)
    bypass_safety = boolean(config, "bypass_safety", False)
    gripper_types = {
        side: config.get(f"franka_{side}", {}).get("gripper_type", "rh_p12_rn_a")
        for side in ("left", "right")
    }

    print(
        f"{overrides_file}: "
        f"spawn_franka_left={str(spawn['left']).lower()} "
        f"spawn_franka_right={str(spawn['right']).lower()} "
        f"use_fake_hardware={str(use_fake_hardware).lower()} "
        f"bypass_safety={str(bypass_safety).lower()} "
        f"gripper_type_left={gripper_types['left']} "
        f"gripper_type_right={gripper_types['right']}"
    )

    if use_fake_hardware:
        return 0

    for side in ("left", "right"):
        if not spawn[side] or gripper_types[side] not in DYNAMIXEL_GRIPPER_TYPES:
            continue
        device = Path(f"/dev/dynamixel_{side}")
        if not device.exists():
            print(
                f"Error: spawn_franka_{side} is true but gripper device "
                f"{device} was not found.",
                file=sys.stderr,
            )
            return 1
        if not check_gripper(str(device)):
            print(
                f"Error: spawn_franka_{side} is true but the gripper on "
                f"{device} is not responding. Is it powered on?",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

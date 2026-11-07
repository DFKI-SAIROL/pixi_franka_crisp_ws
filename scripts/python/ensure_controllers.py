#!/usr/bin/env python
"""Finish starting the robot controllers the spawners left loaded but not active.

The arm controller managers block for ~11 s while loading their first controller. The installed spawner waits only
10 s for a load_controller response (hard-coded, --service-call-timeout does not apply to it), retries a load that
already succeeded, fails with "already loaded" and leaves the controller unconfigured (2026-11-07). Which controllers
are hit varies from launch to launch.

This script waits until the spawners have exited, then loads / configures / activates every expected controller that
is not active yet, in the same order the spawners would (state broadcasters before command controllers), with long
service timeouts. It exits non-zero if a controller could not be activated.

Usage: ensure_controllers.py <robot_overrides.yaml>
"""
import subprocess
import sys
import time
from pathlib import Path

import rclpy
import yaml
from builtin_interfaces.msg import Duration
from controller_manager_msgs.srv import ConfigureController, ListControllers, LoadController, SwitchController

CALL_TIMEOUT = 60.0
SPAWNER_WAIT = 180.0
DYNAMIXEL_GRIPPERS = {'rh_p12_rn_a', 'dynamixel'}


def boolean(value):
    return value if isinstance(value, bool) else str(value).lower() == 'true'


def expected_controllers(config):
    """Controller manager -> controllers, in activation order."""
    expected = {}
    for side in ('left', 'right'):
        if not boolean(config.get(f'spawn_franka_{side}', True)):
            continue
        arm = config.get(f'franka_{side}', {}) or {}
        ns = f'/franka_{side}'
        arm_controllers = ['joint_state_broadcaster', arm.get('arm_controller', 'joint_impedance_controller')]
        gripper_type = str(arm.get('gripper_type', 'rh_p12_rn_a'))
        if gripper_type in DYNAMIXEL_GRIPPERS:
            expected[f'{ns}/gripper/controller_manager'] = ['gripper_joint_state_broadcaster', 'gripper_controller']
        elif gripper_type == 'franka_default':
            arm_controllers.append('franka_gripper')
        expected[f'{ns}/controller_manager'] = arm_controllers
    return expected


def wait_for_spawners():
    deadline = time.monotonic() + SPAWNER_WAIT
    while time.monotonic() < deadline:
        if subprocess.run(['pgrep', '-f', 'controller_manager/spawner'], capture_output=True).returncode != 0:
            return
        time.sleep(1.0)
    print('Warning: spawners still running, checking controllers anyway', file=sys.stderr)


def call(node, srv_type, name, request):
    client = node.create_client(srv_type, name)
    try:
        if not client.wait_for_service(timeout_sec=CALL_TIMEOUT):
            raise RuntimeError(f'service {name} not available')
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=CALL_TIMEOUT)
        if not future.done():
            raise RuntimeError(f'no response from {name} within {CALL_TIMEOUT:.0f} s')
        return future.result()
    finally:
        node.destroy_client(client)


def states(node, cm):
    response = call(node, ListControllers, f'{cm}/list_controllers', ListControllers.Request())
    return {c.name: c.state for c in response.controller}


def ensure(node, cm, controllers):
    ok = True
    current = states(node, cm)
    for name in controllers:
        state = current.get(name)
        if state == 'active':
            continue
        print(f'{cm}: {name} is {state or "not loaded"}, starting it')
        if state is None and not call(node, LoadController, f'{cm}/load_controller',
                                      LoadController.Request(name=name)).ok:
            print(f'Error: {cm}: loading {name} failed', file=sys.stderr)
            ok = False
            continue
        if state in (None, 'unconfigured') and not call(node, ConfigureController, f'{cm}/configure_controller',
                                                        ConfigureController.Request(name=name)).ok:
            print(f'Error: {cm}: configuring {name} failed', file=sys.stderr)
            ok = False
            continue
        request = SwitchController.Request(activate_controllers=[name], strictness=SwitchController.Request.STRICT,
                                           activate_asap=True, timeout=Duration(sec=int(CALL_TIMEOUT)))
        if not call(node, SwitchController, f'{cm}/switch_controller', request).ok:
            print(f'Error: {cm}: activating {name} failed', file=sys.stderr)
            ok = False
            continue
    final = states(node, cm)
    for name in controllers:
        print(f'{cm}: {name} {final.get(name, "not loaded")}')
        ok &= final.get(name) == 'active'
    return ok


def main():
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <robot_overrides.yaml>', file=sys.stderr)
        return 1
    config = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
    if boolean(config.get('use_fake_hardware', False)):
        return 0

    wait_for_spawners()
    rclpy.init()
    node = rclpy.create_node('ensure_controllers')
    ok = True
    try:
        for cm, controllers in expected_controllers(config).items():
            try:
                ok &= ensure(node, cm, controllers)
            except RuntimeError as exc:
                print(f'Error: {cm}: {exc}', file=sys.stderr)
                ok = False
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    print('All controllers active.' if ok else 'Error: some controllers are not active, restart the robot launch.',
          file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())

"""Regression checks for shared robot, IK, and teleop frame selection."""

import importlib.util
from pathlib import Path

import pytest
import yaml


HELPER_PATH = Path(__file__).resolve().parents[1] / 'src/franka_launch/utils/launch_utils.py'
SPEC = importlib.util.spec_from_file_location('launch_utils_under_test', HELPER_PATH)
launch_utils = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launch_utils)


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('gripper_type', [None, 'None', 'none', 'rh_p12_rn_a', 'franka_default'])
@pytest.mark.parametrize('base', [{}, {'end_effector_frame': 'stale_frame'}])
def test_gripper_selects_frame_for_all_consumers(tmp_path, side, gripper_type, base):
    arm = f'franka_{side}'
    other_arm = 'franka_right' if side == 'left' else 'franka_left'
    overrides = tmp_path / 'overrides.yaml'
    overrides.write_text(yaml.safe_dump({
        arm: {'gripper_type': gripper_type, 'end_effector_frame': 'auto'},
        other_arm: {'gripper_type': 'rh_p12_rn_a'},
    }))
    original_base = dict(base)
    merged = launch_utils.merge_overrides(base, str(overrides), arm)
    no_gripper = gripper_type in (None, 'None', 'none')
    expected_suffix = 'fr3_link8' if no_gripper else 'grasp_point'
    assert merged['end_effector_frame'] == f'{arm}_{expected_suffix}'
    assert merged['gripper_type'] == ('none' if no_gripper else gripper_type)
    assert base == original_base
    other = launch_utils.merge_overrides({}, str(overrides), other_arm)
    assert other['end_effector_frame'] == f'{other_arm}_grasp_point'


def test_frame_preserved_without_gripper_setting(tmp_path):
    overrides = tmp_path / 'overrides.yaml'
    overrides.write_text('franka_left: {robot_ip: 192.168.1.4}\n')
    merged = launch_utils.merge_overrides(
        {'end_effector_frame': 'custom_tool'}, str(overrides), 'franka_left'
    )
    assert merged['end_effector_frame'] == 'custom_tool'


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('gripper_type', [None, 'None', 'none', 'rh_p12_rn_a', 'franka_default'])
@pytest.mark.parametrize('explicit_in_override', [False, True])
def test_explicit_frame_preserved_with_gripper(tmp_path, side, gripper_type, explicit_in_override):
    arm = f'franka_{side}'
    settings = {'gripper_type': gripper_type}
    base = {'end_effector_frame': 'custom_base_tool'}
    if explicit_in_override:
        settings['end_effector_frame'] = 'custom_override_tool'
    overrides = tmp_path / 'overrides.yaml'
    overrides.write_text(yaml.safe_dump({arm: settings}))
    merged = launch_utils.merge_overrides(base, str(overrides), arm)
    expected = 'custom_override_tool' if explicit_in_override else 'custom_base_tool'
    assert merged['end_effector_frame'] == expected
    if gripper_type in (None, 'None', 'none'):
        assert merged['gripper_type'] == 'none'


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('gripper_type', [None, 'rh_p12_rn_a', 'franka_default'])
def test_omitted_frame_defaults_to_auto(tmp_path, side, gripper_type):
    arm = f'franka_{side}'
    overrides = tmp_path / 'overrides.yaml'
    overrides.write_text(yaml.safe_dump({arm: {'gripper_type': gripper_type}}))
    merged = launch_utils.merge_overrides({}, str(overrides), arm)
    suffix = 'fr3_link8' if gripper_type is None else 'grasp_point'
    assert merged['end_effector_frame'] == f'{arm}_{suffix}'

"""Start the CSIL ZED cameras on the Jetson and publish their hand-eye calibrations on this PC.

    ros2 launch config/zed/zed.launch.py

1. Copies jetson_cameras.launch.py and camera_params.yaml to /tmp/csil_zed/ on the Jetson and starts them over ssh
   (Ctrl-C here stops the cameras). The Jetson's shared files (launch_zed.sh, zed_multi_camera) are not used.
2. For every calibrated camera, runs the launch file exported by MoveIt hand-eye calibration (parent -> optical
   frame) with /tf_static remapped to a private topic, and zed_remote_launcher's calibration_tf.py, which publishes
   the same pose as parent -> <camera>_camera_link (the root of the camera's frame tree; a second parent for the
   optical frame would break TF).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, GroupAction, IncludeLaunchDescription, \
    OpaqueFunction, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, SetRemap

HERE = os.path.dirname(os.path.realpath(__file__))
REMOTE_DIR = '/tmp/csil_zed'

# camera -> calibration launch file in zed_remote_launcher/config/calibration/
CALIBRATIONS = {
    'zed_right': '030726_zedx_middle_40deg.launch.py',
}


def launch_setup(context):
    ssh_target = context.launch_configurations['ssh_target']
    actions = []

    for camera, calibration_file in CALIBRATIONS.items():
        calibration_launch = os.path.join(get_package_share_directory('zed_remote_launcher'), 'config', 'calibration',
                                          calibration_file)
        # own topic and node names, so a parallel zed_remote_launcher session (lieflows) does not interfere
        calibration_topic = f'/csil/{camera}/calibration/tf_static'
        actions.append(GroupAction([
            SetRemap(src='/tf_static', dst=calibration_topic),
            IncludeLaunchDescription(PythonLaunchDescriptionSource(calibration_launch)),
        ], scoped=True))
        actions.append(Node(
            package='zed_remote_launcher',
            executable='calibration_tf.py',
            name=f'calibration_tf_csil_{camera}',
            output='screen',
            parameters=[{'root_frame': f'{camera}_camera_link', 'input_topic': calibration_topic}],
        ))

    copy = ExecuteProcess(
        cmd=['bash', '-c', 'ssh -o BatchMode=yes "$1" mkdir -p "$2" && scp -q "$3" "$4" "$1:$2/"', 'copy',
             ssh_target, REMOTE_DIR,
             os.path.join(HERE, 'jetson_cameras.launch.py'), os.path.join(HERE, 'camera_params.yaml')],
        name='copy_zed_config',
        output='screen',
    )
    remote_cmd = (
        'trap "pkill -P $$" EXIT'
        ' && source ~/.bashrc_ros'
        ' && source /opt/ros/humble/setup.bash'
        ' && source ~/Projects/ros2_ws/install/setup.bash'
        f' && ros2 launch {REMOTE_DIR}/jetson_cameras.launch.py params:={REMOTE_DIR}/camera_params.yaml'
    )
    run = ExecuteProcess(cmd=['ssh', '-t', '-t', ssh_target, remote_cmd], name='zed_cameras', output='screen')
    actions.append(copy)
    actions.append(RegisterEventHandler(OnProcessExit(target_action=copy, on_exit=[run])))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('ssh_target', default_value='jetson'),
        OpaqueFunction(function=launch_setup),
    ])

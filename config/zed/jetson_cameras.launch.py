"""CSIL ZED cameras, run ON THE JETSON (copied to /tmp by zed.launch.py, nothing installed there).

All cameras are loaded into one component container: with one process per camera only the first ZED X (GMSL)
camera streamed, the others logged "Failed to connect to zed_x_daemon" and published nothing (2026-11-07).

Same layout as `launch_zed.sh csil` (zed_multi_camera): namespace /zed_multi, topics /zed_multi/<camera>/...,
frames <camera>_camera_link -> ... from each camera's own URDF. Unlike zed_multi_camera, the multi-camera URDF
(zed_multi.urdf.xacro) is not loaded: it gives every camera a fixed pose by its position in the camera list, which is
wrong for the CSIL order. The calibrated camera poses are published on the PC instead (zed.launch.py).
"""
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import ComposableNodeContainer

NAMESPACE = 'zed_multi'
CONTAINER = 'zed_multi_container'

# name, model, serial
CAMERAS = [
    ('zed_middle', 'zedxm', '54516821'),
    ('zed_right', 'zedx', '49078146'),
    ('zed_right_arm', 'zedxm', '58133554'),
]


def launch_setup(context):
    params = context.launch_configurations['params']
    zed_launch = get_package_share_directory('zed_wrapper') + '/launch/zed_camera.launch.py'

    actions = [ComposableNodeContainer(
        name=CONTAINER,
        namespace=NAMESPACE,
        package='rclcpp_components',
        executable='component_container_mt',
        arguments=['--ros-args', '--log-level', 'info'],
        output='screen',
    )]
    for name, model, serial in CAMERAS:
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(zed_launch),
            launch_arguments={
                'container_name': CONTAINER,
                'namespace': NAMESPACE,
                'camera_name': name,
                'camera_model': model,
                'serial_number': serial,
                'publish_tf': 'false',
                'publish_map_tf': 'false',
                'ros_params_override_path': params,
            }.items(),
        ))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('params', description='ZED parameter override file (on the Jetson)'),
        OpaqueFunction(function=launch_setup),
    ])

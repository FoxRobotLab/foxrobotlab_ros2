# This is the centralized launch client

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def _include(package_dir, launch_file, launch_arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(package_dir, 'launch', launch_file)
        ),
        launch_arguments=(launch_arguments or {}).items(),
    )


def generate_launch_description():
    package_dir = get_package_share_directory('foxrobotlab_ros2')

    ld = LaunchDescription()
    ld.add_action(_include(package_dir, 'kobuki.launch.py', {'astra': 'true'}))
    ld.add_action(_include(package_dir, 'video_stream_client.launch.py'))
    ld.add_action(_include(package_dir, 'match_planner.launch.py'))
    return ld

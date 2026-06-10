import os
import sys

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def _load_config(package_dir):
    config_path = os.path.join(package_dir, 'config', 'match_planner.yaml')
    with open(config_path, 'r', encoding='utf-8') as config_file:
        return yaml.safe_load(config_file)


def _as_env(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    return str(value)


def generate_launch_description():
    ld = LaunchDescription()
    package_dir = get_package_share_directory('foxrobotlab_ros2')
    config = _load_config(package_dir)
    remote_localizer = config['remote_localizer']

    localizer_client = os.path.join(package_dir, 'src', 'localizer_client.py')

    ld.add_action(
        ExecuteProcess(
            cmd=[sys.executable, localizer_client],
            additional_env={
                'FOX_LOCALIZER_SERVER_IP': _as_env(remote_localizer['server_ip']),
                'FOX_LOCALIZER_SERVER_PORT': _as_env(remote_localizer['server_port']),
            },
            output='screen',
        )
    )

    return ld

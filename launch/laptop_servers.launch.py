import os
import sys

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def _load_config(package_dir):
    config_path = os.path.join(package_dir, 'config', 'client_server.yaml')
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

    localizer_config = config['localizer_server']
    video_server_config = config['video_stream']['server']
    video_gui_config = config['video_stream']['gui']

    localizer_server = os.path.join(package_dir, 'src', 'localizer_server.py')
    seeker_gui = os.path.join(package_dir, 'src', 'seeker_gui_unified.py')

    ld.add_action(
        ExecuteProcess(
            cmd=[sys.executable, localizer_server],
            additional_env={
                'FOX_LOCALIZER_SERVER_HOST': _as_env(localizer_config['host']),
                'FOX_LOCALIZER_SERVER_PORT': _as_env(localizer_config['port']),
                'FOX_LOCALIZER_SHOW_IMAGES': _as_env(localizer_config['show_images']),
            },
            output='screen',
        )
    )

    ld.add_action(
        ExecuteProcess(
            cmd=[sys.executable, seeker_gui],
            additional_env={
                'FOX_VIDEO_SERVER_HOST': _as_env(video_server_config['host']),
                'FOX_VIDEO_SERVER_PORT': _as_env(video_server_config['port']),
                'FOX_VIDEO_FPS_REPORT_PERIOD': _as_env(video_server_config['fps_report_period']),
                'FOX_GUI_REFRESH_MS': _as_env(video_gui_config['refresh_ms']),
                'FOX_GUI_STATUS_SERVER_HOST': _as_env(video_gui_config['planner_status_host']),
                'FOX_GUI_STATUS_SERVER_PORT': _as_env(video_gui_config['planner_status_port']),
                'FOX_GUI_COMMAND_SERVER_IP': _as_env(video_gui_config['planner_command_ip']),
                'FOX_GUI_COMMAND_SERVER_PORT': _as_env(video_gui_config['planner_command_port']),
            },
            output='screen',
        )
    )

    return ld

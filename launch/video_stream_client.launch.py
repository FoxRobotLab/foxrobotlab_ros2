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
    video_client_config = config['video_stream']['client']

    video_stream_client = os.path.join(package_dir, 'src', 'video_stream_client.py')

    ld.add_action(
        ExecuteProcess(
            cmd=[sys.executable, video_stream_client],
            additional_env={
                'FOX_VIDEO_SERVER_IP': _as_env(video_client_config['server_ip']),
                'FOX_VIDEO_SERVER_PORT': _as_env(video_client_config['port']),
                'FOX_VIDEO_TARGET_FPS': _as_env(video_client_config['target_fps']),
                'FOX_VIDEO_JPEG_QUALITY': _as_env(video_client_config['jpeg_quality']),
                'FOX_VIDEO_RESIZE_WIDTH': _as_env(video_client_config['resize_width']),
                'FOX_VIDEO_RESIZE_HEIGHT': _as_env(video_client_config['resize_height']),
                'FOX_VIDEO_SEND_DEPTH': _as_env(video_client_config['send_depth']),
            },
            output='screen',
        )
    )

    return ld

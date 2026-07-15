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


def _workspace_dir(package_dir):
    return os.path.abspath(os.path.join(package_dir, '..', '..', '..', '..'))


def _resolve_path(package_dir, path):
    if not path:
        return ''
    if os.path.isabs(path):
        return path
    return os.path.join(_workspace_dir(package_dir), path)


def _python_executable(package_dir, python_config):
    if not python_config.get('enabled', False):
        return sys.executable

    configured_python = python_config.get('python_executable', '')
    if configured_python:
        return _resolve_path(package_dir, configured_python)

    venv_path = _resolve_path(package_dir, python_config.get('venv_path', '.venv'))
    return os.path.join(venv_path, 'bin', 'python')

def _merge_env(*env_maps):
    merged = {}
    for env_map in env_maps:
        for key, value in env_map.items():
            if value is not None and value != '':
                merged[key] = _as_env(value)
    return merged


def generate_launch_description():
    ld = LaunchDescription()
    package_dir = get_package_share_directory('foxrobotlab_ros2')
    config = _load_config(package_dir)

    localizer_config = config['localizer_server']
    python_config = config.get('python_env', {})
    video_server_config = config['video_stream']['server']
    video_gui_config = config['video_stream']['gui']

    localizer_server = os.path.join(package_dir, 'src', 'client_server', 'localizer_server.py')
    seeker_gui = os.path.join(package_dir, 'src', 'client_server', 'gui_unified.py')
    localizer_python = _python_executable(package_dir, python_config)
    gui_python = localizer_python if python_config.get('use_for_gui', False) else sys.executable
    
    ld.add_action(
        ExecuteProcess(
            cmd=[localizer_python, localizer_server],
            additional_env=_merge_env(
                python_config.get('env', {}),
                {
                    'FOX_LOCALIZER_SERVER_HOST': _as_env(localizer_config['host']),
                    'FOX_LOCALIZER_SERVER_PORT': _as_env(localizer_config['port']),
                    'FOX_LOCALIZER_SHOW_IMAGES': _as_env(localizer_config['show_images']),
                    'FOX_LOCALIZER_MODE': _as_env(localizer_config.get('mode', 'cnn_mcl')),
                    'FOX_LOCALIZER_MODEL': _as_env(localizer_config.get('model', 'mock')),
                    'FOX_LOCALIZER_MODEL_PATH': _resolve_path(
                        package_dir,
                        localizer_config.get('cell_model_path', ''),
                    ),
                    'FOX_LOCALIZER_SHOW_MCL': _as_env(localizer_config.get('show_mcl', False)),
                    'FOX_LOCALIZER_MCL_PARTICLES': _as_env(localizer_config.get('mcl_particles', 250)),
                },
            ),
            output='screen',
        )
    )

    ld.add_action(
        ExecuteProcess(
            cmd=[gui_python, seeker_gui],
            additional_env=_merge_env(
                python_config.get('env', {}) if python_config.get('use_for_gui', False) else {},
                {
                    'FOX_VIDEO_SERVER_HOST': _as_env(video_server_config['host']),
                    'FOX_VIDEO_SERVER_PORT': _as_env(video_server_config['port']),
                    'FOX_VIDEO_FPS_REPORT_PERIOD': _as_env(video_server_config['fps_report_period']),
                    'FOX_GUI_REFRESH_MS': _as_env(video_gui_config['refresh_ms']),
                    'FOX_GUI_STATUS_SERVER_HOST': _as_env(video_gui_config['planner_status_host']),
                    'FOX_GUI_STATUS_SERVER_PORT': _as_env(video_gui_config['planner_status_port']),
                    'FOX_GUI_COMMAND_SERVER_IP': _as_env(video_gui_config['planner_command_ip']),
                    'FOX_GUI_COMMAND_SERVER_PORT': _as_env(video_gui_config['planner_command_port']),
                },
            ),
            output='screen',
        )
    )

    return ld

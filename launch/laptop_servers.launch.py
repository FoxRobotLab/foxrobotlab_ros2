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


def _nvidia_library_path(package_dir, python_config):
    if not python_config.get('enabled', False):
        return ''
    if not python_config.get('add_nvidia_library_path', False):
        return ''

    venv_path = _resolve_path(package_dir, python_config.get('venv_path', '.venv'))
    nvidia_root = os.path.join(venv_path, 'lib')
    library_dirs = []

    for root, _, files in os.walk(nvidia_root):
        if '/nvidia/' not in root:
            continue
        if any(name.endswith('.so') or '.so.' in name for name in files):
            library_dirs.append(root)

    return ':'.join(sorted(set(library_dirs)))


def _merge_env(base_env, extra_env):
    merged = dict(base_env)
    for key, value in extra_env.items():
        if value:
            merged[key] = value
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
    tensorflow_check = os.path.join(package_dir, 'src', 'client_server', 'tensorflow_check.py')
    localizer_python = _python_executable(package_dir, python_config)
    gui_python = localizer_python if python_config.get('use_for_gui', False) else sys.executable
    nvidia_library_path = _nvidia_library_path(package_dir, python_config)
    tensorflow_env = {
        'LD_LIBRARY_PATH': (
            nvidia_library_path + ':' + os.environ.get('LD_LIBRARY_PATH', '')
            if nvidia_library_path else ''
        ),
        'TF_ENABLE_ONEDNN_OPTS': (
            '0' if python_config.get('disable_onednn_opts', False) else ''
        ),
        'PYTHONUNBUFFERED': '1',
    }

    if python_config.get('run_tensorflow_check', False):
        ld.add_action(
            ExecuteProcess(
                cmd=[localizer_python, tensorflow_check],
                additional_env=tensorflow_env,
                output='screen',
            )
        )

    ld.add_action(
        ExecuteProcess(
            cmd=[localizer_python, localizer_server],
            additional_env=_merge_env(
                {
                    'FOX_LOCALIZER_SERVER_HOST': _as_env(localizer_config['host']),
                    'FOX_LOCALIZER_SERVER_PORT': _as_env(localizer_config['port']),
                    'FOX_LOCALIZER_SHOW_IMAGES': _as_env(localizer_config['show_images']),
                },
                tensorflow_env,
            ),
            output='screen',
        )
    )

    ld.add_action(
        ExecuteProcess(
            cmd=[gui_python, seeker_gui],
            additional_env=_merge_env(
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
                tensorflow_env if python_config.get('use_for_gui', False) else {},
            ),
            output='screen',
        )
    )

    return ld

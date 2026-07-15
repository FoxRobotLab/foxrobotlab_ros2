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
    package_dir = get_package_share_directory('foxrobotlab_ros2')
    config = _load_config(package_dir)
    python_config = config.get('python_env', {})
    check_config = config.get('tensorflow_check', {})

    tensorflow_check = os.path.join(package_dir, 'src', 'client_server', 'tensorflow_check.py')
    python = _python_executable(package_dir, python_config)

    return LaunchDescription([
        ExecuteProcess(
            cmd=[python, tensorflow_check],
            additional_env=_merge_env(
                python_config.get('env', {}),
                {
                    'FOX_TENSORFLOW_MODEL_PATH': _resolve_path(
                        package_dir,
                        check_config.get('model_path', ''),
                    ),
                    'FOX_TENSORFLOW_RUN_MODEL_PREDICT': check_config.get('run_model_predict', True),
                },
            ),
            output='screen',
        )
    ])

import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
import yaml


def _load_match_planner_config(package_dir):
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
    config = _load_match_planner_config(package_dir)
    remote_localizer = config['remote_localizer']
    planner = config['planner']
    gui_status_bridge = config['gui_status_bridge']
    gui_command_server = config['gui_command_server']

    match_planner = os.path.join(
        package_dir,
        'src',
        'match_seeker',
        'scripts',
        'matchPlanner.py',
    )

    receiver_node = Node(
        package='foxrobotlab_ros2',
        executable='turtle_control_reciever.py',
        name='control_reciever',
        output='screen',
    )

    planner_process = ExecuteProcess(
        cmd=[sys.executable, match_planner],
        additional_env={
            'FOX_REMOTE_LOCALIZER': _as_env(remote_localizer['enabled']),
            'FOX_LOCALIZER_SERVER_IP': _as_env(remote_localizer['server_ip']),
            'FOX_LOCALIZER_SERVER_PORT': _as_env(remote_localizer['server_port']),
            'FOX_LOCALIZER_TIMEOUT': _as_env(remote_localizer['timeout']),
            'FOX_MATCH_LOOP_SLEEP': _as_env(planner['match_loop_sleep']),
            'FOX_USE_LEGACY_GUI': _as_env(planner['use_legacy_gui']),
            'FOX_GUI_STATUS_BRIDGE': _as_env(gui_status_bridge['enabled']),
            'FOX_GUI_STATUS_SERVER_IP': _as_env(gui_status_bridge['server_ip']),
            'FOX_GUI_STATUS_SERVER_PORT': _as_env(gui_status_bridge['server_port']),
            'FOX_GUI_COMMAND_SERVER': _as_env(gui_command_server['enabled']),
            'FOX_GUI_COMMAND_SERVER_HOST': _as_env(gui_command_server['host']),
            'FOX_GUI_COMMAND_SERVER_PORT': _as_env(gui_command_server['port']),
            'FOX_DISPLAY_WINDOWS': _as_env(planner['display_windows']),
        },
        output='screen',
    )

    ld.add_action(receiver_node)
    ld.add_action(planner_process)
    return ld

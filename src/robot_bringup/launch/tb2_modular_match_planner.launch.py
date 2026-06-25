import os
import sys

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def _load_match_planner_config():
    package_dir = get_package_share_directory("foxrobotlab_ros2")
    config_path = os.path.join(package_dir, "config", "match_planner.yaml")
    with open(config_path, "r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def _as_env(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def generate_launch_description():
    namespace = LaunchConfiguration("namespace")
    astra = LaunchConfiguration("astra")
    xtion = LaunchConfiguration("xtion")
    lidar_a2 = LaunchConfiguration("lidar_a2")
    lidar_s2 = LaunchConfiguration("lidar_s2")

    config = _load_match_planner_config()
    remote_localizer = config["remote_localizer"]
    planner = config["planner"]
    gui_status_bridge = config["gui_status_bridge"]
    gui_command_server = config["gui_command_server"]

    foxrobotlab_dir = get_package_share_directory("foxrobotlab_ros2")
    match_planner = os.path.join(
        foxrobotlab_dir,
        "src",
        "match_seeker",
        "scripts",
        "matchPlanner.py",
    )

    system = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("robot_bringup"),
                "launch",
                "tb2_system.launch.py",
            ])
        ),
        launch_arguments={
            "namespace": namespace,
            "astra": astra,
            "xtion": xtion,
            "lidar_a2": lidar_a2,
            "lidar_s2": lidar_s2,
        }.items(),
    )

    planner_process = ExecuteProcess(
        cmd=[sys.executable, match_planner],
        additional_env={
            "FOX_USE_MODULAR_ROBOT_PROCESSOR": "1",
            "FOX_REMOTE_LOCALIZER": _as_env(remote_localizer["enabled"]),
            "FOX_LOCALIZER_SERVER_IP": _as_env(remote_localizer["server_ip"]),
            "FOX_LOCALIZER_SERVER_PORT": _as_env(remote_localizer["server_port"]),
            "FOX_LOCALIZER_TIMEOUT": _as_env(remote_localizer["timeout"]),
            "FOX_MATCH_LOOP_SLEEP": _as_env(planner["match_loop_sleep"]),
            "FOX_USE_LEGACY_GUI": _as_env(planner["use_legacy_gui"]),
            "FOX_GUI_STATUS_BRIDGE": _as_env(gui_status_bridge["enabled"]),
            "FOX_GUI_STATUS_SERVER_IP": _as_env(gui_status_bridge["server_ip"]),
            "FOX_GUI_STATUS_SERVER_PORT": _as_env(gui_status_bridge["server_port"]),
            "FOX_GUI_COMMAND_SERVER": _as_env(gui_command_server["enabled"]),
            "FOX_GUI_COMMAND_SERVER_HOST": _as_env(gui_command_server["host"]),
            "FOX_GUI_COMMAND_SERVER_PORT": _as_env(gui_command_server["port"]),
            "FOX_DISPLAY_WINDOWS": _as_env(planner["display_windows"]),
        },
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("astra", default_value="true"),
        DeclareLaunchArgument("xtion", default_value="false"),
        DeclareLaunchArgument("lidar_a2", default_value="false"),
        DeclareLaunchArgument("lidar_s2", default_value="false"),
        system,
        planner_process,
    ])

import os
import sys

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def include_launch(package_name, launch_file, launch_arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare(package_name),
                "launch",
                launch_file,
            ])
        ),
        launch_arguments=(launch_arguments or {}).items(),
    )


def declare_launch_arguments():
    return [
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("astra", default_value="true"),
        DeclareLaunchArgument("xtion", default_value="false"),
        DeclareLaunchArgument("lidar_a2", default_value="false"),
        DeclareLaunchArgument("lidar_s2", default_value="false"),
    ]


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
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the hardware options passed down to tb2_system.launch.py.
    namespace = LaunchConfiguration("namespace")
    astra = LaunchConfiguration("astra")
    xtion = LaunchConfiguration("xtion")
    lidar_a2 = LaunchConfiguration("lidar_a2")
    lidar_s2 = LaunchConfiguration("lidar_s2")

    # ---------------- Include Launch Files ----------------
    # Start the full TurtleBot2 modular system before the planner.
    system = include_launch(
        "robot_bringup",
        "tb2_system.launch.py",
        {
            "namespace": namespace,
            "astra": astra,
            "xtion": xtion,
            "lidar_a2": lidar_a2,
            "lidar_s2": lidar_s2,
        },
    )

    # ---------------- Configure Match Planner ----------------
    # Find matchPlanner.py from the installed foxrobotlab_ros2 share directory.
    foxrobotlab_dir = get_package_share_directory("foxrobotlab_ros2")
    match_planner = os.path.join(
        foxrobotlab_dir,
        "src",
        "match_seeker",
        "scripts",
        "matchPlanner.py",
    )

    # Load YAML settings used by matchPlanner.py and client-server helpers.
    config = _load_match_planner_config()
    remote_localizer = config["remote_localizer"]
    planner = config["planner"]
    gui_status_bridge = config["gui_status_bridge"]
    gui_command_server = config["gui_command_server"]

    # ---------------- Initialize Processes ----------------
    # Run matchPlanner.py with the modular RobotControlProcessor enabled.
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

    # ---------------- Add to Launch Description ----------------
    # Add arguments first so they are available to included launch files.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(system)
    ld.add_action(planner_process)

    return ld

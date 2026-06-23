from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def include_launch(package_name, launch_file):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare(package_name),
                "launch",
                launch_file
            ])
        )
    )


def generate_launch_description():
    system = include_launch("robot_bringup", "tb2_system.launch.py")

    config_file = PathJoinSubstitution([
        FindPackageShare("robot_apps"),
        "config",
        "state_printer.yaml"
    ])

    app = Node(
        package="robot_apps",
        executable="print_robot_state_app.py",
        name="print_robot_state_app",
        output="screen",
        parameters=[config_file]
    )

    return LaunchDescription([
        system,
        app
    ])

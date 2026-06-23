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
        "simple_drive.yaml"
    ])

    app = Node(
        package="robot_apps",
        executable="simple_drive_app.py",
        name="simple_drive_app",
        output="screen",
        parameters=[config_file]
    )

    return LaunchDescription([
        system,
        app
    ])
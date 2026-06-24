from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = LaunchConfiguration("config")

    config_file = PathJoinSubstitution([
        FindPackageShare("test"),
        "config",
        config,
    ])

    verifier = Node(
        package="test",
        executable="phase2_topic_verifier.py",
        name="phase2_topic_verifier",
        output="screen",
        parameters=[config_file],
    )

    return LaunchDescription([
        DeclareLaunchArgument("config", default_value="phase2_verifier.yaml"),
        verifier,
    ])

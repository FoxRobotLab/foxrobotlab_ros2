from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    smoke = Node(
        package="test",
        executable="robot_control_processor_smoke.py",
        name="robot_control_processor_smoke",
        output="screen",
    )

    return LaunchDescription([smoke])

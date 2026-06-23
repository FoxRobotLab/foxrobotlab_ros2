from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    ld = LaunchDescription()

    robot = LaunchConfiguration("robot")

    args = [
        DeclareLaunchArgument("robot", default_value="tb2")
    ]
    
    config_file = PathJoinSubstitution([
        FindPackageShare("robot_adapters"),
        "config",
        "tb2_topics.yaml"
    ])

    tb2_adapter_node = Node(
        package="robot_adapters",
        executable="tb2_adapter.py",
        name="tb2_adapter",
        output="screen",
        parameters=[config_file]
    )

    for arg in args:
        ld.add_action(arg)

    ld.add_action(tb2_adapter_node)

    return ld
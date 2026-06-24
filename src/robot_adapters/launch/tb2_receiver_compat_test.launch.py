from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():

    # Create a new launch description
    ld = LaunchDescription()

    # Load the configuration file
    config_file = PathJoinSubstitution([
        FindPackageShare("robot_adapters"),
        "config",
        "tb2_topics.yaml",
    ])

    # Create the TurtleBot2 adapter node that uses the loaded configuration file.
    tb2_adapter_node = Node(
        package="robot_adapters",
        executable="tb2_adapter.py",
        name="tb2_adapter",
        output="screen",
        parameters=[config_file],
    )

    # add node to launch description
    ld.add_action(tb2_adapter_node)

    return ld

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Parameters ----------------
    # Load the default TurtleBot2 adapter configuration file.
    config_file = PathJoinSubstitution([
        FindPackageShare("robot_adapters"),
        "config",
        "tb2_topics.yaml",
    ])

    # ---------------- Initialize Nodes ----------------
    # Start only the adapter for compatibility testing against an existing robot stack.
    tb2_adapter_node = Node(
        package="robot_adapters",
        executable="tb2_adapter.py",
        name="tb2_adapter",
        output="screen",
        parameters=[config_file],
    )

    # ---------------- Add to Launch Description ----------------
    # Add the compatibility-test adapter node.
    ld.add_action(tb2_adapter_node)

    return ld

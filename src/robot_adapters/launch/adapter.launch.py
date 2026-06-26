from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def declare_launch_arguments():
    return [
        DeclareLaunchArgument("robot", default_value="tb2"),
        DeclareLaunchArgument("config", default_value="tb2_topics.yaml"),
    ]


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the adapter config file name from the launch arguments.
    config = LaunchConfiguration("config")

    # ---------------- Get Parameters ----------------
    # Build the full path to the adapter YAML file.
    config_file = PathJoinSubstitution([
        FindPackageShare("robot_adapters"),
        "config",
        config,
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the TurtleBot2 adapter.
    tb2_adapter_node = Node(
        package="robot_adapters",
        executable="tb2_adapter.py",
        name="tb2_adapter",
        output="screen",
        parameters=[config_file],
    )

    # ---------------- Add to Launch Description ----------------
    # Add arguments before the node that consumes them.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(tb2_adapter_node)

    return ld

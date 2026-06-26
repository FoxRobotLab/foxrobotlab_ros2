from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def declare_launch_arguments():
    return [
        DeclareLaunchArgument("config", default_value="phase2_verifier.yaml"),
    ]


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the verifier config file name from the launch arguments.
    config = LaunchConfiguration("config")

    # ---------------- Get Parameters ----------------
    # Build the full path to the verifier YAML file.
    config_file = PathJoinSubstitution([
        FindPackageShare("test"),
        "config",
        config,
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the subscriber-based Phase 2 topic verifier.
    verifier = Node(
        package="test",
        executable="phase2_topic_verifier.py",
        name="phase2_topic_verifier",
        output="screen",
        parameters=[config_file],
    )

    # ---------------- Add to Launch Description ----------------
    # Add arguments before the node that consumes them.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(verifier)

    return ld

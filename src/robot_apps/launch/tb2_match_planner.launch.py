from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def declare_launch_arguments():
    return [
        DeclareLaunchArgument("config", default_value="match_planner.yaml"),
        DeclareLaunchArgument("use_localizer_stub", default_value="true"),
    ]


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the planner config file name from the launch arguments.
    config = LaunchConfiguration("config")
    use_localizer_stub = LaunchConfiguration("use_localizer_stub")

    # ---------------- Get Parameters ----------------
    # Build the full path to the planner YAML file.
    config_file = PathJoinSubstitution([
        FindPackageShare("robot_apps"),
        "apps",
        "match_planner",
        "config",
        config,
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the localizer stub node.
    localizer_stub_node = Node(
        package="robot_apps",
        executable="localizer_stub_node.py",
        name="localizer_stub_node",
        output="screen",
        parameters=[config_file],
        condition=IfCondition(use_localizer_stub),
    )

    # Start the match planner app shell.
    match_planner_node = Node(
        package="robot_apps",
        executable="match_planner_node.py",
        output="screen",
        parameters=[config_file],
    )

    # ---------------- Add to Launch Description ----------------
    # Add arguments before the node that consumes them.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(localizer_stub_node)
    ld.add_action(match_planner_node)

    return ld

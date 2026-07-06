from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.conditions import IfCondition
from launch.substitutions import PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def declare_launch_arguments():
    return [
        DeclareLaunchArgument("robot", default_value="tb2"),
    ]


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the adapter config file name from the launch arguments.
    robot = LaunchConfiguration("robot")

    # ---------------- Get Parameters ----------------
    # Build the full path to the adapter YAML file.
    tb2_parameters = PathJoinSubstitution([
        FindPackageShare("robot_adapters"),
        "config",
        "tb2_topics.yaml",
    ])

    tb4_parameters = PathJoinSubstitution([
        FindPackageShare("robot_adapters"),
        "config",
        "tb4_topics.yaml",
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the TurtleBot2 adapter.
    tb2_adapter_node = Node(
        package="robot_adapters",
        executable="tb2_adapter.py",
        name="tb2_adapter",
        output="screen",
        parameters=[tb2_parameters],
        condition=IfCondition(PythonExpression(["'", robot, "' == 'tb2'"])),
    )

    tb4_adapter_node = Node(
        package="robot_adapters",
        executable="tb4_adapter.py",
        name="tb4_adapter",
        output="screen",
        parameters=[tb4_parameters],
        condition=IfCondition(PythonExpression(["'", robot, "' == 'tb4'"])),
    )

    # ---------------- Add to Launch Description ----------------
    # Add arguments before the node that consumes them.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(tb2_adapter_node)
    ld.add_action(tb4_adapter_node)
    
    return ld

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Parameters ----------------
    # Load robot processor parameters.
    core_params = PathJoinSubstitution([
        FindPackageShare("robot_core"),
        "config",
        "core_params.yaml",
    ])

    # Load safety monitor parameters.
    safety_params = PathJoinSubstitution([
        FindPackageShare("robot_core"),
        "config",
        "safety_params.yaml",
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the robot state processor.
    robot_processor = Node(
        package="robot_core",
        executable="robot_processor.py",
        name="robot_processor",
        output="screen",
        parameters=[core_params],
    )

    # Start the safety monitor.
    safety_monitor = Node(
        package="robot_core",
        executable="safety_monitor.py",
        name="safety_monitor",
        output="screen",
        parameters=[safety_params],
    )

    # ---------------- Add to Launch Description ----------------
    # Add core nodes to the launch description.
    ld.add_action(robot_processor)
    ld.add_action(safety_monitor)

    return ld

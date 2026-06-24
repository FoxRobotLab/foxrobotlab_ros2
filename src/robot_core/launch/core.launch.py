from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Parameters ----------------
    core_params = PathJoinSubstitution([
        FindPackageShare("robot_core"),
        "config",
        "core_params.yaml"
    ])

    safety_params = PathJoinSubstitution([
        FindPackageShare("robot_core"),
        "config",
        "safety_params.yaml"
    ])

    # ---------------- Initialize Nodes ----------------
    robot_processor = Node(
        package="robot_core",
        executable="robot_processor.py",
        name="robot_processor",
        output="screen",
        parameters=[core_params]
    )

    safety_monitor = Node(
        package="robot_core",
        executable="safety_monitor.py",
        name="safety_monitor",
        output="screen",
        parameters=[safety_params]
    )

    ld.add_action(robot_processor)
    ld.add_action(safety_monitor)

    return ld
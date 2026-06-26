from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Initialize Nodes ----------------
    # Start the modular RobotControlProcessor smoke test.
    smoke = Node(
        package="test",
        executable="robot_control_processor_smoke.py",
        name="robot_control_processor_smoke",
        output="screen",
    )

    # ---------------- Add to Launch Description ----------------
    # Add the smoke test node.
    ld.add_action(smoke)

    return ld

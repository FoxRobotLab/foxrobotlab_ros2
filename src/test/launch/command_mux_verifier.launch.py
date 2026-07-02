from launch import LaunchDescription
from launch.actions import EmitEvent, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Parameters ----------------
    command_mux_config = PathJoinSubstitution([
        FindPackageShare("robot_core"),
        "config",
        "command_mux.yaml",
    ])
    verifier_config = PathJoinSubstitution([
        FindPackageShare("test"),
        "config",
        "command_mux_verifier.yaml",
    ])

    # ---------------- Initialize Nodes ----------------
    command_mux = Node(
        package="robot_core",
        executable="command_mux.py",
        name="command_mux",
        output="screen",
        parameters=[command_mux_config],
    )

    verifier = Node(
        package="test",
        executable="command_mux_verifier.py",
        name="command_mux_verifier",
        output="screen",
        parameters=[verifier_config],
    )

    # ---------------- Add to Launch Description ----------------
    ld.add_action(command_mux)
    ld.add_action(verifier)
    ld.add_action(
        RegisterEventHandler(
            OnProcessExit(
                target_action=verifier,
                on_exit=[
                    EmitEvent(event=Shutdown(reason="command mux verifier finished")),
                ],
            )
        )
    )

    return ld

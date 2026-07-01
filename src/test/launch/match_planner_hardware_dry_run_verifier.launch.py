from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def declare_launch_arguments():
    return [
        DeclareLaunchArgument(
            "app_config",
            default_value="match_planner_hardware_dry_run.yaml",
        ),
        DeclareLaunchArgument(
            "verifier_config",
            default_value="match_planner_hardware_dry_run_verifier.yaml",
        ),
    ]


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the app and verifier config file names from launch arguments.
    app_config = LaunchConfiguration("app_config")
    verifier_config = LaunchConfiguration("verifier_config")

    # ---------------- Get Parameters ----------------
    # Build paths to the app launch file and verifier YAML file.
    app_launch_file = PathJoinSubstitution([
        FindPackageShare("robot_apps"),
        "launch",
        "tb2_match_planner.launch.py",
    ])
    verifier_config_file = PathJoinSubstitution([
        FindPackageShare("test"),
        "config",
        verifier_config,
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the Phase 4 planner shell without the stub localizer.
    app_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(app_launch_file),
        launch_arguments={
            "config": app_config,
            "use_localizer_stub": "false",
        }.items(),
    )

    # Start the hardware dry-run verifier.
    verifier = Node(
        package="test",
        executable="match_planner_shell_verifier.py",
        name="match_planner_shell_verifier",
        output="screen",
        parameters=[verifier_config_file],
    )

    # ---------------- Add to Launch Description ----------------
    # Add arguments before the actions that consume them.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(app_launch)
    ld.add_action(verifier)
    ld.add_action(
        RegisterEventHandler(
            OnProcessExit(
                target_action=verifier,
                on_exit=[
                    EmitEvent(event=Shutdown(reason="hardware dry-run verifier finished")),
                ],
            )
        )
    )

    return ld

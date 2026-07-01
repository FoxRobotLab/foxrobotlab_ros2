from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Parameters ----------------
    # Reuse the shell verifier launch with deterministic guarded-turn configs.
    verifier_launch_file = PathJoinSubstitution([
        FindPackageShare("test"),
        "launch",
        "match_planner_shell_verifier.launch.py",
    ])

    # ---------------- Initialize Launches ----------------
    turn_test_verifier = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(verifier_launch_file),
        launch_arguments={
            "app_config": "match_planner_turn_test.yaml",
            "verifier_config": "match_planner_turn_test_verifier.yaml",
        }.items(),
    )

    # ---------------- Add to Launch Description ----------------
    ld.add_action(turn_test_verifier)

    return ld

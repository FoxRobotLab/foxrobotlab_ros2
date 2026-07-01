from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Parameters ----------------
    # Reuse the shell verifier launch with deterministic dry-run configs.
    verifier_launch_file = PathJoinSubstitution([
        FindPackageShare("test"),
        "launch",
        "match_planner_shell_verifier.launch.py",
    ])

    # ---------------- Initialize Launches ----------------
    dry_run_verifier = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(verifier_launch_file),
        launch_arguments={
            "app_config": "match_planner_dry_run.yaml",
            "verifier_config": "match_planner_dry_run_verifier.yaml",
        }.items(),
    )

    # ---------------- Add to Launch Description ----------------
    ld.add_action(dry_run_verifier)

    return ld

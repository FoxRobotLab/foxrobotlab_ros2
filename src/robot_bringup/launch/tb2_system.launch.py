from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


# ------------- Helper Function to find launch files -------------
def include_launch(package_name, launch_file, launch_arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare(package_name),
                "launch",
                launch_file
            ])
        ),
        launch_arguments=(launch_arguments or {}).items(),
    )


def generate_launch_description():

    ld = LaunchDescription()

    tb2_base = include_launch("robot_bringup", "tb2_base.launch.py")
    tb2_adapter = include_launch(
        "robot_adapters",
        "adapter.launch.py",
        {"robot": "tb2"},
    )
    core = include_launch("robot_core", "core.launch.py")

    ld.add_action(tb2_base)
    ld.add_action(tb2_adapter)
    ld.add_action(core)

    return ld

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
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

    namespace = LaunchConfiguration("namespace")
    astra = LaunchConfiguration("astra")
    xtion = LaunchConfiguration("xtion")
    lidar_a2 = LaunchConfiguration("lidar_a2")
    lidar_s2 = LaunchConfiguration("lidar_s2")

    args = [
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("astra", default_value="true"),
        DeclareLaunchArgument("xtion", default_value="false"),
        DeclareLaunchArgument("lidar_a2", default_value="false"),
        DeclareLaunchArgument("lidar_s2", default_value="false"),
    ]

    tb2_base = include_launch(
        "robot_bringup",
        "tb2_base.launch.py",
        {
            "namespace": namespace,
            "astra": astra,
            "xtion": xtion,
            "lidar_a2": lidar_a2,
            "lidar_s2": lidar_s2,
        },
    )
    tb2_adapter = include_launch(
        "robot_adapters",
        "adapter.launch.py",
        {"robot": "tb2"},
    )
    core = include_launch("robot_core", "core.launch.py")

    for arg in args:
        ld.add_action(arg)

    ld.add_action(tb2_base)
    ld.add_action(tb2_adapter)
    ld.add_action(core)

    return ld

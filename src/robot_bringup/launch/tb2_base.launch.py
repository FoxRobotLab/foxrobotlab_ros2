from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


# ---------------- Helper Functions ----------------
def include_launch(package_name, launch_file, launch_arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare(package_name),
                "launch",
                launch_file,
            ])
        ),
        launch_arguments=(launch_arguments or {}).items(),
    )


def declare_launch_arguments():
    return [
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("astra", default_value="true"),
        DeclareLaunchArgument("xtion", default_value="false"),
        DeclareLaunchArgument("lidar_a2", default_value="false"),
        DeclareLaunchArgument("lidar_s2", default_value="false"),
    ]


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Get Launch Configurations ----------------
    # Load the hardware options passed to foxrobotlab_ros2/kobuki.launch.py.
    namespace = LaunchConfiguration("namespace")
    astra = LaunchConfiguration("astra")
    xtion = LaunchConfiguration("xtion")
    lidar_a2 = LaunchConfiguration("lidar_a2")
    lidar_s2 = LaunchConfiguration("lidar_s2")

    # ---------------- Include Launch Files ----------------
    # Start the existing FoxRobotLab TurtleBot2 hardware wrapper.
    description = include_launch(
        "foxrobotlab_ros2",
        "kobuki.launch.py",
        {
            "namespace": namespace,
            "astra": astra,
            "xtion": xtion,
            "lidar_a2": lidar_a2,
            "lidar_s2": lidar_s2,
        },
    )

    # ---------------- Add to Launch Description ----------------
    # Add arguments first so they are available to included launch files.
    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(description)

    return ld

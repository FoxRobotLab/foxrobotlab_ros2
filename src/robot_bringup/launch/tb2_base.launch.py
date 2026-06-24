from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


# Declare launch arguments to use associated sensors
def declare_launch_arguments():
    args = [
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("astra", default_value="true"),
        DeclareLaunchArgument("xtion", default_value="false"),
        DeclareLaunchArgument("lidar_a2", default_value="false"),
        DeclareLaunchArgument("lidar_s2", default_value="false"),
    ]
    return args

def generate_launch_description():
    ld = LaunchDescription()

    # 
    namespace = LaunchConfiguration("namespace")
    astra = LaunchConfiguration("astra")
    xtion = LaunchConfiguration("xtion")
    lidar_a2 = LaunchConfiguration("lidar_a2")
    lidar_s2 = LaunchConfiguration("lidar_s2")

    description = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("foxrobotlab_ros2"),
                "launch",
                "kobuki.launch.py",
            ])
        ),
        launch_arguments={
            "namespace": namespace,
            "astra": astra,
            "xtion": xtion,
            "lidar_a2": lidar_a2,
            "lidar_s2": lidar_s2,
        }.items(),
    )

    for arg in declare_launch_arguments():
        ld.add_action(arg)

    ld.add_action(description)

    return ld

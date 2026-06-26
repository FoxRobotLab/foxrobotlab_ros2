from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
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


def generate_launch_description():
    ld = LaunchDescription()

    # ---------------- Include Launch Files ----------------
    # Start the full TurtleBot2 modular system.
    system = include_launch("robot_bringup", "tb2_system.launch.py")

    # ---------------- Get Parameters ----------------
    # Load state printer app parameters.
    config_file = PathJoinSubstitution([
        FindPackageShare("robot_apps"),
        "config",
        "state_printer.yaml",
    ])

    # ---------------- Initialize Nodes ----------------
    # Start the robot state printer app.
    app = Node(
        package="robot_apps",
        executable="print_robot_state_app.py",
        name="print_robot_state_app",
        output="screen",
        parameters=[config_file],
    )

    # ---------------- Add to Launch Description ----------------
    # Add the system launch before the app.
    ld.add_action(system)
    ld.add_action(app)

    return ld

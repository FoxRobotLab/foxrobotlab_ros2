import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    package_dir = get_package_share_directory('foxrobotlab_ros2')
    match_planner = os.path.join(
        package_dir,
        'src',
        'match_seeker',
        'scripts',
        'matchPlanner.py',
    )

    receiver_node = Node(
        package='foxrobotlab_ros2',
        executable='turtle_control_reciever.py',
        name='control_reciever',
        output='screen',
    )

    planner_process = ExecuteProcess(
        cmd=[sys.executable, match_planner],
        output='screen',
    )

    ld.add_action(receiver_node)
    ld.add_action(planner_process)
    return ld

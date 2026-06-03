from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    ld = LaunchDescription()

    receiver_node = Node(
        package='foxrobotlab_ros2',
        executable='turtle_control_reciever.py',
        name='control_reciever',
        output='screen'
    )

    processor_node = Node(
        package='foxrobotlab_ros2',
        executable='turtle_control_processor.py',
        name='control_processor',
        output='screen'
    )

    display_node = Node(
        package='foxrobotlab_ros2',
        executable='turtle_control_display.py',
        name='control_display',
        output='screen'
    )

    ld.add_action(receiver_node)
    ld.add_action(processor_node)
    ld.add_action(display_node)

    return ld

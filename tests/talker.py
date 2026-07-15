#!/usr/bin/env python3
"""Minimal ROS 2 publisher for testing discovery between machines."""

import os
import socket

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class DiscoveryTalker(Node):
    """Publish a short, identifiable message once per second."""

    def __init__(self) -> None:
        super().__init__('discovery_test_talker')
        self.publisher = self.create_publisher(String, '/discovery_test', 10)
        self.timer = self.create_timer(1.0, self.publish_message)
        self.message_number = 0
        self.host = socket.gethostname()

        self.get_logger().info(
            f'Publishing on /discovery_test from {self.host} (PID {os.getpid()})'
        )

    def publish_message(self) -> None:
        message = String()
        message.data = (
            f'Hello #{self.message_number} from {self.host} (PID {os.getpid()})'
        )
        self.publisher.publish(message)
        self.get_logger().info(f'Published: "{message.data}"')
        self.message_number += 1


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DiscoveryTalker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Minimal ROS 2 subscriber for testing discovery between machines."""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class DiscoveryListener(Node):
    """Log every message received from the discovery test talker."""

    def __init__(self) -> None:
        super().__init__('discovery_test_listener')
        self.subscription = self.create_subscription(
            String,
            '/discovery_test',
            self.message_callback,
            10,
        )
        self.get_logger().info('Listening on /discovery_test')

    def message_callback(self, message: String) -> None:
        self.get_logger().info(f'Received: "{message.data}"')


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DiscoveryListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

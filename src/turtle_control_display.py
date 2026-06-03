#!/usr/bin/env python3

# This file displays processed turtle control information in the terminal.
# Author Andre Mojica, June 2026

import rclpy
from rclpy.node import Node

from std_msgs.msg import String


QOS = 10


class TurtleControlDisplay(Node):
    def __init__(self):
        super().__init__('control_display')
        self.create_subscription(
            String,
            '/foxrobotlab/processed/status_text',
            self.status_callback,
            QOS,
        )

    def status_callback(self, msg: String):
        self.get_logger().info(msg.data)


def main(args=None):
    rclpy.init(args=args)
    display = TurtleControlDisplay()
    rclpy.spin(display)
    display.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

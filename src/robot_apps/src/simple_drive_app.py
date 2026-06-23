#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist


QOS = 10


class SimpleDriveApp(Node):
    def __init__(self):
        super().__init__("simple_drive_app")

        self.declare_parameter("cmd_vel_topic", "/robot/cmd_vel")
        self.declare_parameter("linear_x", 0.03)
        self.declare_parameter("angular_z", 0.0)
        self.declare_parameter("duration_sec", 2.0)
        self.declare_parameter("publish_rate_hz", 10.0)

        self.linear_x = float(self.get_parameter("linear_x").value)
        self.angular_z = float(self.get_parameter("angular_z").value)
        self.duration_sec = float(self.get_parameter("duration_sec").value)
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        self.started_time = self.get_clock().now()
        self.finished = False
        self.cmd_pub = self.create_publisher(
            Twist, self.get_parameter("cmd_vel_topic").value, QOS
        )

        period_sec = 1.0 / publish_rate_hz if publish_rate_hz > 0.0 else 0.1
        self.create_timer(period_sec, self._timer_callback)

        self.get_logger().info(
            f"Driving slowly for {self.duration_sec:.1f}s at linear.x={self.linear_x:.3f}."
        )

    def _timer_callback(self):
        elapsed = (
            self.get_clock().now() - self.started_time
        ).nanoseconds / 1_000_000_000.0

        if elapsed >= self.duration_sec:
            self._publish_stop()
            if not self.finished:
                self.finished = True
                self.get_logger().info("Simple drive complete; stop command published.")
            return

        msg = Twist()
        msg.linear.x = self.linear_x
        msg.angular.z = self.angular_z
        self.cmd_pub.publish(msg)

    def _publish_stop(self):
        self.cmd_pub.publish(Twist())

    def destroy_node(self):
        self._publish_stop()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SimpleDriveApp()
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

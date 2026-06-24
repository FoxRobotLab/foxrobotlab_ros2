#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from lab_interfaces.msg import RobotState, SafetyStatus
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan


QOS = 10


class RobotProcessor(Node):
    def __init__(self):
        super().__init__(
            "robot_processor",
            automatically_declare_parameters_from_overrides=True,
        )

        # core_params.yaml is the source of truth for processor parameters.
        self.robot_name = self.get_parameter("robot_name").value
        self.robot_type = self.get_parameter("robot_type").value
        self.stale_timeout_sec = float(self.get_parameter("stale_timeout_sec").value)
        self.use_scan = bool(self.get_parameter("use_scan").value)
        self.require_scan = bool(self.get_parameter("require_scan").value)

        self.last_odom = None
        self.last_scan = None
        self.last_safety = None
        self.last_odom_time = None
        self.last_scan_time = None

        self.state_pub = self.create_publisher(
            RobotState, self.get_parameter("state_topic").value, QOS
        )
        self.create_subscription(
            Odometry,
            self.get_parameter("odom_topic").value,
            self._odom_callback,
            QOS,
        )
        if self.use_scan:
            self.create_subscription(
                LaserScan,
                self.get_parameter("scan_topic").value,
                self._scan_callback,
                QOS,
            )
        self.create_subscription(
            SafetyStatus,
            self.get_parameter("safety_topic").value,
            self._safety_callback,
            QOS,
        )

        rate_hz = float(self.get_parameter("publish_rate_hz").value)
        period_sec = 1.0 / rate_hz if rate_hz > 0.0 else 0.2
        self.create_timer(period_sec, self._publish_state)

        self.get_logger().info("Robot processor started.")

    def _odom_callback(self, msg):
        self.last_odom = msg
        self.last_odom_time = self.get_clock().now()

    def _scan_callback(self, msg):
        self.last_scan = msg
        self.last_scan_time = self.get_clock().now()

    def _safety_callback(self, msg):
        self.last_safety = msg

    def _is_recent(self, stamp):
        if stamp is None:
            return False
        age = (self.get_clock().now() - stamp).nanoseconds / 1_000_000_000.0
        return age <= self.stale_timeout_sec

    def _publish_state(self):
        msg = RobotState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.robot_name = self.robot_name
        msg.robot_type = self.robot_type
        msg.odom_valid = self._is_recent(self.last_odom_time)
        msg.scan_valid = self._is_recent(self.last_scan_time)

        if self.last_odom is not None:
            msg.pose.header = self.last_odom.header
            msg.pose.pose = self.last_odom.pose
            msg.velocity = self.last_odom.twist.twist

        if self.last_safety is not None:
            msg.safety_stop_active = (
                self.last_safety.emergency_stop or self.last_safety.hazard_detected
            )

        msg.status_message = self._status_message(msg)
        self.state_pub.publish(msg)

    def _status_message(self, msg):
        if msg.safety_stop_active:
            return "Safety stop active"
        if not msg.odom_valid:
            return "Waiting for odometry"
        if self.require_scan and not msg.scan_valid:
            return "Waiting for scan"
        if not msg.scan_valid:
            return "Robot state nominal; scan unavailable"
        return "Robot state nominal"


def main(args=None):
    rclpy.init(args=args)
    node = RobotProcessor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

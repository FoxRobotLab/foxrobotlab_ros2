#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from lab_interfaces.msg import RobotState, SafetyStatus


QOS = 10


class PrintRobotStateApp(Node):
    def __init__(self):
        super().__init__("print_robot_state_app")

        self.declare_parameter("state_topic", "/robot/state")
        self.declare_parameter("safety_topic", "/robot/safety_status")
        self.declare_parameter("log_period_sec", 1.0)
        self.log_period_sec = float(self.get_parameter("log_period_sec").value)
        self.last_state_log_time = None

        self.create_subscription(
            RobotState,
            self.get_parameter("state_topic").value,
            self._state_callback,
            QOS,
        )
        self.create_subscription(
            SafetyStatus,
            self.get_parameter("safety_topic").value,
            self._safety_callback,
            QOS,
        )
        self.get_logger().info("Printing /robot/state and /robot/safety_status.")

    def _state_callback(self, msg):
        now = self.get_clock().now()
        if self.last_state_log_time is not None:
            elapsed = (now - self.last_state_log_time).nanoseconds / 1_000_000_000.0
            if elapsed < self.log_period_sec:
                return
        self.last_state_log_time = now

        position = msg.pose.pose.pose.position
        velocity = msg.velocity
        self.get_logger().info(
            "state robot=%s odom=%s scan=%s stop=%s "
            "pose=(%.3f, %.3f) vel=(%.3f, %.3f) status=%s"
            % (
                msg.robot_name,
                msg.odom_valid,
                msg.scan_valid,
                msg.safety_stop_active,
                position.x,
                position.y,
                velocity.linear.x,
                velocity.angular.z,
                msg.status_message,
            )
        )

    def _safety_callback(self, msg):
        if msg.hazard_detected or msg.emergency_stop:
            self.get_logger().warn(
                "safety source=%s bumper=%s cliff=%s wheel_drop=%s emergency=%s status=%s"
                % (
                    msg.source_robot,
                    msg.bumper_pressed,
                    msg.cliff_detected,
                    msg.wheel_drop_detected,
                    msg.emergency_stop,
                    msg.status_message,
                )
            )


def main(args=None):
    rclpy.init(args=args)
    node = PrintRobotStateApp()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from lab_interfaces.msg import SafetyStatus


QOS = 10


class SafetyMonitor(Node):
    def __init__(self):
        super().__init__(
            "safety_monitor",
            automatically_declare_parameters_from_overrides=True,
        )

        # safety_params.yaml is the source of truth for monitor parameters.
        self.last_warning_signature = None
        self.create_subscription(
            SafetyStatus,
            self.get_parameter("safety_topic").value,
            self._safety_callback,
            QOS,
        )

        self.get_logger().info("Safety monitor started.")

    def _safety_callback(self, msg):
        active_conditions = []

        if msg.emergency_stop:
            active_conditions.append("emergency_stop")
        if msg.bumper_pressed:
            active_conditions.append("bumper_pressed")
        if msg.cliff_detected:
            active_conditions.append("cliff_detected")
        if msg.wheel_drop_detected:
            active_conditions.append("wheel_drop_detected")
        if msg.hazard_detected:
            active_conditions.append("hazard_detected")

        if not active_conditions:
            self.last_warning_signature = None
            return

        signature = tuple(active_conditions)
        if signature == self.last_warning_signature:
            return

        self.last_warning_signature = signature
        self.get_logger().warn(
            f"Robot safety condition active: {', '.join(active_conditions)}"
        )
        # Future work: gate /robot/cmd_vel here or in a dedicated command mux.


def main(args=None):
    rclpy.init(args=args)
    node = SafetyMonitor()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

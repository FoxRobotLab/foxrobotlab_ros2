#!/usr/bin/env python3

import sys

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Image, Imu

from kobuki_ros_interfaces.msg import BumperEvent, CliffEvent, SensorState, WheelDropEvent
from lab_interfaces.msg import RobotState, SafetyStatus


QOS = 10


class Phase2TopicVerifier(Node):
    def __init__(self):
        super().__init__(
            "phase2_topic_verifier",
            automatically_declare_parameters_from_overrides=True,
        )

        self.timeout_sec = float(self.get_parameter("timeout_sec").value)
        self.exit_on_finish = bool(self.get_parameter("exit_on_finish").value)
        report_period_sec = float(self.get_parameter("report_period_sec").value)
        cmd_vel_probe_period_sec = float(
            self.get_parameter("cmd_vel_probe_period_sec").value
        )

        self.required = {}
        self.optional = {}
        self.finished = False
        self.failed = False
        self.start_time = self.get_clock().now()

        self._add_common_topic("robot_odom", Odometry, "common_topics.odom")
        self._add_common_topic("robot_imu", Imu, "common_topics.imu")
        self._add_common_topic("robot_battery", BatteryState, "common_topics.battery")
        self._add_common_topic("robot_core", SensorState, "common_topics.core")
        self._add_common_topic("robot_safety_status", SafetyStatus, "common_topics.safety_status")

        if bool(self.get_parameter("require_robot_state").value):
            self._add_common_topic("robot_state", RobotState, "common_topics.state")

        if bool(self.get_parameter("require_camera").value):
            self._add_common_topic("robot_color_image", Image, "common_topics.color_image")
            self._add_common_topic("robot_depth_image", Image, "common_topics.depth_image")

        if bool(self.get_parameter("require_compatibility_topics").value):
            self._add_common_topic("compat_odom", Odometry, "compatibility_topics.odom")
            self._add_common_topic("compat_imu", Imu, "compatibility_topics.imu")
            self._add_common_topic(
                "compat_battery",
                BatteryState,
                "compatibility_topics.battery",
            )
            self._add_common_topic("compat_core", SensorState, "compatibility_topics.core")

            if bool(self.get_parameter("require_camera").value):
                self._add_common_topic(
                    "compat_color_image",
                    Image,
                    "compatibility_topics.color_image",
                )
                self._add_common_topic(
                    "compat_depth_image",
                    Image,
                    "compatibility_topics.depth_image",
                )

            if bool(self.get_parameter("require_event_compatibility_topics").value):
                self._add_common_topic(
                    "compat_bumper",
                    BumperEvent,
                    "compatibility_topics.bumper",
                )
                self._add_common_topic(
                    "compat_cliff",
                    CliffEvent,
                    "compatibility_topics.cliff",
                )
                self._add_common_topic(
                    "compat_wheel_drop",
                    WheelDropEvent,
                    "compatibility_topics.wheel_drop",
                )
            else:
                self._add_optional_topic(
                    "compat_bumper",
                    BumperEvent,
                    "compatibility_topics.bumper",
                )
                self._add_optional_topic(
                    "compat_cliff",
                    CliffEvent,
                    "compatibility_topics.cliff",
                )
                self._add_optional_topic(
                    "compat_wheel_drop",
                    WheelDropEvent,
                    "compatibility_topics.wheel_drop",
                )

        if bool(self.get_parameter("publish_cmd_vel_probe").value):
            internal_cmd_vel = self.get_parameter("command_topics.internal_cmd_vel").value
            native_cmd_vel = self.get_parameter("command_topics.native_cmd_vel").value
            self.cmd_vel_pub = self.create_publisher(Twist, internal_cmd_vel, QOS)
            self._add_common_topic("cmd_vel_forwarded", Twist, "command_topics.native_cmd_vel")
            self.create_timer(cmd_vel_probe_period_sec, self._publish_zero_cmd_vel_probe)
            self.get_logger().info(
                f"Command probe enabled: publishing zero Twist on {internal_cmd_vel}, "
                f"waiting on {native_cmd_vel}"
            )

        self.create_timer(report_period_sec, self._report_progress)
        self.create_timer(0.25, self._check_finished)

        self.get_logger().info(
            "Phase 2 verifier started. This test uses received messages, not ros2 topic list."
        )

    def _add_common_topic(self, name, msg_type, parameter_name):
        topic = self.get_parameter(parameter_name).value
        self.required[name] = {"topic": topic, "count": 0}
        self.create_subscription(
            msg_type,
            topic,
            lambda msg, topic_name=name: self._mark_received(topic_name),
            QOS,
        )

    def _add_optional_topic(self, name, msg_type, parameter_name):
        topic = self.get_parameter(parameter_name).value
        self.optional[name] = {"topic": topic, "count": 0}
        self.create_subscription(
            msg_type,
            topic,
            lambda msg, topic_name=name: self._mark_received(topic_name, required=False),
            QOS,
        )

    def _mark_received(self, name, required=True):
        group = self.required if required else self.optional
        group[name]["count"] += 1
        if group[name]["count"] == 1:
            self.get_logger().info(f"PASS receive {name}: {group[name]['topic']}")

    def _publish_zero_cmd_vel_probe(self):
        self.cmd_vel_pub.publish(Twist())

    def _missing_required(self):
        return [
            f"{name} ({data['topic']})"
            for name, data in self.required.items()
            if data["count"] == 0
        ]

    def _report_progress(self):
        if self.finished:
            return
        received = sum(1 for data in self.required.values() if data["count"] > 0)
        total = len(self.required)
        missing = self._missing_required()
        if missing:
            self.get_logger().info(
                f"Phase 2 verifier progress: {received}/{total} required streams received. "
                f"Waiting for: {', '.join(missing)}"
            )
        else:
            self.get_logger().info(
                f"Phase 2 verifier progress: {received}/{total} required streams received."
            )

    def _check_finished(self):
        if self.finished:
            return

        missing = self._missing_required()
        if not missing:
            self.finished = True
            self.get_logger().info("PHASE 2 VERIFICATION PASSED: all required streams received.")
            self._print_summary()
            return

        elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1_000_000_000.0
        if elapsed >= self.timeout_sec:
            self.finished = True
            self.failed = True
            self.get_logger().error(
                "PHASE 2 VERIFICATION FAILED: timed out waiting for required streams."
            )
            for item in missing:
                self.get_logger().error(f"Missing: {item}")
            self._print_summary()

    def _print_summary(self):
        for name, data in self.required.items():
            status = "PASS" if data["count"] > 0 else "FAIL"
            self.get_logger().info(
                f"{status} required {name}: {data['topic']} count={data['count']}"
            )
        for name, data in self.optional.items():
            status = "SEEN" if data["count"] > 0 else "not seen"
            self.get_logger().info(
                f"{status} optional {name}: {data['topic']} count={data['count']}"
            )


def main(args=None):
    rclpy.init(args=args)
    node = Phase2TopicVerifier()

    while rclpy.ok() and not (node.exit_on_finish and node.finished):
        rclpy.spin_once(node, timeout_sec=0.1)

    failed = node.failed
    node.destroy_node()
    rclpy.shutdown()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

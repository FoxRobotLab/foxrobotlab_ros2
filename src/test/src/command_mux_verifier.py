#!/usr/bin/env python3

import sys

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from lab_interfaces.msg import CommandMuxStatus, SafetyStatus


QOS = 10


class CommandMuxVerifier(Node):
    def __init__(self):
        super().__init__(
            "command_mux_verifier",
            automatically_declare_parameters_from_overrides=True,
        )

        self.timeout_sec = float(self.get_parameter("timeout_sec").value)
        self.command_timeout_sec = float(
            self.get_parameter("command_timeout_sec").value
        )

        self.start_time = self.get_clock().now()
        self.phase = "send_safe"
        self.phase_start_time = self.start_time
        self.finished = False
        self.failed = False

        self.saw_forwarded_command = False
        self.saw_stale_stop = False
        self.saw_safety_stop = False

        self.last_output = None
        self.last_status = None

        app_topic = self.get_parameter("app_cmd_vel_topic").value
        output_topic = self.get_parameter("output_cmd_vel_topic").value
        safety_topic = self.get_parameter("safety_topic").value
        status_topic = self.get_parameter("status_topic").value

        self.app_pub = self.create_publisher(Twist, app_topic, QOS)
        self.safety_pub = self.create_publisher(SafetyStatus, safety_topic, QOS)
        self.create_subscription(Twist, output_topic, self._output_callback, QOS)
        self.create_subscription(
            CommandMuxStatus,
            status_topic,
            self._status_callback,
            QOS,
        )

        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)
        period_sec = 1.0 / publish_rate_hz if publish_rate_hz > 0.0 else 0.1
        self.create_timer(period_sec, self._timer_callback)

        self.get_logger().info(
            "Command mux verifier started. This test uses messages, not ros2 topic list."
        )

    # ---------------- Callback Functions ----------------
    def _output_callback(self, msg):
        self.last_output = msg

    def _status_callback(self, msg):
        self.last_status = msg

    def _timer_callback(self):
        if self.finished:
            return

        self._publish_safety()

        elapsed = (
            self.get_clock().now() - self.start_time
        ).nanoseconds / 1_000_000_000.0
        if elapsed >= self.timeout_sec:
            self._fail("timed out before all command mux checks passed")
            return

        if self.phase == "send_safe":
            self._publish_app_command(0.12)
            if self._saw_allowed_output():
                self.saw_forwarded_command = True
                self._start_phase("wait_stale")
            return

        if self.phase == "wait_stale":
            if self._phase_elapsed() <= self.command_timeout_sec + 0.3:
                return
            if self._saw_stale_stop_output():
                self.saw_stale_stop = True
                self._start_phase("send_blocked")
            return

        if self.phase == "send_blocked":
            self._publish_app_command(0.12)
            if self._saw_safety_stop_output():
                self.saw_safety_stop = True
                self._pass()

    # ---------------- Helper Functions ----------------
    def _publish_safety(self):
        msg = SafetyStatus()
        if self.phase == "send_blocked":
            msg.bumper_pressed = True
            msg.status_message = "fake bumper pressed"
        else:
            msg.status_message = "fake safety clear"
        self.safety_pub.publish(msg)

    def _publish_app_command(self, linear_x):
        msg = Twist()
        msg.linear.x = linear_x
        self.app_pub.publish(msg)

    def _saw_allowed_output(self):
        if self.last_output is None or self.last_status is None:
            return False
        return (
            self.last_output.linear.x > 0.05
            and self.last_status.command_allowed
            and not self.last_status.command_blocked
        )

    def _saw_stale_stop_output(self):
        if self.last_output is None or self.last_status is None:
            return False
        return (
            abs(self.last_output.linear.x) < 0.001
            and self.last_status.command_blocked
            and self.last_status.input_stale
        )

    def _saw_safety_stop_output(self):
        if self.last_output is None or self.last_status is None:
            return False
        return (
            abs(self.last_output.linear.x) < 0.001
            and self.last_status.command_blocked
            and self.last_status.safety_stop_active
        )

    def _start_phase(self, phase):
        self.phase = phase
        self.phase_start_time = self.get_clock().now()
        self.get_logger().info(f"Command mux verifier phase: {phase}")

    def _phase_elapsed(self):
        elapsed = self.get_clock().now() - self.phase_start_time
        return elapsed.nanoseconds / 1_000_000_000.0

    def _pass(self):
        self.finished = True
        self.get_logger().info("PASS safe command forwarded")
        self.get_logger().info("PASS stale app command stopped")
        self.get_logger().info("PASS safety status blocked command")
        self.get_logger().info("COMMAND MUX VERIFICATION PASSED")

    def _fail(self, message):
        self.finished = True
        self.failed = True
        self.get_logger().error(f"COMMAND MUX VERIFICATION FAILED: {message}")
        self.get_logger().error(
            "Checks: "
            f"forwarded={self.saw_forwarded_command}, "
            f"stale_stop={self.saw_stale_stop}, "
            f"safety_stop={self.saw_safety_stop}"
        )


def main(args=None):
    rclpy.init(args=args)
    node = CommandMuxVerifier()

    while rclpy.ok() and not node.finished:
        rclpy.spin_once(node, timeout_sec=0.1)

    failed = node.failed
    node.destroy_node()
    rclpy.shutdown()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

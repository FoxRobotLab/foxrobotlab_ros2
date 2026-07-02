#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from lab_interfaces.msg import CommandMuxStatus, SafetyStatus


QOS = 10


class CommandMux(Node):
    def __init__(self):
        super().__init__(
            "command_mux",
            automatically_declare_parameters_from_overrides=True,
        )

        # command_mux.yaml is the source of truth for command-gating parameters.
        self.app_cmd_vel_topic = self.get_parameter("app_cmd_vel_topic").value
        self.output_cmd_vel_topic = self.get_parameter("output_cmd_vel_topic").value
        self.safety_topic = self.get_parameter("safety_topic").value
        self.status_topic = self.get_parameter("status_topic").value

        self.command_timeout_sec = float(
            self.get_parameter("command_timeout_sec").value
        )
        publish_rate_hz = float(self.get_parameter("publish_rate_hz").value)

        self.stop_on_emergency_stop = bool(
            self.get_parameter("stop_on_emergency_stop").value
        )
        self.stop_on_bumper = bool(self.get_parameter("stop_on_bumper").value)
        self.stop_on_cliff = bool(self.get_parameter("stop_on_cliff").value)
        self.stop_on_wheel_drop = bool(
            self.get_parameter("stop_on_wheel_drop").value
        )
        self.stop_on_hazard = bool(self.get_parameter("stop_on_hazard").value)

        self.last_command = None
        self.last_command_time = None
        self.last_safety = None

        # ---------------- Initialize Publishers and Subscribers ----------------
        self.cmd_pub = self.create_publisher(Twist, self.output_cmd_vel_topic, QOS)
        self.status_pub = self.create_publisher(
            CommandMuxStatus,
            self.status_topic,
            QOS,
        )

        self.create_subscription(
            Twist,
            self.app_cmd_vel_topic,
            self._command_callback,
            QOS,
        )
        self.create_subscription(
            SafetyStatus,
            self.safety_topic,
            self._safety_callback,
            QOS,
        )

        period_sec = 1.0 / publish_rate_hz if publish_rate_hz > 0.0 else 0.1
        self.create_timer(period_sec, self._timer_callback)

        self.get_logger().info(
            f"Command mux started: {self.app_cmd_vel_topic} -> "
            f"{self.output_cmd_vel_topic}"
        )

    # ---------------- Callback Functions ----------------
    def _command_callback(self, msg):
        self.last_command = msg
        self.last_command_time = self.get_clock().now()

    def _safety_callback(self, msg):
        self.last_safety = msg

    def _timer_callback(self):
        command_age = self._last_command_age()
        input_stale = self._input_stale(command_age)
        safety_stop_active = self._safety_stop_active()

        if self.last_command is None:
            output = Twist()
            allowed = False
            blocked = False
            status = "waiting for app command"
        elif input_stale:
            output = Twist()
            allowed = False
            blocked = True
            status = "app command stale; publishing stop"
        elif safety_stop_active:
            output = Twist()
            allowed = False
            blocked = True
            status = "safety stop active; publishing stop"
        else:
            output = self.last_command
            allowed = True
            blocked = False
            status = "forwarding app command"

        self.cmd_pub.publish(output)
        self._publish_status(
            allowed,
            blocked,
            safety_stop_active,
            input_stale,
            command_age,
            status,
        )

    # ---------------- Helper Functions ----------------
    def _last_command_age(self):
        if self.last_command_time is None:
            return -1.0
        age = self.get_clock().now() - self.last_command_time
        return age.nanoseconds / 1_000_000_000.0

    def _input_stale(self, command_age):
        if self.last_command is None:
            return True
        if self.command_timeout_sec <= 0.0:
            return False
        return command_age > self.command_timeout_sec

    def _safety_stop_active(self):
        if self.last_safety is None:
            return False

        if self.stop_on_emergency_stop and self.last_safety.emergency_stop:
            return True
        if self.stop_on_bumper and self.last_safety.bumper_pressed:
            return True
        if self.stop_on_cliff and self.last_safety.cliff_detected:
            return True
        if self.stop_on_wheel_drop and self.last_safety.wheel_drop_detected:
            return True
        if self.stop_on_hazard and self.last_safety.hazard_detected:
            return True
        return False

    def _publish_status(
        self,
        allowed,
        blocked,
        safety_stop_active,
        input_stale,
        command_age,
        status,
    ):
        msg = CommandMuxStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.active_source = "robot_apps" if self.last_command is not None else ""
        msg.command_allowed = allowed
        msg.command_blocked = blocked
        msg.safety_stop_active = safety_stop_active
        msg.input_stale = input_stale
        msg.last_command_age_sec = float(command_age)
        msg.status_message = status
        self.status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CommandMux()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

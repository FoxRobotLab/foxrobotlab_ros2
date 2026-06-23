#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, LaserScan

from lab_interfaces.msg import SafetyStatus

try:
    from kobuki_ros_interfaces.msg import BumperEvent, CliffEvent, WheelDropEvent
except ImportError:
    BumperEvent = None
    CliffEvent = None
    WheelDropEvent = None


QOS = 10


class TurtleBot2Adapter(Node):
    def __init__(self):
        super().__init__("tb2_adapter")

        self._declare_parameters()
        self.robot_name = self.get_parameter("robot_name").value
        self.robot_type = self.get_parameter("robot_type").value

        self.bumper_pressed = False
        self.cliff_detected = False
        self.wheel_drop_detected = False

        output_odom = self.get_parameter("output_topics.odom").value
        output_scan = self.get_parameter("output_topics.scan").value
        output_imu = self.get_parameter("output_topics.imu").value
        output_safety = self.get_parameter("output_topics.safety_status").value
        internal_cmd_vel = self.get_parameter("command_topics.internal_cmd_vel").value
        native_cmd_vel = self.get_parameter("command_topics.native_cmd_vel").value

        self.odom_pub = self.create_publisher(Odometry, output_odom, QOS)
        self.scan_pub = self.create_publisher(LaserScan, output_scan, QOS)
        self.imu_pub = self.create_publisher(Imu, output_imu, QOS)
        self.safety_pub = self.create_publisher(SafetyStatus, output_safety, QOS)
        self.native_cmd_pub = self.create_publisher(Twist, native_cmd_vel, QOS)

        self.create_subscription(
            Odometry,
            self.get_parameter("input_topics.odom").value,
            self._odom_callback,
            QOS,
        )
        self._subscribe_scan_if_enabled()
        self._subscribe_imu_if_enabled()
        self._subscribe_kobuki_events_if_available()
        self.create_subscription(Twist, internal_cmd_vel, self._cmd_vel_callback, QOS)
        self.create_timer(1.0, self._publish_safety_heartbeat)

        self.get_logger().info(
            f"TurtleBot2 adapter started: {internal_cmd_vel} -> {native_cmd_vel}"
        )

    def _declare_parameters(self):
        self.declare_parameter("robot_name", "turtlebot2")
        self.declare_parameter("robot_type", "hardware")

        self.declare_parameter("input_topics.odom", "/odom")
        self.declare_parameter("input_topics.scan", "/scan")
        self.declare_parameter("input_topics.imu", "/sensors/imu_data")
        self.declare_parameter("input_topics.bumper", "/events/bumper")
        self.declare_parameter("input_topics.cliff", "/events/cliff")
        self.declare_parameter("input_topics.wheel_drop", "/events/wheel_drop")

        self.declare_parameter("output_topics.odom", "/robot/odom")
        self.declare_parameter("output_topics.scan", "/robot/scan")
        self.declare_parameter("output_topics.imu", "/robot/imu")
        self.declare_parameter("output_topics.safety_status", "/robot/safety_status")

        self.declare_parameter("command_topics.internal_cmd_vel", "/robot/cmd_vel")
        self.declare_parameter("command_topics.native_cmd_vel", "/commands/velocity")

        self.declare_parameter("capabilities.has_lidar", True)
        self.declare_parameter("capabilities.has_imu", True)
        self.declare_parameter("capabilities.has_cliff_detection", True)
        self.declare_parameter("capabilities.has_wheel_drop_detection", True)

    def _subscribe_scan_if_enabled(self):
        if not self.get_parameter("capabilities.has_lidar").value:
            self.get_logger().info("LaserScan adapter disabled by configuration.")
            return
        self.create_subscription(
            LaserScan,
            self.get_parameter("input_topics.scan").value,
            self._scan_callback,
            QOS,
        )

    def _subscribe_imu_if_enabled(self):
        if not self.get_parameter("capabilities.has_imu").value:
            self.get_logger().info("IMU adapter disabled by configuration.")
            return
        self.create_subscription(
            Imu,
            self.get_parameter("input_topics.imu").value,
            self._imu_callback,
            QOS,
        )

    def _subscribe_kobuki_events_if_available(self):
        if BumperEvent is None:
            self.get_logger().warn(
                "kobuki_ros_interfaces is not importable; safety event subscriptions skipped."
            )
            self._publish_safety_status("Kobuki event message types unavailable")
            return

        self.create_subscription(
            BumperEvent,
            self.get_parameter("input_topics.bumper").value,
            self._bumper_callback,
            QOS,
        )

        if self.get_parameter("capabilities.has_cliff_detection").value:
            self.create_subscription(
                CliffEvent,
                self.get_parameter("input_topics.cliff").value,
                self._cliff_callback,
                QOS,
            )

        if self.get_parameter("capabilities.has_wheel_drop_detection").value:
            self.create_subscription(
                WheelDropEvent,
                self.get_parameter("input_topics.wheel_drop").value,
                self._wheel_drop_callback,
                QOS,
            )

        self._publish_safety_status("Waiting for Kobuki safety events")

    def _odom_callback(self, msg):
        self.odom_pub.publish(msg)

    def _scan_callback(self, msg):
        self.scan_pub.publish(msg)

    def _imu_callback(self, msg):
        self.imu_pub.publish(msg)

    def _cmd_vel_callback(self, msg):
        self.native_cmd_pub.publish(msg)

    def _bumper_callback(self, msg):
        self.bumper_pressed = msg.state == BumperEvent.PRESSED
        self._publish_safety_status("Bumper pressed" if self.bumper_pressed else "Bumper released")

    def _cliff_callback(self, msg):
        self.cliff_detected = msg.state == CliffEvent.CLIFF
        self._publish_safety_status("Cliff detected" if self.cliff_detected else "Floor detected")

    def _wheel_drop_callback(self, msg):
        self.wheel_drop_detected = msg.state == WheelDropEvent.DROPPED
        self._publish_safety_status(
            "Wheel drop detected" if self.wheel_drop_detected else "Wheel raised"
        )

    def _publish_safety_status(self, status_message):
        msg = SafetyStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.source_robot = self.robot_name
        msg.bumper_pressed = self.bumper_pressed
        msg.cliff_detected = self.cliff_detected
        msg.wheel_drop_detected = self.wheel_drop_detected
        msg.hazard_detected = (
            msg.bumper_pressed or msg.cliff_detected or msg.wheel_drop_detected
        )
        msg.status_message = status_message
        self.safety_pub.publish(msg)

    def _publish_safety_heartbeat(self):
        if self.bumper_pressed or self.cliff_detected or self.wheel_drop_detected:
            status_message = "Safety hazard active"
        else:
            status_message = "Safety nominal"
        self._publish_safety_status(status_message)


def main(args=None):
    rclpy.init(args=args)
    node = TurtleBot2Adapter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

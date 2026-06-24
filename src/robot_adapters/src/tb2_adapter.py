#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import (
    BatteryState, 
    Image, 
    Imu, 
    LaserScan
    )

from lab_interfaces.msg import SafetyStatus

# From Third Party Package. Credit to Intelligent Robotics Lab from Universidad Rey Juan Carlos
from kobuki_ros_interfaces.msg import (
    BumperEvent,
    CliffEvent,
    SensorState,
    WheelDropEvent,
    )

QOS = 10


class TurtleBot2Adapter(Node):
    # NOTE: automatically_declare_parameters_from_overrides is a feature of rclpy that 
    # automatically declares parameters from the launch file. This the yaml file is strictly where parameters are defined and configured.
    def __init__(self):
        super().__init__(
            "tb2_adapter",
            automatically_declare_parameters_from_overrides=True,
        )
        
        # ---------------- Initialize Parameters ----------------
        self.robot_name = self.get_parameter("robot_name").value
        self.robot_type = self.get_parameter("robot_type").value
        output_odom = self.get_parameter("output_topics.odom").value
        output_imu = self.get_parameter("output_topics.imu").value
        output_safety = self.get_parameter("output_topics.safety_status").value
        internal_cmd_vel = self.get_parameter("command_topics.internal_cmd_vel").value
        native_cmd_vel = self.get_parameter("command_topics.native_cmd_vel").value
        self.compatibility_enabled = self.get_parameter("compatibility_topics.enabled").value

        # ---------------- Specific Robot Parameters ----------------
        self.bumper_pressed = False
        self.cliff_detected = False
        self.wheel_drop_detected = False

        # ---------------- Initialize Publishers and Subscribers ----------------
        self.odom_pub = self.create_publisher(Odometry, output_odom, QOS)
        self.imu_pub = self.create_publisher(Imu, output_imu, QOS)
        self.safety_pub = self.create_publisher(SafetyStatus, output_safety, QOS)
        self.native_cmd_pub = self.create_publisher(Twist, native_cmd_vel, QOS)

        self.odom_compat_pub = self._create_compat_publisher(
            Odometry, "compatibility_topics.odom"
        )
        self.imu_compat_pub = self._create_compat_publisher(
            Imu, "compatibility_topics.imu"
        )

        self.create_subscription(
            Odometry,
            self.get_parameter("input_topics.odom").value,
            self._odom_callback,
            QOS,
        )
        
        self._subscribe_imu_if_enabled()
        self._subscribe_scan_if_enabled()
        self._subscribe_battery_if_enabled()
        self._subscribe_camera_if_enabled()
        self._subscribe_core_if_enabled()
        self._subscribe_kobuki_events_if_available()
        
        self.create_subscription(Twist, internal_cmd_vel, self._cmd_vel_callback, QOS)
        self.create_timer(1.0, self._publish_safety_heartbeat)

        self.get_logger().info(
            f"TurtleBot2 adapter started: {internal_cmd_vel} -> {native_cmd_vel}"
        )

    def _create_compat_publisher(self, msg_type, parameter_name):
        if not self.compatibility_enabled:
            return None
        return self.create_publisher(
            msg_type,
            self.get_parameter(parameter_name).value,
            QOS,
        )

    def _publish_common_and_compat(self, msg, common_pub, compat_pub=None):
        common_pub.publish(msg)
        if compat_pub is not None:
            compat_pub.publish(msg)

    # ----------------- Subscription to Specific Robot Capabilities ----------------
    def _subscribe_scan_if_enabled(self):
        if not self.get_parameter("capabilities.has_lidar").value:
            self.get_logger().info("LaserScan adapter disabled by configuration.")
            return
        self.scan_pub = self.create_publisher(
            LaserScan,
            self.get_parameter("output_topics.scan").value,
            QOS,
        )
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

    def _subscribe_battery_if_enabled(self):
        if not self.get_parameter("capabilities.has_battery").value:
            self.get_logger().info("Battery adapter disabled by configuration.")
            return
        self.battery_pub = self.create_publisher(
            BatteryState,
            self.get_parameter("output_topics.battery").value,
            QOS,
        )
        self.battery_compat_pub = self._create_compat_publisher(
            BatteryState,
            "compatibility_topics.battery",
        )
        self.create_subscription(
            BatteryState,
            self.get_parameter("input_topics.battery").value,
            self._battery_callback,
            QOS,
        )

    def _subscribe_camera_if_enabled(self):
        if not self.get_parameter("capabilities.has_camera").value:
            self.get_logger().info("Color camera adapter disabled by configuration.")
            return
        self.color_image_pub = self.create_publisher(
            Image,
            self.get_parameter("output_topics.image_color").value,
            QOS,
        )
        self.color_image_compat_pub = self._create_compat_publisher(
            Image,
            "compatibility_topics.color_image",
        )
        self.create_subscription(
            Image,
            self.get_parameter("input_topics.image_color").value,
            self._color_image_callback,
            QOS,
        )

        if not self.get_parameter("capabilities.has_depth_camera").value:
            self.get_logger().info("Depth camera adapter disabled by configuration.")
            return
        self.depth_image_pub = self.create_publisher(
            Image,
            self.get_parameter("output_topics.image_depth").value,
            QOS,
        )
        self.depth_image_compat_pub = self._create_compat_publisher(
            Image,
            "compatibility_topics.depth_image",
        )
        self.create_subscription(
            Image,
            self.get_parameter("input_topics.image_depth").value,
            self._depth_image_callback,
            QOS,
        )

    def _subscribe_core_if_enabled(self):
        if not self.get_parameter("capabilities.has_core_sensors").value:
            self.get_logger().info("Kobuki core sensor adapter disabled by configuration.")
            return
        if SensorState is None:
            self.get_logger().warn(
                "kobuki_ros_interfaces is not importable; core sensor adapter skipped."
            )
            return
        self.core_pub = self.create_publisher(
            SensorState,
            self.get_parameter("output_topics.core").value,
            QOS,
        )
        self.core_compat_pub = self._create_compat_publisher(
            SensorState,
            "compatibility_topics.core",
        )
        self.create_subscription(
            SensorState,
            self.get_parameter("input_topics.core").value,
            self._core_callback,
            QOS,
        )

    def _subscribe_kobuki_events_if_available(self):
        if BumperEvent is None:
            self.get_logger().warn(
                "kobuki_ros_interfaces is not importable; safety event subscriptions skipped."
            )
            self._publish_safety_status("Kobuki event message types unavailable")
            return

        if self.get_parameter("capabilities.has_bumper_detection").value:
            self.create_subscription(
                BumperEvent,
                self.get_parameter("input_topics.bumper").value,
                self._bumper_callback,
                QOS,
            )
            self.bumper_compat_pub = self._create_compat_publisher(
                BumperEvent,
                "compatibility_topics.bumper",
            )
        else:
            self.bumper_compat_pub = None

        if self.get_parameter("capabilities.has_cliff_detection").value:
            self.create_subscription(
                CliffEvent,
                self.get_parameter("input_topics.cliff").value,
                self._cliff_callback,
                QOS,
            )
            self.cliff_compat_pub = self._create_compat_publisher(
                CliffEvent,
                "compatibility_topics.cliff",
            )
        else:
            self.cliff_compat_pub = None

        if self.get_parameter("capabilities.has_wheel_drop_detection").value:
            self.create_subscription(
                WheelDropEvent,
                self.get_parameter("input_topics.wheel_drop").value,
                self._wheel_drop_callback,
                QOS,
            )
            self.wheel_drop_compat_pub = self._create_compat_publisher(
                WheelDropEvent,
                "compatibility_topics.wheel_drop",
            )
        else:
            self.wheel_drop_compat_pub = None

        self._publish_safety_status("Waiting for Kobuki safety events")

    # ----------------- Callback functions for Subscribers ----------------
    def _odom_callback(self, msg):
        self._publish_common_and_compat(msg, self.odom_pub, self.odom_compat_pub)

    def _scan_callback(self, msg):
        self.scan_pub.publish(msg)

    def _imu_callback(self, msg):
        self._publish_common_and_compat(msg, self.imu_pub, self.imu_compat_pub)

    def _battery_callback(self, msg):
        self._publish_common_and_compat(
            msg,
            self.battery_pub,
            self.battery_compat_pub,
        )

    def _color_image_callback(self, msg):
        self._publish_common_and_compat(
            msg,
            self.color_image_pub,
            self.color_image_compat_pub,
        )

    def _depth_image_callback(self, msg):
        self._publish_common_and_compat(
            msg,
            self.depth_image_pub,
            self.depth_image_compat_pub,
        )

    def _core_callback(self, msg):
        self._publish_common_and_compat(msg, self.core_pub, self.core_compat_pub)

    def _cmd_vel_callback(self, msg):
        self.native_cmd_pub.publish(msg)

    def _bumper_callback(self, msg):
        if self.bumper_compat_pub is not None:
            self.bumper_compat_pub.publish(msg)
        self.bumper_pressed = msg.state == BumperEvent.PRESSED
        self._publish_safety_status("Bumper pressed" if self.bumper_pressed else "Bumper released")

    def _cliff_callback(self, msg):
        if self.cliff_compat_pub is not None:
            self.cliff_compat_pub.publish(msg)
        self.cliff_detected = msg.state == CliffEvent.CLIFF
        self._publish_safety_status("Cliff detected" if self.cliff_detected else "Floor detected")

    def _wheel_drop_callback(self, msg):
        if self.wheel_drop_compat_pub is not None:
            self.wheel_drop_compat_pub.publish(msg)
        self.wheel_drop_detected = msg.state == WheelDropEvent.DROPPED
        self._publish_safety_status(
            "Wheel drop detected" if self.wheel_drop_detected else "Wheel raised"
        )
    
    # ----------------- Status Printers -----------------
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

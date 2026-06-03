#!/usr/bin/env python3

# This file adapts hardware-driver topics into project-owned raw topics.
# Author: Andre Mojica, May 2026

# Import the node system from ROS
import rclpy
from rclpy.node import Node

# Import necessary message to create ROS topics
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, Imu, BatteryState

# Import message types from the downloaded ROS2 Kobuki library
from kobuki_ros_interfaces.msg import SensorState, BumperEvent, WheelDropEvent, CliffEvent

QOS = 10

class ControlReceiver(Node):
    def __init__(self):
        super().__init__('control_receiver')
        # ===================== Image Data =====================
        # Depth Sensor Subscription
        self.depth_subscription = self.create_subscription(
            Image, '/depth/image_raw', self.depth_callback, QOS
        )
        self.depth_publisher = self.create_publisher(
            Image, '/foxrobotlab/raw/depth/image_raw', QOS
        )

        # Image Sensor Subscription
        self.image_subscription = self.create_subscription(
            Image, '/color/image_raw', self.image_callback, QOS
        )
        self.image_publisher = self.create_publisher(
            Image, '/foxrobotlab/raw/color/image_raw', QOS
        )

        # ================== Odometry and IMU Data ===================
        # Odometry Subscription
        self.odom_subscription = self.create_subscription(
            Odometry, '/odom', self.odom_callback, QOS
        )
        self.odom_publisher = self.create_publisher(
            Odometry, '/foxrobotlab/raw/odom', QOS
        )

        # IMU Sensor Subscription
        self.imu_subscription = self.create_subscription(
            Imu, '/sensors/imu_data', self.imu_callback, QOS
        )
        self.imu_publisher = self.create_publisher(
            Imu, '/foxrobotlab/raw/sensors/imu_data', QOS
        )

        # ================ Kobuki Sensor Data ======================
        # Core Sensors
        self.kobuki_core_subscription = self.create_subscription(
            SensorState, '/sensors/core', self.core_callback, QOS
        )
        self.kobuki_core_publisher = self.create_publisher(
            SensorState, '/foxrobotlab/raw/sensors/core', QOS
        )

        # Battery Sensor
        self.kobuki_battery_subscription = self.create_subscription(
            BatteryState, '/sensors/battery_state', self.battery_callback, QOS
        )
        self.kobuki_battery_publisher = self.create_publisher(
            BatteryState, '/foxrobotlab/raw/sensors/battery_state', QOS
        )

        # Bumper Sensor
        self.kobuki_bumper_subscription = self.create_subscription(
            BumperEvent, '/events/bumper', self.bumper_callback, QOS
        )
        self.kobuki_bumper_publisher = self.create_publisher(
            BumperEvent, '/foxrobotlab/raw/events/bumper', QOS
        )

        # Wheel Drop Sensor (Detects if the Kobuki is on the ground)
        self.kobuki_wheeldrop_subscription = self.create_subscription(
            WheelDropEvent, '/events/wheel_drop', self.wheeldrop_callback, QOS
        )
        self.kobuki_wheeldrop_publisher = self.create_publisher(
            WheelDropEvent, '/foxrobotlab/raw/events/wheel_drop', QOS
        )

        # Cliff Sensor (Detects if a Kobuki wheel is missing a floor)
        self.kobuki_cliff_subscription = self.create_subscription(
            CliffEvent, '/events/cliff', self.cliff_callback, QOS
        )
        self.kobuki_cliff_publisher = self.create_publisher(
            CliffEvent, '/foxrobotlab/raw/events/cliff', QOS
        )

    # ====================== Callbacks ===================
    #-----------------------------------------
    def depth_callback(self, msg: Image):
        self.depth_publisher.publish(msg)

    def image_callback(self, msg: Image):
        self.image_publisher.publish(msg)

    #-----------------------------------------
    def odom_callback(self, msg: Odometry):
        self.odom_publisher.publish(msg)

    def imu_callback(self, msg: Imu):
        self.imu_publisher.publish(msg)

    #-----------------------------------------
    def core_callback(self, msg: SensorState):
        self.kobuki_core_publisher.publish(msg)

    def battery_callback(self, msg: BatteryState):
        self.kobuki_battery_publisher.publish(msg)
    
    def bumper_callback(self, msg: BumperEvent):
        self.kobuki_bumper_publisher.publish(msg)

    def wheeldrop_callback(self, msg: WheelDropEvent):
        self.kobuki_wheeldrop_publisher.publish(msg)

    def cliff_callback(self, msg: CliffEvent):
        self.kobuki_cliff_publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    receiver = ControlReceiver()
    rclpy.spin(receiver)
    receiver.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()

#!/usr/bin/env python3

# This file will be used to process the data from turtle_control_reciever.py.
# Converts ROS2 data into Python data
# Author Andre Mojica, June 2026

import math 

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Image, Imu
from kobuki_ros_interfaces.msg import SensorState, BumperEvent, WheelDropEvent, CliffEvent


QOS = 10


class TurtleControlProcessor(Node):
    def __init__(self):
        super().__init__("turtle_control_processor")

        # Initialize Class Variables
        self.latest_color_image = None
        self.latest_depth_image = None
        self.latest_odom = None
        self.latest_imu = None
        self.latest_core = None
        self.latest_battery = None
        self.latest_bumper = None
        self.latest_wheel_drop = None
        self.latest_cliff = None  
        
        # ======================= Project Subscribers =================
        # ------------------- Image and Depth --------------------
        self.create_subscription(
            Image,
            "/foxrobotlab/raw/color/image_raw",
            self.color_image_callback,
            QOS,
        )
        self.create_subscription(
            Image,
            "/foxrobotlab/raw/depth/image_raw",
            self.depth_image_callback,
            QOS,
        )

        # ------------------- Odometry and IMU -------------------
        self.create_subscription(
            Odometry,
            "/foxrobotlab/raw/odom",
            self.odom_callback,
            QOS,
        )
        self.create_subscription(
            Imu,
            "/foxrobotlab/raw/sensors/imu_data",
            self.imu_callback,
            QOS,
        )

        # ----------------------- Kobuki Sensors --------------------
        self.create_subscription(
            SensorState,
            "/foxrobotlab/raw/sensors/core",
            self.core_callback,
            QOS,
        )
        self.create_subscription(
            BatteryState,
            "/foxrobotlab/raw/sensors/battery_state",
            self.battery_callback,
            QOS,
        )
        self.create_subscription(
            BumperEvent,
            "/foxrobotlab/raw/events/bumper",
            self.bumper_callback,
            QOS,
        )
        self.create_subscription(
            WheelDropEvent,
            "/foxrobotlab/raw/events/wheel_drop",
            self.wheeldrop_callback,
            QOS,
        )
        self.create_subscription(
            CliffEvent,
            "/foxrobotlab/raw/events/cliff",
            self.cliff_callback,
            QOS,
        )

    # =================== Callbacks =======================
    def color_image_callback(self, msg: Image):
        self.latest_color_image = msg

    def depth_image_callback(self, msg: Image):
        self.latest_depth_image = msg

    def odom_callback(self, msg: Odometry):
        self.latest_odom = msg
        position = msg.pose.pose.position
        orientation = msg.pose.pose.orientation
        self.get_logger().info(f'X: {position.x} | Y: {position.y} | Yaw: {self.euler_from_quaternion(orientation)}')

    def imu_callback(self, msg: Imu):
        self.latest_imu = msg

    def core_callback(self, msg: SensorState):
        self.latest_core = msg
        battery = msg.battery
        self.get_logger().info(battery)

    def battery_callback(self, msg: BatteryState):
        self.latest_battery = msg

    def bumper_callback(self, msg: BumperEvent):
        self.latest_bumper = msg

    def wheeldrop_callback(self, msg: WheelDropEvent):
        self.latest_wheel_drop = msg

    def cliff_callback(self, msg: CliffEvent):
        self.latest_cliff = msg
    
    # ======================== Odometry Methods ========================
    def euler_from_quaternion(orientation):
        x = orientation.x
        y = orientation.y
        z = orientation.z 
        w = orientation.w
        
        # hard coded yaw equation 
        siny_cosp = 2 * (w*z + x*y)
        cosy_cosp = 1 - 2 * (y**2 + z**2)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return math.degrees(yaw)
        

def main(args=None):
    rclpy.init(args=args)
    processor = TurtleControlProcessor()
    rclpy.spin(processor)
    processor.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
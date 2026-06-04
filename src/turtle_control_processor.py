#!/usr/bin/env python3

# This file will be used to process the data from turtle_control_reciever.py.
# Converts ROS2 data into Python data
# Author Andre Mojica, June 2026

import math 

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Image, Imu
from std_msgs.msg import String
from kobuki_ros_interfaces.msg import SensorState, BumperEvent, WheelDropEvent, CliffEvent


QOS = 10
STATUS_PERIOD_SECONDS = 0.5


class TurtleControlProcessor(Node):
    def __init__(self):
        super().__init__('control_processor')

        # Internal State Variables
        self.imageColor_msg = None
        self.imageDepth_msg = None
        self.odom_msg = None
        self.imu_msg = None
        self.core_msg = None
        self.battery_msg = None
        self.bumper_msg = None
        self.wheelDrop_msg = None
        self.cliff_msg = None  

        #-------Imported Variables from turtleControl.py-------
        # Offset Variables
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_yaw = 0.0

        # Travel Distance Variables
        self.prev_x = 0.0
        self.prev_y = 0.0
        self.prev_yaw = 0.0

        self.wheel_drop_flag = False
        self.image_served_count = 0

        # ======================== Internal State Publisher ================
        self.status_publisher = self.create_publisher(
            String,
            '/foxrobotlab/processed/status_text',
            QOS,
        )
        self.create_timer(STATUS_PERIOD_SECONDS, self.publish_status)
        
        # ======================= Project Subscribers =================
        # ------------------- Image and Depth --------------------
        self.create_subscription(
            Image,
            '/foxrobotlab/raw/color/image_raw',
            self.color_image_callback,
            QOS,
        )
        self.create_subscription(
            Image,
            '/foxrobotlab/raw/depth/image_raw',
            self.depth_image_callback,
            QOS,
        )

        # ------------------- Odometry and IMU -------------------
        self.create_subscription(
            Odometry,
            '/foxrobotlab/raw/odom',
            self.odom_callback,
            QOS,
        )
        self.create_subscription(
            Imu,
            '/foxrobotlab/raw/sensors/imu_data',
            self.imu_callback,
            QOS,
        )

        # ----------------------- Kobuki Sensors --------------------
        self.create_subscription(
            SensorState,
            '/foxrobotlab/raw/sensors/core',
            self.core_callback,
            QOS,
        )
        self.create_subscription(
            BatteryState,
            '/foxrobotlab/raw/sensors/battery_state',
            self.battery_callback,
            QOS,
        )
        self.create_subscription(
            BumperEvent,
            '/foxrobotlab/raw/events/bumper',
            self.bumper_callback,
            QOS,
        )
        self.create_subscription(
            WheelDropEvent,
            '/foxrobotlab/raw/events/wheel_drop',
            self.wheeldrop_callback,
            QOS,
        )
        self.create_subscription(
            CliffEvent,
            '/foxrobotlab/raw/events/cliff',
            self.cliff_callback,
            QOS,
        )

    # =================== Callbacks =======================
    def color_image_callback(self, msg: Image):
        self.imageColor_msg = msg

    def depth_image_callback(self, msg: Image):
        self.imageDepth_msg = msg

    def odom_callback(self, msg: Odometry):
        self.odom_msg = msg

    def imu_callback(self, msg: Imu):
        self.imu_msg = msg

    def core_callback(self, msg: SensorState):
        self.core_msg = msg

    def battery_callback(self, msg: BatteryState):
        self.battery_msg = msg

    def bumper_callback(self, msg: BumperEvent):
        self.bumper_msg = msg

    def wheeldrop_callback(self, msg: WheelDropEvent):
        self.wheelDrop_msg = msg

    def cliff_callback(self, msg: CliffEvent):
        self.cliff_msg = msg

    # ========================= Class Methods ====================
    def getOdomData(self):
        odom = self.odom_msg
        if odom is None:
            return 0.0, 0.0, 0.0
    
        position = odom.pose.pose.position
        orientation = odom.pose.pose.orientation
        yaw = self.euler_from_quaternion(orientation)

        x = position.x + self.offset_x
        y = position.y + self.offset_y
        yaw = math.degrees(yaw + self.offset_yaw)

        return x, y, yaw
    
        
    # ======================== Status Formatting ========================
    # -------------- String Building ----------------
    def publish_status(self):
        message = String()
        message.data = self.build_status_text()
        self.status_publisher.publish(message)

    def build_status_text(self):
        sections = [
            'FOX ROBOT LAB TURTLE CONTROL',
            '============================',
            '',
            self.format_odometry(),
            '',
            self.format_imu(),
            '',
            self.format_battery(),
            '',
            self.format_core(),
            '',
            self.format_events(),
            '',
            self.format_images(),
        ]
        return '\n'.join(sections)

    # -------------------- String Formatting -------------------
    def format_odometry(self):
        if self.latest_odom is None:
            return 'ODOMETRY\nwaiting...'

        position = self.latest_odom.pose.pose.position
        orientation = self.latest_odom.pose.pose.orientation
        linear_vel = self.latest_odom.twist.twist.linear
        angular_vel = self.latest_odom.twist.twist.angular
        yaw = self.euler_from_quaternion(orientation)

        return (
            'ODOMETRY\n'
            f'x: {position.x:.3f} m\n'
            f'y: {position.y:.3f} m\n'
            f'yaw: {yaw:.2f} deg\n'
            f'linear x: {linear_vel.x:.3f} m/s\n'
            f'linear y: {linear_vel.y:3f} m/s\n'
            f'angular z: {math.degrees(angular_vel.z):.3f} deg/s'
        )

    def format_imu(self):
        if self.latest_imu is None:
            return 'IMU\nwaiting...'

        linear_accel = self.latest_imu.linear_acceleration
        angular_vel = self.latest_imu.angular_velocity

        return (
            'IMU\n'
            f'linear accel x: {linear_accel.x:.3f} m/s^2\n'
            f'linear accel y: {linear_accel.y:.3f} m/s^2\n'
            f'yaw rate z: {angular_vel.z:.3f} rad/s'
        )

    def format_battery(self):
        if self.latest_battery is None:
            return 'BATTERY\nwaiting...'

        percentage = 'unknown'
        if self.latest_battery.percentage >= 0.0:
            percentage = f'{self.latest_battery.percentage * 100.0:.1f}%'

        return (
            'BATTERY\n'
            f'voltage: {self.latest_battery.voltage:.2f} V\n'
            f'percentage: {percentage}'
        )

    def format_core(self):
        if self.latest_core is None:
            return 'KOBUKI CORE\nwaiting...'

        return (
            'KOBUKI CORE\n'
            f'raw battery: {self.latest_core.battery}\n'
            f'bumper bitmask: {self.latest_core.bumper}\n'
            f'wheel drop bitmask: {self.latest_core.wheel_drop}\n'
            f'cliff bitmask: {self.latest_core.cliff}'
        )

    def format_events(self):
        return (
            'EVENTS\n'
            f'bumper: {self.format_bumper_event()}\n'
            f'wheel drop: {self.format_wheel_drop_event()}\n'
            f'cliff: {self.format_cliff_event()}'
        )

    def format_images(self):
        color = self.format_image_info(self.latest_color_image)
        depth = self.format_image_info(self.latest_depth_image)
        return (
            'IMAGE TOPICS\n'
            f'color: {color}\n'
            f'depth: {depth}'
        )

    def format_image_info(self, image):
        if image is None:
            return 'waiting...'
        return f'{image.width}x{image.height} {image.encoding}'

    def format_bumper_event(self):
        if self.latest_bumper is None:
            return 'waiting...'
        return (
            f'{self.bumper_name(self.latest_bumper.bumper)} '
            f'{self.bumper_state(self.latest_bumper.state)}'
        )

    def format_wheel_drop_event(self):
        if self.latest_wheel_drop is None:
            return 'waiting...'
        return (
            f'{self.wheel_name(self.latest_wheel_drop.wheel)} '
            f'{self.wheel_state(self.latest_wheel_drop.state)}'
        )

    def format_cliff_event(self):
        if self.latest_cliff is None:
            return 'waiting...'
        return (
            f'{self.cliff_sensor_name(self.latest_cliff.sensor)} '
            f'{self.cliff_state(self.latest_cliff.state)} '
            f'(bottom: {self.latest_cliff.bottom})'
        )

    # ======================== Helper Methods ========================
    def bumper_name(self, value):
        names = {
            BumperEvent.LEFT: 'LEFT',
            BumperEvent.CENTER: 'CENTER',
            BumperEvent.RIGHT: 'RIGHT',
        }
        return names.get(value, f'UNKNOWN({value})')

    def bumper_state(self, value):
        states = {
            BumperEvent.RELEASED: 'RELEASED',
            BumperEvent.PRESSED: 'PRESSED',
        }
        return states.get(value, f'UNKNOWN({value})')

    def wheel_name(self, value):
        names = {
            WheelDropEvent.LEFT: 'LEFT',
            WheelDropEvent.RIGHT: 'RIGHT',
        }
        return names.get(value, f'UNKNOWN({value})')

    def wheel_state(self, value):
        states = {
            WheelDropEvent.RAISED: 'RAISED',
            WheelDropEvent.DROPPED: 'DROPPED',
        }
        return states.get(value, f'UNKNOWN({value})')

    def cliff_sensor_name(self, value):
        names = {
            CliffEvent.LEFT: 'LEFT',
            CliffEvent.CENTER: 'CENTER',
            CliffEvent.RIGHT: 'RIGHT',
        }
        return names.get(value, f'UNKNOWN({value})')

    def cliff_state(self, value):
        states = {
            CliffEvent.FLOOR: 'FLOOR',
            CliffEvent.CLIFF: 'CLIFF',
        }
        return states.get(value, f'UNKNOWN({value})')
    
    def euler_from_quaternion(self, orientation):
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

if __name__ == '__main__':
    main()

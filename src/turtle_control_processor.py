#!/usr/bin/env python3

# This file will be used to process the data from turtle_control_reciever.py.
# Converts ROS2 data into Python data
# Author Andre Mojica, June 2026

import math 
import numpy as np

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Image, Imu
from std_msgs.msg import String
from geometry_msgs.msg import Twist
from kobuki_ros_interfaces.msg import SensorState, BumperEvent, WheelDropEvent, CliffEvent

from cv_bridge import CvBridge

# NOTE: This is a placeholder to make the current matchPlanner work
import threading

QOS = 10
STATUS_PERIOD_SECONDS = 0.5


class TurtleControlProcessor(Node):
    def __init__(self, spin_in_background=False):
        super().__init__('control_processor')

        # Variables for ROS topics
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
        # Offset Variables, temporary summer 2018 offsets
        self.offset_x = 6.1
        self.offset_y = 41.1
        self.offset_yaw = 270.0

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

        # Movement Publisher 
        # NOTE: This is a placeholder to make the current matchPlanner work
        self.move_publisher = self.create_publisher(
            Twist, '/cmd_vel', QOS
        )
        self.movement_paused = False

        self.spin_thread = None
        if spin_in_background:
            self.spin_thread = threading.Thread(target=self._spin, daemon=True)
            self.spin_thread.start()

    # =================== Callbacks =======================
    def color_image_callback(self, msg: Image):
        self.imageColor_msg = msg

    def depth_image_callback(self, msg: Image):
        self.imageDepth_msg = msg

    def odom_callback(self, msg: Odometry):
        # this is to make sure that the previous odom is saved as the first instance of the odometry upon initialization
        if self.odom_msg is None:
            self.odom_msg = msg
            self.prev_x, self.prev_y, self.prev_yaw = self.getOdomData()
        else:
            self.odom_msg = msg

    def imu_callback(self, msg: Imu):
        self.imu_msg = msg

    def core_callback(self, msg: SensorState):
        self.core_msg = msg
        if msg.wheel_drop > 0:
            self.wheel_drop_flag = True

    def battery_callback(self, msg: BatteryState):
        self.battery_msg = msg

    def bumper_callback(self, msg: BumperEvent):
        self.bumper_msg = msg

    def wheeldrop_callback(self, msg: WheelDropEvent):
        self.wheelDrop_msg = msg

    def cliff_callback(self, msg: CliffEvent):
        self.cliff_msg = msg

    # ========================= Class Methods ====================
    # ---------------------- For Localizer ------------------
    def getOdomData(self):
        raw_x, raw_y, raw_yaw = self.get_raw_odom()
        x = raw_x + self.offset_x
        y = raw_y + self.offset_y
        yaw = self.normalize_degrees(raw_yaw + self.offset_yaw)

        return x, y, yaw
    
    def updateOdomLocation(self, x=0, y=0, yaw=0.0):
        raw_x, raw_y, raw_yaw = self.get_raw_odom()

        old_x = self.prev_x - self.offset_x
        old_y = self.prev_y - self.offset_y
        old_yaw = self.prev_yaw - self.offset_yaw

        self.offset_x = x - raw_x
        self.offset_y = y - raw_y
        self.offset_yaw = self.normalize_degrees(yaw - raw_yaw)

        self.prev_x = old_x + self.offset_x
        self.prev_y = old_y + self.offset_y
        self.prev_yaw = self.normalize_degrees(old_yaw + self.offset_yaw)

        return self.offset_x, self.offset_y, self.offset_yaw
    
    def getTravelDist(self):
        cur_x, cur_y, cur_yaw = self.getOdomData()
        dx = cur_x - self.prev_x
        dy = cur_y - self.prev_y
        dyaw = self.normalize_degrees(cur_yaw - self.prev_yaw)
        rad_yaw = math.radians(self.prev_yaw)

        rx = dx * math.cos(rad_yaw) + dy * math.sin(rad_yaw)
        ry = -dx * math.sin(rad_yaw) + dy * math.cos(rad_yaw)

        self.prev_x = cur_x
        self.prev_y = cur_y
        self.prev_yaw = cur_yaw

        return rx, ry, dyaw
    
    def getBumperStatus(self): 
        if self.core_msg is None: return 0
        else: return self.core_msg.bumper
    
    def getWheelDropStatus(self):
        if self.core_msg is None: return 0
        else: return self.core_msg.wheel_drop

    def getCliffStatus(self):
        if self.core_msg is None: return 0
        else: return self.core_msg.cliff

    def hasWheelDrop(self):
        drop_event = self.wheel_drop_flag
        self.wheel_drop_flag = False
        return drop_event
    
    # ------------------------- Images and Depth ---------------------
    def getImage(self, x=0, y=0, width = 640, height = 480):
        raw_image = self.wait_for_message(lambda: self.imageColor_msg, 'color image')
        if raw_image is None:
            return None, 0

        cv_image = CvBridge().imgmsg_to_cv2(raw_image, 'passthrough')
        cropped_image = cv_image[y:y + height, x:x + width]

        self.image_served_count += 1
        return cropped_image, self.image_served_count

    def getDepth(self, x=0, y=0, width = 640, height = 480):
        ros_image = self.wait_for_message(lambda: self.imageDepth_msg, 'depth image')        
        if ros_image is None:
            return np.zeros((height, width))
        cv_image = CvBridge().imgmsg_to_cv2(ros_image, 'passthrough')
        numpy_array = np.asarray(cv_image)
        return numpy_array[y:y + height, x:x + width]
    
    # NOTE: Tha lambda is for reading NEW values of the ROS message, when wait_for_message is called
    # it re-checks imageColor_msg topic not whatever the current value of self.imageColor_msg.
    
    # ---------------------- Movement Methods ----------------------
    # NOTE: This will be removed in future work. The goal is the have Nav2 do all the movement
    # based on our localization data, so these movement methods will be removed from matchPlanner in future updating.
    def pauseMovement(self):
        self.stop()
        self.movement_paused = True

    def unpauseMovement(self):
        self.movement_paused = False

    def move(self, translate, rotate):
        if self.movement_paused:
            return

        twist = Twist()
        twist.linear.x = translate
        twist.angular.z = rotate
        self.move_publisher.publish(twist)

    def stop(self):
        self.move_publisher.publish(Twist())
        
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
        odom = self.odom_msg
        if odom is None:
            return 'ODOMETRY\nwaiting...'

        x, y, yaw = self.getOdomData()
        linear_vel = odom.twist.twist.linear
        angular_vel = odom.twist.twist.angular

        return (
            'ODOMETRY\n'
            f'x: {x:.3f} m\n'
            f'y: {y:.3f} m\n'
            f'yaw: {yaw:.2f} deg\n'
            f'linear x: {linear_vel.x:.3f} m/s\n'
            f'linear y: {linear_vel.y:3f} m/s\n'
            f'angular z: {math.degrees(angular_vel.z):.3f} deg/s'
        )

    def format_imu(self):
        if self.imu_msg is None:
            return 'IMU\nwaiting...'

        linear_accel = self.imu_msg.linear_acceleration
        angular_vel = self.imu_msg.angular_velocity

        return (
            'IMU\n'
            f'linear accel x: {linear_accel.x:.3f} m/s^2\n'
            f'linear accel y: {linear_accel.y:.3f} m/s^2\n'
            f'yaw rate z: {angular_vel.z:.3f} rad/s'
        )

    def format_battery(self):
        if self.battery_msg is None:
            return 'BATTERY\nwaiting...'

        percentage = 'unknown'
        if self.battery_msg.percentage >= 0.0:
            percentage = f'{self.battery_msg.percentage * 100.0:.1f}%'

        return (
            'BATTERY\n'
            f'voltage: {self.battery_msg.voltage:.2f} V\n'
            f'percentage: {percentage}'
        )

    def format_core(self):
        if self.core_msg is None:
            return 'KOBUKI CORE\nwaiting...'

        return (
            'KOBUKI CORE\n'
            f'raw battery: {self.core_msg.battery}\n'
            f'bumper bitmask: {self.core_msg.bumper}\n'
            f'wheel drop bitmask: {self.core_msg.wheel_drop}\n'
            f'cliff bitmask: {self.core_msg.cliff}'
        )

    def format_events(self):
        return (
            'EVENTS\n'
            f'bumper: {self.format_bumper_event()}\n'
            f'wheel drop: {self.format_wheel_drop_event()}\n'
            f'cliff: {self.format_cliff_event()}'
        )

    def format_images(self):
        color = self.format_image_info(self.imageColor_msg)
        depth = self.format_image_info(self.imageDepth_msg)
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
        if self.bumper_msg is None:
            return 'waiting...'
        return (
            f'{self.bumper_name(self.bumper_msg.bumper)} '
            f'{self.bumper_state(self.bumper_msg.state)}'
        )

    def format_wheel_drop_event(self):
        if self.wheelDrop_msg is None:
            return 'waiting...'
        return (
            f'{self.wheel_name(self.wheelDrop_msg.wheel)} '
            f'{self.wheel_state(self.wheelDrop_msg.state)}'
        )

    def format_cliff_event(self):
        if self.cliff_msg is None:
            return 'waiting...'
        return (
            f'{self.cliff_sensor_name(self.cliff_msg.sensor)} '
            f'{self.cliff_state(self.cliff_msg.state)} '
            f'(bottom: {self.cliff_msg.bottom})'
        )

    # ======================== Helper Methods ========================
    # -------------------------- Class Helpers --------------------------
    def get_raw_odom(self):
        odom = self.odom_msg
        if odom is None:
            return 0.0, 0.0, 0.0

        odom_position = odom.pose.pose.position
        odom_orientation = odom.pose.pose.orientation

        x = odom_position.x
        y = odom_position.y
        yaw = self.euler_from_quaternion(odom_orientation)

        return x, y, yaw
    
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
    
    def normalize_degrees(self, angle): # allows us to have consistent angles
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle

    def wait_for_message(self, getter, label):
        while rclpy.ok():
            msg = getter()
            if msg is not None:
                return msg
            self.get_logger().info(f'Waiting for {label}...')
            rclpy.spin_once(self, timeout_sec=0.2)
        return None

    def _spin(self):
        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)
    
    # --------------------------- String Format Helpers ----------------------
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
    
def main(args=None):
    rclpy.init(args=args)
    processor = TurtleControlProcessor()
    rclpy.spin(processor)
    processor.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

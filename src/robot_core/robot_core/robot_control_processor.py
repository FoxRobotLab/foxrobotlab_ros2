#!/usr/bin/env python3

import math
import threading
import time

import numpy as np
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from kobuki_ros_interfaces.msg import SensorState
from lab_interfaces.msg import SafetyStatus
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Image, Imu
from std_msgs.msg import String


QOS = 10
STATUS_PERIOD_SECONDS = 0.5


class RobotControlProcessor(Node):
    """Modular replacement for the legacy TurtleControlProcessor.

    This class intentionally preserves the public method names used by
    matchPlanner.py while consuming only the architecture-owned /robot topics.
    """

    def __init__(self, spin_in_background=False, node_name="robot_control_processor"):
        self.owns_rclpy = False
        if not rclpy.ok():
            rclpy.init()
            self.owns_rclpy = True

        super().__init__(node_name)

        self.bridge = CvBridge()

        self.imageColor_msg = None
        self.imageDepth_msg = None
        self.odom_msg = None
        self.imu_msg = None
        self.core_msg = None
        self.battery_msg = None
        self.safety_msg = None

        self.offset_x = 6.1
        self.offset_y = 41.1
        self.offset_yaw = 270.0

        self.prev_x = 0.0
        self.prev_y = 0.0
        self.prev_yaw = 0.0

        self.wheel_drop_flag = False
        self.image_served_count = 0
        self.movement_paused = False

        # ----------------- Initialize Publishers and Subscribers -----------------
        self.status_publisher = self.create_publisher(
            String,
            "/foxrobotlab/processed/status_text",
            QOS,
        )
        self.move_publisher = self.create_publisher(Twist, "/robot/cmd_vel", QOS)

        self.create_subscription(
            Image,
            "/robot/camera/color/image_raw",
            self.color_image_callback,
            QOS,
        )
        self.create_subscription(
            Image,
            "/robot/camera/depth/image_raw",
            self.depth_image_callback,
            QOS,
        )
        self.create_subscription(Odometry, "/robot/odom", self.odom_callback, QOS)
        self.create_subscription(Imu, "/robot/imu", self.imu_callback, QOS)
        self.create_subscription(SensorState, "/robot/kobuki/core", self.core_callback, QOS)
        self.create_subscription(BatteryState, "/robot/battery", self.battery_callback, QOS)
        self.create_subscription(
            SafetyStatus,
            "/robot/safety_status",
            self.safety_callback,
            QOS,
        )

        self.create_timer(STATUS_PERIOD_SECONDS, self.publish_status)

        self.spin_in_background = spin_in_background
        self.spin_running = False
        self.spin_thread = None
        if spin_in_background:
            self.spin_running = True
            self.spin_thread = threading.Thread(target=self._spin, daemon=True)
            self.spin_thread.start()

        self.get_logger().info(
            "RobotControlProcessor using modular /robot topics and /robot/cmd_vel."
        )

    # =================== Callbacks =======================
    def color_image_callback(self, msg):
        self.imageColor_msg = msg

    def depth_image_callback(self, msg):
        self.imageDepth_msg = msg

    def odom_callback(self, msg):
        if self.odom_msg is None:
            self.odom_msg = msg
            self.prev_x, self.prev_y, self.prev_yaw = self.getOdomData()
        else:
            self.odom_msg = msg

    def imu_callback(self, msg):
        self.imu_msg = msg

    def core_callback(self, msg):
        self.core_msg = msg
        if msg.wheel_drop > 0:
            self.wheel_drop_flag = True

    def battery_callback(self, msg):
        self.battery_msg = msg

    def safety_callback(self, msg):
        if msg.wheel_drop_detected:
            self.wheel_drop_flag = True
        self.safety_msg = msg

    # ========================= Status Publisher ====================
    def publish_status(self):
        x, y, yaw = self.getOdomData()
        msg = String()
        msg.data = (
            "robot_control_processor "
            f"odom=({x:.2f}, {y:.2f}, {yaw:.2f}) "
            f"paused={self.movement_paused} "
            f"bumper={self.getBumperStatus()} "
            f"cliff={self.getCliffStatus()} "
            f"wheel_drop={self.getWheelDropStatus()}"
        )
        self.status_publisher.publish(msg)

    # ========================= Public API ====================
    # Odometry
    def getOdomData(self):
        raw_x, raw_y, raw_yaw = self.get_raw_odom()
        x, y = self.transform_raw_xy_to_map(raw_x, raw_y)
        yaw = self.normalize_degrees(raw_yaw + self.offset_yaw)
        return x, y, yaw

    def updateOdomLocation(self, x=0, y=0, yaw=0.0):
        raw_x, raw_y, raw_yaw = self.get_raw_odom()

        self.offset_yaw = self.normalize_degrees(yaw - raw_yaw)

        rotated_raw_x, rotated_raw_y = self.rotate_raw_xy(raw_x, raw_y)
        self.offset_x = x - rotated_raw_x
        self.offset_y = y - rotated_raw_y

        self.prev_x, self.prev_y, self.prev_yaw = self.getOdomData()
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

    # Robot Status
    def getBumperStatus(self):
        if self.core_msg is not None:
            return self.core_msg.bumper
        if self.safety_msg is not None and self.safety_msg.bumper_pressed:
            return 1
        return 0

    def getWheelDropStatus(self):
        if self.core_msg is not None:
            return self.core_msg.wheel_drop
        if self.safety_msg is not None and self.safety_msg.wheel_drop_detected:
            return 1
        return 0

    def getCliffStatus(self):
        if self.core_msg is not None:
            return self.core_msg.cliff
        if self.safety_msg is not None and self.safety_msg.cliff_detected:
            return 1
        return 0

    def hasWheelDrop(self):
        drop_event = self.wheel_drop_flag
        self.wheel_drop_flag = False
        return drop_event

    def getBatteryLevel(self):
        if self.core_msg is not None:
            return self.core_msg.battery
        if self.battery_msg is not None and self.battery_msg.percentage >= 0.0:
            return self.battery_msg.percentage
        return 0

    # Images and Depth for CNN Image Mapping
    def getImage(self, x=0, y=0, width=640, height=480):
        raw_image = self.wait_for_message(lambda: self.imageColor_msg, "color image")
        if raw_image is None:
            return None, 0

        cv_image = self.bridge.imgmsg_to_cv2(raw_image, "passthrough")
        cropped_image = cv_image[y:y + height, x:x + width]

        self.image_served_count += 1
        return cropped_image, self.image_served_count

    def getDepth(self, x=0, y=0, width=640, height=480):
        ros_image = self.wait_for_message(lambda: self.imageDepth_msg, "depth image")
        if ros_image is None:
            return np.zeros((height, width))
        cv_image = self.bridge.imgmsg_to_cv2(ros_image, "passthrough")
        numpy_array = np.asarray(cv_image)
        return numpy_array[y:y + height, x:x + width]

    # Movement
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

    def turnLeft(self, amount):
        self.move(0.0, amount)

    def turnRight(self, amount):
        self.move(0.0, -amount)

    def turnByAngle(self, angle, timeout_sec=None):
        curr_x, curr_y, curr_yaw = self.getOdomData()
        goal_yaw = self.normalize_degrees(curr_yaw + angle)
        start_time = time.monotonic()

        while rclpy.ok():
            _, _, curr_yaw = self.getOdomData()
            yaw_error = self.normalize_degrees(goal_yaw - curr_yaw)
            if abs(yaw_error) <= 5:
                self.stop()
                return True

            if timeout_sec is not None and time.monotonic() - start_time >= timeout_sec:
                break

            if yaw_error > 0:
                self.turnLeft(0.5)
            else:
                self.turnRight(0.5)
            time.sleep(0.05)

        self.stop()
        return False

    # Shutdown
    def is_shutdown(self):
        return not rclpy.ok()

    def shutdown(self):
        if rclpy.ok():
            self.stop()
        self.spin_running = False
        if self.spin_thread is not None:
            self.spin_thread.join(timeout=1.0)
        self.destroy_node()
        if self.owns_rclpy and rclpy.ok():
            rclpy.shutdown()

    # ======================== Helper Methods ========================
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

    def transform_raw_xy_to_map(self, raw_x, raw_y):
        rotated_x, rotated_y = self.rotate_raw_xy(raw_x, raw_y)
        return rotated_x + self.offset_x, rotated_y + self.offset_y

    def rotate_raw_xy(self, raw_x, raw_y):
        yaw_offset = math.radians(self.offset_yaw)
        cos_yaw = math.cos(yaw_offset)
        sin_yaw = math.sin(yaw_offset)
        map_x = raw_x * cos_yaw - raw_y * sin_yaw
        map_y = raw_x * sin_yaw + raw_y * cos_yaw
        return map_x, map_y

    def euler_from_quaternion(self, orientation):
        x = orientation.x
        y = orientation.y
        z = orientation.z
        w = orientation.w

        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y**2 + z**2)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return math.degrees(yaw)

    def normalize_degrees(self, angle):
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
            self.get_logger().info(f"Waiting for {label}...")
            if self.spin_in_background:
                time.sleep(0.2)
            else:
                rclpy.spin_once(self, timeout_sec=0.2)
        return None

    def _spin(self):
        while self.spin_running and rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.1)

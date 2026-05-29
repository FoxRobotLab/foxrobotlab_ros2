#!/usr/bin/env python3

# This file will be responsible for subscribing and publishing the necesarry topics for the rest of the system to use
# Author: Andre Mojica, May 2026

# Import the node system from ROS
import rclpy
from rclpy.node import Node

# Import necessary message to create ROS topics
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from std_msgs.msg import Empty
from kobuki_ros_interfaces.msg import SensorState

class ControlReciever(Node):
    def __init__(self):
        super().__init__("control_subscriber")

        # Odometry Subscription ("/odom" topic)
        self.odom_subscription = self.create_subscription(
            Odometry,
            "/odom",
            self.odom_callback,
            10
        )
        self.odom_subscription

        # Movement Suscription ("/cmd_vel" topic)
        self.control_subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.mov_callback,
            10
        )
        self.control_subscription

        # Depth Sensor Subscription ("/camera/depth/image_raw" topic)
        self.depth_subscription = self.create_subscription(
            Image,
            '/depth/image_raw',
            self.depth_callback,
            10
        )
        self.depth_subscription

        # Image Sensor Subscription ("/camera/color/image_raw" topic)
        self.image_subscription = self.create_subscription(
            Image,
            '/color/image_raw',
            self.image_callback,
            10
        )
        self.image_subscription

        # Core Sensor Subscription ("????" Topic)
        self.core_subscription = self.create_subscription(
            
        )
    
    def odom_callback(self, msg: Odometry):
        # Getting position data
        position = msg.pose.pose.position
        self.get_logger().info(f'X: {position.x} | Y: {position.y}')

    def mov_callback(self, msg):
        pass 

    def depth_callback(self, msg):
        pass

    def image_callback(self, msg):
        pass

    def sensor_callback(self, msg):
        pass 



def main(args=None):
    rclpy.init(args=args)
    reciever = ControlReciever()
    rclpy.spin(reciever)
    reciever.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()





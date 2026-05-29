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

# Import ROS to CV Bridge 
from cv_bridge import CvBridge

class OdometrySubscriber(Node):
    def __init__(self):
        super.__init__("odometry_subscriber")
        self.subscriptions = self.create_subscription(
            Odometry,
            "/odom",
            self.odom_callback,
            10
        )
        self.subscription
    
    def odom_callback(self, msg):
        # Getting position data
        position = msg.pose.pose.position
        self.get_logger().info(f'X: {position.x} | Y: {position.y}')

def main(args=None):
    rclpy.init(args=args)
    odom_listener = OdometrySubscriber()
    rclpy.spin(odom_listener)
    odom_listener.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()





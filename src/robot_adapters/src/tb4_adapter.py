#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import (
    BatteryState,
    Image,
    Imu,
    LaserScan,
)

QOS = 10

class TurtleBot4Adapter(Node):
    def __init__(self):
        super().__init__(
            "tb4_adapter",
            automatically_declare_parameters_from_overrides=True
            )

        # ---------------- Initialize Parameters ----------------
        self.robot_name = self.get_parameter("robot_name").value
        self.robot_type = self.get_parameter("robot_type").value
        

        # ---------------- Specific Robot Parameters ----------------


        # ---------------- Initialize Publishers and Subscribers ----------------



        # ---------------- Subscription to Specific Robot Capabilities ----------------


        # ---------------- Callbacks functions for Subscribers ----------------

        
        # ---------------- Status Printers ----------------

def main(args=None):
    rclpy.init(args=args)
    node = TurtleBot4Adapter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
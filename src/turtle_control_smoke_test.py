#!/usr/bin/env python3

# Smoke test for the turtle control ROS2 migration.
# Run this after launching the receiver, processor, and display nodes.

import argparse
import time

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Image, Imu
from std_msgs.msg import String
from kobuki_ros_interfaces.msg import SensorState, BumperEvent, WheelDropEvent, CliffEvent


QOS = 10


class TurtleControlSmokeTest(Node):
    def __init__(self):
        super().__init__('turtle_control_smoke_test')
        self.seen = {}
        self.details = {}

        self.watch(Odometry, '/foxrobotlab/raw/odom', 'odom', self.describe_odom)
        self.watch(Image, '/foxrobotlab/raw/color/image_raw', 'color image', self.describe_image)
        self.watch(Image, '/foxrobotlab/raw/depth/image_raw', 'depth image', self.describe_image)
        self.watch(Imu, '/foxrobotlab/raw/sensors/imu_data', 'imu', self.describe_imu)
        self.watch(SensorState, '/foxrobotlab/raw/sensors/core', 'core sensors', self.describe_core)
        self.watch(BatteryState, '/foxrobotlab/raw/sensors/battery_state', 'battery', self.describe_battery)
        self.watch(BumperEvent, '/foxrobotlab/raw/events/bumper', 'bumper event', self.describe_event)
        self.watch(WheelDropEvent, '/foxrobotlab/raw/events/wheel_drop', 'wheel drop event', self.describe_event)
        self.watch(CliffEvent, '/foxrobotlab/raw/events/cliff', 'cliff event', self.describe_event)
        self.watch(String, '/foxrobotlab/processed/status_text', 'processed status', self.describe_status)

    def watch(self, msg_type, topic, label, describer):
        self.seen[label] = False
        self.details[label] = 'waiting...'
        self.create_subscription(
            msg_type,
            topic,
            lambda msg, label=label, describer=describer: self.record(label, describer(msg)),
            QOS,
        )

    def record(self, label, detail):
        self.seen[label] = True
        self.details[label] = detail

    def describe_odom(self, msg):
        pos = msg.pose.pose.position
        return f'x={pos.x:.3f}, y={pos.y:.3f}'

    def describe_image(self, msg):
        return f'{msg.width}x{msg.height}, encoding={msg.encoding}'

    def describe_imu(self, msg):
        return f'yaw rate z={msg.angular_velocity.z:.3f}'

    def describe_core(self, msg):
        return f'bumper={msg.bumper}, wheel_drop={msg.wheel_drop}, cliff={msg.cliff}'

    def describe_battery(self, msg):
        return f'voltage={msg.voltage:.2f}'

    def describe_event(self, msg):
        return str(msg)

    def describe_status(self, msg):
        first_line = msg.data.splitlines()[0] if msg.data else 'empty status'
        return first_line

    def print_report(self):
        print('\nTurtle control smoke test')
        print('=========================')
        for label in self.seen:
            state = 'PASS' if self.seen[label] else 'WAITING'
            print(f'{state:7} {label}: {self.details[label]}')

    def passed(self, required_labels):
        return all(self.seen[label] for label in required_labels)


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--timeout',
        type=float,
        default=10.0,
        help='seconds to wait for required topics',
    )
    parsed_args, ros_args = parser.parse_known_args(args)

    rclpy.init(args=ros_args)
    node = TurtleControlSmokeTest()

    required_labels = [
        'odom',
        'color image',
        'depth image',
        'core sensors',
        'processed status',
    ]

    deadline = time.monotonic() + parsed_args.timeout
    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
            if node.passed(required_labels):
                break

        node.print_report()
        if node.passed(required_labels):
            print('\nRequired topics are publishing. Smoke test passed.')
        else:
            missing = [label for label in required_labels if not node.seen[label]]
            print('\nSmoke test failed. Missing required topics: ' + ', '.join(missing))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

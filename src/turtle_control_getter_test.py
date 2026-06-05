#!/usr/bin/env python3

# Tests the TurtleControlProcessor getter methods used by matchPlanner.py.
# Run this while the receiver is publishing /foxrobotlab/raw/... topics.

import argparse
import time

from turtle_control_processor import TurtleControlProcessor


def wait_until(label, getter, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = getter()
        if value is not None:
            return value
        print(f'WAITING {label}')
        time.sleep(0.2)
    return None


def print_result(label, value, passed=True):
    state = 'PASS' if passed else 'FAIL'
    print(f'{state:4} {label}: {value}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--timeout',
        type=float,
        default=10.0,
        help='seconds to wait for required data',
    )
    args = parser.parse_args()

    robot = TurtleControlProcessor(
        spin_in_background=True,
        node_name='turtle_control_getter_test',
    )

    try:
        print('\nTurtleControlProcessor getter test')
        print('==================================')

        odom = wait_until('odom', lambda: robot.odom_msg, args.timeout)
        image_msg = wait_until('color image', lambda: robot.imageColor_msg, args.timeout)
        depth_msg = wait_until('depth image', lambda: robot.imageDepth_msg, args.timeout)
        core = wait_until('core sensors', lambda: robot.core_msg, args.timeout)

        required_ready = {
            'odom message': odom is not None,
            'color image message': image_msg is not None,
            'depth image message': depth_msg is not None,
            'core sensor message': core is not None,
        }

        for label, passed in required_ready.items():
            print_result(label, 'ready' if passed else 'missing', passed)

        if not all(required_ready.values()):
            print('\nGetter test stopped because required source data is missing.')
            return

        x, y, yaw = robot.getOdomData()
        print_result('getOdomData()', f'x={x:.3f}, y={y:.3f}, yaw={yaw:.2f}')

        dx, dy, dyaw = robot.getTravelDist()
        print_result('getTravelDist()', f'dx={dx:.3f}, dy={dy:.3f}, dyaw={dyaw:.2f}')

        bumper_status = robot.getBumperStatus()
        print_result('getBumperStatus()', bumper_status)

        wheel_drop_status = robot.getWheelDropStatus()
        print_result('getWheelDropStatus()', wheel_drop_status)

        cliff_status = robot.getCliffStatus()
        print_result('getCliffStatus()', cliff_status)

        wheel_drop_event = robot.hasWheelDrop()
        print_result('hasWheelDrop()', wheel_drop_event)

        image, image_count = robot.getImage()
        print_result(
            'getImage()',
            f'shape={image.shape}, count={image_count}',
            image is not None and len(image.shape) >= 2,
        )

        depth = robot.getDepth()
        print_result(
            'getDepth()',
            f'shape={depth.shape}',
            depth is not None and len(depth.shape) >= 2,
        )

        print('\nGetter methods needed by matchPlanner are callable.')
    finally:
        robot.shutdown()


if __name__ == '__main__':
    main()

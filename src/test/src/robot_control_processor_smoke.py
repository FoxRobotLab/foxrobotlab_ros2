#!/usr/bin/env python3

import sys
import time

from robot_core import RobotControlProcessor


TIMEOUT_SEC = 20.0


def main():
    processor = RobotControlProcessor(spin_in_background=True)
    logger = processor.get_logger()
    logger.info("RobotControlProcessor smoke test started.")

    deadline = time.monotonic() + TIMEOUT_SEC
    while time.monotonic() < deadline:
        ready = {
            "odom": processor.odom_msg is not None,
            "color_image": processor.imageColor_msg is not None,
            "depth_image": processor.imageDepth_msg is not None,
            "battery": processor.battery_msg is not None,
            "core": processor.core_msg is not None,
            "safety": processor.safety_msg is not None,
        }
        missing = [name for name, is_ready in ready.items() if not is_ready]
        if not missing:
            break
        logger.info(f"Waiting for modular processor inputs: {', '.join(missing)}")
        time.sleep(1.0)

    failed = False
    checks = {
        "odom": processor.odom_msg is not None,
        "color_image": processor.imageColor_msg is not None,
        "depth_image": processor.imageDepth_msg is not None,
        "battery": processor.battery_msg is not None,
        "core": processor.core_msg is not None,
        "safety": processor.safety_msg is not None,
    }

    for name, passed in checks.items():
        if passed:
            logger.info(f"PASS {name}")
        else:
            logger.error(f"FAIL {name}")
            failed = True

    if not failed:
        odom = processor.getOdomData()
        image, image_count = processor.getImage()
        depth = processor.getDepth()
        processor.move(0.0, 0.0)
        processor.stop()

        logger.info(f"PASS getOdomData returned {odom}")
        logger.info(f"PASS getImage returned shape={image.shape} count={image_count}")
        logger.info(f"PASS getDepth returned shape={depth.shape}")
        logger.info("PASS zero command published through /robot/apps/cmd_vel")

    processor.shutdown()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

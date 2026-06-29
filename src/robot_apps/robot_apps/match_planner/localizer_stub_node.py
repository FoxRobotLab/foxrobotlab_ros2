#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from lab_interfaces.srv import MatchLocalize


class LocalizerStubNode(Node):
    def __init__(self):
        super().__init__(
            "localizer_stub_node",
            automatically_declare_parameters_from_overrides=True,
        )

        # match_planner.yaml is the source of truth for service names.
        localize_service = self.get_parameter("localize_service").value

        # ------------------- Initialize Services -------------------
        self.localize_service = self.create_service(
            MatchLocalize,
            localize_service,
            self.localize_callback,
        )

        self.get_logger().info(
            f"Localizer stub ready on {localize_service}; returning no-match responses."
        )

    # ------------------- Service Callbacks -------------------
    def localize_callback(self, request, response):
        response.matched = False
        response.status = "localizer stub active; no match produced"
        response.node = -1
        response.x = request.odom_x
        response.y = request.odom_y
        response.yaw = request.odom_yaw
        response.confidence = 0.0
        return response


def main(args=None):
    rclpy.init(args=args)
    node = LocalizerStubNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

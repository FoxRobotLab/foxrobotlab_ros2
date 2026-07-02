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
        self.stub_matched = bool(self._param_value("stub_matched", False))
        self.stub_node = int(self._param_value("stub_node", -1))
        self.stub_x = float(self._param_value("stub_x", 0.0))
        self.stub_y = float(self._param_value("stub_y", 0.0))
        self.stub_yaw = float(self._param_value("stub_yaw", 0.0))
        self.stub_confidence = float(self._param_value("stub_confidence", 0.0))
        self.stub_status = self._param_value(
            "stub_status",
            "localizer stub active; no match produced",
        )
        self.stub_node_sequence = self._param_list("stub_node_sequence")
        self.stub_x_sequence = self._param_list("stub_x_sequence")
        self.stub_y_sequence = self._param_list("stub_y_sequence")
        self.stub_yaw_sequence = self._param_list("stub_yaw_sequence")
        self.stub_confidence_sequence = self._param_list("stub_confidence_sequence")
        self.stub_status_sequence = self._param_list("stub_status_sequence")
        self.request_count = 0

        # ------------------- Initialize Services -------------------
        self.localize_service = self.create_service(
            MatchLocalize,
            localize_service,
            self.localize_callback,
        )

        self.get_logger().info(
            f"Localizer stub ready on {localize_service}; deterministic stub enabled."
        )

    # ------------------- Service Callbacks -------------------
    def localize_callback(self, request, response):
        stub = self._next_stub_response(request)
        response.matched = stub["matched"]
        response.status = stub["status"]
        response.node = stub["node"]
        response.x = stub["x"]
        response.y = stub["y"]
        response.yaw = stub["yaw"]
        response.confidence = stub["confidence"]
        return response

    # ------------------- Helper Functions -------------------
    def _next_stub_response(self, request):
        if self.stub_node_sequence:
            index = min(self.request_count, len(self.stub_node_sequence) - 1)
            self.request_count += 1
            node = int(self.stub_node_sequence[index])
            return {
                "matched": node >= 0,
                "status": self._sequence_value(
                    self.stub_status_sequence,
                    index,
                    f"localizer stub matched node {node}",
                ),
                "node": node,
                "x": float(self._sequence_value(self.stub_x_sequence, index, request.odom_x)),
                "y": float(self._sequence_value(self.stub_y_sequence, index, request.odom_y)),
                "yaw": float(
                    self._sequence_value(self.stub_yaw_sequence, index, request.odom_yaw)
                ),
                "confidence": float(
                    self._sequence_value(
                        self.stub_confidence_sequence,
                        index,
                        self.stub_confidence,
                    )
                ),
            }

        if self.stub_matched:
            return {
                "matched": True,
                "status": self.stub_status,
                "node": self.stub_node,
                "x": self.stub_x,
                "y": self.stub_y,
                "yaw": self.stub_yaw,
                "confidence": self.stub_confidence,
            }

        return {
            "matched": False,
            "status": self.stub_status,
            "node": -1,
            "x": request.odom_x,
            "y": request.odom_y,
            "yaw": request.odom_yaw,
            "confidence": 0.0,
        }

    def _sequence_value(self, sequence, index, default):
        if not sequence:
            return default
        return sequence[min(index, len(sequence) - 1)]

    def _param_value(self, name, default):
        if not self.has_parameter(name):
            return default
        value = self.get_parameter(name).value
        if value is None:
            return default
        return value

    def _param_list(self, name):
        value = self._param_value(name, [])
        return list(value) if value is not None else []


def main(args=None):
    rclpy.init(args=args)
    node = LocalizerStubNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

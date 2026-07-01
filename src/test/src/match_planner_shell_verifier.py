#!/usr/bin/env python3

import sys

import rclpy
from rclpy.node import Node

from lab_interfaces.msg import MatchPlannerStatus
from lab_interfaces.srv import SetMatchPlannerGoal, SetMatchPlannerStart


QOS = 10


class MatchPlannerShellVerifier(Node):
    def __init__(self):
        super().__init__(
            "match_planner_shell_verifier",
            automatically_declare_parameters_from_overrides=True,
        )

        self.timeout_sec = float(self.get_parameter("timeout_sec").value)
        self.exit_on_finish = bool(self.get_parameter("exit_on_finish").value)
        report_period_sec = float(self.get_parameter("report_period_sec").value)

        self.status_topic = self.get_parameter("status_topic").value
        self.set_start_service_name = self.get_parameter("set_start_service").value
        self.set_goal_service_name = self.get_parameter("set_goal_service").value
        self.start_node = int(self.get_parameter("start_node").value)
        self.destination_node = int(self.get_parameter("destination_node").value)
        self.require_dry_run_decision = bool(
            self.get_parameter("require_dry_run_decision").value
        )
        self.require_arrival = bool(self.get_parameter("require_arrival").value)
        self.require_turn_intent = bool(
            self.get_parameter("require_turn_intent").value
        )
        self.require_guarded_turn_result = bool(
            self.get_parameter("require_guarded_turn_result").value
        )

        self.finished = False
        self.failed = False
        self.start_time = self.get_clock().now()
        self.status_count = 0
        self.last_status = None
        self.saw_active_goal = False
        self.saw_dry_run_decision = False
        self.saw_arrival = False
        self.saw_turn_intent = False
        self.saw_guarded_turn_result = False
        self.start_response = None
        self.goal_response = None
        self.start_future = None
        self.goal_future = None

        self.set_start_client = self.create_client(
            SetMatchPlannerStart,
            self.set_start_service_name,
        )
        self.set_goal_client = self.create_client(
            SetMatchPlannerGoal,
            self.set_goal_service_name,
        )

        self.create_subscription(
            MatchPlannerStatus,
            self.status_topic,
            self._status_callback,
            QOS,
        )

        self.create_timer(0.25, self._drive_verification)
        self.create_timer(report_period_sec, self._report_progress)

        self.get_logger().info(
            "Match planner shell verifier started. "
            "This test uses services and received status messages, not ros2 topic list."
        )

    # ------------------- Callbacks -------------------
    def _status_callback(self, msg):
        self.status_count += 1
        self.last_status = msg
        if (
            msg.current_node == self.start_node
            and msg.destination_node == self.destination_node
            and msg.navigation_active
        ):
            self.saw_active_goal = True
        if "movement disabled; would" in msg.status_message:
            self.saw_dry_run_decision = True
        if "would turn" in msg.status_message or "turn toward node" in msg.status_message:
            self.saw_turn_intent = True
        if "guarded turn completed" in msg.status_message or "guarded turn timed out" in msg.status_message:
            self.saw_guarded_turn_result = True
        if (
            msg.current_node == self.destination_node
            and msg.destination_node == self.destination_node
            and msg.next_node == -1
            and not msg.navigation_active
            and "arrived" in msg.status_message
        ):
            self.saw_arrival = True
        if self.status_count == 1:
            self.get_logger().info(f"PASS receive planner status: {self.status_topic}")

    def _drive_verification(self):
        if self.finished:
            return

        if not self._services_ready():
            self._check_timeout()
            return

        if self.start_future is None:
            self._call_set_start()
            return

        if self.start_response is None:
            self._read_start_response()
            self._check_timeout()
            return

        if self.goal_future is None:
            self._call_set_goal()
            return

        if self.goal_response is None:
            self._read_goal_response()
            self._check_timeout()
            return

        if self._verification_passed():
            self.finished = True
            self.get_logger().info("MATCH PLANNER SHELL VERIFICATION PASSED.")
            self._print_summary()
            return

        self._check_timeout()

    # ------------------- Service Helpers -------------------
    def _services_ready(self):
        return (
            self.set_start_client.service_is_ready()
            and self.set_goal_client.service_is_ready()
        )

    def _call_set_start(self):
        request = SetMatchPlannerStart.Request()
        request.use_current_pose = False
        request.node = self.start_node
        request.x = 0.0
        request.y = 0.0
        request.yaw = 0.0
        self.start_future = self.set_start_client.call_async(request)
        self.get_logger().info(f"Calling set_start with node {self.start_node}")

    def _call_set_goal(self):
        request = SetMatchPlannerGoal.Request()
        request.destination_node = self.destination_node
        self.goal_future = self.set_goal_client.call_async(request)
        self.get_logger().info(f"Calling set_goal with node {self.destination_node}")

    def _read_start_response(self):
        if not self.start_future.done():
            return

        self.start_response = self.start_future.result()
        if self.start_response.accepted:
            self.get_logger().info(f"PASS set_start: {self.start_response.message}")
        else:
            self.get_logger().error(f"FAIL set_start: {self.start_response.message}")

    def _read_goal_response(self):
        if not self.goal_future.done():
            return

        self.goal_response = self.goal_future.result()
        if self.goal_response.accepted:
            self.get_logger().info(f"PASS set_goal: {self.goal_response.message}")
        else:
            self.get_logger().error(f"FAIL set_goal: {self.goal_response.message}")

    # ------------------- Verification Helpers -------------------
    def _verification_passed(self):
        if self.start_response is None or self.goal_response is None:
            return False
        if not self.start_response.accepted or not self.goal_response.accepted:
            return False
        if self.last_status is None:
            return False

        if self.require_dry_run_decision and not self.saw_dry_run_decision:
            return False
        if self.require_turn_intent and not self.saw_turn_intent:
            return False
        if self.require_guarded_turn_result and not self.saw_guarded_turn_result:
            return False
        if self.require_arrival:
            return self.saw_arrival and self.last_status.movement_paused

        return self.saw_active_goal and self.last_status.movement_paused

    def _check_timeout(self):
        elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1_000_000_000.0
        if elapsed < self.timeout_sec:
            return

        self.finished = True
        self.failed = True
        self.get_logger().error("MATCH PLANNER SHELL VERIFICATION FAILED: timed out.")
        self._print_summary()

    def _report_progress(self):
        if self.finished:
            return

        waiting = []
        if not self._services_ready():
            waiting.append("start/goal services")
        if self.status_count == 0:
            waiting.append("status messages")
        if self.start_response is None:
            waiting.append("set_start response")
        if self.goal_response is None:
            waiting.append("set_goal response")
        if self.require_dry_run_decision and not self.saw_dry_run_decision:
            waiting.append("dry-run movement decision")
        if self.require_turn_intent and not self.saw_turn_intent:
            waiting.append("turn intent")
        if self.require_guarded_turn_result and not self.saw_guarded_turn_result:
            waiting.append("guarded turn result")
        if self.require_arrival and not self.saw_arrival:
            waiting.append("arrival status")

        if waiting:
            self.get_logger().info(
                f"Match planner verifier waiting for: {', '.join(waiting)}"
            )

    def _print_summary(self):
        status_seen = self.status_count > 0
        start_ok = self.start_response is not None and self.start_response.accepted
        goal_ok = self.goal_response is not None and self.goal_response.accepted
        state_ok = self._verification_passed()

        self.get_logger().info(
            f"{'PASS' if status_seen else 'FAIL'} status received: "
            f"{self.status_topic} count={self.status_count}"
        )
        self.get_logger().info(
            f"{'PASS' if start_ok else 'FAIL'} set_start service: "
            f"{self.set_start_service_name}"
        )
        self.get_logger().info(
            f"{'PASS' if goal_ok else 'FAIL'} set_goal service: "
            f"{self.set_goal_service_name}"
        )
        self.get_logger().info(
            f"{'PASS' if self.saw_active_goal else 'FAIL'} planner active state reached "
            f"start={self.start_node}, goal={self.destination_node}"
        )
        if self.require_dry_run_decision:
            self.get_logger().info(
                f"{'PASS' if self.saw_dry_run_decision else 'FAIL'} "
                "dry-run movement decision observed"
            )
        if self.require_turn_intent:
            self.get_logger().info(
                f"{'PASS' if self.saw_turn_intent else 'FAIL'} "
                "turn intent observed"
            )
        if self.require_guarded_turn_result:
            self.get_logger().info(
                f"{'PASS' if self.saw_guarded_turn_result else 'FAIL'} "
                "guarded turn result observed"
            )
        if self.require_arrival:
            self.get_logger().info(
                f"{'PASS' if self.saw_arrival else 'FAIL'} arrival status observed"
            )
        self.get_logger().info(
            f"{'PASS' if state_ok else 'FAIL'} verifier acceptance criteria"
        )


def main(args=None):
    rclpy.init(args=args)
    node = MatchPlannerShellVerifier()

    while rclpy.ok() and not (node.exit_on_finish and node.finished):
        rclpy.spin_once(node, timeout_sec=0.1)

    failed = node.failed
    node.destroy_node()
    rclpy.shutdown()
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

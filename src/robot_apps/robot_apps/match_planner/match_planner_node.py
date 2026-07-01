#!/usr/bin/env python3

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from lab_interfaces.msg import MatchPlannerStatus
from lab_interfaces.srv import MatchLocalize, SetMatchPlannerGoal, SetMatchPlannerStart
from robot_core import RobotControlProcessor
from robot_apps.match_planner.planner_core import PlannerCore


QOS = 10


class MatchPlannerNode(Node):
    def __init__(self):
        super().__init__(
            "match_planner_node",
            automatically_declare_parameters_from_overrides=True,
        )

        # match_planner.yaml is the source of truth for app parameters.
        self.status_topic = self.get_parameter("status_topic").value
        self.set_start_service_name = self.get_parameter("set_start_service").value
        self.set_goal_service_name = self.get_parameter("set_goal_service").value
        self.localize_service_name = self.get_parameter("localize_service").value
        self.match_loop_period_sec = float(
            self.get_parameter("match_loop_period_sec").value
        )
        self.start_paused = bool(self.get_parameter("start_paused").value)
        self.localize_while_idle = bool(
            self.get_parameter("localize_while_idle").value
        )
        self.load_map = bool(self.get_parameter("load_map").value)
        self.log_to_file = bool(self.get_parameter("log_to_file").value)
        self.log_to_console = bool(self.get_parameter("log_to_console").value)
        self.enable_movement = bool(self.get_parameter("enable_movement").value)
        self.enable_turning = bool(self.get_parameter("enable_turning").value)
        self.enable_potential_field = bool(
            self.get_parameter("enable_potential_field").value
        )
        self.turn_threshold_deg = float(self.get_parameter("turn_threshold_deg").value)
        self.hard_turn_threshold_deg = float(
            self.get_parameter("hard_turn_threshold_deg").value
        )
        self.depth_image_width = int(self.get_parameter("depth_image_width").value)
        self.depth_image_height = int(self.get_parameter("depth_image_height").value)
        self.turn_timeout_sec = float(self.get_parameter("turn_timeout_sec").value)
        self.max_turn_angle_deg = float(self.get_parameter("max_turn_angle_deg").value)

        self.planner = PlannerCore(
            start_paused=self.start_paused,
            localize_while_idle=self.localize_while_idle,
            load_map=self.load_map,
            log_to_file=self.log_to_file,
            log_to_console=self.log_to_console,
            turn_threshold_deg=self.turn_threshold_deg,
            hard_turn_threshold_deg=self.hard_turn_threshold_deg,
        )
        self.localize_request_active = False
        self.brain = None
        self.goal_seeker = None

        # ------------------- Initialize Robot Control -------------------
        # Keep the robot stopped while the Phase 4 planner shell is being proven.
        self.robot = RobotControlProcessor(spin_in_background=False)
        if self.start_paused:
            self.robot.pauseMovement()

        if self.enable_movement and self.enable_potential_field:
            self.initialize_potential_field()

        # ------------------- Initialize Publishers -------------------
        self.status_pub = self.create_publisher(
            MatchPlannerStatus,
            self.status_topic,
            QOS,
        )

        # ------------------- Initialize Services -------------------
        self.set_start_service = self.create_service(
            SetMatchPlannerStart,
            self.set_start_service_name,
            self.set_start_callback,
        )
        self.set_goal_service = self.create_service(
            SetMatchPlannerGoal,
            self.set_goal_service_name,
            self.set_goal_callback,
        )

        # ------------------- Initialize Clients -------------------
        self.localize_client = self.create_client(
            MatchLocalize,
            self.localize_service_name,
        )

        # ------------------- Initialize Timers -------------------
        self.create_timer(self.match_loop_period_sec, self.timer_callback)

        self.get_logger().info(
            f"Match planner node started. Publishing status on {self.status_topic}."
        )

    # ------------------- Timer Callbacks -------------------
    def timer_callback(self):
        self.publish_status()

        if self.localize_request_active:
            return

        if not self.planner.should_request_localization():
            return

        if not self.localize_client.service_is_ready():
            self.planner.set_status_message("waiting for localizer service")
            return

        self.request_localization()

    def localize_done_callback(self, future):
        self.localize_request_active = False

        try:
            response = future.result()
        except Exception as error:
            self.planner.set_status_message(f"localizer call failed: {error}")
            return

        decision = self.planner.apply_localization(response)
        self.execute_navigation_decision(decision)
        self.publish_status()

    # ------------------- Service Callbacks -------------------
    def set_start_callback(self, request, response):
        response.accepted, response.message = self.planner.set_start(request)
        return response

    def set_goal_callback(self, request, response):
        response.accepted, response.message = self.planner.set_goal(request)
        return response

    # ------------------- Helper Functions -------------------
    def request_localization(self):
        odom_x, odom_y, odom_yaw = self.robot.getOdomData()

        request = MatchLocalize.Request()
        request.odom_x = odom_x
        request.odom_y = odom_y
        request.odom_yaw = odom_yaw

        self.localize_request_active = True
        future = self.localize_client.call_async(request)
        future.add_done_callback(self.localize_done_callback)

    def publish_status(self):
        msg = MatchPlannerStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.mode = "planner_core"
        msg.status_message = self.planner.status_message
        msg.current_node = self.planner.current_node
        msg.next_node = self.planner.next_node
        msg.destination_node = self.planner.destination_node
        msg.confidence = self.planner.confidence
        msg.navigation_active = self.planner.navigation_active
        msg.movement_paused = self.planner.movement_paused

        self.status_pub.publish(msg)

    def execute_navigation_decision(self, decision):
        if decision is None:
            return

        if not self.enable_movement:
            self.pause_potential_field()
            if decision.should_stop:
                self.planner.set_status_message(
                    f"movement disabled; would stop: {decision.message}"
                )
            elif decision.should_turn:
                self.planner.set_status_message(
                    f"movement disabled; would turn {decision.turn_angle:.2f} deg "
                    f"toward node {decision.next_node}"
                )
            elif decision.use_potential_field:
                self.planner.set_status_message(
                    f"movement disabled; would track node {decision.next_node}: "
                    f"{decision.message}"
                )
            return

        if decision.should_stop:
            self.pause_potential_field()
            self.robot.stop()
            self.robot.pauseMovement()
            self.planner.movement_paused = True
            self.planner.set_status_message(decision.message)
            return

        if decision.should_turn:
            self.pause_potential_field()
            if self.enable_turning:
                turn_angle = self.limit_turn_angle(decision.turn_angle)
                self.robot.unpauseMovement()
                self.planner.movement_paused = False
                turn_reached = self.robot.turnByAngle(
                    turn_angle,
                    timeout_sec=self.turn_timeout_sec,
                )
                self.robot.pauseMovement()
                self.planner.movement_paused = True
                if turn_reached:
                    self.planner.set_status_message(
                        f"guarded turn completed: turned {turn_angle:.2f} deg "
                        f"toward node {decision.next_node}"
                    )
                else:
                    self.planner.set_status_message(
                        f"guarded turn timed out after {self.turn_timeout_sec:.2f}s: "
                        f"commanded {turn_angle:.2f} deg toward node "
                        f"{decision.next_node}"
                    )
            else:
                self.planner.set_status_message(
                    f"turning disabled; would turn {decision.turn_angle:.2f} deg "
                    f"toward node {decision.next_node}"
                )
            return

        if decision.use_potential_field:
            if self.enable_potential_field and self.goal_seeker is not None:
                self.robot.unpauseMovement()
                self.planner.movement_paused = False
                current_heading = (
                    self.planner.current_pose[2]
                    if self.planner.current_pose is not None
                    else 0.0
                )
                self.goal_seeker.setGoal(
                    decision.target_distance,
                    decision.target_heading,
                    current_heading,
                )
                self.unpause_potential_field()
                self.planner.set_status_message(decision.message)
            else:
                self.pause_potential_field()
                self.planner.set_status_message(
                    f"potential field disabled; would track node {decision.next_node}: "
                    f"{decision.message}"
                )

    def limit_turn_angle(self, turn_angle):
        if self.max_turn_angle_deg <= 0:
            return turn_angle
        if turn_angle > self.max_turn_angle_deg:
            return self.max_turn_angle_deg
        if turn_angle < -self.max_turn_angle_deg:
            return -self.max_turn_angle_deg
        return turn_angle

    def initialize_potential_field(self):
        from robot_apps.match_planner import FieldBehaviors
        from robot_apps.match_planner.PotentialFieldThread import PotentialFieldBrain

        self.brain = PotentialFieldBrain(self.robot)
        self.brain.pause()
        self.brain.add(FieldBehaviors.KeepMoving())
        self.brain.add(FieldBehaviors.BumperReact())
        self.brain.add(FieldBehaviors.CliffReact())
        self.goal_seeker = FieldBehaviors.seekGoal()
        self.brain.add(self.goal_seeker)

        num_pieces = 6
        width_pieces = int(self.depth_image_width / float(num_pieces))
        speed_multiplier = 50
        for index in range(0, num_pieces):
            self.brain.add(
                FieldBehaviors.ObstacleForce(
                    index * width_pieces,
                    width_pieces / 2,
                    speed_multiplier,
                    self.depth_image_width,
                    self.depth_image_height,
                )
            )

        self.brain.start()
        self.brain.pause()

    def pause_potential_field(self):
        if self.goal_seeker is not None:
            self.goal_seeker.setGoal(None, None, None)
        if self.brain is not None:
            self.brain.pause()

    def unpause_potential_field(self):
        if self.brain is not None:
            self.brain.unpause()

    def destroy_node(self):
        if self.brain is not None:
            self.brain.stop()
        self.robot.shutdown()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = MatchPlannerNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    executor.add_node(node.robot)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

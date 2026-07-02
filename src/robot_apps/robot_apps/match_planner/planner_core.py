"""Plain Python state and path logic for the Phase 4 match planner."""

from dataclasses import dataclass


@dataclass
class NavigationDecision:
    state: str = "idle"
    next_node: int = -1
    target_heading: float = 0.0
    target_distance: float = 0.0
    turn_angle: float = 0.0
    arrived: bool = False
    should_stop: bool = False
    should_turn: bool = False
    use_potential_field: bool = False
    message: str = "waiting for start and goal"


class PlannerCore:
    def __init__(
        self,
        start_paused=True,
        localize_while_idle=False,
        load_map=True,
        log_to_file=True,
        log_to_console=True,
        turn_threshold_deg=30.0,
        hard_turn_threshold_deg=90.0,
    ):
        self.current_node = -1
        self.next_node = -1
        self.destination_node = -1
        self.confidence = 0.0
        self.navigation_active = False
        self.movement_paused = start_paused
        self.status_message = "match planner node started; waiting for start and goal"

        self.localize_while_idle = localize_while_idle
        self.world_map = None
        self.path_location = None
        self.path_load_error = None
        self.current_pose = None
        self.ignore_location_count = 0
        self.turn_threshold_deg = turn_threshold_deg
        self.hard_turn_threshold_deg = hard_turn_threshold_deg
        self.last_decision = NavigationDecision(
            state="idle",
            message=self.status_message,
        )

        if load_map:
            self._load_path_modules(log_to_file, log_to_console)

    # ------------------- Service State Changes -------------------
    def set_start(self, request):
        if request.use_current_pose:
            message = "start set from current pose placeholder"
        elif request.node >= 0:
            if not self._valid_node(request.node):
                return False, f"invalid start node {request.node}"
            self.current_node = request.node
            message = f"start node set to {request.node}"
        else:
            message = self._set_start_from_pose(request.x, request.y, request.yaw)

        self._update_route_from_current()
        self.status_message = message
        return True, message

    def set_goal(self, request):
        if request.destination_node == -1:
            self.destination_node = -1
            self.next_node = -1
            self.navigation_active = False
            self.path_location = None
            self.last_decision = NavigationDecision(
                state="idle",
                should_stop=True,
                message="goal cleared; navigation inactive",
            )
            message = "goal cleared; navigation inactive"
            self.status_message = message
            return True, message

        if request.destination_node < 0:
            message = "invalid destination node"
            self.status_message = message
            return False, message

        if not self._valid_node(request.destination_node):
            message = f"invalid destination node {request.destination_node}"
            self.status_message = message
            return False, message

        self.destination_node = request.destination_node
        self.navigation_active = True
        self._begin_path()
        self._update_route_from_current()

        if self.next_node >= 0:
            message = (
                f"goal set to node {request.destination_node}; "
                f"next node {self.next_node}"
            )
        else:
            message = f"goal set to node {request.destination_node}"

        self.status_message = message
        return True, message

    # ------------------- Localization State Changes -------------------
    def should_request_localization(self):
        return self.navigation_active or self.localize_while_idle

    def apply_localization(self, response):
        self.confidence = float(response.confidence)

        if not response.matched:
            message = response.status or "localizer returned no match"
            self.status_message = message
            self.last_decision = NavigationDecision(
                state="localizing",
                message=message,
            )
            return self.last_decision

        self.current_node = response.node
        self.current_pose = (response.x, response.y, response.yaw)
        decision = self._plan_from_current_localization()

        if response.status and decision.state in ["idle", "localizing"]:
            decision.message = response.status
            self.status_message = response.status

        self.last_decision = decision
        return decision

    def set_status_message(self, message):
        self.status_message = message
        self.last_decision.message = message

    # ------------------- Navigation Decisions -------------------
    def _plan_from_current_localization(self):
        if not self.navigation_active:
            message = "localized while navigation inactive"
            self.status_message = message
            return NavigationDecision(
                state="idle",
                next_node=self.next_node,
                message=message,
            )

        self._update_route_from_current()

        if self.current_node == self.destination_node:
            self.navigation_active = False
            self.next_node = -1
            message = f"arrived at destination node {self.destination_node}"
            self.status_message = message
            return NavigationDecision(
                state="arrived",
                next_node=-1,
                arrived=True,
                should_stop=True,
                message=message,
            )

        self._record_path_progress()
        decision = self._choose_next_target()
        self.status_message = decision.message
        return decision

    def _record_path_progress(self):
        if self.path_location is None or self.current_node < 0:
            return

        self.ignore_location_count += 1
        if (
            self.path_location.visitNewNode(self.current_node)
            or self.ignore_location_count > 50
        ):
            self.ignore_location_count = 0
            self.path_location.continueJourney(self.current_node)

    def _choose_next_target(self):
        if self.world_map is None or self.path_location is None:
            message = "navigation active; map/path modules unavailable"
            return NavigationDecision(
                state="path_unavailable",
                message=message,
            )

        curr_path = self.path_location.getCurrentPath()
        if curr_path is None or curr_path == []:
            message = "navigation active; waiting for path"
            return NavigationDecision(
                state="waiting_for_path",
                message=message,
            )

        if len(curr_path) < 2:
            message = "path has no next node"
            return NavigationDecision(
                state="waiting_for_path",
                message=message,
            )

        near_node = self.current_node
        curr_loc = self.current_pose
        just_visited_node = curr_path[0]
        immediate_goal_node = curr_path[1]
        next_node = immediate_goal_node

        if near_node == just_visited_node or near_node == immediate_goal_node:
            next_node = immediate_goal_node
        elif near_node in curr_path:
            path_index = curr_path.index(near_node)
            if len(curr_path) > path_index + 1:
                next_node = curr_path[path_index + 1]
            else:
                next_node = near_node
        elif self.world_map.areNeighbors(near_node, immediate_goal_node):
            next_node = immediate_goal_node
        elif self.world_map.areNeighbors(near_node, just_visited_node):
            next_node = just_visited_node
        else:
            next_node = immediate_goal_node

        target_heading = self.world_map.calcAngle(curr_loc, next_node)
        target_distance = self.world_map.straightDist2d(curr_loc, next_node)
        turn_angle = self._angle_to_turn(curr_loc[2], target_heading)
        self.next_node = next_node

        if target_distance < 1.5:
            message = (
                f"tracking next node {next_node}; target distance "
                f"{target_distance:.2f} below turn threshold"
            )
            return NavigationDecision(
                state="tracking",
                next_node=next_node,
                target_heading=target_heading,
                target_distance=target_distance,
                turn_angle=turn_angle,
                use_potential_field=True,
                message=message,
            )

        if abs(turn_angle) >= self.turn_threshold_deg:
            state = "hard_turn" if abs(turn_angle) >= self.hard_turn_threshold_deg else "turn"
            message = (
                f"turn toward node {next_node}: angle {turn_angle:.2f}, "
                f"target distance {target_distance:.2f}"
            )
            return NavigationDecision(
                state=state,
                next_node=next_node,
                target_heading=target_heading,
                target_distance=target_distance,
                turn_angle=turn_angle,
                should_turn=True,
                message=message,
            )

        message = (
            f"continue toward node {next_node}: angle {turn_angle:.2f}, "
            f"target distance {target_distance:.2f}"
        )
        return NavigationDecision(
            state="tracking",
            next_node=next_node,
            target_heading=target_heading,
            target_distance=target_distance,
            turn_angle=turn_angle,
            use_potential_field=True,
            message=message,
        )

    # ------------------- Path Helpers -------------------
    def _load_path_modules(self, log_to_file, log_to_console):
        try:
            from robot_apps.match_planner.OlinWorldMap import WorldMap
            from robot_apps.match_planner.OutputLogger import OutputLogger
            from robot_apps.match_planner.PathLocation import PathLocation

            logger = OutputLogger(toFile=log_to_file, toConsole=log_to_console)
            self.world_map = WorldMap()
            self.path_location = PathLocation(self.world_map, logger)
            self.status_message = "match planner map loaded; waiting for start and goal"
        except Exception as error:
            self.path_load_error = str(error)
            self.world_map = None
            self.path_location = None
            self.status_message = f"map/path modules unavailable: {error}"

    def _set_start_from_pose(self, x, y, yaw):
        if self.world_map is not None:
            closest_node, _, _, distance = self.world_map.findClosestNode((x, y, yaw))
            self.current_node = closest_node
            return (
                f"start pose mapped to node {closest_node} "
                f"from x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}, distance={distance:.2f}"
            )

        return f"start pose set to x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}"

    def _begin_path(self):
        if self.world_map is None:
            return

        from robot_apps.match_planner.PathLocation import PathLocation

        logger = self.path_location.logger if self.path_location is not None else None
        if logger is None:
            from robot_apps.match_planner.OutputLogger import OutputLogger

            logger = OutputLogger(toFile=False, toConsole=False)
        self.path_location = PathLocation(self.world_map, logger)
        self.path_location.beginJourney(self.destination_node)

    def _update_route_from_current(self):
        self.next_node = -1
        if (
            self.world_map is None
            or self.path_location is None
            or not self.navigation_active
            or self.current_node < 0
            or self.destination_node < 0
        ):
            return

        if self.current_node == self.destination_node:
            self.navigation_active = False
            return

        try:
            path = self.world_map.getShortestPath(self.current_node, self.destination_node)
        except Exception as error:
            self.status_message = f"path planning failed: {error}"
            return

        self.path_location.goalPath = path
        if len(path) > 1:
            self.next_node = path[1]

    def _angle_to_turn(self, current_heading, target_heading):
        angle_to_turn = target_heading - (current_heading % 360)
        if angle_to_turn < -180:
            angle_to_turn += 360
        elif 180 < angle_to_turn:
            angle_to_turn -= 360
        return angle_to_turn

    def _valid_node(self, node):
        if self.world_map is None:
            return node >= 0
        return self.world_map.isValidNode(node)

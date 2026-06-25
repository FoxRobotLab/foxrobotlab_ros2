# FoxRobotLab ROS 2 Modular Architecture

This workspace is being migrated from the older `foxrobotlab_ros2` package into a modular robot architecture for Macalester robotics research.

The long-term goal is to let TurtleBot2, TurtleBot4, Gazebo simulation, and future robots use the same upper-level software. Robot-specific code should stay in low-level driver and adapter layers, reusable robot services should live in the middle layers, and experiment-specific behavior should live in application packages.

This refactor is inspired by a layered operating-system style architecture:

```text
Hardware / Simulation
  -> Adapters
  -> Common Internal Interface
  -> Frameworks / Services
  -> Robot Applications
```

## Current Phase

Phase 2 is proving that `robot_adapters/tb2_adapter.py` can replace the forwarding behavior of `foxrobotlab_ros2/src/turtle_control_reciever.py`.

Current Phase 2 goal:

- Publish new common `/robot/...` sensor topics.
- Temporarily keep `/foxrobotlab/raw/...` compatibility topics alive for old code.
- Keep native topic names in adapter YAML files.
- Do not change legacy launch files until adapter equivalence has been tested on hardware.

## Current Packages

- `lab_interfaces`: shared messages and future services for the common interface.
- `robot_adapters`: converts native robot topics to common `/robot/...` topics.
- `robot_core`: reusable robot-agnostic services such as state processing and safety monitoring.
- `robot_bringup`: launch files for starting low-level infrastructure.
- `robot_apps`: application-level tests and future experiments.
- `foxrobotlab_ros2`: legacy working code retained during migration.
- `ThirdParty/*`: imported drivers and support libraries.

## Planned Package Layout

Future package layout under `src/`:

```text
Hardware / Simulation
  robot_description/
    urdf/
    meshes/
    config/
    launch/
  robot_simulation/
    launch/
    worlds/
    models/
    config/
  hardware driver packages

Adapter Layer
  robot_adapters/
    src/
    config/
    launch/

Internal Interface Layer
  lab_interfaces/
    msg/
    srv/

Framework / Service Layer
  robot_bringup/
    launch/
    config/
  robot_core/
    src/
    config/
    launch/
  robot_navigation/
    launch/
    config/
    maps/
    rviz/
  robot_ml/
    scripts/
    config/
    launch/
    models/

Application Layer
  robot_apps/
    launch/
    config/
    src/

Cross Layer Resources
  robot_res/
    maps/
    labels/
    images/
    bags/
    logs/
```

Package purpose:

- `robot_description`: robot URDF, meshes, and description configuration.
- `robot_simulation`: Gazebo or other simulation worlds, models, and launch files.
- `robot_adapters`: native robot topics become common `/robot/...` topics.
- `lab_interfaces`: shared messages and services used across the architecture.
- `robot_core`: reusable robot services that are not tied to one robot model.
- `robot_navigation`: future Nav2 localization and navigation configuration.
- `robot_ml`: future camera/CNN/localization model integration.
- `robot_res`: maps, labels, datasets, bags, logs, and shared research artifacts.
- `robot_bringup`: low-level system launch orchestration.
- `robot_apps`: specific experiments, tests, demos, and application workflows.

## Common Topics

The TurtleBot2 adapter currently exposes:

```text
/robot/odom
/robot/imu
/robot/battery
/robot/kobuki/core
/robot/camera/color/image_raw
/robot/camera/depth/image_raw
/robot/cmd_vel
/robot/safety_status
/robot/state
```

Optional topics are exposed only when the robot configuration says the hardware exists. For the current TurtleBot2 base, `has_lidar: false`, so `/robot/scan` is not published unless a lidar is added and enabled in `tb2_topics.yaml`. `robot_core` also leaves scan consumption off by default with `use_scan: false`.

The current `tb2_topics.yaml` capability block matches what `foxrobotlab_ros2` uses today: odometry, IMU, color/depth camera, battery, Kobuki core sensors, bumper, cliff, and wheel-drop events. Lidar, docking, simulation, and separate hazard detection are disabled by default.

Native TurtleBot2 topic names are kept in:

```text
src/robot_adapters/config/tb2_topics.yaml
```

High-level code should use `/robot/...` topics instead of subscribing directly to Kobuki native topics.

Architecture nodes use YAML files as their parameter source of truth. The Python nodes auto-declare parameters from launch-provided YAML overrides, so run them through their launch files rather than directly with `ros2 run` unless you also provide the required parameters.

## Build

```bash
cd ~/robotics/foxrobotlab_ws
colcon build
source install/setup.bash
```

## Phase 1 Run Commands

TurtleBot2 base only:

```bash
ros2 launch robot_bringup tb2_base.launch.py
```

This includes `foxrobotlab_ros2/launch/kobuki.launch.py`, the current FoxRobotLab hardware wrapper around `kobuki_node`. Driver launch arguments are passed through:

```bash
ros2 launch robot_bringup tb2_base.launch.py astra:=true xtion:=false lidar_a2:=false lidar_s2:=false
```

Adapter only:

```bash
ros2 launch robot_adapters adapter.launch.py robot:=tb2
```

Core only:

```bash
ros2 launch robot_core core.launch.py
```

Full TurtleBot2 Phase 1 system:

```bash
ros2 launch robot_bringup tb2_system.launch.py
```

The full system accepts the same base driver arguments:

```bash
ros2 launch robot_bringup tb2_system.launch.py astra:=true lidar_a2:=false lidar_s2:=false
```

Print robot state:

```bash
ros2 launch robot_apps tb2_state_test.launch.py
```

Careful slow-drive command path test:

```bash
ros2 launch robot_apps tb2_simple_drive.launch.py
```

## Phase 1 Topic Checks

```bash
ros2 topic list | grep /robot
ros2 topic echo /robot/odom
ros2 topic echo /robot/imu
ros2 topic echo /robot/safety_status
ros2 topic echo /robot/state
```

The state printer is throttled to one log per second by default. If no lidar is running, `scan=False` is expected and the core will report `Robot state nominal; scan unavailable` once odometry is valid.

For command-path testing, publish zero velocity first:

```bash
ros2 topic pub --once /robot/cmd_vel geometry_msgs/msg/Twist "{}"
```

Then test the slow drive app only when the TurtleBot2 is on the floor with clear space around it.

## Phase 2 Status

Already implemented in the adapter:

- `/odom` -> `/robot/odom` and `/foxrobotlab/raw/odom`
- `/sensors/imu_data` -> `/robot/imu` and `/foxrobotlab/raw/sensors/imu_data`
- `/sensors/battery_state` -> `/robot/battery` and `/foxrobotlab/raw/sensors/battery_state`
- `/sensors/core` -> `/robot/kobuki/core` and `/foxrobotlab/raw/sensors/core`
- `/color/image_raw` -> `/robot/camera/color/image_raw` and `/foxrobotlab/raw/color/image_raw`
- `/depth/image_raw` -> `/robot/camera/depth/image_raw` and `/foxrobotlab/raw/depth/image_raw`
- Kobuki bumper, cliff, and wheel-drop events -> `/robot/safety_status` and `/foxrobotlab/raw/events/...`

Not changed yet:

- `foxrobotlab_ros2/launch/match_planner.launch.py` still launches `turtle_control_reciever.py`.
- `turtle_control_reciever.py` remains as the legacy reference implementation.
- `turtle_control_processor.py`, match planner, client-server, Nav2, Gazebo, TurtleBot4, and CNN code are not part of this Phase 2 validation step.

## Adapter Compatibility Test

Use this launch file when the native robot/camera stack is already running and you want to verify that the new adapter can provide both new and legacy topic outputs:

```bash
ros2 launch robot_adapters tb2_receiver_compat_test.launch.py
```

This launch starts only `tb2_adapter.py` with `tb2_topics.yaml`. It does not start `kobuki_node`, camera drivers, or legacy `foxrobotlab_ros2` nodes.

New code should subscribe to `/robot/...` topics. The `/foxrobotlab/raw/...` topics are temporary compatibility outputs so old `foxrobotlab_ros2` code can keep running during migration.

## Adapter Compatibility Checklist

Build and source:

```bash
cd ~/robotics/foxrobotlab_ws
colcon build --packages-select robot_adapters robot_core robot_apps robot_bringup lab_interfaces
source install/setup.bash
```

Run the existing robot stack or driver/camera stack as usual, then run:

```bash
ros2 launch robot_adapters tb2_receiver_compat_test.launch.py
```

If the robot is running through a ROS Discovery Server, `ros2 topic list` may not show the active topics even when nodes are successfully exchanging messages. In that setup, use the subscriber-based Phase 2 verifier as the authoritative test:

```bash
ros2 launch test phase2_topic_verifier.launch.py
```

The verifier passes only after it receives real messages on the required `/robot/...` and temporary `/foxrobotlab/raw/...` streams. This is more reliable than graph inspection for the current Discovery Server setup.

Check new common topics:

```bash
ros2 topic list | grep /robot
ros2 topic echo /robot/odom
ros2 topic echo /robot/imu
ros2 topic echo /robot/battery
ros2 topic echo /robot/kobuki/core
ros2 topic hz /robot/camera/color/image_raw
ros2 topic hz /robot/camera/depth/image_raw
ros2 topic echo /robot/safety_status
```

Check temporary legacy compatibility topics:

```bash
ros2 topic list | grep /foxrobotlab/raw
ros2 topic echo /foxrobotlab/raw/odom
ros2 topic echo /foxrobotlab/raw/sensors/imu_data
ros2 topic echo /foxrobotlab/raw/sensors/battery_state
ros2 topic echo /foxrobotlab/raw/sensors/core
ros2 topic hz /foxrobotlab/raw/color/image_raw
ros2 topic hz /foxrobotlab/raw/depth/image_raw
```

Expected topic pairs:

```text
/robot/battery                  <-> /foxrobotlab/raw/sensors/battery_state
/robot/camera/color/image_raw   <-> /foxrobotlab/raw/color/image_raw
/robot/camera/depth/image_raw   <-> /foxrobotlab/raw/depth/image_raw
/robot/kobuki/core              <-> /foxrobotlab/raw/sensors/core
/robot/safety_status            <-> /foxrobotlab/raw/events/bumper, cliff, wheel_drop
```

Acceptance criteria:

- Adapter starts without errors.
- Available native sensors appear on matching `/robot/...` topics.
- The same data appears on temporary `/foxrobotlab/raw/...` compatibility topics.
- `/robot/scan` does not appear by default because `has_lidar: false`.
- Existing Phase 1 state test still works.
- No legacy launch files are changed yet.

## Phase 3 Modular Planner Path

Phase 3 adds a modular replacement for the legacy `TurtleControlProcessor`. The new processor lives in `robot_core` and consumes `/robot/...` topics instead of `/foxrobotlab/raw/...`. It publishes motion commands to `/robot/cmd_vel`.

The legacy `turtle_control_processor.py`, `turtle_control_reciever.py`, and `foxrobotlab_ros2/launch/match_planner.launch.py` remain available as references.

Run the modular processor smoke test after `tb2_system.launch.py` is already running:

```bash
ros2 launch test robot_control_processor_smoke.launch.py
```

Run the modular match planner path:

```bash
ros2 launch robot_bringup tb2_modular_match_planner.launch.py astra:=true
```

This launch starts the TurtleBot2 system and runs the existing `matchPlanner.py` with `FOX_USE_MODULAR_ROBOT_PROCESSOR=1`, so the planner uses `robot_core.RobotControlProcessor` instead of the legacy processor.

## How To Compare Old Receiver Vs New Adapter

Old receiver flow:

```text
native topics -> turtle_control_reciever.py -> /foxrobotlab/raw/...
```

New adapter compatibility flow:

```text
native topics -> tb2_adapter.py -> /robot/...
                              -> /foxrobotlab/raw/...
```

To compare them safely, run one forwarding path at a time. Do not run `turtle_control_reciever.py` and `tb2_adapter.py` compatibility mode at the same time, because both will publish the same `/foxrobotlab/raw/...` topics.

Example battery comparison:

```bash
# Old path
ros2 run foxrobotlab_ros2 turtle_control_reciever.py
ros2 topic echo /foxrobotlab/raw/sensors/battery_state

# New path
ros2 launch robot_adapters tb2_receiver_compat_test.launch.py
ros2 topic echo /robot/battery
ros2 topic echo /foxrobotlab/raw/sensors/battery_state
```

Human learning pattern:

1. Find the native topic in `turtle_control_reciever.py`.
2. Find the old `/foxrobotlab/raw/...` output.
3. Add or verify the new `/robot/...` output in `tb2_topics.yaml`.
4. In `tb2_adapter.py`, import the message type, declare parameters, create publishers/subscribers, and republish in the callback.
5. Test the new `/robot/...` topic and the temporary compatibility topic.

## Refactoring Roadmap

### Phase 1: TurtleBot2 Base Foundation

Status: in progress.

- Keep the imported Kobuki driver intact.
- Use `robot_adapters` to translate native TurtleBot2 topics to `/robot/...`.
- Use `robot_core` to publish `/robot/state` and monitor safety status.
- Use `robot_apps` for simple state-printing and slow-drive tests.
- Do not add Nav2, Gazebo, TurtleBot4, CNN localization, or client-server migration yet.

### Phase 2: Complete Sensor Adapters

- Move remaining native sensor forwarding out of `foxrobotlab_ros2`.
- Add common battery and camera topics.
- Keep all native topic names in adapter YAML files.
- Keep high-level packages dependent only on `/robot/...`.

Likely common topics:

```text
/robot/battery
/robot/camera/color/image_raw
/robot/camera/depth/image_raw
```

### Phase 3: Replace Legacy Receiver/Processor Paths

- Replace `turtle_control_reciever.py` behavior with adapter nodes.
- Split `turtle_control_processor.py` behavior into smaller `robot_core` and `robot_apps` responsibilities.
- Stop publishing high-level commands directly to native `/cmd_vel` or `/commands/velocity`.

Future command path:

```text
robot_apps
  -> /robot/apps/cmd_vel
  -> robot_core command mux / safety gate
  -> /robot/cmd_vel
  -> robot_adapters
  -> native driver command topic
```

### Phase 4: Add Reusable Core Services

- Add a command mux.
- Add safety command gating.
- Add reusable status reporting.
- Keep localization and experiment-specific behavior outside the core unless it is robot-agnostic infrastructure.

### Phase 5: Migrate Applications

- Port match planner behavior into `robot_apps` or a dedicated application package.
- Make application code consume `/robot/state`, `/robot/odom`, `/robot/safety_status`, and future common camera topics.
- Make application code publish commands only through the common command path.

### Phase 6: Migrate Client-Server Code

- Keep client-server code in `foxrobotlab_ros2` until the base stack is stable.
- Update bridges to consume `/robot/...` topics.
- Move reusable networking/protocol code into a future package only after the interfaces are clear.

### Phase 7: Add ML And Localization Packages

- Create `robot_ml` for CNN model integration and camera-based localization.
- Keep CNN dependencies optional.
- Publish localization outputs through common interfaces rather than app-specific globals.

Possible topics:

```text
/robot/localization/pose
/robot/localization/state
/robot/localization/candidates
```

### Phase 8: Add Navigation

- Create `robot_navigation` for Nav2 configuration, maps, costmaps, RViz, and navigation launch files.
- Route Nav2 command output through the common command mux and safety gate.
- Do not let Nav2 bypass `/robot/cmd_vel`.

### Phase 9: Add TurtleBot4 And Simulation

- Add `tb4_adapter` and `tb4_topics.yaml` under `robot_adapters`.
- Add TurtleBot4 bringup launch files.
- Add `robot_simulation` for Gazebo after hardware layering is stable.
- Require simulation to satisfy the same `/robot/...` interface contract.

### Phase 10: Retire `foxrobotlab_ros2`

Retire or archive the old package when:

- No launch file depends on `foxrobotlab_ros2`.
- No active app subscribes to `/foxrobotlab/raw/...`.
- No active app publishes directly to native velocity topics.
- Client-server code uses `/robot/...`.
- Localization and CNN code live in dedicated architecture packages.

## Phase 1 Notes

- The adapter has been verified to create the common `/robot/...` topics.
- `/robot/scan` depends on a lidar source publishing the configured native scan topic. TurtleBot2 base does not have lidar by default, so `has_lidar` should stay `false` unless a physical lidar is attached and launched.
- The safety monitor logs hazards but does not block velocity commands yet.
- `foxrobotlab_ros2` remains in place as legacy working code during migration.
- Nav2, Gazebo, TurtleBot4 support, CNN localization, and client-server migration are intentionally out of scope for Phase 1.

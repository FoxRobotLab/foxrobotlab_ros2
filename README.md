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

Phase 1 proves the TurtleBot2 hardware path without Nav2, Gazebo, TurtleBot4, CNN localization, or client-server migration.

```text
kobuki_node
  -> robot_adapters
  -> /robot/... common topics
  -> robot_core
  -> robot_apps
```

The imported Kobuki driver package is treated as the native hardware layer and is not rewritten.

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
/robot/scan
/robot/imu
/robot/cmd_vel
/robot/safety_status
/robot/state
```

Native TurtleBot2 topic names are kept in:

```text
src/robot_adapters/config/tb2_topics.yaml
```

High-level code should use `/robot/...` topics instead of subscribing directly to Kobuki native topics.

## Phase 1 Build

```bash
cd ~/robotics/foxrobotlab_ws
colcon build
source install/setup.bash
```

## Phase 1 Run Commands

Driver only:

```bash
ros2 launch kobuki_node kobuki_node-launch.py
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
/robot/camera/camera_info
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
- `/robot/scan` depends on a lidar source publishing the configured native scan topic. It is optional for Phase 1 base testing.
- The safety monitor logs hazards but does not block velocity commands yet.
- `foxrobotlab_ros2` remains in place as legacy working code during migration.
- Nav2, Gazebo, TurtleBot4 support, CNN localization, and client-server migration are intentionally out of scope for Phase 1.

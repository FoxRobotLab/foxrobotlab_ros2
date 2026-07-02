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

Reverted back to phase 3 because it is the safest build, while we are doing the network configuration for turtlebot4. 

The goal now is the first setup the foundation for both turtlebot2 and turtlebot4. To do this we must have the following:
- tb2 and tb4 have different network configurations thus they must load certain environment variables unique to their setup when launching its bringup. This needs to be using the import OS package. 

- tb4 packages are ROS dependencies that came with the vendor with their own tools. To adapt this into our architecture, we make sripts and launch files that find inlclude the packages associated with the vendor.

- these outside packages publish their own topics that the code should subscribe to then republish into internal messages

## Current Packages

- `lab_interfaces`: shared messages and future services for the common interface.
- `robot_adapters`: converts native robot topics to common `/robot/...` topics.
- `robot_core`: reusable robot-agnostic services such as state processing and safety monitoring.
- `robot_bringup`: launch files for starting low-level infrastructure.
- `robot_apps`: application-level tests and future experiments.
- `foxrobotlab_ros2`: legacy working code retained during migration.
- `ThirdParty/*`: imported drivers and support libraries for turtlebot2.

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
    robot_apps/
      simple_drive/
        config/
        simple_drive_app.py
      state_printer/
        config/
        print_robot_state_app.py
      match_planner/
        config/
        res/
        match_planner_node.py
        localizer_stub_node.py
        planner_core.py

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
/robot/apps/cmd_vel
/robot/cmd_vel
/robot/command_mux/status
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

## Planning Source Of Truth

Use this README as the source of truth for architecture and testing plans. Future AI chats should read this file before proposing phase plans or test procedures, and the user may update the README with AI-suggested corrections when the plan changes.

Important correction for the current network setup: this workspace uses a ROS Discovery Server. Because of that, `ros2 topic list` may not show all active topics even when messages are being transmitted correctly between the TurtleBot2, workstation, and test nodes. Do not treat topic-list visibility as proof that the system is broken or working.

For network/topic validation, the authoritative test is subscriber-based message receipt:

```bash
ros2 launch test phase2_topic_verifier.launch.py
```

That verifier passes only when it receives real messages on the configured `/robot/...` and temporary `/foxrobotlab/raw/...` streams. Manual `ros2 topic echo` commands are useful for debugging after the verifier result, but the verifier result should guide planning decisions.

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
ros2 launch test tb2_state_test.launch.py
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

For command-path testing, publish app-requested zero velocity first. Applications publish to `/robot/apps/cmd_vel`; `robot_core` forwards approved commands to `/robot/cmd_vel`.

```bash
ros2 topic pub --once /robot/apps/cmd_vel geometry_msgs/msg/Twist "{}"
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
ros2 launch test phase2_adapter_compat_test.launch.py
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
ros2 launch test phase2_adapter_compat_test.launch.py
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

### ROS Discovery Server Design Change

The old `foxrobotlab_ros2` socket server-client setup is now considered legacy. New architecture work should assume that robot, workstation, and test nodes communicate through ROS 2 with the ROS Discovery Server configured correctly.

Important testing note: under the current Discovery Server setup, `ros2 topic list` may not show the full graph even when messages are being transmitted successfully. Do not use topic-list visibility as the main acceptance test. Use subscriber-based tests from the `test` package instead.

Preferred verification flow:

```bash
ros2 launch robot_bringup tb2_system.launch.py astra:=true
ros2 launch test phase2_topic_verifier.launch.py
ros2 launch test robot_control_processor_smoke.launch.py
```

These tests prove that real messages are being received on the expected topics. That is stronger evidence than graph inspection for this workspace.

## Refactoring Roadmap

### Phase 1: TurtleBot2 Base Foundation

Status: implemented and hardware-tested as the foundation layer.

- Keep the imported Kobuki driver intact.
- Use `robot_adapters` to translate native TurtleBot2 topics to `/robot/...`.
- Use `robot_core` to publish `/robot/state` and monitor safety status.
- Use `robot_apps` for simple state-printing and slow-drive tests.
- Do not add Nav2, Gazebo, TurtleBot4, CNN localization, or client-server migration yet.

### Phase 2: Complete Sensor Adapters

Status: implemented and verified with subscriber-based tests.

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

Status: implemented as a bridge path and hardware-tested.

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

### Phase 4: Add turtleebot4 configuration and be able to use its SLAM packages

This phase will need to bringup the tb4 by calling its external packages that came with the robot. Additionally, during bringup we must able to switch the ROS Discovery server between tb4 and tb2.
- In our current setup tb2 is the client and the workstation is the server. This works for tb2

- In tb4, the robot must be the server as it communicates directly with create3 base and the workstation as the client.

- Need placeholders for setting up the server id, ports and dds configs.

### Phase 5: Add Reusable Core Services

Status: current implementation phase. The command mux, safety command gating, app command topic, command mux status message, and mux verifier exist.

- Add a command mux.
- Add safety command gating.
- Add reusable status reporting.
- Keep localization and experiment-specific behavior outside the core unless it is robot-agnostic infrastructure.

### Phase 6: Migrate the matchPlanner and all its functionalities

- Start by making sure that this codebase can run everything on foxrobotlab_ros2 
- This includes being able to run the GUI

1. The first step of the migration is to retire the socket client-server setup since we migrated to ROS discovery server.
2. The second step is to be able to Run the program and GUI without the socket client-server
3. Migrate the core programs to robot_apps

### Phase 7: Add ML And Localization Packages

### Phase 8: Retire `foxrobotlab_ros2`

Retire or archive the old package when:

- No launch file depends on `foxrobotlab_ros2`.
- No active app subscribes to `/foxrobotlab/raw/...`.
- No active app publishes directly to native velocity topics.
- Socket client-server code has been removed, archived, or replaced by ROS-native communication.
- Localization and CNN code live in dedicated architecture packages.

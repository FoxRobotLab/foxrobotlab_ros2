# FoxRobotLab ROS 2 Modular Architecture

This workspace is being migrated from the older `foxrobotlab_ros2` package into a layered robot architecture.

Phase 1 proves the TurtleBot2 hardware path without Nav2, Gazebo, TurtleBot4, CNN localization, or client-server migration.

## Phase 1 Stack

```text
kobuki_node
  -> robot_adapters
  -> /robot/... common topics
  -> robot_core
  -> robot_apps
```

The imported Kobuki driver package is treated as the native hardware layer and is not rewritten.

## Packages Added For The New Architecture

- `lab_interfaces`: shared custom messages.
- `robot_adapters`: converts native robot topics to common `/robot/...` topics.
- `robot_core`: robot-agnostic state and safety processing.
- `robot_bringup`: reusable launch files for TurtleBot2 bringup.
- `robot_apps`: simple app-level tests.

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

## Build

```bash
cd ~/robotics/foxrobotlab_ws
colcon build
source install/setup.bash
```

## Run Each Layer

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

## Verify Topics

```bash
ros2 topic list | grep /robot
ros2 topic echo /robot/odom
ros2 topic echo /robot/imu
ros2 topic echo /robot/safety_status
ros2 topic echo /robot/state
```

For command-path testing, publish zero velocity first:

```bash
ros2 topic pub --once /robot/cmd_vel geometry_msgs/msg/Twist "{}"
```

Then test the slow drive app only when the TurtleBot2 is on the floor with clear space around it.

## Phase 1 Notes

- The adapter has been verified to create the common `/robot/...` topics.
- `/robot/scan` depends on a lidar source publishing the configured native scan topic.
- The safety monitor logs hazards but does not block velocity commands yet.
- `foxrobotlab_ros2` remains in place as legacy working code during migration.
- Nav2, Gazebo, TurtleBot4 support, CNN localization, and client-server migration are intentionally out of scope for Phase 1.

# Turtle Control Migration Test Guide

Use this guide to test the ROS2 receiver, processor, and display before running
`matchPlanner.py`.

## 1. Build And Source

From the workspace root:

```bash
colcon build --packages-select foxrobotlab_ros2
source install/setup.bash
```

## 2. Launch The Control Nodes

Run the receiver, processor, and display together:

```bash
ros2 launch foxrobotlab_ros2 turtle_control.launch.py
```

Expected behavior:

- `turtle_control_reciever.py` republishes hardware topics to `/foxrobotlab/raw/...`
- `turtle_control_processor.py` subscribes to those raw topics
- `turtle_control_display.py` prints `/foxrobotlab/processed/status_text`

## 3. Run The Getter Test

The getter test creates a `TurtleControlProcessor` object the same way
`matchPlanner.py` does, then calls the compatibility methods used by the old
planner stack:

```bash
source install/setup.bash
ros2 run foxrobotlab_ros2 turtle_control_getter_test.py
```

This checks:

- `getOdomData()`
- `getTravelDist()`
- `getBumperStatus()`
- `getWheelDropStatus()`
- `getCliffStatus()`
- `hasWheelDrop()`
- `getImage()`
- `getDepth()`

If this passes, the processor API is ready for the first `matchPlanner.py`
runtime test.

Because the getter test needs the same raw topics as the processor, a passing
getter test also confirms the basic receiver-to-processor topic flow.

## 4. Optional Topic Checks

If the getter test is missing source data, check the topic directly:

```bash
ros2 topic list
ros2 topic echo /foxrobotlab/raw/odom
ros2 topic echo /foxrobotlab/processed/status_text
```

For camera topics, use `ros2 topic hz` instead of `echo`:

```bash
ros2 topic hz /foxrobotlab/raw/color/image_raw
ros2 topic hz /foxrobotlab/raw/depth/image_raw
```

## 5. Run matchPlanner

After the getter test passes, run:

```bash
python3 src/foxrobotlab_ros2/src/match_seeker/scripts/matchPlanner.py
```

At this stage, the goal is only to find the next migration failure. Likely
failure points are GUI setup, image database paths, localizer setup, or old
movement assumptions.

## Important Note

`matchPlanner.py` directly creates its own `TurtleControlProcessor` object.
That means the launched processor is useful for display/status testing, but
`matchPlanner.py` still reads the raw ROS topics through its own processor
instance.

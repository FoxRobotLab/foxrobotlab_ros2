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

## 3. Run The Smoke Test

In a second terminal:

```bash
source install/setup.bash
ros2 run foxrobotlab_ros2 turtle_control_smoke_test.py
```

The required checks are:

- `/foxrobotlab/raw/odom`
- `/foxrobotlab/raw/color/image_raw`
- `/foxrobotlab/raw/depth/image_raw`
- `/foxrobotlab/raw/sensors/core`
- `/foxrobotlab/processed/status_text`

If these pass, the receiver and processor are connected well enough for the
next `matchPlanner.py` test.

## 4. Optional Topic Checks

If the smoke test is missing a topic, check the topic directly:

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

After the smoke test passes, run:

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

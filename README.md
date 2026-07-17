# Susan's Robotics Lab
Welcome to the Macalester Robotics Research group under Susan Fox! 🤖🔥

I will take you through onboarding - ANDRE

## The Robots
This repository currently supports 4 robots in the lab, two Turtlebot2s and two Turtlebot4s.

The Turtlebot2s are Speedy and Cutie. Speedy is the robot with the arm with all those wires and electronics around. Cutie on the other hand is more **cute** because the it doesn't have all those messy wired around it and it has the picture of the cat. 

Both robots are running on the Kobuki roomba base. This is important to know because the Kobuki drivers are not natively developed for ROS2, thus effort was done to upgrade these into ROS2.

The Turtlebot4s are Merry and Pippin. These robots look identical to each other as inspired by the character pair of the same name in the Lord of the Rings. They have a modern look and a big power button. These have more functionalities than the turtlebot2s and future development would use turtlebot4 functionalities.

**as of August 2026, tb4 are still being integrated into the codebase**
## Installation
**If you are setting up a brand-new machine, use the steps below.** If you are working on one of the lab workstations, you can usually skip these setup steps because the expected environment is already installed there:
- Ubuntu Noble
- ROS 2 Jazzy
- TensorFlow 2.18

### 1. Install ROS 2 and source it
Follow the official ROS 2 Jazzy installation guide:
- https://docs.ros.org/en/jazzy/Installation.html

After installation, open a new terminal and source ROS:
```bash
source /opt/ros/jazzy/setup.bash
```

### 2. Create a workspace and clone the repository
```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone <repository-url> foxrobotlab_ros2
```

### 3. Pull the third-party dependencies
**For Turtlebot2 support**, import the additional repositories listed in the workspace manifest:
```bash
cd ~/ros2_ws/src
vcs import < foxrobotlab_ros2/thirdparty.repos
```

If `vcs import` fails, run it again once more.

### 4. Install additional system packages
```bash
sudo apt update
sudo apt install -y libusb-1.0-0-dev libftdi1-dev libuvc-dev ros-dev-tools
```

### 5. Set up udev rules for hardware
When you connect hardware to the PC, it may appear as `/dev/ttyUSB*` without the correct permissions. The following rules create stable device names and grant access:
```bash
cd ~/ros2_ws
sudo cp src/ThirdParty/ros_astra_camera/astra_camera/scripts/56-orbbec-usb.rules /etc/udev/rules.d/
sudo cp src/ThirdParty/rplidar_ros/scripts/rplidar.rules /etc/udev/rules.d/
sudo cp src/ThirdParty/kobuki_ros/60-kobuki.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 6. Install dependencies and build the workspace
```bash
sudo rosdep init
rosdep update
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

After the build completes, source the workspace in each new terminal:
```bash
source ~/ros2_ws/install/setup.bash
```

Installation is complete!!
## Running matchSeeker (Main Program)
Below are instructions on how to run the main program for Susan's research.

If you are using one of the lab workstations, the environment is usually already configured. If you are on a new machine, make sure the workspace has been built and sourced first.

### Before you start
```bash
source .bashrc
```

### On the workstation
1. Select the robot profile:
```bash
choose_robot tb2
# or
choose_robot tb4
```

2. In a second terminal, connect to the robot using the lab-specific alias:
```bash
# Turtlebot2s
speedy_connect
# or
cutie_connect

# Turtlebot4s
merry_connect
#or
pippin_connect
```

3. Start the workstation-side GUI and listener services:
```bash
ros2 launch foxrobotlab_ros2 laptop_servers.launch.py
```

### On the robot/client
Start the robot-side stack:
```bash
ros2 launch foxrobotlab_ros2 robot_system.launch.py
```

### Expected behavior
- The workstation terminal launches the localizer server and GUI.
- The robot terminal launches the base, camera, and planner-related nodes.
- Once both sides are running, enter a starting cell, yaw, and destination cell in the GUI to have the robot start autonomously navigating.

### Troubleshooting
If the planner cannot connect, confirm that:
- both terminals were sourced
- ROS Discovery Server is turned on
- the workspace was rebuilt after recent changes <- important to be aware of

If needed, rebuild and re-source the workspace:
```bash
cd PycharmProjects/turtlebot_ros2_ws
colcon build --packages-select foxrobotlab_ros2 --symlink-install
source install/setup.bash
```

## Useful Links and Tutorials
Credit to [Intelligent Robotics Lab](https://intelligentroboticslab.gsyc.urjc.es/) research group from the [Universidad Rey Juan Carlos](https://www.urjc.es/) for the ROS2 Kobuki drivers.

**[ROS2 Crash Courses by Robotics Back-End](https://www.youtube.com/watch?v=Gg25GfA456o&list=PLLSegLrePWgJk6dfV-UXSh2TZ74wNntWt)**

**[ROS2 Courses Intermediate by Automatic Addison](https://www.youtube.com/@automaticaddison/playlists)**

[Susan Fox Lab Documentation](https://docs.google.com/document/d/1IJRMkSybLFnE4yOeIK3kVz7pgWu4PH3ltX2sdyCFDuU/edit?usp=sharing)

[Andre Research Documentation](https://docs.google.com/document/d/1eTwPKTrFZLToqb6qz6YCPc723MG57R67jhoT5S0uStA/edit?usp=sharing)
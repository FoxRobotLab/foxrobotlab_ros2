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
If you are setting up a brand-new machine, use the steps below. If you are working on one of the lab workstations, you can usually skip these setup steps because the expected environment is already installed there:
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
sudo apt install -y libusb-1.0-0-dev libftdi1-dev libuvc-dev ros-jazzy-ros-dev-tools
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
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```

After the build completes, source the workspace in each new terminal:
```bash
source ~/ros2_ws/install/setup.bash
```

Installation is complete!!

## To run the program

**Make sure to source the terminal before anything** 

On the terminal in the Workstation/server:
1) Make sure to build if not already
     - cd PycharmProjects/turtlebot2_ros2_ws/
     - colcon build --packages-select foxrobotlab_ros2
     - source it again in the home directory

2) running the GUI and server side program
     - ros2 launch foxrobotlab_ros2 laptop_servers.launch.py
  
On the robot/client
1) Make sure to build similar to the workstation
2) running the main program and robot startup
    - ros2 launch foxrobotlab_ros2 robot_system.launch.py

## Base robot bringup
To launch the robot ONLY
- ros2 launch foxrobotlab_ros2 kobuki.launch.py

for camera functionality
- ros2 launch foxrobotlab_ros2 kobuki.launch.py astra:=true

for teleop
- ros2 run teleop_twist_keyboard teleop_twist_keyboard

to see camera/video feed
- ros2 run image_view image_view --ros-args -r image:=/color/image_raw

## Useful Links and Tutorials
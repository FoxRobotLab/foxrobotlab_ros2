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

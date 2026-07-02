cmake_minimum_required(VERSION 3.8)
project(robot_apps)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ------------------- Find Dependencies -------------------
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

find_package(rclpy REQUIRED)
find_package(cv_bridge REQUIRED)

find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

find_package(lab_interfaces REQUIRED)

# ------------------- Python Packages -------------------
ament_python_install_package(robot_apps)

# ------------------- Python Executables -------------------
install(
  PROGRAMS
    robot_apps/simple_drive/simple_drive_app.py
    robot_apps/state_printer/print_robot_state_app.py
  DESTINATION lib/${PROJECT_NAME}
)

# ------------------- Launch Files -------------------
install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
  PATTERN "__pycache__" EXCLUDE
)

# ------------------- Application Config and Resource Files -------------------
# Simple Drive App
install(
  DIRECTORY robot_apps/simple_drive/config
  DESTINATION share/${PROJECT_NAME}/apps/simple_drive
)

# State Printer App
install(
  DIRECTORY robot_apps/state_printer/config
  DESTINATION share/${PROJECT_NAME}/apps/state_printer
)

# Match Planner App [MAIN APPLICATION]
install(
  DIRECTORY 
    robot_apps/match_planner/config
    robot_apps/match_planner/res
  DESTINATION share/${PROJECT_NAME}/apps/match_planner
)

ament_package()

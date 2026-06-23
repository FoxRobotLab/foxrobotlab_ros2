cmake_minimum_required(VERSION 3.8)
project(robot_core)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# --------------- Find Dependencies ---------------
find_package(ament_cmake REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(lab_interfaces REQUIRED)

# --------------- Python Executables ---------------
install(
  PROGRAMS
    src/robot_processor.py
    src/safety_monitor.py
  DESTINATION lib/${PROJECT_NAME}
)

# ------------------- Config Files Visibility -------------------
install(
  DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
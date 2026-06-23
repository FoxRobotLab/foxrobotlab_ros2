cmake_minimum_required(VERSION 3.8)
project(robot_apps)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ----------------- Find Dependencies -----------------
find_package(ament_cmake REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(lab_interfaces REQUIRED)

# ---------------- Python Executables ----------------
install(
  PROGRAMS
    src/print_robot_state_app.py
    src/simple_drive_app.py
  DESTINATION lib/${PROJECT_NAME}
)

# ---------------- Install Configuration and Launch Files ----------------
install(
  DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
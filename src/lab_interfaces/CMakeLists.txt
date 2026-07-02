cmake_minimum_required(VERSION 3.8)
project(lab_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ------------------- Find Dependencies -------------------
find_package(ament_cmake REQUIRED)

find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)

find_package(rosidl_default_generators REQUIRED)

# ------------------- Generate Interfaces -------------------
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/SafetyStatus.msg"
  "msg/RobotState.msg"
  "msg/MatchPlannerStatus.msg"
  "msg/CommandMuxStatus.msg"
  "srv/MatchLocalize.srv"
  "srv/SetMatchPlannerGoal.srv"
  "srv/SetMatchPlannerStart.srv"
  DEPENDENCIES
    std_msgs
    geometry_msgs
    nav_msgs
    sensor_msgs
)

# ------------------- Export Dependencies -------------------
ament_export_dependencies(rosidl_default_runtime)

ament_package()

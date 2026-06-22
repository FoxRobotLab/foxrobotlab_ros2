cmake_minimum_required(VERSION 3.8)
project(foxrobotlab_ros2)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)

# include the following folders into the CMake when present
set(FOXROBOTLAB_SHARE_DIRS)
foreach(dir launch config scripts)
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${dir}")
    list(APPEND FOXROBOTLAB_SHARE_DIRS ${dir})
  endif()
endforeach()

if(FOXROBOTLAB_SHARE_DIRS)
  install(DIRECTORY
    ${FOXROBOTLAB_SHARE_DIRS}
    DESTINATION share/${PROJECT_NAME}
  )
endif()

install(DIRECTORY
  src/match_seeker
  src/client_server
  DESTINATION share/${PROJECT_NAME}/src
  USE_SOURCE_PERMISSIONS
  PATTERN "__pycache__" EXCLUDE
  PATTERN "*.pyc" EXCLUDE
)

# Installing python modules
ament_python_install_package(${PROJECT_NAME})

# Installing python executables
install(PROGRAMS
  src/turtle_control_reciever.py
  src/turtle_control_processor.py
  src/client_server/localizer_server.py
  src/client_server/tensorflow_check.py
  src/client_server/video_client.py
  src/client_server/video_server.py
  src/client_server/gui_unified.py
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  src/turtle_control_processor.py
  DESTINATION share/${PROJECT_NAME}/src
)

# Small utilities for checking ROS 2 discovery between hosts.
install(PROGRAMS
  tests/talker.py
  tests/listener.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

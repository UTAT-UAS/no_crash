cmake_minimum_required(VERSION 3.8)
project(flight_core_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/AcquireControl.srv"
  "srv/ReleaseControl.srv"
  "srv/ResetControl.srv"
  "srv/Command.srv"
  "srv/Goto.srv"
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()

cmake_minimum_required(VERSION 3.8)
project(flight_core)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_msgs REQUIRED)
find_package(flight_core_interfaces REQUIRED)

add_library(control_lease src/control_lease.cpp)
target_include_directories(control_lease PUBLIC include)
target_compile_features(control_lease PUBLIC cxx_std_17)

add_executable(flight_core_cpp src/main.cpp src/flight_core_node.cpp)
target_compile_features(flight_core_cpp PUBLIC cxx_std_17)
target_link_libraries(flight_core_cpp control_lease)
ament_target_dependencies(flight_core_cpp rclcpp px4_msgs flight_core_interfaces)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(control_lease PRIVATE -Wall -Wextra -Wpedantic)
  target_compile_options(flight_core_cpp PRIVATE -Wall -Wextra -Wpedantic)
endif()

ament_python_install_package(${PROJECT_NAME})

install(TARGETS flight_core_cpp
  DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/example_mission
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_control_lease test/test_control_lease.cpp)
  target_link_libraries(test_control_lease control_lease)
endif()

ament_package()

cmake_minimum_required(VERSION 3.8)
project(target_detloc)

set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ============================================================
# Backend selection flag
#   ONNX  -> uses YOLOs-CPP + onnxruntime
#   TRT   -> uses YOLOSegmentationDetector + TensorRT
# Usage:  colcon build --cmake-args -DBACKEND=ONNX
#     or: colcon build --cmake-args -DBACKEND=TRT
# ============================================================
set(BACKEND "ONNX" CACHE STRING "Inference backend: ONNX or TRT")
set_property(CACHE BACKEND PROPERTY STRINGS ONNX TRT)
string(TOUPPER "${BACKEND}" BACKEND)

if(NOT BACKEND STREQUAL "ONNX" AND NOT BACKEND STREQUAL "TRT")
  message(FATAL_ERROR "BACKEND must be ONNX or TRT, got '${BACKEND}'")
endif()

message(STATUS "target_detloc: building with BACKEND=${BACKEND}")

# ---- Common dependencies ----
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(OpenCV REQUIRED)

# ---- Common: frame_mux ----
add_executable(frame_mux src/frame_mux.cpp)

target_include_directories(frame_mux PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
)

ament_target_dependencies(frame_mux
  rclcpp
  sensor_msgs
  std_msgs
  cv_bridge
  OpenCV
)

# ============================================================
# Backend-specific: detect node
# ============================================================
if(BACKEND STREQUAL "ONNX")

  # ---- ONNX Runtime backend ----
  set(onnxruntime_DIR
      "${CMAKE_CURRENT_SOURCE_DIR}/YOLOs-CPP/onnxruntime-linux-x64-1.20.1/lib/cmake/onnxruntime"
  )
  find_package(onnxruntime REQUIRED)

  add_executable(detect src/detect.cpp)

  target_include_directories(detect PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/YOLOs-CPP/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/YOLOs-CPP/include/yolos/core>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/YOLOs-CPP/onnxruntime-linux-x64-1.20.1/include>
    $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
  )

  ament_target_dependencies(detect
    rclcpp
    sensor_msgs
    std_msgs
    cv_bridge
    OpenCV
  )

  set_target_properties(onnxruntime::onnxruntime PROPERTIES
      INTERFACE_INCLUDE_DIRECTORIES
      "${CMAKE_CURRENT_SOURCE_DIR}/YOLOs-CPP/onnxruntime-linux-x64-1.20.1/include"
  )

  target_link_libraries(detect
    onnxruntime::onnxruntime
  )

elseif(BACKEND STREQUAL "TRT")

  # ---- TensorRT backend ----
  find_package(CUDAToolkit REQUIRED)

  # Compile YOLOSegmentationDetector.cpp directly into the detect node
  add_executable(detect
    src/detect.cpp
    src/YOLOSegmentationDetector.cpp
  )

  target_include_directories(detect PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include/${PROJECT_NAME}>
  )

  ament_target_dependencies(detect
    rclcpp
    sensor_msgs
    std_msgs
    cv_bridge
    OpenCV
  )

  target_link_libraries(detect
    nvinfer
    CUDA::cudart
  )

endif()

# ---- Install ----
install(TARGETS frame_mux
  DESTINATION lib/${PROJECT_NAME})

install(TARGETS detect
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
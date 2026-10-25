# ROS 2 workspace

ROS 2 Jazzy packages live under `src/`.

- [`flight_core`](src/flight_core/README.md): central PX4 offboard node and the
  Python `Drone` client library.
- [`flight_core_interfaces`](src/flight_core_interfaces/README.md): services used to
  command `flight_core`.
- `px4_msgs`: Git submodule pinned to PX4 v1.17.0 messages.

Build from the monorepo root so the container's existing overlay setup applies:

```bash
cd ~/workspace
rosdep install --from-paths uas_ws/src --ignore-src -r -y
colcon build --base-paths uas_ws/src --symlink-install
source install/local_setup.bash
```

The container supplies ROS 2 Jazzy, colcon, rosdep, vcstool, ament, CMake,
and C/C++ compilers. Build output and logs default to `/build/colcon`; the
install overlay stays at `~/workspace/install`.

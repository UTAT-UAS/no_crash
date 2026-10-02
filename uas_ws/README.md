# ROS 2 workspace

Placeholder for ROS 2 Jazzy packages. Add packages under `src/`.

Build from the monorepo root so the container's existing overlay setup applies:

```bash
cd ~/workspace
rosdep install --from-paths uas_ws/src --ignore-src -r -y
colcon build --base-paths uas_ws/src --symlink-install
source install/local_setup.bash
```

The container supplies ROS 2 Jazzy, colcon, rosdep, vcstool, ament, CMake,
and C/C++ compilers. Build output and logs default to `/build/colcon`; the
install overlay stays at `~/workspace/install`. There are no packages to build yet.

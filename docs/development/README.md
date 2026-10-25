# Developing in the monorepo

The ROS workspace contains the mixed Python and C++ `flight_core` package;
the other project directories contain README placeholders. Each project owns
its dependencies; install them explicitly when working on that project.

For environment setup and included tools, see
[the development container guide](../devcontainer/README.md).

## ROS 2 flight software

Add Jazzy packages under [`uas_ws/src/`](../../uas_ws/src/README.md), with a
`package.xml` and their own build configuration. Build from the repository root:

```bash
rosdep install --from-paths uas_ws/src --ignore-src -r -y
colcon build --base-paths uas_ws/src --symlink-install
source install/local_setup.bash
```

Keep the overlay at the root `install/`. The
[ROS workspace README](../../uas_ws/README.md) describes that project's layout.
`px4_msgs` is a Git submodule pinned to the PX4 release in use (v1.17.0); run
`git submodule update --init` after cloning and declare it as a dependency of
consumers.

## Flight visualizer

The [frontend](../../flight_visualizer/frontend/README.md) uses Svelte and Bun.
Once its manifest, scripts, and lockfile exist:

```bash
cd flight_visualizer/frontend
bun install --frozen-lockfile
bun run dev
```

Commit `bun.lock` alongside dependency changes. Use Node LTS for tools that
require Node.

The [Python backend](../../flight_visualizer/backend/README.md) manages a
separate environment and dependency manifest. Create a dedicated venv using
the system Python interpreter, then install the declared dependencies. Use
`--system-site-packages` when creating a ROS-dependent venv that needs `rclpy`
or other apt-provided Python modules. No backend framework has been selected.

## Hardware manager

The [hardware manager](../../hardware_manager/README.md) contains Bash and Python
scripts. Prefer the standard library when sufficient; declare any extra Python
dependencies and use a dedicated venv. Add device access as hardware needs
become known; see [equipment setup](../devcontainer/host-setup.md).

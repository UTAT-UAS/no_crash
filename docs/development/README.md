# Developing in the monorepo

The ROS workspace contains the mixed Python and C++ `flight_core` package and
`flight_visualizer_bridge`; the flight visualizer has a FastAPI backend and a
SvelteKit frontend; `hardware_manager` is a placeholder. Each project owns
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
[ROS workspace README](../../uas_ws/README.md) describes that project's layout
and the `uas_ws/scripts/sitl` helper for simulation tests, for example
`uas_ws/scripts/sitl run -- ros2 run flight_core example_mission`.
`px4_msgs` is a Git submodule pinned to the PX4 release in use (v1.17.0); run
`git submodule update --init` after cloning and declare it as a dependency of
consumers.

## Flight visualizer

The [frontend](../../flight_visualizer/frontend/flight_visualizer/README.md) is a SvelteKit app
in `flight_visualizer/frontend/flight_visualizer`, managed with Bun:

```bash
cd flight_visualizer/frontend/flight_visualizer
bun install --frozen-lockfile
bun run dev
```

Commit `bun.lock` alongside dependency changes. Use Node LTS for tools that
require Node.

The [Python backend](../../flight_visualizer/backend/README.md) is a FastAPI
app managed with uv (`pyproject.toml`, `uv.lock`); it does not need ROS. It
connects to `flight_visualizer_bridge` on the drone. The container publishes
ports 5173 and 8000 on the host's `localhost`.

## Hardware manager

The [hardware manager](../../hardware_manager/README.md) contains Bash and Python
scripts. Prefer the standard library when sufficient; declare any extra Python
dependencies and use a dedicated venv. Add device access as hardware needs
become known; see [equipment setup](../devcontainer/host-setup.md).

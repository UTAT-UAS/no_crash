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
[ROS workspace README](../../uas_ws/README.md) describes that project's layout.
Use [`scripts/sim`](#simulation) for simulation tests, for example
`scripts/sim sitl run -- ros2 run flight_core example_mission`.
`px4_msgs` is a Git submodule pinned to the PX4 release in use (v1.17.0); run
`git submodule update --init` after cloning and declare it as a dependency of
consumers.

## Simulation

[`scripts/sim`](../../scripts/sim) runs reproducible simulation sessions
against the PX4 SITL build, and the flight visualizer, as background
processes. Build the ROS workspace first; run it from anywhere.

| Command | Effect |
|---|---|
| `sim sitl start [--no-gui] [--no-core] [--real]` | Start MicroXRCEAgent, Gazebo, its GUI, PX4 SITL and `flight_core` (`mode:=sim`, or `mode:=real` with `--real`, which rejects arming); wait until ready |
| `sim sitl restart` | Restart PX4 with fresh parameters and respawn the drone at the origin; Gazebo, the GUI and the agent keep running, and `flight_core` is restarted in the same mode if it was running |
| `sim sitl run [start options] -- <command>` | Start, run the command, stop; exit with the command's status |
| `sim sitl gui` | Open the Gazebo GUI on the running simulation, e.g. one started with `--no-gui`; closing it leaves the simulation running |
| `sim sitl px4 <module> [args]` | PX4 shell command, e.g. `sim sitl px4 param show NAV_DLL_ACT` or `sim sitl px4 commander takeoff` |
| `sim viz start [--no-bridge] [--no-backend] [--no-frontend]` | Start `flight_visualizer_bridge`, the backend (port 8000) and the frontend dev server (port 5173); wait until ready |
| `sim viz restart` | Restart the running visualizer components |
| `sim <sitl\|viz> stop` | Stop everything the group started |
| `sim <sitl\|viz> status` | Show running components and log paths |

`viz start` expects the backend's `uv sync && ./generate.sh` and the
frontend's `bun install --frozen-lockfile` to have been run; it does not
install dependencies.

Gazebo runs as its own process. The script spawns the drone at the origin
and PX4 starts in standalone mode, attached to it. `restart` removes the
drone and spawns a new one under a new name (`x500_0`, `x500_1`, …): Gazebo
keeps a removed model's sensors publishing, so reusing the name would give
PX4 two conflicting sets of sensor data.

Each PX4 start uses a fresh PX4 working directory under `SIM_STATE_DIR`, so
parameters begin at their defaults and the PX4 build's own parameter file is
never modified. For the session, `NAV_DLL_ACT` is set to 0 so PX4 arms without
a ground station, and `COM_RC_LOSS_T` is set to 5 s. Logs for each component
are in `$SIM_STATE_DIR/<sitl|viz>/logs` and are kept after `stop` until the
next `start`; `sitl restart` starts the `px4` and `core` logs afresh.

| Variable | Default |
|---|---|
| `PX4_DIR` | `~/build/PX4-Autopilot` |
| `PX4_SIM_MODEL` | `gz_x500` |
| `PX4_GZ_WORLD` | `default`: a world in [`sim/worlds`](../../sim/worlds), else in PX4's `Tools/simulation/gz/worlds` |
| `SIM_STATE_DIR` | `${TMPDIR:-/tmp}/no_crash_sim` |
| `SIM_TIMEOUT` | `120` seconds to wait for readiness |
| `XRCE_PORT` | `8888` |

## Linting and formatting

C++ in `uas_ws/src` uses clang-format and clang-tidy (`uas_ws/.clang-format`,
`uas_ws/.clang-tidy`, ROS 2 style). Python uses ruff and pyright, configured
per project in `uas_ws/ruff.toml` and `uas_ws/pyrightconfig.json`, and in
`flight_visualizer/backend/pyproject.toml`. The tools are in the container.
[`scripts/lint`](../../scripts/lint) runs them all:

```bash
colcon build --base-paths uas_ws/src --symlink-install  # clang-tidy needs compile_commands.json
scripts/lint                # check only; non-zero exit on any finding
scripts/lint --fix          # format and apply automatic fixes
scripts/lint python         # or cpp, to run one language
```

clang-tidy reads each package's `compile_commands.json` from its colcon build
directory (`/build/colcon/build/<package>`); ament CMake packages enable it
with `set(CMAKE_EXPORT_COMPILE_COMMANDS ON)`. Add new C++ packages the same
way, and add new Python projects to `PYTHON_PROJECTS` in `scripts/lint` with
their own ruff and pyright configuration. Extensionless Python scripts need
listing in `extend-include`. pyright resolves `uas_ws` imports through the ROS
environment, which the script sources, including the `install/` overlay; the
backend's resolve through its uv `.venv`, so run `uv sync` first.

Editor tools such as clangd look for `compile_commands.json` beside the
sources. Symlink it into the package once; the link is ignored by Git and
stays valid across rebuilds:

```bash
ln -s /build/colcon/build/flight_core/compile_commands.json uas_ws/src/flight_core/
```

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

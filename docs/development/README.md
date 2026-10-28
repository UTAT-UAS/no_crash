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
Use [`scripts/sitl`](#sitl-testing) for simulation tests, for example
`scripts/sitl run -- ros2 run flight_core example_mission`.
`px4_msgs` is a Git submodule pinned to the PX4 release in use (v1.17.0); run
`git submodule update --init` after cloning and declare it as a dependency of
consumers.

## SITL testing

[`scripts/sitl`](../../scripts/sitl) runs reproducible simulation sessions
against the PX4 SITL build. Build the ROS workspace first; run it from anywhere.

| Command | Effect |
|---|---|
| `sitl start [--no-core] [--gui]` | Start MicroXRCEAgent, Gazebo, PX4 SITL and `flight_core` (`mode:=sim`); wait until ready |
| `sitl restart` | Restart PX4 with fresh parameters and respawn the drone at the origin; Gazebo and the agent keep running, and `flight_core` is restarted if it was running |
| `sitl stop` | Stop everything `start` launched |
| `sitl status` | Show running components and log paths |
| `sitl run [start options] -- <command>` | Start, run the command, stop; exit with the command's status |
| `sitl px4 <module> [args]` | PX4 shell command, e.g. `sitl px4 param show NAV_DLL_ACT` or `sitl px4 commander takeoff` |

Gazebo runs as its own process. The script spawns the drone at the origin
and PX4 starts in standalone mode, attached to it. `restart` removes the
drone and spawns a new one under a new name (`x500_0`, `x500_1`, …): Gazebo
keeps a removed model's sensors publishing, so reusing the name would give
PX4 two conflicting sets of sensor data.

Each PX4 start uses a fresh PX4 working directory under `SITL_STATE_DIR`, so
parameters begin at their defaults and the PX4 build's own parameter file is
never modified. For the session, `NAV_DLL_ACT` is set to 0 so PX4 arms without
a ground station, and `COM_RC_LOSS_T` is set to 5 s. Logs for `agent`, `gz`, `gui`, `px4` and `core` are in
`$SITL_STATE_DIR/logs` and are kept after `stop`; `restart` starts the `px4`
and `core` logs afresh.

| Variable | Default |
|---|---|
| `PX4_DIR` | `~/build/PX4-Autopilot` |
| `PX4_SIM_MODEL` | `gz_x500` |
| `PX4_GZ_WORLD` | `default` (a world in PX4's `Tools/simulation/gz/worlds`) |
| `SITL_STATE_DIR` | `${TMPDIR:-/tmp}/flight_core_sitl` |
| `SITL_TIMEOUT` | `120` seconds to wait for readiness |
| `XRCE_PORT` | `8888` |

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

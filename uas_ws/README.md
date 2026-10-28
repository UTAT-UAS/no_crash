# ROS 2 workspace

ROS 2 Jazzy packages live under `src/`.

- [`flight_core`](src/flight_core/README.md): central PX4 offboard node and the
  Python `Drone` client library.
- [`flight_core_interfaces`](src/flight_core_interfaces/README.md): services used to
  command `flight_core`.
- `px4_msgs`: Git submodule pinned to PX4 v1.17.0 messages.
- [`scripts/sitl`](scripts/sitl): start, stop and script PX4 SITL test sessions.

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

## SITL testing

`scripts/sitl` runs reproducible simulation sessions against the PX4 SITL
build. Build the workspace first; run it from anywhere.

| Command | Effect |
|---|---|
| `sitl start [--no-core] [--gui]` | Start MicroXRCEAgent, Gazebo, PX4 SITL and `flight_core` (`mode:=sim`); wait until ready |
| `sitl restart` | Restart PX4 with fresh parameters and respawn the drone at the origin; Gazebo and the agent keep running, and `flight_core` is restarted if it was running |
| `sitl stop` | Stop everything `start` launched |
| `sitl status` | Show running components and log paths |
| `sitl run [start options] -- <command>` | Start, run the command, stop; exit with the command's status |
| `sitl px4 <module> [args]` | PX4 shell command, e.g. `sitl px4 param show NAV_DLL_ACT` or `sitl px4 commander takeoff` |

Gazebo runs as its own process and PX4 starts in standalone mode, spawning
the drone into the running world. `restart` removes the drone model before
starting PX4 again, so the new PX4 spawns a fresh drone at the origin instead
of attaching to the old one wherever it was.

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

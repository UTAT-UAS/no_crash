# no_crash

A monorepo for drone software: ROS 2 flight software, flight visualization,
and hardware management. Development uses an Ubuntu 24.04 / ROS 2 Jazzy
container targeting `linux/amd64`.

## Quickstart

For host dependencies, Docker installation, and GPU drivers, see
[host setup](docs/devcontainer/host-setup.md).

### Clone and choose a profile

```bash
git clone https://github.com/UTAT-UAS/no_crash.git
cd no_crash
```

Start with `cpu`, or choose `nvidia`, `nvidia-compat`, `amd` (Linux), or
`amd-wsl` (Windows/WSL2) after setting up the host GPU driver.
The [profile table](docs/devcontainer/README.md#profiles) describes each backend.

Install submodules with:

```sh
git submodule update --init --recursive
```

### Open in VS Code

1. Open the repository:

   ```bash
   code .
   ```

2. On Windows, open the folder in WSL using the WSL extension before continuing.
3. Run **Dev Containers: Reopen in Container** from the Command Palette and
   select **no_crash Jazzy: cpu (prebuilt)**, or your chosen profile.
4. Open an integrated terminal and run `no-crash-check`.

Select **local image** to build from source automatically. Local builds compile
large native dependencies; allow time and disk space. See
[image selection](docs/devcontainer/building.md#prebuilt-images) for published images.

### Enter from a terminal

With the Dev Container CLI installed and on `PATH`, run from the repository root:

```bash
./enter.sh                          # Show help
./enter.sh --profile cpu             # Use the prebuilt CPU image
./enter.sh --profile nvidia          # Use the prebuilt NVIDIA image
./enter.sh --profile nvidia --local  # Build locally through Dev Containers
./enter.sh --profile nvidia --rebuild # Remove and recreate the profile container
```

Inside the container, run `no-crash-check`, or `no-crash-check --gpu` for a GPU
profile. Exit the shell with `exit`. Code lives in the mounted `~/workspace`;
export changes stored elsewhere before recreating the container.

## Run the flight stack in simulation

All commands run inside the container, from `~/workspace`. Each long-running
step needs its own terminal; source the overlay in every new ROS terminal with
`source install/local_setup.bash`. This is automatically done for you in the container's `.bashrc`.

1. Build the ROS workspace:

   ```bash
   rosdep install --from-paths uas_ws/src --ignore-src -r -y
   colcon build --base-paths uas_ws/src --symlink-install
   source install/local_setup.bash
   ```

2. Start the simulator: MicroXRCEAgent, Gazebo, PX4 SITL and `flight_core`
   in sim mode.

   ```bash
   scripts/sitl start --gui
   scripts/sitl status    # Components and log paths
   ```

3. Start the bridge that exposes `flight_core` to the visualizer (TCP port 8765):

   ```bash
   ros2 run flight_visualizer_bridge flight_visualizer_bridge
   ```

4. Start the visualizer backend (port 8000); it connects to the bridge on
   `127.0.0.1:8765` by default:

   ```bash
   cd flight_visualizer/backend
   uv run uvicorn app:app --host 0.0.0.0 --port 8000
   ```

5. Start the dashboard and open <http://localhost:5173>:

   ```bash
   cd flight_visualizer/frontend/flight_visualizer
   bun install --frozen-lockfile
   bun run dev
   ```

6. Fly. Acquire control and send commands from the dashboard, or run a
   mission script against the core:

   ```bash
   ros2 run flight_core example_mission
   ```

   Only one client holds control at a time, so a mission script and the
   dashboard cannot both command the drone.

7. Stop the simulator with `scripts/sitl stop`, and the other components with
   Ctrl-C.

`scripts/sitl restart` resets PX4 and respawns the drone without restarting
Gazebo. For a one-shot test, `scripts/sitl run -- ros2 run flight_core example_mission`
starts the simulator, runs the command and stops everything. See
[SITL testing](docs/development/README.md#sitl-testing) for options and logs.

On the drone, run MicroXRCEAgent for the flight controller's link,
`ros2 launch flight_core flight_core.launch.py` (real mode, which never arms
the vehicle), and the bridge. Point the backend at the drone with
`BRIDGE_HOST=<drone address>`.

## Project layout

- [`uas_ws/src/`](uas_ws/README.md): ROS 2 Jazzy packages, built with colcon from the monorepo root.
- [`flight_visualizer/frontend/`](flight_visualizer/frontend/flight_visualizer/README.md): Svelte frontend using Bun.
- [`flight_visualizer/backend/`](flight_visualizer/backend/README.md): Python backend with its own environment and dependencies.
- [`hardware_manager/`](hardware_manager/README.md): Bash and Python hardware scripts.

The ROS workspace contains `flight_core`, a Python and C++ package for the PX4
offboard flight controller, and `flight_visualizer_bridge`, which links it to
the flight visualizer's FastAPI backend and Svelte dashboard.
`hardware_manager` is still a placeholder. Each project declares its own
dependencies.

## Guides

- [Project development](docs/development/README.md): workflows and dependencies.
- [Development container](docs/devcontainer/README.md): profiles and daily use.
- [Documentation index](docs/README.md): host setup, customization, and image maintenance.
- [Agent guide](AGENTS.md): repository conventions for coding agents.

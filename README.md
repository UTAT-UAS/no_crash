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

## Project layout

- [`uas_ws/src/`](uas_ws/README.md): ROS 2 Jazzy packages, built with colcon from the monorepo root.
- [`flight_visualizer/frontend/`](flight_visualizer/frontend/README.md): Svelte frontend using Bun.
- [`flight_visualizer/backend/`](flight_visualizer/backend/README.md): Python backend with its own environment and dependencies.
- [`hardware_manager/`](hardware_manager/README.md): Bash and Python hardware scripts.

These directories currently contain README placeholders. Each project will
declare its dependencies when implementation begins.

## Guides

- [Project development](docs/development/README.md): workflows and dependencies.
- [Development container](docs/devcontainer/README.md): profiles and daily use.
- [Documentation index](docs/README.md): host setup, customization, and image maintenance.
- [Agent guide](AGENTS.md): repository conventions for coding agents.

# Development container

The Ubuntu 24.04 / ROS 2 Jazzy image includes PX4 SITL, Gazebo Harmonic,
QGroundControl, MAVROS, Micro XRCE-DDS Agent, GStreamer with WebRTC, and
OpenCV with GStreamer capture. Start with the [README quickstart](../../README.md#quickstart).
Run repository scripts from the repository root.

## Profiles

Each profile has a **local image** and **prebuilt** configuration, targeting
`linux/amd64`:

| Profile | PyTorch backend | Host |
| --- | --- | --- |
| `cpu` | CPU | Linux or WSL2; host graphics can still accelerate Gazebo |
| `nvidia` | CUDA 13.2 | Linux or WSL2 with compatible NVIDIA hardware and drivers |
| `nvidia-compat` | CUDA 12.6 | Linux or WSL2; additional older supported GPUs/drivers |
| `amd` | ROCm 7.14 | Native Linux with supported AMD hardware |
| `amd-wsl` | ROCm 7.14 plus ROCDXG 1.2.2 | WSL2 with supported AMD hardware and Windows drivers |

See [host setup](host-setup.md) before choosing a GPU profile. The CPU profile
needs no compute GPU. Setup detects displays and devices and generates ignored
host overrides; it does not install drivers.

Each profile has a Compose project name such as `no_crash_nvidia`, shared across
checkouts and local/prebuilt selections. Use `--rebuild` when changing its
checkout or image selection so the container's mount and image match.

`./enter.sh` shows help. `./enter.sh --profile <profile>` selects a prebuilt image.
Add `--local` to build
from source through Dev Containers; VS Code's **local image** choices also build
automatically. Add `--rebuild` to remove the existing profile container, rerun
creation hooks, and rebuild local configurations using Docker's cache.
Export container-local changes before recreation. For manual image builds and
published image selection, see [the build guide](building.md).

## Workspace and storage

| Path inside the container | Purpose |
| --- | --- |
| `~/workspace` | Bind-mounted monorepo; keep project source here |
| `~/workspace/install` | ROS install overlay, sourced by interactive shells when present |
| `~/build` → `/build` | Native compilation, Cargo targets, ccache, temporary files, and colcon build/log output |
| `/build/PX4-Autopilot` | Pinned, editable PX4 checkout and prepared SITL build |
| `~/.local` → `/opt/uas/.local` | Installed commands, native libraries, wheels, and version inventories |
| `~/.venvs` → `/opt/uas/.venvs` | Prepared `vision`, `px4`, and `build-tools` Python environments |
| `~/.cargo`, `~/.rustup`, `~/.bun` | Home symlinks to installations under `/opt/uas` |

The `uas` user has passwordless sudo and is mapped to the host UID/GID.
Large installations and builds live outside home to keep ownership remapping
fast. Those image directories are writable by remapped users; preserve their
home symlinks when installing tools. Apt manages system packages and system Python.

Container-local files survive restarts. Recreation restores the image's files;
keep ongoing code in the mounted workspace and export other changes first.
Create a branch before editing the detached PX4 checkout. Personal tools can be
reinstalled with the [custom installation hook](custom-software.md).

## Daily use

Build ROS packages from the monorepo root, keeping the overlay at `install/`:

```bash
cd ~/workspace
colcon build --base-paths uas_ws/src --symlink-install
```

Projects own and install their dependencies; container hooks do not discover
manifests. Use Bun and committed `bun.lock` files for JavaScript/TypeScript.
Create a dedicated venv for each Python project; ROS-dependent venvs can use
system Python with `--system-site-packages`. See [project workflows](../development/README.md).

Activate the supplied vision tools explicitly:

```bash
source ~/.venvs/vision/bin/activate
python -c 'import torch, cv2; print(torch.__version__, cv2.__version__)'
```

The prepared OpenCV wheel is under `~/.local/share/no-crash/wheels` and depends
on this image's native libraries. Keep NumPy 1.26.4 when using it with Jazzy's
apt-managed `cv_bridge`.

For [PX4/Gazebo simulation](https://docs.px4.io/main/en/sim_gazebo_gz/), prepare
the shell with `sim` (an alias for `source px4-sim`), then launch the model:

```bash
sim
make px4_sitl gz_x500
```

This activates PX4's isolated Python environment, including Empy 3.x, and changes
to its checkout. Run `MicroXRCEAgent udp4 -p 8888` and `qgc` in separate terminals.
ROS builds use Jazzy's system dependencies.

## Maintenance

- [Host setup](host-setup.md): Docker, GPU drivers, displays, and equipment.
- [Custom software](custom-software.md): personal creation hook.
- [Build and publish](building.md): local images, release pins, and validation.
- [Container agent guide](../../.devcontainer/AGENTS.md): implementation conventions.

Release pins and download hashes are in `.devcontainer/versions.env`; the
Dockerfile pins the Jazzy base by SHA-256. Apt packages follow supported Noble,
Jazzy, and Gazebo repositories, with installed versions recorded in the image.

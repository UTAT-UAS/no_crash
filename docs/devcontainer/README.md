# Development container

An Ubuntu 24.04 / ROS 2 Jazzy development environment for the no_crash monorepo.
It includes PX4 SITL, Gazebo Harmonic, QGroundControl, MAVROS,
Micro XRCE-DDS Agent, GStreamer with WebRTC, and OpenCV with GStreamer capture.

Run repository scripts from the repository root. For project workflows, see
[the development guide](../development/README.md).

## Choose a machine configuration

Open this repository in VS Code with the Dev Containers extension, then use
**Dev Containers: Reopen in Container** and select a configuration. Each profile
has a **local image** and **prebuilt** choice:

| Profile | Compute backend | Host |
| --- | --- | --- |
| `cpu` | CPU PyTorch; host graphics can still accelerate Gazebo | Linux or WSL2 |
| `nvidia` | CUDA 13.2 PyTorch | Linux or WSL2 with supported NVIDIA drivers |
| `nvidia-compat` | CUDA 12.6 PyTorch | Linux or WSL2; older supported GPUs/drivers |
| `amd` | ROCm 7.14 PyTorch | Native Linux with supported AMD hardware |
| `amd-wsl` | ROCm 7.14 plus ROCDXG 1.2.2 | WSL2 with supported AMD hardware/drivers |

The configurations target `linux/amd64`. The default terminal entry command
selects the local CPU image, building it only if the tag is missing:

```bash
./enter.sh
./enter.sh --profile nvidia
./enter.sh --profile nvidia --build # Build the image and recreate the container
./enter.sh --profile amd-wsl --prebuilt
```

Existing local images are reused without invoking a source build. To update one,
run `./.devcontainer/build-images.sh <profile>` or pass `--build` to the launcher, which also
recreates the container and reruns its creation hooks. Export any changes kept
only inside the container before recreating it. When using
VS Code's local-image configurations, build the selected image first. Registry
profiles use `--prebuilt`. Dev Containers may still build a cached derived image
to map `uas` to your host UID/GID; this remaps installed home files and skips the
external `/build` tree.

Host requirements: Docker Engine with Compose 2.24 or newer, Bash, Python 3,
and either the VS Code extension or the Dev Container CLI. On Windows, open the
repository through **Remote - WSL**, with Docker Engine running in that WSL
distribution. Keep the checkout on the Linux filesystem. This is particularly
important for AMD WSL: the Docker daemon must see `/dev/dxg` and the DXCore
libraries in that distribution. Docker Desktop's separate daemon is not the
supported AMD WSL configuration.

### NixOS host tools

The pinned `flake.nix` and `flake.lock` supply Bash, Git, Python, the Docker CLI
with Compose and Buildx, the Dev Container CLI, ShellCheck, Hadolint, and uv:

```bash
nix develop path:.
python3 .devcontainer/scripts/validate.py
```

Use `nix develop` once the flake files are tracked by Git. The `path:.` form also
includes files in a new, uncommitted checkout. Docker Engine must already be
enabled on the host and accessible to your user. The flake provides client tools;
the Ubuntu container's dependencies are installed by its Dockerfile.

Run `code .` from this shell to make its tools available to VS Code, or run
`./enter.sh` in the shell when ready to build or use a published image.

No drivers are installed or changed on the host by the setup scripts.
See [host setup](host-setup.md) for GPU, display, and equipment access.

## Workspace

```text
~/workspace/                     # Monorepo, bind-mounted from the host
~/build/ -> /build/              # Shared writable builds, skipped by UID remapping
/build/PX4-Autopilot/            # Editable pinned source and prepared SITL build
/build/cargo-target/             # Cargo compilation output
/build/ccache/                   # Compiler cache
/build/colcon/{build,log}/        # ROS compilation output and logs
/build/tmp/                      # Temporary build files (TMPDIR)
~/.local/bin/                    # qgc, px4-sim, no-crash-check
~/.local/opt/                    # Node, QGC, GStreamer, OpenCV, DDS Agent, ROCDXG
~/.local/share/no-crash/          # Release pins, wheels, package inventories
~/.venvs/vision/                 # Prepared vision tools; activation is explicit
~/.venvs/px4/                    # Isolated PX4 Python build requirements
~/.venvs/build-tools/            # Meson and wheel packaging tools
~/.cargo/, ~/.rustup/            # User Rust toolchain
~/.bun/                          # Bun, bunx, global tools, and package cache
```

The `uas` user has passwordless sudo. Apt manages system packages and system
Python. Custom software is compiled under `~/build` (a symlink to the mode-0777
`/build` directory) and installed in userspace. The retained PX4 checkout and
build files are writable by remapped container users. Dev Containers remaps home
ownership without traversing the build symlink.

Cargo, ccache, and temporary build files use `/build` through environment
variables. Colcon defaults in `~/.colcon/defaults.yaml` place build output and
logs there as well; its install prefix remains `~/workspace/install` so the
workspace overlay can be sourced normally. CMake and Meson custom projects
should likewise use build directories under `/build`.
No project dependency manifests are installed automatically.

```bash
cd ~/workspace
colcon build --symlink-install
```

Once ROS packages are added to the monorepo, build them from its root. Interactive
shells source `~/workspace/install/local_setup.bash` when it exists.

Use Bun for JavaScript/TypeScript dependencies and scripts. Commit each
project's `bun.lock` and use `bun install --frozen-lockfile` for reproducible
installs. Node LTS remains available for tools that require Node.

System Python remains the default. For the supplied vision tools:

```bash
source ~/.venvs/vision/bin/activate
python -c 'import torch, cv2; print(torch.__version__, cv2.__version__)'
```

Future projects should create and manage their own venvs. ROS projects that need
apt-provided modules such as `rclpy` can use the system Python interpreter to
create a venv with `--system-site-packages`. The image's prepared OpenCV wheel is
available under `~/.local/share/no-crash/wheels/`; it relies on the native libraries
installed in this image and is not portable to arbitrary machines. Keep NumPy
1.26.4 when combining this wheel with Jazzy's apt-managed `cv_bridge`.

Use `px4-sim`, `qgc`, and
`MicroXRCEAgent udp4 -p 8888`. `px4-sim` activates only the PX4 venv, preserving
Empy 3.x for its build. ROS builds continue to use Jazzy's system dependencies.

The container's writable home survives restarts. Recreating a container restores
its image-provided home; keep ongoing code changes in the mounted workspace or
export them before rebuilding. Create a development branch before editing the
detached, pinned PX4 checkout.

## Customize and build

See [the build and runtime validation report](test-results.md) for measured
image sizes, ownership-remapping checks, and CPU/NVIDIA test coverage.

- [Container agent guide](../../.devcontainer/AGENTS.md): image conventions and validation commands.
- [Migration audit](migration-audit.md): feature comparison and final dependency corrections.
- [Custom software installer](custom-software.md): a Git-ignored script run
  as `uas` on container creation.
- [Build and manually publish images](building.md): local build targets,
  versioned tags, validation, and image-size checks.
- [Host setup](host-setup.md): graphics, GPU runtimes, USB, and networking.

Release pins and download checksums are in `.devcontainer/versions.env`. The
Jazzy base image is pinned by SHA-256 in the Dockerfile. System packages follow
the supported Noble, Jazzy, and Gazebo repositories; builds record the versions
actually installed. No GitHub Actions build or publishing workflow is provided.

Man pages are not restored with `unminimize`; use online documentation.

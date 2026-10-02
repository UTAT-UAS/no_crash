# Host setup: Docker, GPUs, and equipment

The host scripts generate ignored Compose overrides for the selected profile.
They do not install drivers or change display access controls. Configure the
host first, then enter the container and verify the selected backend.

## Required software

| Software | Needed for |
| --- | --- |
| [Git](https://git-scm.com/downloads), Bash, Python 3 | Cloning and running the setup scripts on Linux or inside WSL2 |
| [Docker Engine](https://docs.docker.com/engine/install/), Compose v2.24+, Buildx | Running and building containers; install the Compose and Buildx plugins alongside Engine |
| [VS Code](https://code.visualstudio.com/download) and [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) | Opening the environment in VS Code |
| [Dev Container CLI](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli) | Using `./enter.sh` from a terminal |
| [Node.js LTS](https://nodejs.org/en/download) and [Bun](https://bun.sh/docs/installation) | Installing the CLI manually: `bun add --global @devcontainers/cli` |
| [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) with Ubuntu 24.04 and [VS Code WSL](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl) | Windows hosts |

## Docker and host tools

Install [Docker Engine](https://docs.docker.com/engine/install/) with its Compose
and Buildx plugins, plus Git, Bash, and Python 3. On Ubuntu, follow
[Docker's Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/)
for `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, and
`docker-compose-plugin`. Use Compose v2.24 or newer.
Follow [Docker's Linux post-installation guide](https://docs.docker.com/engine/install/linux-postinstall/)
to make the daemon accessible to your user, then check:

```bash
docker info
docker compose version
docker buildx version
```

Install VS Code and its Dev Containers extension for editor use. For terminal
entry, install the [Dev Container CLI](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli).
With Node LTS and Bun on `PATH`:

```bash
bun add --global @devcontainers/cli
devcontainer --version
```

Ensure Bun's global bin directory (`~/.bun/bin` by default) is on `PATH`.

On NixOS, enable Docker in your host configuration and use the pinned host tools:

```bash
nix develop
code . # Or run ./enter.sh --profile cpu from this shell
```

The flake supplies Bash, Git, Python, the Docker CLI with Compose/Buildx,
Dev Container CLI, ShellCheck, Hadolint, and uv. It supplies client tools;
the Docker daemon and GPU drivers are host-managed.

## GPU profiles at a glance

| Host / GPU | Profile | Driver and Docker access |
| --- | --- | --- |
| Linux / NVIDIA | `nvidia` or `nvidia-compat` | Linux NVIDIA driver plus NVIDIA Container Toolkit; CDI or runtime GPU request |
| Windows / NVIDIA | `nvidia` or `nvidia-compat` | Windows NVIDIA driver, WSL2, and Container Toolkit for the Docker Engine in WSL |
| Linux / AMD | `amd` | Compatible AMDGPU kernel driver; `/dev/kfd` and `/dev/dri` passed to Docker |
| Windows / AMD | `amd-wsl` | Supported Windows AMD driver and WSL2; `/dev/dxg` and DXCore passed to Docker |

GPU compute and GUI acceleration are separate checks. Use `cpu` when your GPU
is outside the vendor's supported matrix.

## NVIDIA on Linux

1. Install the driver using your distribution's packages, following
   [NVIDIA's driver installation guide](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/latest/index.html).
   Reboot after installation and confirm `nvidia-smi` works on the host.
2. Match the GPU and driver to the image's CUDA backend using
   [NVIDIA's CUDA compatibility guide](https://docs.nvidia.com/deploy/cuda-compatibility/).
   `nvidia` supplies CUDA 13.2; `nvidia-compat` supplies CUDA 12.6. The latter
   supports additional older hardware, subject to the wheel's supported architectures.
3. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
   from NVIDIA's package repository. For a system Docker daemon using the NVIDIA
   runtime, configure it and restart Docker:

   ```bash
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

   The toolkit guide has separate configuration instructions for rootless Docker.

The initializer selects CDI when it finds an NVIDIA spec under `/etc/cdi` or
`/var/run/cdi`; otherwise it requests GPUs through the runtime. CDI must be enabled
in the Docker daemon; [Docker enables it by default from Engine 28.3](https://docs.docker.com/reference/cli/dockerd/#configure-cdi-devices).
See [NVIDIA's CDI guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html)
for spec generation and `nvidia-ctk cdi list`. On NixOS, enable the distribution's
NVIDIA container tooling and generated CDI specification.

To select the runtime explicitly, create ignored `.devcontainer/runtime-options.json`:

```json
{"nvidia_mode": "runtime"}
```

Valid modes are `auto` (default), `cdi`, and `runtime`. For a CDI-enabled Docker
daemon, a driver visibility check is:

```bash
docker run --rm --device nvidia.com/gpu=all ubuntu:24.04 nvidia-smi
```

For the NVIDIA runtime, replace `--device nvidia.com/gpu=all` with `--gpus all`.
Then run `./enter.sh --profile nvidia` and `no-crash-check --gpu` inside the container.
The image supplies its CUDA/PyTorch libraries; a host CUDA toolkit is unnecessary.

## AMD on Linux

Check your GPU, host distribution, kernel, and driver against
[AMD's ROCm 7.14.1 compatibility matrix](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html).
Follow the matching [AMD installation instructions](https://rocm.docs.amd.com/en/docs-7.14.1/install/rocm.html)
for the host AMDGPU driver and reboot after a driver change. Confirm the
compute and render device nodes exist:

```bash
ls -l /dev/kfd /dev/dri/render*
```

The container shares the host kernel, so the driver must work on the host.
The image's PyTorch dependencies provide userspace ROCm libraries; installing
the entire ROCm SDK on the host is unnecessary for this container.
[AMD's Docker guide](https://rocmdocs.amd.com/en/latest/install/docker-containers.html)
explains direct device passthrough. This repo uses that approach, passing
`/dev/kfd`, `/dev/dri`, and their device groups to `uas`, with private shared
memory and no privileged mode. No AMD container runtime toolkit is required.

Run `./enter.sh --profile amd`, then `no-crash-check --gpu` inside the container.
If devices are absent, fix the host driver first; if access is denied, inspect
device ownership and the generated `.devcontainer/runtime/amd.yaml` groups.

## Windows and WSL2

Use Windows 11 with a current WSL2 installation and WSLg. Follow
[Microsoft's WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).
In an Administrator PowerShell terminal:

```powershell
wsl --install -d Ubuntu-24.04
wsl --update
wsl --list --verbose
```

Confirm the distribution is using WSL version 2. Install Docker Engine and the
Linux host tools **inside that distribution**, then open the checkout through
[VS Code's WSL extension](https://code.visualstudio.com/docs/remote/wsl).
Keep source under `~/no_crash`, rather than `/mnt/c`, following
[Docker's WSL filesystem guidance](https://docs.docker.com/desktop/features/wsl/best-practices/).
Check `docker context show` and `docker info` to confirm the CLI targets that
distribution's daemon. This keeps host detection, GPU devices, and bind mounts
on the same machine.

### NVIDIA on Windows

Install a supported [NVIDIA Windows driver](https://www.nvidia.com/en-us/drivers/)
and follow [NVIDIA's CUDA on WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).
The Windows driver exposes CUDA to WSL; do not install a Linux NVIDIA display
or kernel driver inside WSL. Update WSL and confirm `nvidia-smi` works there
(use `/usr/lib/wsl/lib/nvidia-smi` if it is not on `PATH`). Install and configure
NVIDIA Container Toolkit for the Docker Engine in the WSL distribution as above.

Select `nvidia` or `nvidia-compat` according to CUDA/GPU compatibility, then run
`no-crash-check --gpu` inside the container. Docker Desktop also supports
[NVIDIA GPU passthrough with its WSL2 backend](https://docs.docker.com/desktop/features/gpu/);
this repo's WSLg/device mounts are configured for a daemon inside the checkout's
WSL distribution, so use that route for the documented environment.

### AMD on Windows

Use the `amd-wsl` profile. Check your GPU and Windows driver against the
[ROCDXG release's compatibility matrix](https://github.com/ROCm/librocdxg/tree/v1.2.2)
and [AMD's WSL guidance](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/wsl/howto_wsl.html).
Install the matching [AMD Windows driver](https://www.amd.com/en/support/download/drivers.html),
restart Windows, and update WSL. In the WSL distribution, confirm:

```bash
ls -l /dev/dxg /usr/lib/wsl/lib/libdxcore.so
```

The Windows driver and WSL provide GPU access; Linux AMDGPU/DKMS installation
is not part of this path. The image supplies ROCm and ROCDXG 1.2.2, while the
initializer passes `/dev/dxg` and mounts Microsoft's DXCore library read-only.
Use Docker Engine in this distribution; Docker Desktop's separate daemon is
not the supported configuration for these AMD WSL mounts.

Run `./enter.sh --profile amd-wsl`, then `no-crash-check --gpu`. Verify Gazebo
graphics separately; successful compute does not establish GUI acceleration.

## Displays

On Linux, start VS Code or `enter.sh` with `DISPLAY` set. Setup passes the X11
socket and available `XAUTHORITY` file (or `~/.Xauthority`), plus `/dev/dri` for
rendering. Wayland sessions can use XWayland. If an X11 grant is required, scope
it to the container user and revoke it afterward. Verify access with `xeyes`.

On WSL2, setup passes available WSLg sockets, display/audio variables, `/dev/dxg`,
and WSL graphics libraries. For headless use, start without `DISPLAY`.
Preview host settings without writing files:

```bash
python3 .devcontainer/scripts/prepare-host.py --profile cpu --headless --dry-run
```

## Equipment and networking

Devices are opt-in through ignored `.devcontainer/runtime-options.json`:

```json
{"hardware_devices": ["/dev/ttyACM0", "/dev/video0", "/dev/input/js0"]}
```

List only needed paths; missing devices fail initialization. A `/dev/input`
directory exposes its current device nodes, so prefer specific nodes where
possible. Numeric device groups are added on Linux. Recreate the container
after hotplug or option changes. For Windows USB devices, first follow
[Microsoft's USB-to-WSL instructions](https://learn.microsoft.com/en-us/windows/wsl/connect-usb).
Set `SDL_GAMECONTROLLERCONFIG` in your shell configuration if QGC needs a custom
joystick mapping; its wrapper preserves this variable.

Simulation, QGC, and the DDS Agent run in the same container by default. For
external ROS discovery or host QGC on native Linux, add `"host_network": true`
to the options file, recreate the container, and check firewall/ROS domain
settings. This override is restricted to native Linux.

# Environment migration audit

Compared on 2026-10-01 against the previous environment's local working tree,
including its Dockerfile, Compose and Dev Container settings, lifecycle hooks,
personal profile, shell aliases, editor files, repository manifests, launcher,
Nix shell, ignore rules, and README. The comparison includes local changes;
the previous checkout's HEAD was `a41082060a270d7f00235957a2d6af96d445ded5`.

The core drone development tools and workflows are accounted for. The final
comparison found missing firmware, simulation, and numerical development
dependencies and restored them in
[`install-system.sh`](../../.devcontainer/image/install-system.sh).
Previously built images do not contain these additions until rebuilt.

## Release and toolchain comparison

These are the reviewed pins in
[`versions.env`](../../.devcontainer/versions.env), rather than versions resolved
from a moving `latest` tag during a build.

| Component | Previous environment | Current environment |
| --- | --- | --- |
| OS / ROS | Ubuntu 22.04 / Humble desktop-full | Ubuntu 24.04 / Jazzy desktop-full; SHA-256 pinned |
| Python | Ubuntu Python 3.10 | Ubuntu Python 3.12; separate vision, PX4, and build-tool venvs |
| PX4 | 1.16.0 | 1.17.0; pinned commit, recursive submodules, retained writable sources and SITL build |
| Gazebo | Harmonic, installed by PX4 setup | Harmonic, installed explicitly from the Noble repository; 8.15.0 in tested images |
| Micro XRCE-DDS Agent | 2.4.2; patched Fast DDS superbuild | 2.4.3; Jazzy system Fast DDS/Fast CDR/spdlog; Agent 2.x retained for PX4 compatibility |
| MAVROS / rosbridge / ROS-Gazebo | Humble packages and Gazebo setup dependencies | Jazzy packages; GeographicLib datasets installed by a checksum-verified script |
| QGroundControl | 5.0.6 AppImage, extracted at launch | 5.1.5; verified download, extracted once, userspace `qgc` wrapper |
| OpenCV + contrib | 4.12.0, global Python installation | 4.14.0; pinned commits, userspace native libraries and a custom vision-venv wheel |
| GStreamer | Moving `1.26` branch | 1.28.7; pinned commit, userspace installation |
| Rust WebRTC plugins | `gstreamer-1.26.7` branch | Reviewed `0.15.4+fixup` commit; WebRTC plugin and signalling server |
| PyTorch / torchvision | 2.8.0 / 0.23.0; manually edited backend | 2.14.1 / 0.29.1; CPU, CUDA 13.2, CUDA 12.6, and ROCm 7.14 profiles |
| Ultralytics | 8.3.217, global pip | 8.4.171 in the vision venv; custom OpenCV and NumPy constraints |
| NumPy and scientific Python | Ubuntu apt packages; pip packages subsequently uninstalled | Apt scientific Python retained; NumPy 1.26.4 constraint for OpenCV and Jazzy `cv_bridge` |
| Node / JS package manager | Node 22; pnpm installed at creation | Node 24.21.0 LTS; Bun 1.4.2; verified archives |
| Rust / build tooling | Unpinned Rust, cargo-c, and Meson | Rust 1.99.0, cargo-c 0.10.25+cargo-0.99.0, Meson 1.12.1; userspace tools |
| Nix host tools | Unpinned `shell.nix` with Dev Container CLI | `flake.nix` plus committed lock; CLI, Docker/Compose/Buildx, linters, Bash, Python, Git, and uv |

Apt packages track the supported Noble, Jazzy, and Gazebo repositories. Their
installed versions are recorded in `~/.local/share/no-crash/apt-packages.tsv`;
the base digest does not freeze subsequent apt updates. Python inventories are
recorded alongside the release pins and in the retained PX4 checkout.

## Dependency gaps corrected

The previous Dockerfile ran PX4's setup script with its default firmware and
simulation options. Comparing its
[PX4 1.16 setup script](https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/Tools/setup/ubuntu.sh)
against the explicit package list exposed omitted dependencies. They now have
explicit entries, including dependencies already supplied transitively:

- Firmware: `binutils-dev`, `gcc-multilib`, `gettext`, `kconfig-frontends`,
  `libisl-dev`, `libmpc-dev`, `libmpfr-dev`, `libncurses-dev`, `screen`, `texinfo`,
  `u-boot-tools`, `util-linux`, and `vim-common`. Existing ARM GCC, Newlib,
  multilib, GDB, and build tools remain. LLVM `lld` and `lldb` are also included
  to follow the current PX4 setup dependency list.
- Simulation/media: `dmidecode`, `gstreamer1.0-plugins-base`,
  `gstreamer1.0-plugins-ugly`, `libeigen3-dev`, `libimage-exiftool-perl`,
  `libopencv-dev`, and `protobuf-compiler`.
- Numerical development: `gfortran` and `libatlas-base-dev`, which were explicit
  dependencies of the previous OpenCV build. ATLAS and Kconfig frontends are
  available in Noble's repositories; see
  [the ATLAS package](https://packages.ubuntu.com/noble/libatlas-base-dev) and
  [the Kconfig package](https://packages.ubuntu.com/noble/kconfig-frontends).

The full updated apt install list was resolved with `apt-get -s install` in a
disposable container based on the existing CPU image. It resolved 34 new
packages, zero upgrades, and zero removals. This establishes repository and
dependency compatibility; it does not test installation, firmware compilation,
or the resulting OpenCV build. New image sizes must be measured after rebuilding.

## Workflow and configuration comparison

| Previous behavior | Current behavior |
| --- | --- |
| One GPU-oriented configuration; backend selected by editing the creation hook | Five profiles, each with local and prebuilt selections; no compute installs at creation |
| Registry image or manually edited Compose image reference | Local tags reused; missing tags built by the launcher; explicit `--build` rebuilds and recreates; ignored registry overrides supported |
| Non-root `uas`, passwordless sudo, dialout access | Preserved; host UID/GID mapping tested; numeric hardware groups passed as needed; account passwords are not cleared |
| Writable `/build`, but some later tools installed in a remapped home | Every compilation path uses `/build`; large userspace installs use `/opt/uas`; both are reached through home symlinks |
| ROS overlay under `uas_ws/install` | Colcon builds from the monorepo root; overlay at `~/workspace/install`, automatically sourced in interactive shells |
| Separate creation/start hooks; repeated appends to `.bashrc` and Git safe-directory settings | Idempotent creation hook; managed shell block; safe directory added once |
| Custom profile chosen through `.user`; personal software mixed with shared setup | Git-ignored `.devcontainer/custom-install.sh` executed as `uas`; [installer guide](custom-software.md) |
| Simulator VS Code task launching PX4, DDS Agent, and QGC | Portable `px4-sim`, `MicroXRCEAgent udp4 -p 8888`, and `qgc` commands; `sim` and `uxrce` aliases; [runtime commands](building.md) |
| Global pip installs and uninstalling NumPy/OpenCV afterward | Dedicated venvs; apt system Python; version constraints and `pip check` |
| X11 mount and hardcoded authority path | Detected X11 socket/authority; WSLg integration; headless selection |
| Privileged mode, all of `/dev`, host IPC, fixed container name | Scoped devices and numeric groups; no privileged mode; private IPC with 2 GB shared memory; Compose-managed container names |
| NVIDIA CDI manually edited into Compose; other GPU guidance incomplete | NVIDIA CDI/runtime selection plus native AMD and AMD WSL integration; host drivers remain host-managed |
| Manually edited host networking and joystick mounts | Ignored host options for native Linux networking, serial devices, cameras, and joysticks; QGC preserves personal SDL mappings |
| Build and installation sources stored in final layers | Native builder stage; installed artifacts copied to final images; editable PX4 retained; build caches excluded |

## Deliberate removals and narrower defaults

- Repository manifests, import/pull/tag aliases, and nested-repository editor
  paths are removed for the monorepo. `vcstool` remains available as a tool.
  Application source and a matching `px4_msgs` package must be added to the
  monorepo; they are not fetched by container setup.
- The old `.vscode` files are removed. Useful C/C++, CMake, Python, Ruff, Git,
  spelling, and Svelte extensions are selected in the Dev Container generator.
  Personal resource monitoring, Pylint, docstring, formatter, and keybinding
  choices can be configured per developer. Simulator tasks are covered by the
  portable commands above.
- The Zellij profile and personal terminal/joystick settings are removed from
  shared setup. Personal customization uses the documented installer.
- Forwarded ports and the commented desktop-lite/VNC configuration are absent.
  GUI use is through X11/WSLg; headless simulation is supported.
- `unminimize`, explicit `man-db`, and upstream documentation/test/example builds
  are omitted. `apt-utils` and cosmetic `neofetch` are not explicitly installed.
- ROS 1's `python3-genpy` is not installed. PX4 gets `pyros-genmsg` through its
  own requirements and venv; Jazzy supplies the ROS 2 development tools.
- `gnupg2` is replaced by `gnupg`; `libexpat-dev` by `libexpat1-dev`; the manual
  `python` symlink by `python-is-python3`. QGC uses `libxcb-cursor0` instead of
  development headers and runs without `libfuse2` because it is already extracted.
- ModemManager is absent from the tested image; the old unconditional removal
  is unnecessary. Host ModemManager and device permissions remain host concerns.
- The custom GStreamer build explicitly omits GES, Python/introspection bindings,
  Qt plugins, RTSP server, C# bindings, validation/development tools, and the
  aggregate `gst-full` library. WebRTC, libnice, libav, CLI tools, and OpenCV
  capture remain enabled. Its plugin paths are isolated from the older distro
  GStreamer; QGC uses its own runtime rather than these overrides.
- The custom OpenCV build omits `viz`, Java, Python 2, and standalone sample apps;
  its remaining available contrib modules, GTK, FFmpeg, V4L2, and GStreamer are
  retained. The custom wheel is installed into the vision venv, with native
  libraries under `~/.local/opt`, rather than into system Python.
- Temporary firmware payloads and camera firmware/log files from the previous
  working tree are not environment dependencies and are not imported.
- Images are built locally with `.devcontainer/build-images.sh` and published
  by invoking `.devcontainer/push-images.sh`; no hosted image publishing workflow
  is added. Registry configurations select the published tags or digests.

## Verification and remaining coverage

The documentation move preserves the existing
[image and runtime report](test-results.md). All five previously built targets
passed image checks; CPU and NVIDIA had actual Dev Container, ROS, vision,
simulation, and GUI checks. AMD, AMD WSL, and NVIDIA compatibility GPU execution
remain untested on this host. Firmware compilation, flashing, and live flight
controller/camera/joystick hardware are not established by the SITL tests.

The final comparison adds apt dependency resolution, a rerun of static
validation, and local documentation link checks. Rebuild the image targets and
rerun their checks to validate the restored dependencies in final images.
The existing NVIDIA container is unaffected by these file changes.

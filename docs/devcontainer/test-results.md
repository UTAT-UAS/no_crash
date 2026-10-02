# Build and runtime results

The image IDs and initial runtime results below describe the images built before
the final migration audit and external installation storage changes. The
subsequent storage tests are recorded separately below. Rebuild images to apply
the current installation layout. See [the migration audit](migration-audit.md).

Validated on 2026-10-01 on an x86_64 NixOS 26.05 host with an NVIDIA RTX 5070 Ti
and driver 595.71.05. Builds used the pinned flake, Docker Buildx, and
`NO_CRASH_BUILD_JOBS=12`.

## Images

All five targets built successfully and passed their built-in
`no-crash-check --build` checks.

| Local image tag                | Image ID (short) | Expanded size |
| ------------------------------ | ---------------- | ------------: |
| `no_crash:local-cpu`           | `129177c00d39`   |       16.0 GB |
| `no_crash:local-nvidia`        | `2b5e11bdeb81`   |       20.6 GB |
| `no_crash:local-nvidia-compat` | `d74fa2a1a461`   |       21.8 GB |
| `no_crash:local-amd`           | `0d695e54fb5a`   |       32.9 GB |
| `no_crash:local-amd-wsl`       | `2dd2b5988d5b`   |       32.9 GB |

Sizes are Docker's uncompressed image sizes in decimal GB. Common layers are
shared between profiles; adding these sizes does not give actual disk usage.
These are local images, without published registry digests. Inspect them with:

```bash
docker image inspect no_crash:local-cpu --format '{{.Id}} {{.Size}}'
docker system df
```

## Checks that passed

- Static validation: Bash/Python syntax, ShellCheck, Hadolint, all ten merged
  Compose configurations, release pins, generated configuration consistency,
  and 23 tests covering host setup, lifecycle hooks, OpenCV relocation, and
  launcher image selection.
- CPU and NVIDIA runtime integration: OpenCV/GStreamer capture, `cv_bridge`,
  vision package imports, WebRTC tools, C++ compilation with colcon, ROS Jazzy
  publish/subscribe, and Bun execution.
- NVIDIA compute: tensor operations and torchvision NMS on CUDA through NixOS
  CDI (`nvidia.com/gpu=all`).
- Actual CPU and NVIDIA Dev Containers startup: generated host overrides,
  automatic host UID/GID mapping, workspace mounts, and `onCreateCommand`.
  Runtime integration also passed inside both remapped containers.
- CPU headless Gazebo Harmonic/PX4 simulation and XRCE-DDS Agent connection:
  ROS discovered `/fmu/out/vehicle_status_v1` among 67 topics.
- NVIDIA simulation with `gz_x500_mono_cam`: DDS discovery and reception of a
  rendered 1280×960 camera frame through the generated GPU/X11 configuration.
- NVIDIA OpenGL: direct rendering reported the RTX 5070 Ti renderer.
- QGroundControl: CLI help and its `--simple-boot-test` passed with Qt offscreen;
  the boot test also passed through the generated native X11 configuration.

## Build directories and ownership

Every configured compilation directory is under the mode-0777 `/build`:

| Purpose                                    | Location                    |
| ------------------------------------------ | --------------------------- |
| Native source compilation and retained PX4 | `/build/<software>`         |
| Cargo compilation output                   | `/build/cargo-target`       |
| Compiler cache                             | `/build/ccache`             |
| Colcon compilation output and logs         | `/build/colcon/{build,log}` |
| Temporary build files                      | `/build/tmp`                |

`~/build` is a symlink to `/build`. Installed tools and venvs remain in userspace,
and the ROS install overlay remains `~/workspace/install`.

The host user is UID 1000, GID 100. After Dev Containers remapping, home was
owned by `1000:100`, while `/build/PX4-Autopilot` remained `1000:1000` and
writable. This verifies that recursive home ownership remapping skipped the
external build tree. A separate container running as UID/GID `12345:12345` could
also write to the retained PX4 tree. Upstream permission overrides are normalized
in the builder; Docker's copied top directory is explicitly made writable.

In that original layout, installed home files still required remapping. First
startup took approximately 6 minutes for CPU and 4 minutes for NVIDIA after the
base image build completed on this host. Later starts reused the derived image.
The unused Ubuntu `users`
group at GID 100 is removed when it has no users, allowing NixOS GID mapping.

Local-image configurations contain no Compose `build:` instructions. The
launcher reuses an existing `no_crash:local-<profile>` tag, builds a missing tag,
and requires `--build` to update an existing one. Live NVIDIA startup confirmed
Compose reported `No services to build` and used `no_crash:local-nvidia` as the
base for its UID/GID mapping layer. This avoids the previous full source build
when startup's default four jobs differed from the twelve used for validation.
After that mapping completed, a second `./enter.sh --profile nvidia` attached
to the same running container without a build. The local NVIDIA image ID stayed
`2b5e11bdeb81`.

## Image helper validation

After moving the build helper into `.devcontainer/` and adding the GHCR push
helper, static validation passed with 28 tests. The additional checks use a fake
Docker executable to verify building all profiles from another working
directory, publication destinations and image IDs, preflight handling of
missing images, and stopping after build or push failures. Documentation links
and executable permissions also passed. No real builds or registry pushes ran
as part of this helper validation.

## External installation storage

The current image inputs make the large installation paths in home symlinks:

| Home path | Physical installation path |
| --- | --- |
| `~/.local` | `/opt/uas/.local` |
| `~/.venvs` | `/opt/uas/.venvs` |
| `~/.cargo` | `/opt/uas/.cargo` |
| `~/.rustup` | `/opt/uas/.rustup` |
| `~/.bun` | `/opt/uas/.bun` |

Directories are mode 0777 and installed files are writable across UID changes;
ordinary files retain no execute bits. Normalization happens during installation
to avoid adding another copy of the installed files to final image layers.
BuildKit cache mounts and external symlink targets are excluded. `.cache` stays
in home so pip sees cache ownership matching its user. Home also contains
`.hushlogin`, suppressing Ubuntu's sudo hint and its `groups` lookup.

Static validation passed with 30 tests, including permission preservation,
cache exclusion, and avoiding traversal of symlink targets. The actual storage
initialization from `install-system.sh` also passed in a disposable pinned Jazzy
base container, with permission normalization executed as `uas`.

A disposable container using CPU image `b9889af62fa2` relocated the existing
installed tools while retaining their home paths. After editing the account
and recursively changing home ownership as Dev Containers does:

- Home was 1.4 MB; the moved installation trees previously occupied about 4 GB.
- The home chown completed in under 100 ms on this host. External installation
  directory ownership stayed unchanged.
- Runtime checks passed as UID/GID `12345:12345`: OpenCV/GStreamer capture,
  `cv_bridge`, PyTorch/torchvision, WebRTC, ROS delivery, colcon C++ compilation,
  Node, Bun, Rust, Meson, PX4's Empy environment, and QGC help.
- The mapped user could write through every home link, rewrite an existing venv
  configuration, create a fresh venv and run its pip entry point, and change
  Rustup settings.
- A fresh interactive login shell displayed neither the sudo hint nor the group
  warning, with supplemental GID 303 left unnamed. Device group mappings were
  unchanged.

A second disposable container using NVIDIA image `af42ca9d9289` passed the same
storage, mutation, shell, and tool checks with CUDA 13.2 on the RTX 5070 Ti.
PyTorch tensor operations and torchvision NMS executed on CUDA as the remapped
user. Home was again 1.4 MB; its ownership update took 43 ms. The successful CPU
ownership update took 34 ms. These timings measure just the recursive home
chown in the test containers.

These checks exercise the layout with an existing compiled toolchain. They do
not establish a full rebuild of the new Dockerfile or measure total Dev
Containers startup time. Published images and existing containers need rebuilding
and recreation to adopt the new storage layout.

## Coverage limits

AMD and AMD WSL images compiled and passed their image checks. AMD hardware,
WSL GPU passthrough, and the NVIDIA compatibility profile's GPU kernels were
not tested on this host. Typed PX4 ROS message consumption requires matching
`px4_msgs` in the monorepo; the simulation check validates DDS discovery.
Interactive flight, vehicle arming, and manual QGC camera viewing remain manual
checks. See [the build guide](building.md) for repeatable commands.

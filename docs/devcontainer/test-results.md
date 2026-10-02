# Build and runtime results

The image IDs and runtime results below describe the images built before the
final migration audit. The audit restored firmware and simulation dependencies
in the image inputs; those additions require an image rebuild before they are
available in the local tags. See [the migration audit](migration-audit.md).

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

Installed home files still require remapping. First startup took approximately
6 minutes for CPU and 4 minutes for NVIDIA after the base image build completed
on this host. Later starts reuse the derived image. The unused Ubuntu `users`
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

## Coverage limits

AMD and AMD WSL images compiled and passed their image checks. AMD hardware,
WSL GPU passthrough, and the NVIDIA compatibility profile's GPU kernels were
not tested on this host. Typed PX4 ROS message consumption requires matching
`px4_msgs` in the monorepo; the simulation check validates DDS discovery.
Interactive flight, vehicle arming, and manual QGC camera viewing remain manual
checks. See [the build guide](building.md) for repeatable commands.

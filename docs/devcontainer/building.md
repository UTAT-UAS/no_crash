# Local builds and manual publishing

Run the commands in this guide from the repository root.

All builds run locally. There is no hosted build or publishing workflow.
Start with four concurrent compilation jobs; reduce this for machines with
limited RAM. Native compilation and GPU packages require substantial disk space.

On NixOS, enter the pinned host tool environment with `nix develop path:.`
before running the commands below. Use `nix develop` after tracking the flake
files in Git. Entering the shell does not build a container image.

```bash
NO_CRASH_BUILD_JOBS=4 ./.devcontainer/build-images.sh all
```

`all` builds the five profiles in order, sharing the common BuildKit stages and
stopping if a build fails. To build a single profile instead:

```bash
NO_CRASH_BUILD_JOBS=4 ./.devcontainer/build-images.sh cpu
./.devcontainer/build-images.sh nvidia
./.devcontainer/build-images.sh nvidia-compat
./.devcontainer/build-images.sh amd
./.devcontainer/build-images.sh amd-wsl
```

The helper loads `no_crash:local-<profile>` into Docker. The corresponding local
devcontainer configuration uses that tag without a Compose `build:` section.
BuildKit shares the
common stages across profiles. `amd-wsl` extends the AMD image with ROCDXG;
NVIDIA and CPU profiles contain only their selected PyTorch backend.

`./enter.sh --profile nvidia` reuses `no_crash:local-nvidia` when present. A
missing local image is built once by the launcher. Use
`./enter.sh --profile nvidia --build` to explicitly rebuild and recreate the
container, or run the build helper separately. Export changes kept only inside
the container before recreating it. VS Code's local-image configurations require the image to
have been built already. Both local and registry profiles can create a cached
UID/GID mapping image during startup; this does not compile the toolchain again.

The equivalent direct command is:

```bash
docker buildx build --load --platform linux/amd64 --target cpu \
  --build-arg BUILD_JOBS=4 -f .devcontainer/Dockerfile -t no_crash:local-cpu .
```

## Validate

Before any image build:

```bash
python3 .devcontainer/scripts/validate.py
```

This checks Bash syntax, release pin formats, profile consistency, all ten merged
Compose models, and simulated Linux/WSL/device cases. It tests the custom setup
hook with isolated temporary homes and OpenCV extension relocation. ShellCheck
and Hadolint run when available. It does not
build images or start containers.

The flake supplies all validation tools. Update its host tool versions with
`nix flake update nixpkgs`, and review and commit the resulting `flake.lock`.

Each image build runs `no-crash-check --build`, which imports the prepared vision
tools, performs a GStreamer video capture and a `cv_bridge` conversion, checks
WebRTC plugins and command-line tools, and verifies the prepared PX4 executable.
After entering the selected devcontainer:

```bash
no-crash-check
no-crash-check --gpu       # For a GPU profile on supported hardware
bash .devcontainer/scripts/test-runtime.sh       # ROS delivery and CPU vision ops
bash .devcontainer/scripts/test-runtime.sh --gpu # NVIDIA vision kernels and ROS
bash .devcontainer/scripts/test-sitl.sh           # Headless Gazebo/PX4 DDS discovery
bash .devcontainer/scripts/test-sitl.sh gz_x500_mono_cam # Also verify a camera frame
px4-sim                   # GUI/manual simulation validation
MicroXRCEAgent udp4 -p 8888 # In a second terminal
qgc                       # In a third terminal
```

The headless check discovers the DDS topic names and types. To consume typed
messages, include `px4_msgs` matching the pinned PX4 release in the monorepo, then build
the ROS packages before validating DDS:

```bash
cd ~/workspace
colcon build --symlink-install
source install/setup.bash
ros2 topic echo /fmu/out/vehicle_status_v1 --qos-reliability best_effort
```

Confirm the simulator connects to QGC and the Agent, messages arrive, and the
camera viewer works. Check each intended Linux and WSL GPU/GUI combination on
real hardware. A passed static check does not establish that native compilation
or GPU passthrough works.

## Push built images

Choose a namespace you can publish to, log in using your normal Docker registry
credentials, then invoke the push helper:

```bash
docker login ghcr.io
./.devcontainer/push-images.sh all
# Or publish one profile:
./.devcontainer/push-images.sh cpu
```

The helper checks every selected `no_crash:local-<profile>` image before any
push, tags the inspected image IDs, and publishes
`ghcr.io/utat-uas/no_crash:<snapshot-date>-<profile>`. The default release date
comes from `.devcontainer/versions.env`. It stops on an error; earlier successful
pushes remain published if a later push fails. Docker manages credentials;
the helper does not log in or build images.

To rebuild all images and push only after every build succeeds:

```bash
./.devcontainer/build-images.sh all && ./.devcontainer/push-images.sh all
```

Use a new release tag for changed published images. Set `NO_CRASH_IMAGE_PREFIX`
and `NO_CRASH_IMAGE_TAG` for a different GHCR repository or release:

```bash
NO_CRASH_IMAGE_PREFIX=ghcr.io/your-org/no_crash \
NO_CRASH_IMAGE_TAG=2026-10-01-r2 ./.devcontainer/push-images.sh all
```

The push helper accepts GHCR repository prefixes without a tag or digest. Use
the same settings when selecting those images through the prebuilt profiles.
Per-profile `.devcontainer/images.json` overrides affect image selection;
publishing uses the prefix and tag settings above.

The prebuilt profiles default to
`ghcr.io/utat-uas/no_crash:2026-10-01-<profile>`. They become usable after those
images are published. To use another namespace/tag, set `NO_CRASH_IMAGE_PREFIX`
and `NO_CRASH_IMAGE_TAG` before launching VS Code or `enter.sh`. Alternatively,
create the ignored `.devcontainer/images.json` with per-profile references:

```json
{
  "cpu": "ghcr.io/your-org/no_crash:2026-10-01-cpu",
  "nvidia": "ghcr.io/your-org/no_crash:2026-10-01-nvidia"
}
```

References can include `@sha256:<published-digest>` for immutable selection.
The host initializer generates an ignored Compose override; tracked files do
not need editing. Prebuilt configurations contain no Docker build instructions.

## Space and rebuilds

- No `unminimize`, explicit `man-db`, documentation builds, or upstream test and
  example builds are added.
- Apt-installed man pages and documentation are excluded through dpkg settings;
  package copyright files are retained. Documentation inherited from the pinned
  base is left in its existing layers.
- Native builder stages contribute installed artifacts rather than temporary
  source and compilation trees. PX4 sources, submodules, development headers,
  toolchains, and its prepared SITL build remain available for development.
- Cargo, pip, and compiler caches use BuildKit mounts and are excluded from
  published images. Apt metadata and downloaded archives are removed in their
  installation steps.
- QGC is extracted once during the build and its AppImage archive is removed.
  OpenCV is installed through the custom wheel, avoiding a second PyPI OpenCV.
- PyTorch's ROCm wheel dependencies supply the userspace runtime; a second full
  system ROCm SDK is not installed.
- The context is allowlisted to image inputs. Workspaces, local installers,
  Git data, and host-specific runtime files are excluded.

Measure image size separately from your local build cache:

```bash
docker image inspect no_crash:local-cpu --format '{{.Size}} bytes'
docker history no_crash:local-cpu
docker buildx du
docker system df
```

The pinned desktop-full base has approximately 1.325 GiB of compressed layers;
expanded image size and GPU dependencies are larger. Measured sizes and runtime
coverage are recorded in [the validation report](test-results.md).
Home-directory ownership remapping can take time on
first creation; record this in the Dev Containers log when testing with a host
UID or GID other than 1000. The retained PX4 source and build tree lives in the
mode-0777 `/build`, with `~/build` as a symlink, so home-directory remapping skips
that tree. Large userspace installations are also outside home: `.local`,
`.venvs`, `.cargo`, `.rustup`, and `.bun` point to matching paths under `/opt/uas`.
These links exist before installation, preserving home paths in Python
activation scripts, executable shebangs, and native library paths. Their image
contents are made writable for remapped users during the installation step;
there is no recursive runtime chown of `/opt/uas`. Builder-stage copies use
physical paths to preserve the links and permissions.

Dev Containers' [UID update step](https://github.com/devcontainers/cli/blob/main/scripts/updateUID.Dockerfile)
recursively changes ownership in the user's home. The external trees are skipped
by that traversal. The small runtime `.cache` stays in home so pip gets cache
ownership matching the user; BuildKit caches and temporary compiler outputs
are excluded from the published home. `.hushlogin` disables Ubuntu's sudo hint;
numeric hardware groups remain as passed through from the host.
Cargo targets and ccache use `/build/cargo-target` and `/build/ccache`;
`TMPDIR=/build/tmp` also keeps temporary compilation files outside home.
Colcon's editable defaults in `~/.colcon/defaults.yaml` send build output and
logs to `/build/colcon`; the ROS install overlay stays in `~/workspace/install`.
The runtime test compiles a small C++ package with these colcon defaults.

To update releases, edit `.devcontainer/versions.env` with reviewed release
versions, exact source revisions, and verified hashes. Keep PX4 and `px4_msgs`
in sync, preserve Jazzy's Agent 2.x and Gazebo Harmonic compatibility, then rebuild
and rerun checks. Apt packages follow their supported repositories and are
recorded in `~/.local/share/no-crash/apt-packages.tsv`; the pinned base alone does
not freeze later apt repository updates. Python environment inventories are
also recorded under `~/.local/share/no-crash` and in the PX4 checkout.

Common profile settings live in `.devcontainer/scripts/generate-configs.py`.
After changing them, run that script and commit its generated configurations.

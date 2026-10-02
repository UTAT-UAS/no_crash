# Build, validate, and publish images

Run these commands from the repository root. Images are built locally and
published manually. Use `nix develop` on NixOS for the pinned host tools.

## Local builds

```bash
NO_CRASH_BUILD_JOBS=4 ./.devcontainer/build-images.sh cpu
./.devcontainer/build-images.sh all
```

The helper accepts `cpu`, `nvidia`, `nvidia-compat`, `amd`, `amd-wsl`, or `all`.
It loads `no_crash:local-<profile>` into Docker. `all` builds profiles in order,
shares common BuildKit stages, and stops on failure. Start with four compilation
jobs; lower `NO_CRASH_BUILD_JOBS` on machines with limited RAM. Native builds
and GPU dependencies need substantial disk space.

The equivalent direct command for CPU is:

```bash
docker buildx build --load --platform linux/amd64 --target cpu \
  --build-arg BUILD_JOBS=4 -f .devcontainer/Dockerfile -t no_crash:local-cpu .
```

Local configurations declare the Dockerfile, build context, and profile target
in Compose. Dev Containers builds them automatically with `./enter.sh --local`
or VS Code's **local image** choice. They use `NO_CRASH_BUILD_JOBS` (default 4)
and tag the result `no_crash:local-<profile>`. The build helper remains available
for explicit builds and publishing.

`./enter.sh` shows help; `./enter.sh --profile cpu` uses the prebuilt CPU image.
Add `--rebuild` to remove the existing
profile container and rerun setup, or `--local --rebuild` to also run the local
build using Docker's cache. Export container-local changes before recreation.
Prebuilt configurations have no Compose `build:` section. Dev Containers may
build a cached layer to map `uas` to the host UID/GID for either image choice.

## Validation

Before building or after changing container inputs:

```bash
python3 .devcontainer/scripts/generate-configs.py # If profile settings changed
python3 .devcontainer/scripts/validate.py
```

Static validation checks container Bash/Python syntax, release pin formats,
generated configurations, all ten merged Compose models, and simulated
Linux/WSL/device cases. Tests cover lifecycle hooks, launch/build/push helpers,
permissions, and OpenCV extension relocation. ShellCheck and Hadolint run when
available; the pinned flake supplies both. Application source, local environments,
and the personal installer are outside this container validation's scope.
It does not compile software or start containers.

Each image build runs `no-crash-check --build`, which imports vision tools,
captures GStreamer video through OpenCV, checks `cv_bridge`, WebRTC plugins,
CLI tools, and the prepared PX4 executable. After entering a container:

```bash
no-crash-check
no-crash-check --gpu # On supported GPU hardware
bash .devcontainer/scripts/test-runtime.sh # ROS delivery, C++ compilation, CPU vision
bash .devcontainer/scripts/test-runtime.sh --gpu # GPU vision kernels and ROS
bash .devcontainer/scripts/test-sitl.sh # Headless Gazebo/PX4 DDS discovery
bash .devcontainer/scripts/test-sitl.sh gz_x500_mono_cam # Rendered camera frame
```

For manual simulation, run these in separate terminals:

```bash
sim && make px4_sitl gz_x500
MicroXRCEAgent udp4 -p 8888
qgc
```

Confirm QGC and the Agent connect. For typed ROS message consumption, add
`px4_msgs` matching the pinned PX4 release under `uas_ws/src`, build from the
monorepo root, and source `install/local_setup.bash` before consuming topics.
The headless test checks topic discovery without that package.

Record the actual image ID (`docker image inspect <tag> --format '{{.Id}}'`) and
hardware when reporting runtime checks. Static checks, image builds, compute,
GUI, and live equipment checks establish different things. Test each intended
Linux/WSL GPU configuration on supported hardware; SITL does not validate
firmware flashing or flight-controller/camera/joystick hardware.

## Manual publishing

Log in with Docker-managed credentials, then publish images you have built:

```bash
docker login ghcr.io
./.devcontainer/push-images.sh cpu
# Or publish every local profile:
./.devcontainer/push-images.sh all
```

The helper checks all selected local tags before any push, retains their exact
image IDs, and publishes `ghcr.io/utat-uas/no_crash:<snapshot-date>-<profile>`.
The default date comes from `.devcontainer/versions.env`. It does not log in or
build images. A push failure stops the helper; earlier pushes remain published.
Use a new release tag when changing published images. To choose another GHCR
repository or release:

```bash
NO_CRASH_IMAGE_PREFIX=ghcr.io/your-org/no_crash \
NO_CRASH_IMAGE_TAG=2026-10-01-r2 ./.devcontainer/push-images.sh all
```

## Prebuilt images

Prebuilt configurations default to
`ghcr.io/utat-uas/no_crash:2026-10-01-<profile>` and work once those images are
published. Choose a prebuilt configuration in VS Code, or run:

```bash
./enter.sh --profile cpu
```

Set `NO_CRASH_IMAGE_PREFIX` and `NO_CRASH_IMAGE_TAG` before starting VS Code or
`enter.sh` to select another repository/release. Alternatively, create ignored
`.devcontainer/images.json` with per-profile references:

```json
{
  "cpu": "ghcr.io/your-org/no_crash:2026-10-01-cpu",
  "nvidia": "ghcr.io/your-org/no_crash@sha256:<published-digest>"
}
```

Use an actual published SHA-256 digest for immutable selection. Setup writes an
ignored Compose override, leaving tracked configuration files intact.
Publishing uses prefix/tag settings, rather than `images.json` overrides.

## Image maintenance

Update `.devcontainer/versions.env` with reviewed versions, exact source commits,
URLs, and verified hashes. Preserve Jazzy's Gazebo Harmonic and Agent 2.x
compatibility and match `px4_msgs` to PX4. Rebuild and rerun relevant checks.
Apt packages follow supported repositories; the pinned base digest does not
freeze subsequent apt updates. Installed inventories are retained under
`~/.local/share/no-crash` and in the PX4 checkout.

Common profile settings belong in `.devcontainer/scripts/generate-configs.py`;
regenerate and commit its outputs after changes. To update host tools, run
`nix flake update nixpkgs`, review, and commit `flake.lock`.

Native builder stages retain installed artifacts and editable PX4 sources,
rather than other temporary source trees. BuildKit caches and downloaded
archives are excluded from final images. QGC is extracted once; OpenCV uses
its prepared wheel; PyTorch supplies the selected userspace GPU runtime.
Apt documentation is excluded except copyright files, and inherited base layers
are retained. The build context includes only shared image inputs.

Build output lives under `/build`; large userspace installations live under
`/opt/uas`, reached through home symlinks. Both remain writable after UID/GID
mapping, while ownership remapping only traverses the small home directory.
See [workspace storage](README.md#workspace-and-storage).
Measure image size separately from local build cache:

```bash
docker image inspect no_crash:local-cpu --format '{{.Size}} bytes'
docker history no_crash:local-cpu
docker buildx du
docker system df
```

# Development container agent guide

## Scope

These instructions apply to `.devcontainer/`. Also read them before changing
container documentation under `docs/devcontainer/`, the root `enter.sh` launcher,
or the host `flake.nix` and `flake.lock`.
Run the commands below from the repository root.

The checkout is mounted at `~/workspace`. Build ROS packages from that root;
interactive shells source `~/workspace/install/local_setup.bash` when it exists.

## Environment conventions

- Target Ubuntu 24.04, ROS 2 Jazzy, and `linux/amd64`.
- Keep the ROS base pinned by SHA-256. Record release versions, source commits,
  download URLs, and checksums in `.devcontainer/versions.env`.
- Preserve Jazzy compatibility: Gazebo Harmonic, Micro XRCE-DDS Agent 2.x, and
  NumPy 1.26.4 for the prepared OpenCV wheel and apt-managed `cv_bridge`.
- Install and compile as the non-root `uas` user whenever possible. Compile in
  `~/build`; install into `~/.local`, `~/.venvs`, `~/.cargo`, `~/.rustup`, or
  `~/.bun`. `~/build` is a symlink to the mode-0777 `/build`, keeping large build
  trees outside home ownership remapping. `.local`, `.venvs`, `.cargo`, `.rustup`,
  and `.bun` are home symlinks to their corresponding directories under
  `/opt/uas`; create these before installing software so virtual install paths
  remain stable. Keep image-provided installation directories mode 0777 and
  files writable by remapped users, preserving executable bits. Normalize new
  artifacts within their installation step; skip cache mounts and symlink
  targets. Copy builder outputs to their physical `/opt/uas` paths. Cargo targets,
  ccache, colcon build/log output, and temporary build files also live under
  `/build`. Retained PX4 files
  must remain writable after UID changes. Use apt for system dependencies and
  separate Python venvs.
- Keep the small `.cache` directory in home so pip's cache is owned by the
  remapped user. BuildKit caches stay out of final images. Provide `.hushlogin`
  to suppress Ubuntu's repeated sudo hint; retain numeric host device groups.
- Use Bun for JavaScript/TypeScript package management and scripts. Commit
  `bun.lock`; use `bun install --frozen-lockfile` when consuming an existing lock.
  Node LTS is available for software that requires it.
- Project dependencies are managed by their projects. Container lifecycle hooks
  do not discover or install application dependency manifests.
- Keep personal installs in the Git-ignored `.devcontainer/custom-install.sh`.
  It runs through Bash as `uas` on container creation. See
  [the customization guide](../docs/devcontainer/custom-software.md).
- Keep build caches, downloaded archives, and temporary native compilation
  trees out of final images. Preserve development headers and editable PX4
  sources. Do not restore man pages with `unminimize`.

## Configuration changes

- `.devcontainer/scripts/generate-configs.py` owns the shared profile settings.
  Change that generator and regenerate configurations instead of editing the
  generated files directly.
- Profiles are `cpu`, `nvidia`, `nvidia-compat`, `amd`, and `amd-wsl`, each with
  local-image and prebuilt selections. Local configurations declare Compose
  builds so Dev Containers builds the selected target automatically. Prebuilt
  configurations must not include Compose `build:` sections.
  The launcher shows help without arguments and otherwise defaults to prebuilt
  images; `--local` selects source builds and
  `--rebuild` removes the existing profile container before setup. Developers
  can also build images manually with `.devcontainer/build-images.sh`.
  Keep hardware selection out of the creation hook.
- `.devcontainer/scripts/prepare-host.py` generates ignored host overrides.
  Keep GPU/device access scoped and privileged mode disabled by default.
- Port forwarding is currently unconfigured; add ports when requested.
- Images are built locally and pushed manually. Do not add hosted image-build
  or publishing workflows. `.devcontainer/push-images.sh` publishes local images
  to GHCR only when invoked; keep credentials managed by Docker login.
- Host development dependencies belong in `flake.nix` and its committed
  `flake.lock`. Container dependencies belong in the image installation scripts.
- Keep setup, image, and host documentation in `docs/devcontainer/`. The root
  README describes the monorepo and links to these guides. Update documentation
  when behavior or commands change. Keep documentation focused on the current
  setup. When reporting runtime checks, identify the actual images tested.

## Validation

On the NixOS host, use the pinned development shell:

```bash
nix develop
python3 .devcontainer/scripts/generate-configs.py # After changing the generator
python3 .devcontainer/scripts/validate.py
```

Validation checks
syntax, release pins, generated configurations, merged Compose models,
ShellCheck, Hadolint, host setup, lifecycle hooks, and OpenCV packaging paths.
It does not build images or start containers.

Run image builds and runtime/hardware checks when requested by the user. Test
GPU profiles only on supported hardware. Report which checks ran and distinguish
static validation, image builds, and runtime results. See
[the build guide](../docs/devcontainer/building.md) for build and hardware checks.

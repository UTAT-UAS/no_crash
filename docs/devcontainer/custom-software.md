# Personal software and mounts

Personal container settings live in one host file,
`${XDG_CONFIG_HOME:-$HOME/.config}/no_crash/runtime-options.json`. This uses
`$XDG_CONFIG_HOME` when set and nonempty, otherwise `~/.config`:

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/no_crash"
cp docs/devcontainer/example/runtime-options.json "${XDG_CONFIG_HOME:-$HOME/.config}/no_crash/"
$EDITOR "${XDG_CONFIG_HOME:-$HOME/.config}/no_crash/runtime-options.json"
```

All fields are optional. Ready-to-copy examples are in
[`example/`](example/); copy one as `runtime-options.json`:

| Example | Shows |
| --- | --- |
| [`runtime-options.json`](example/runtime-options.json) | Every field |
| [`hardware.json`](example/hardware.json) | Device passthrough and host networking |
| [`prebuilt-images.json`](example/prebuilt-images.json) | Per-profile image references |
| [`mounts.json`](example/mounts.json) | On-create script, extra mounts, and state mounts |
| [`on-create.sh`](example/on-create.sh) | A rerunnable on-create script |

| Field | Value |
| --- | --- |
| `nvidia_mode` | `auto`, `cdi`, or `runtime`; see [NVIDIA setup](host-setup.md#nvidia-on-linux) |
| `hardware_devices` | List of `/dev` paths; see [equipment](host-setup.md#equipment-and-networking) |
| `host_network` | `true` for host networking on native Linux |
| `images` | Map of profile to prebuilt image reference; see [prebuilt images](building.md#prebuilt-images) |
| `on_create_script` | Host path of a script run on container creation |
| `extra_mounts` | Map of container path to `{"source": <host path>, "read_only": <bool>}` |
| `state_mounts` | Map of container path to a directory name under `${XDG_STATE_HOME:-$HOME/.local/state}/no_crash` |

Host paths may start with `~` and relative host paths resolve against the
`no_crash` configuration directory. Container paths must be absolute or start
with `~`, which means `/home/uas`. Each container path may be used once and
cannot replace `~/workspace` or another setup mount. Missing sources and invalid
values fail the host initializer before the container starts. Recreate the
container with `./enter.sh --profile <profile> --rebuild` after changing options.

The host initializer also mounts the existing `no_crash` configuration
directory read-only at `/home/uas/.config/no_crash`. Personal configuration stays
outside the checkout and image builds.

## On-create script

`on_create_script` names a host script, for example `"on-create.sh"` for one
next to `runtime-options.json`. The initializer mounts it read-only into the
container, and each new container runs it through Bash as `uas`, with
`~/workspace` as the working directory. It needs no executable permission.
Failures appear in the Dev Containers log and fail the creation step. The script
runs on creation, including recreation after a rebuild, rather than on restart
or when the file changes. It runs as a child process, so persistent environment
variables belong in a shell configuration file.

`custom-install.sh` no longer runs automatically. If the configuration directory
still contains one, the initializer stops until `runtime-options.json` sets
`"on_create_script": "custom-install.sh"` (or another script).

Make scripts safe to rerun: check installed versions, replace owned files,
and avoid repeatedly appending shell settings. Check download hashes and limit
compilation jobs with `${BUILD_JOBS:-$(nproc)}`. See the
[example script](example/on-create.sh).

For source builds, use `/build/<software>` and install under `~/.local/opt` or
`~/.local`. Create dedicated Python venvs under `~/.venvs`; keep pip out of system
Python. Use `bun add --global <package>` for personal JavaScript/TypeScript tools.
Preserve the home symlinks into `/opt/uas`; see [storage layout](README.md#workspace-and-storage).
Project dependencies belong in each project's manifests and environments.
Tools the whole team needs belong in the image's
[extras layer](building.md#extras-layer) instead.

## Extra mounts

`extra_mounts` binds existing host files or directories into the container.
They are read-only unless `"read_only": false` is set:

```json
{"extra_mounts": {
  "~/datasets": {"source": "~/datasets"},
  "/mnt/flight-logs": {"source": "/srv/flight-logs", "read_only": false}
}}
```

## State mounts

`state_mounts` keeps container directories across recreation by binding them
read/write to directories under `${XDG_STATE_HOME:-$HOME/.local/state}/no_crash`
on the host. The initializer creates missing state directories:

```json
{"state_mounts": {"~/.claude": "claude", "~/.config/gh": "gh"}}
```

This stores `~/.claude` in `~/.local/state/no_crash/claude` on a host without
`XDG_STATE_HOME`. Names are relative paths within the state directory. Avoid
targets below `~/.local`, `~/.venvs`, `~/.cargo`, `~/.rustup`, and `~/.bun`, which
are symlinks to image-provided storage.

## Rerun setup

Inside the container, from `~/workspace`:

```bash
bash "$NO_CRASH_ON_CREATE_SCRIPT" # On-create script only
bash .devcontainer/on-create.sh # All creation setup, including the script
```

The script is mounted as a single file. Edits saved in place are visible
immediately; editors that replace the file need a container recreation to show
the new version. Installed software survives container restarts and is
reinstalled by the script after recreation. Export any other container-local
files you want to keep, or use a state mount, before recreating the container.

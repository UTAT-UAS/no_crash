# Custom software on container creation

Create `.devcontainer/custom-install.sh` in your host checkout. This exact path
is Git-ignored and excluded from the Docker build context. Every machine
configuration calls it during `onCreateCommand`, after workspace initialization.
It runs as `uas` through Bash, so the file does not need executable permission.
Its working directory is `~/workspace`, and `$HOME` is `/home/uas`.

The hook runs for each new container, including after a rebuild. It does not run
on every restart or when you edit the script. A missing script is skipped; a
failing script makes the creation step fail and shows its output in the Dev
Containers log. It is executed as a child process, so exports that should apply
to later shells must be placed in a shell configuration file.

## Example

This example installs an apt-managed system tool and a personal command in
userspace. Change it to suit your workflow:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Apt is appropriate for system-managed software.
if ! command -v btop >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends btop
fi

# ~/.local/bin is already in PATH. Overwrite our file rather than appending.
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/my-workspace" <<'SCRIPT'
#!/usr/bin/env bash
cd "$HOME/workspace"
exec bash
SCRIPT
chmod +x "$HOME/.local/bin/my-workspace"
```

For source builds, use `~/build/<software>` and a prefix under
`~/.local/opt/<software>` or `~/.local`.
`~/build` points to the mode-0777 `/build`, outside home ownership remapping.
Keep retained sources writable if they must be edited after a UID change.
Use `cmake -S <source> -B /build/<software>` or
`meson setup /build/<software> <source>` for projects kept in the workspace.
Cargo targets, compiler caches, temporary files, and colcon build/log output
already default to `/build`; install prefixes and Python venvs remain userspace.
Check versions and download checksums; limit parallelism with `${BUILD_JOBS:-4}`.
For Python software, create a
dedicated venv under `~/.venvs`; avoid installing pip packages into system Python.
Use `bun add --global <package>` for personal JavaScript/TypeScript tooling;
global command shims live in `~/.bun/bin`, which is already in `PATH`.

The `.local`, `.venvs`, `.cargo`, `.rustup`, and `.bun` paths in home are
symlinks into `/opt/uas`, keeping large installations outside home ownership
remapping. Use those familiar home paths for installs and activation; do not
replace the links with directories. The image prepares their directories and
files for writes after UID/GID mapping. Runtime caches under `.cache` stay in
home, where pip expects ownership by the current user.

Make your installer safe to rerun: check for already-installed versions, replace
owned configuration files, and avoid repeatedly appending lines to `.bashrc`.
Project venvs and application dependencies remain the responsibility of each
project; this hook is for your personal development tools.

## Run it again

Inside the container:

```bash
cd ~/workspace
bash .devcontainer/custom-install.sh
```

To rerun all creation setup, including the hook:

```bash
bash .devcontainer/on-create.sh
```

The script stays in the host checkout across container rebuilds. Installed
software stays in the current container across restarts and is reinstalled by
the hook when the container is recreated. Copying a prebuilt image to another
machine does not copy this personal script.

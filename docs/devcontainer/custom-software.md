# Personal software

Create `.devcontainer/custom-install.sh` in your host checkout. This path is
Git-ignored and excluded from image builds. Each new container runs it through
Bash as `uas`, with `~/workspace` as the working directory. It needs no executable
permission. A missing script is skipped; failures appear in the Dev Containers
log and fail the creation step.

The hook runs on creation, including recreation after a rebuild, rather than
on restart or when the file changes. It runs as a child process, so persistent
environment variables belong in a shell configuration file.

## Example installer

```bash
#!/usr/bin/env bash
set -euo pipefail

if ! command -v btop >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends btop
fi

mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/my-workspace" <<'SCRIPT'
#!/usr/bin/env bash
cd "$HOME/workspace"
exec bash
SCRIPT
chmod +x "$HOME/.local/bin/my-workspace"
```

Make installers safe to rerun: check installed versions, replace owned files,
and avoid repeatedly appending shell settings. Check download hashes and limit
compilation jobs with `${BUILD_JOBS:-4}`.

For source builds, use `/build/<software>` and install under `~/.local/opt` or
`~/.local`. Create dedicated Python venvs under `~/.venvs`; keep pip out of system
Python. Use `bun add --global <package>` for personal JavaScript/TypeScript tools.
Preserve the home symlinks into `/opt/uas`; see [storage layout](README.md#workspace-and-storage).
Project dependencies belong in each project's manifests and environments.

## Rerun setup

Inside the container, from `~/workspace`:

```bash
bash .devcontainer/custom-install.sh # Personal installer only
bash .devcontainer/on-create.sh      # All creation setup, including the installer
```

The script stays in the host checkout. Installed software survives container
restarts and is reinstalled by the hook after recreation. Export any other
container-local files you want to keep before recreating the container.

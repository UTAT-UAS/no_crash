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

#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$workspace"

# The managed shell block is replaced, so repeated setup does not accumulate
# aliases or safe.directory entries. Personal additions to .bashrc are retained.
python3 - <<'PY'
from pathlib import Path
import re

rc = Path.home() / '.bashrc'
content = rc.read_text() if rc.exists() else ''
block = '''# BEGIN no_crash workspace
if [ -f "$HOME/workspace/.devcontainer/bashrc_aliases" ]; then
    source "$HOME/workspace/.devcontainer/bashrc_aliases"
fi
# END no_crash workspace
'''
content = re.sub(r'(?m)^# BEGIN no_crash workspace\n.*?^# END no_crash workspace\n?', '', content, flags=re.S)
rc.write_text(content.rstrip() + '\n\n' + block)
PY
if ! git config --global --get-all safe.directory | grep -Fxq "$workspace"; then
    git config --global --add safe.directory "$workspace"
fi

# Local customization is deliberately never baked into shared images.
custom_script="$workspace/.devcontainer/custom-install.sh"
if [[ -f $custom_script ]]; then
    printf 'Running local custom software installer: %s\n' "$custom_script"
    bash "$custom_script"
fi

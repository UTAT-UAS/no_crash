#!/usr/bin/env bash
# Final image layer for developer tools. Add packages here, rather than to the
# earlier installers, so changes rebuild only this layer.
set -euo pipefail
source /usr/local/lib/no-crash/helpers.sh
# The Dockerfile bind-mounts .devcontainer/extras.env and passes its path.
# shellcheck source=.devcontainer/extras.env
source "$1"
cd "$HOME/build"

# clang-format and clang-tidy are installed earlier by install-system.sh. For
# apt packages here, use sudo apt-get, remove /var/lib/apt/lists afterwards,
# and refresh ~/.local/share/no-crash/apt-packages.tsv.

download "$RUFF_URL" "$RUFF_SHA256" ruff.tar.gz
tar -xzf ruff.tar.gz --strip-components=1 -C "$HOME/.local/bin" \
    ruff-x86_64-unknown-linux-gnu/ruff
rm ruff.tar.gz
test "$(ruff --version)" = "ruff $RUFF_VERSION"

# The npm package is self-contained and runs on the image's Node LTS.
download "$PYRIGHT_URL" "$PYRIGHT_SHA256" pyright.tgz
mkdir -p "$HOME/.local/opt/pyright"
tar -xzf pyright.tgz --strip-components=1 -C "$HOME/.local/opt/pyright"
rm pyright.tgz
ln -s ../opt/pyright/index.js "$HOME/.local/bin/pyright"
test "$(pyright --version)" = "pyright $PYRIGHT_VERSION"

cp "$1" "$HOME/.local/share/no-crash/extras.env"
make_user_storage_writable

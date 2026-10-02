#!/usr/bin/env bash
set -euo pipefail
source /usr/local/lib/no-crash/helpers.sh
cd "$HOME/build"
download "$ROCDXG_URL" "$ROCDXG_SHA256" rocdxg.deb
dpkg-deb --extract rocdxg.deb rocdxg-package
mkdir -p "$HOME/.local/opt/rocdxg/lib" "$HOME/.local/opt/rocdxg/share/rocdxg"
library=$(find rocdxg-package -name 'librocdxg.so*' -type f -print -quit)
config=$(find rocdxg-package -name dids.conf -type f -print -quit)
test -n "$library"
test -n "$config"
cp "$library" "$HOME/.local/opt/rocdxg/lib/librocdxg.so"
cp "$config" "$HOME/.local/opt/rocdxg/share/rocdxg/dids.conf"
# This lookup location is fixed by the upstream runtime. The actual installation
# remains userspace; only a compatibility symlink needs sudo.
sudo mkdir -p /usr/share/rocdxg
sudo ln -s "$HOME/.local/opt/rocdxg/share/rocdxg/dids.conf" /usr/share/rocdxg/dids.conf
rm -rf rocdxg.deb rocdxg-package

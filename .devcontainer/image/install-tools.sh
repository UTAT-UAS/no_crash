#!/usr/bin/env bash
set -euo pipefail
source /usr/local/lib/no-crash/helpers.sh
cd "$HOME/build"

download "$NODE_URL" "$NODE_SHA256" node.tar.xz
mkdir -p "$HOME/.local/opt/node"
tar -xJf node.tar.xz --strip-components=1 -C "$HOME/.local/opt/node"
rm node.tar.xz
download "$BUN_URL" "$BUN_SHA256" bun.zip
unzip -q bun.zip -d bun-archive
install -Dm 0755 bun-archive/bun-linux-x64/bun "$BUN_INSTALL/bin/bun"
ln -s bun "$BUN_INSTALL/bin/bunx"
rm -rf bun.zip bun-archive

download "$RUSTUP_URL" "$RUSTUP_SHA256" rustup-init
chmod +x rustup-init
./rustup-init -y --no-modify-path --profile minimal --default-toolchain "$RUST_VERSION"
rm rustup-init
cargo install --locked --version "$CARGO_C_VERSION" cargo-c

python3 -m venv "$HOME/.venvs/build-tools"
"$HOME/.venvs/build-tools/bin/python" -m pip install \
    "meson==$MESON_VERSION" 'setuptools>=77.0.3' wheel
ln -s "$HOME/.venvs/build-tools/bin/meson" "$HOME/.local/bin/meson"
"$HOME/.venvs/build-tools/bin/python" -m pip freeze > "$HOME/.local/share/no-crash/build-python-requirements.txt"

# Extract once, remove the compressed AppImage, and launch without FUSE.
download "$QGC_URL" "$QGC_SHA256" QGroundControl.AppImage
chmod +x QGroundControl.AppImage
./QGroundControl.AppImage --appimage-extract >/dev/null
mv squashfs-root "$HOME/.local/opt/qgc"
rm QGroundControl.AppImage

# Retain version inventories after removing downloaded archives.
cp /usr/local/share/no-crash/versions.env "$HOME/.local/share/no-crash/versions.env"
dpkg-query -W -f='${Package}\t${Version}\n' > "$HOME/.local/share/no-crash/apt-packages.tsv"

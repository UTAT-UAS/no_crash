#!/usr/bin/env bash
set -euo pipefail
source /usr/local/share/no-crash/versions.env

download() {
    local url=$1 checksum=$2 destination=$3
    curl --fail --location --retry 3 --output "$destination" "$url"
    printf '%s  %s\n' "$checksum" "$destination" | sha256sum --check --strict -
}

checkout() {
    local remote=$1 revision=$2 destination=$3
    git init "$destination"
    git -C "$destination" remote add origin "$remote"
    git -C "$destination" fetch --depth 1 origin "$revision"
    git -C "$destination" checkout --detach FETCH_HEAD
    test "$(git -C "$destination" rev-parse HEAD)" = "$revision"
}

source_ros() {
    # ROS-generated setup files aren't compatible with nounset.
    set +u
    source /opt/ros/jazzy/setup.bash
    set -u
}

make_user_storage_writable() {
    # Normalize new installed artifacts during the same build step that creates
    # them. Never traverse symlink targets or modify BuildKit cache mounts.
    # Executables keep their execute bits; ordinary files only gain read/write.
    local storage_root=${1:-/opt/uas}
    find "$storage_root" \
        \( -path "$storage_root/.cargo/registry" \
           -o -path "$storage_root/.cargo/git" \) -prune -o \
        \( -type d ! -perm -0777 -o -type f ! -perm -0666 \) \
        -exec chmod a+rwX {} +
}

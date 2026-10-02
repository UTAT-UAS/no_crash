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

#!/usr/bin/env bash
# Run inside a CPU or NVIDIA devcontainer; no model downloads are needed.
set -eo pipefail
mode=${1:---build}
case "$mode" in --build|--gpu) ;; *) printf 'Usage: bash test-runtime.sh [--gpu]\n' >&2; exit 2 ;; esac
source /opt/ros/jazzy/setup.bash
source "$HOME/.local/share/no-crash/environment.sh"
no-crash-check "$mode"

test "$(readlink "$HOME/build")" = /build
for directory in /build /build/cargo-target /build/ccache /build/colcon /build/tmp; do
    test "$(stat -c '%a' "$directory")" = 777
    test -w "$directory"
done
test "$CARGO_TARGET_DIR" = /build/cargo-target
test "$CCACHE_DIR" = /build/ccache
test "$TMPDIR" = /build/tmp

# Compile a small CMake package using colcon's configured default build base.
# This checks real output placement and toolchain access after UID/GID remapping.
smoke_root=$(mktemp -d)
smoke_package="no_crash_build_smoke_$$"
trap 'rm -rf "$smoke_root" "/build/colcon/build/$smoke_package"' EXIT
mkdir -p "$smoke_root/source"
cat > "$smoke_root/source/CMakeLists.txt" <<CMAKE
cmake_minimum_required(VERSION 3.16)
project($smoke_package LANGUAGES CXX)
add_executable($smoke_package main.cpp)
install(TARGETS $smoke_package DESTINATION bin)
CMAKE
printf 'int main() { return 0; }\n' > "$smoke_root/source/main.cpp"
colcon build --base-paths "$smoke_root/source" --packages-select "$smoke_package" \
    --install-base "$smoke_root/install" --merge-install --event-handlers console_direct+
test -f "/build/colcon/build/$smoke_package/CMakeCache.txt"
"$smoke_root/install/bin/$smoke_package"
printf 'Shared build directories and colcon C++ compilation passed.\n'

NO_CRASH_CHECK_MODE="$mode" "$HOME/.venvs/vision/bin/python" - <<'PY'
import os
import torch
from torchvision.ops import nms

device = 'cuda' if os.environ['NO_CRASH_CHECK_MODE'] == '--gpu' else 'cpu'
boxes = torch.tensor([[0, 0, 10, 10], [1, 1, 9, 9], [20, 20, 30, 30]], dtype=torch.float32, device=device)
scores = torch.tensor([0.9, 0.8, 0.7], device=device)
assert nms(boxes, scores, 0.5).tolist() == [0, 2]
print('torchvision NMS passed on', device)
PY

# Exercise real ROS serialization and delivery with separate publisher and
# subscriber nodes, isolated from the user's ROS domain.
env -u ROS_LOCALHOST_ONLY ROS_DOMAIN_ID=91 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_STATIC_PEERS= /usr/bin/python3 - <<'PY'
import time
import rclpy
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import String

rclpy.init()
sender = rclpy.create_node('no_crash_test_sender')
receiver = rclpy.create_node('no_crash_test_receiver')
publisher = sender.create_publisher(String, '/no_crash_test', 10)
received = []
subscription = receiver.create_subscription(String, '/no_crash_test', lambda msg: received.append(msg.data), 10)
executor = SingleThreadedExecutor()
executor.add_node(sender)
executor.add_node(receiver)
try:
    deadline = time.monotonic() + 10
    while not received and time.monotonic() < deadline:
        publisher.publish(String(data='no_crash'))
        executor.spin_once(timeout_sec=0.1)
    assert received and received[0] == 'no_crash', 'ROS publish/subscribe timed out'
    print('ROS Jazzy publish/subscribe passed')
finally:
    executor.shutdown()
    sender.destroy_node()
    receiver.destroy_node()
    rclpy.shutdown()
PY

bun -e 'if (2 + 2 !== 4) process.exit(1); console.log("Bun JavaScript execution passed")'
gz sim --help >/dev/null
printf 'Runtime integration checks passed (%s).\n' "$mode"

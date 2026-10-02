#!/usr/bin/env bash
# Headless PX4/Gazebo and DDS discovery check inside an isolated devcontainer.
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source "$HOME/.local/share/no-crash/environment.sh"
logs=$(mktemp -d)
agent_pid=
sim_pid=
cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n $sim_pid ]]; then kill -- "-$sim_pid" 2>/dev/null || true; fi
    if [[ -n $agent_pid ]]; then kill -- "-$agent_pid" 2>/dev/null || true; fi
    if (( status != 0 )); then
        tail -c 16000 "$logs/agent.log" "$logs/px4.log"
    fi
    rm -rf "$logs"
    exit "$status"
}
trap cleanup EXIT
setsid MicroXRCEAgent udp4 -p 8888 -v 4 > "$logs/agent.log" 2>&1 &
agent_pid=$!
# Use the same model and working directory as the prepared make target, with
# PX4's -d flag disabling its interactive shell for this background check.
sitl_build=/build/PX4-Autopilot/build/px4_sitl_default
cd "$sitl_build/src/modules/simulation/gz_bridge"
setsid env HEADLESS=1 PX4_SIM_MODEL="${1:-gz_x500}" GZ_IP=127.0.0.1 \
    "$sitl_build/bin/px4" -d > "$logs/px4.log" 2>&1 < /dev/null &
sim_pid=$!

env -u ROS_LOCALHOST_ONLY -u ROS_AUTOMATIC_DISCOVERY_RANGE -u ROS_STATIC_PEERS \
    ROS_DOMAIN_ID=0 /usr/bin/python3 - <<'PY'
import time
import rclpy

rclpy.init()
node = rclpy.create_node('no_crash_sitl_discovery')
try:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        topics = dict(node.get_topic_names_and_types())
        status_topics = [name for name, types in topics.items()
                         if name.startswith('/fmu/out/vehicle_status')
                         and 'px4_msgs/msg/VehicleStatus' in types]
        if status_topics:
            print('PX4/Gazebo DDS discovery passed:', status_topics[0], 'among', len(topics), 'ROS topics')
            break
        rclpy.spin_once(node, timeout_sec=0.25)
    else:
        raise RuntimeError(f'PX4 vehicle_status was not discovered within 60 seconds: {topics}')
finally:
    node.destroy_node()
    rclpy.shutdown()
PY
kill -0 "$agent_pid"
kill -0 "$sim_pid"
if [[ ${1:-gz_x500} == gz_x500_mono_cam ]]; then
    export GZ_IP=127.0.0.1
    camera_topic=$(gz topic -l | awk '/\/sensor\/imager\/image$/ { print; exit }')
    test -n "$camera_topic"
    timeout 15s gz topic -e -n 1 -t "$camera_topic" --json-output > "$logs/camera.json"
    /usr/bin/python3 - "$logs/camera.json" <<'PY'
import base64
import json
import sys

with open(sys.argv[1]) as stream:
    frame = json.load(stream)
assert frame['width'] == 1280 and frame['height'] == 960, frame.keys()
assert len(base64.b64decode(frame['data'])) >= frame['width'] * frame['height']
print('Gazebo rendered a 1280x960 camera frame')
PY
fi
printf 'Headless SITL check passed (%s).\n' "${1:-gz_x500}"

# flight_visualizer_bridge agent guide

User-facing usage is in [README.md](README.md). Keep it lean; put protocol
and design detail here.

## Protocol

[`proto/flight_visualizer.proto`](proto/flight_visualizer.proto) is the single
source of truth. The bridge, backend and frontend each generate code from it
(none of it is committed):

- Bridge: `setup.py` runs the system `protoc` (apt `protobuf-compiler`) on every
  colcon build, writing `flight_visualizer_pb2.py(i)` into the package.
- Backend: `flight_visualizer/backend/generate.sh` (grpcio-tools' protoc).
- Frontend: `bun run generate` (`protoc-gen-es`), also run by `bun install`.

After changing the `.proto`, rebuild and regenerate all three. Only add
fields; renumbering or reusing field numbers breaks a bridge and backend that
are not updated together.

One TCP connection, served by the bridge; a new connection replaces the old
one. Each frame is a 4-byte big-endian uint32 length followed by a serialized
message; frames over 64 KiB (`MAX_FRAME`) drop the connection.

- Bridge → backend: `BridgeMessage` with a `State` every `1 / rate_hz` s, and a
  `Result` once per command. `State.target` is `CoreState.target_position`,
  the current state's setpoint. Fields and submessages are unset until their
  source topic has been received; floats may be NaN. A state frame is about
  100 bytes, so the default 5 Hz is roughly 0.5 KB/s (1.8 MB/hour).
- Backend → bridge: `BackendMessage` with a `Command`, e.g. name `goto` with
  args `[x, y, z]`.

The backend relays these to browsers as proto3 JSON
(`preserving_proto_field_name`); see the backend's agent guide.

## Design

- Keep it simple and bandwidth-conscious: periodic snapshots of the latest
  values, no history and no per-message acknowledgement. Add fields only
  when the visualizer needs them.
- `BridgeDrone` subclasses `flight_core.client.Drone` to reuse its PX4 and
  core subscriptions and its service calls. It reads `Drone`'s private state
  fields directly.
- Commands run on the connection's reader thread, one at a time. Do not add
  commands that block for long (`goto(wait=True)`, `takeoff`,
  `land(wait=True)`); a later `land` or `hold` would wait behind them.
- A send blocked for `SEND_TIMEOUT` drops the connection; the backend
  reconnects. A failed snapshot is logged and streaming continues.
- Fixed-size message arrays (`float32[3]`) arrive as numpy arrays; convert
  elements with `float()` before assigning them to protobuf fields
  (`_set_vector` does).
- The accept loop polls with a timeout and exits when Ctrl-C shuts down the
  ROS context. rclpy's SIGINT handler does not interrupt a blocking
  `accept()`.
- The bridge does not release its lease on exit. Leases never expire, so a
  restarted bridge needs `reacquire`.

## Verification

```bash
colcon build --base-paths uas_ws/src --packages-select flight_core flight_visualizer_bridge --symlink-install
scripts/sitl start
ros2 run flight_visualizer_bridge flight_visualizer_bridge
```

Then connect with the backend, or with a raw socket sending length-prefixed
`BackendMessage` frames.

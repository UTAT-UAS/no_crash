# flight_visualizer_bridge agent guide

User-facing usage is in [README.md](README.md). Keep it lean; put protocol
and design detail here.

## Protocol

One TCP connection, served by the bridge; a new connection replaces the old
one. Both directions carry newline-delimited compact JSON. Keep
`flight_visualizer/backend/app.py` and the frontend page in step with changes.

- Bridge → backend, every `1 / rate_hz` s:
  `{"type":"state","armed":bool,"mode":"OFFBOARD","landed":bool,"position":[x,y,z],"velocity":[vx,vy,vz],"heading":rad,"core_state":"HOLD","lease_holder":"name","target":[x,y,z]}`.
  `target` is `CoreState.target_position`, the current state's setpoint.
  Fields are null until the source topic has been received; non-finite
  numbers become null (NaN is not valid JSON). Numbers are rounded to 0.01.
  About 230 bytes, so the default 5 Hz is roughly 1.1 KB/s (4 MB/hour).
- Bridge → backend, once per command:
  `{"type":"result","id":<command id>,"ok":bool,"error":str|null}`.
- Backend → bridge: `{"type":"command","id":<any>,"name":"goto","args":[x,y,z]}`.
  `args` may be omitted.

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
  elements with `float()` before JSON encoding (`_rounded` does).
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

Then connect with the backend, or with a raw socket and send command lines.

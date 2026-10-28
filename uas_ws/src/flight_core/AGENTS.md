# flight_core agent guide

Context for changing `flight_core`. User-facing usage is in
[README.md](README.md); keep that file lean and put design rationale and
implementation detail here.

## Design constraints

- `flight_core_cpp` is the only publisher on `/fmu/in/*`. Scripts never
  publish to PX4; they call `/flight_core/in/*` services through `Drone`.
  Shared memory or in-process calls between scripts and the core were
  rejected.
- Keep automation minimal. Do not add lease expiry, client heartbeats,
  watchdogs, geofences or wrapper messages for vehicle state unless asked.
  Clients read PX4's `/fmu/out/*` topics directly.
- Leases change only through acquire, release or reset. Reset clears the
  holder and enters `HOLD` if the position is valid.
- The `mode` parameter (`sim|real`, default `real`) is read-only. Real mode
  rejects `ARM` with "Arming is disabled in real mode; arm from the RC or GCS".
- PX4 topics are versioned: `/fmu/out/vehicle_status_v1` and
  `/fmu/out/vehicle_local_position_v1`; others have no suffix. PX4 publishes
  best effort, so subscribe with `SensorDataQoS` / `qos_profile_sensor_data`.
- Keep `px4_msgs` at the PX4 release in use (v1.17.0). PX4 source for
  checking behaviour is at `~/build/PX4-Autopilot`.

## Node behaviour and why

- **Heartbeat:** `OffboardControlMode` (position) is published every tick
  from startup, so the pilot can select offboard from the RC at any time.
- **Setpoint gating:** setpoints are published only while PX4 is in offboard.
  A goto streamed in other modes stopped PX4's land detector from detecting
  ground contact during land mode.
- **Queued commands:** `OFFBOARD` and `ARM` wait in `pending_commands_` until
  `kHeartbeatsBeforeOffboard` (10) heartbeats have been sent since startup.
  Setpoints cannot be sent before offboard, so heartbeats are what is counted.
  `ARM` is queued too: otherwise, after a disarm with offboard still selected,
  it could go out after a single heartbeat. `DISARM` and `LAND` go out
  immediately. Offboard is `DO_SET_MODE` with param1 = 1, param2 = 6.
- **HOLD as the default:** when offboard engages from a position-controlled
  mode (Position, Altitude, Hold, Mission, Takeoff), PX4 keeps the previous
  flight task's last trajectory setpoint indefinitely, so a stick velocity
  command keeps flying. From Stabilized, Acro or Manual it uses a zero-velocity
  failsafe setpoint. See `MulticopterPositionControl.cpp:401-453`. The hold
  point is captured on entering `HOLD` and again whenever the vehicle becomes
  armed and in offboard (`was_engaged_`).
- **Entering a state** resets its setpoint to the current position and
  heading; trajectory velocity and acceleration become NaN. Switching from
  `TRAJECTORY` to `HOLD` or `GOTO` while moving restarts PX4's goto smoother
  from rest, so the vehicle brakes sharply.
- **Saved targets:** `goto` and `trajectory` requests are accepted outside
  offboard (they need the matching state) and are flown as soon as offboard
  engages.
- **Trajectory validation** mirrors PX4's `_inputValid`: each axis needs at
  least one finite field, and x/y are finite or NaN together.
- **Landing:** PX4's land detector needs a descending setpoint
  (`MulticopterLandDetector.cpp:224-235`). A vehicle armed and holding on the
  ground in offboard is never "landed", so `DISARM` is refused with
  "Disarming denied: not landed". Use `LAND`. After landing and disarm, PX4
  returns to offboard, so `land()` switches to position mode afterwards.
- `POSITION` is `DO_SET_MODE` with param1 = 1, param2 = 3 and, like `LAND`,
  returns the core to `HOLD`.
- PX4 rejections arrive on `vehicle_command_ack` and are only logged. Service
  success means validated and sent or queued; the client confirms the effect
  from PX4 topics.

## Python client

- `Drone` runs its own node on a daemon thread with a `SingleThreadedExecutor`.
  `close()` must shut down the executor and join the thread before destroying
  the node; skipping the join aborts with "terminate called without an active
  exception".
- `_core_state` is the last state this client set (None at first); `goto()`
  and `trajectory()` switch state only when it differs. `land()` and
  `position_mode()` set it to `HOLD` to match the core.
- `land(wait=True)` waits for `vehicle_land_detected.landed`, disarms unless
  PX4 already auto-disarmed, then calls `position_mode()`.
- On context exit, the client calls `hold()` only if offboard and armed, then
  releases.

## Layout

- `src/`, `include/flight_core/`: `FlightCoreNode` and `ControlLease`.
  `ControlLease` has no ROS dependency, is built as the static library
  `control_lease`, and skips id 0.
- `flight_core/client.py`: the `Drone` client.
- `scripts/example_mission`: take off to 5 m, fly a 5 m square, land.
- `launch/flight_core.launch.py`: `mode` (default `real`) and `rate_hz`
  (default 20).
- `test/test_control_lease.cpp`: gtests for the lease.

When adding services or state, also update `flight_core_interfaces` (see
its [AGENTS.md](../flight_core_interfaces/AGENTS.md)), `client.py` and both
READMEs.

## Verification

Report compilation, unit tests, syntax checks and SITL runs separately.

```bash
colcon build --base-paths uas_ws/src --packages-up-to flight_core --symlink-install
colcon test --base-paths uas_ws/src --packages-select flight_core
colcon test-result --verbose --test-result-base /build/colcon/build/flight_core
python3 -m py_compile uas_ws/src/flight_core/flight_core/client.py
uas_ws/scripts/sitl run -- ros2 run flight_core example_mission
```

Use `uas_ws/scripts/sitl` for runtime checks (`start`, `restart`, `px4
<module>`). Logs are in `$SITL_STATE_DIR/logs` (default
`/build/tmp/flight_core_sitl/logs`).

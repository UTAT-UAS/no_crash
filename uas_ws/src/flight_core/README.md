# flight_core

Central PX4 offboard control node (`flight_core_cpp`) and the Python `Drone`
client used by mission scripts.

```
mission script (Drone) ──services──▶ flight_core_cpp ──/fmu/in/*──▶ PX4
        ▲                                                           │
        └──────────────── /fmu/out/* (read directly) ───────────────┘
```

`flight_core_cpp` is the only publisher of PX4 inputs. It streams
`OffboardControlMode` (position) at 20 Hz. While PX4 is in offboard it also
streams a `GotoSetpoint`, so PX4 smooths every motion onboard.
`TrajectorySetpoint` is not used. Scripts read vehicle state from PX4's
`/fmu/out/*` topics themselves.

## Control authority

- One client at a time holds the control lease, through
  `/flight_core/acquire_control`. `command` and `goto` requests from anyone else
  are rejected.
- Leases never expire. They end when the holder releases them, or through
  `/flight_core/reset_control`. Reset clears any holder and holds the current
  position, which is how you recover after a script crashes without releasing:

  ```bash
  ros2 service call /flight_core/reset_control flight_core_interfaces/srv/ResetControl
  ```

- The read-only `mode` parameter is `sim` or `real`, and defaults to `real`. In
  real mode, `ARM` requests are rejected and the pilot arms from the RC or GCS.
  `takeoff()` skips arming if the vehicle is already armed.
- `ARM` and `OFFBOARD` require a valid local position. `goto` requires
  offboard. `LAND` switches to PX4's land mode, after which PX4 lands and disarms.
- Outside offboard, the target follows the vehicle, so switching to offboard
  holds in place. Goto is only streamed while in offboard. Otherwise it would
  interfere with PX4 modes such as land.
- Commands are sent to PX4 once validated. PX4 rejections are logged by the
  node, and the client confirms each effect from PX4 topics.

## Python client

```python
from flight_core.client import Drone

with Drone('survey') as drone:     # acquires control; on exit holds and releases
    drone.takeoff(5.0)              # offboard, arm, climb 5 m
    x, y, z = drone.position        # NED metres, local frame
    drone.goto(x + 10, y, z, max_speed=2.0)
    drone.land()
```

| Call | Effect |
|---|---|
| `arm()`, `disarm()`, `offboard()` | Command and wait for PX4 to confirm |
| `takeoff(altitude)` | Offboard, arm if needed (sim only), goto `altitude` m above the current position |
| `goto(x, y, z, heading=None, max_speed=None, wait=True, tolerance=0.3)` | Fly to NED position. `heading=None` keeps the current heading |
| `hold()` | Hold the current position |
| `land(wait=True)` | PX4 land; waits for auto-disarm |
| `wait_until(predicate, timeout)` | Poll a condition |
| `position`, `velocity`, `heading`, `is_armed`, `is_offboard`, `status` | Latest PX4 state |

Rejected commands and timeouts raise `ControlError`.

## Layout

- `src/`, `include/flight_core/`: `FlightCoreNode` and the ROS-independent
  `ControlLease`.
- `flight_core/client.py`: the `Drone` client.
- `scripts/example_mission`: takes off, flies a 5 m square, and lands.
- `launch/flight_core.launch.py`: starts the node (`mode`, default `real`; `rate_hz`, default 20).
- `test/`: gtest unit tests for `ControlLease`.

## Build and test

From the monorepo root, with ROS 2 Jazzy sourced and submodules initialised:

```bash
rosdep install --from-paths uas_ws/src --ignore-src -r -y
colcon build --base-paths uas_ws/src --packages-up-to flight_core --symlink-install
source install/local_setup.bash
colcon test --base-paths uas_ws/src --packages-select flight_core
colcon test-result --verbose --test-result-base /build/colcon/build/flight_core
```

## Run in SITL

Run each command in its own terminal, with the overlay sourced:

```bash
sim                       # PX4 SITL with gz_x500
uxrce                     # MicroXRCEAgent udp4 -p 8888
ros2 launch flight_core flight_core.launch.py mode:=sim
ros2 run flight_core example_mission
```

PX4 refuses to arm without a ground station connection while `NAV_DLL_ACT` is
non-zero. Either connect QGroundControl, or run `param set NAV_DLL_ACT 0` in the
SITL shell (sim only).

On real hardware, launch with the default `mode:=real`. Arm with the RC or GCS
before starting a script.

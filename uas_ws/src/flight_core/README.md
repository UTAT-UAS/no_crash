# flight_core

Central PX4 offboard control node (`flight_core_cpp`) and the Python `Drone`
client used by mission scripts.

```
mission script (Drone) ──services──▶ flight_core_cpp ──/fmu/in/*──▶ PX4
        ▲                                                           │
        └──────────────── /fmu/out/* (read directly) ───────────────┘
```

`flight_core_cpp` is the only publisher of PX4 inputs. Scripts read vehicle
state from PX4's `/fmu/out/*` topics themselves. Services and topics are
listed in [flight_core_interfaces](../flight_core_interfaces/README.md).

## Core states

| State | Streams |
|---|---|
| `HOLD` (default) | The position and heading captured on entry, and again whenever the vehicle becomes armed in offboard |
| `GOTO` | The latest `goto` target; starts at the current position |
| `TRAJECTORY` | The latest `trajectory` setpoint; starts at the current position |

The offboard heartbeat is always published, so offboard can be selected from
the RC at any time and the vehicle holds where it is. Setpoints are published
only while PX4 is in offboard. A `goto` or `trajectory` target saved before
offboard is flown as soon as offboard engages.

## Control

- One client at a time holds the control lease. Leases never expire; if a
  script crashes without releasing, clear the lease (the core switches to
  `HOLD`):

  ```bash
  ros2 service call /flight_core/in/reset_control flight_core_interfaces/srv/ResetControl
  ```

- The `mode` parameter is `sim` or `real` (default). In real mode the core
  refuses to arm; arm from the RC or GCS before starting a script.
- Finish an offboard flight with `land()`. A plain disarm while holding on the
  ground in offboard is refused by PX4.

## Python client

```python
from flight_core.client import Drone

with Drone('survey') as drone:     # acquires control; on exit holds (if flying) and releases
    drone.takeoff(5.0)              # offboard, arm, climb 5 m
    x, y, z = drone.position        # NED metres, local frame
    drone.goto(x + 10, y, z, max_speed=2.0)
    drone.land()
```

| Call | Effect |
|---|---|
| `arm()`, `disarm()` | Command and wait for PX4 to confirm |
| `offboard_mode()` | Switch to offboard and wait |
| `position_mode()` | Switch to PX4 position mode and wait; the core goes `HOLD` |
| `takeoff(altitude)` | `HOLD`, offboard, arm if needed (sim only), goto `altitude` m above the current position |
| `goto(x, y, z, heading=None, max_speed=None, wait=True, tolerance=0.3)` | Enter `GOTO` if needed and fly to a NED position. `heading=None` keeps the current heading |
| `trajectory(position=None, velocity=None, acceleration=None, yaw=None, yawspeed=None)` | Enter `TRAJECTORY` if needed and set the setpoint (None = uncontrolled). Returns immediately |
| `hold()` | Enter `HOLD` |
| `has_arrived(x, y, z, tolerance=0.3, max_speed=0.3)` | Within `tolerance` m of the point and slower than `max_speed` m/s |
| `land(wait=True)` | PX4 land; the core goes `HOLD`. With `wait`, waits until landed, disarms and switches to position mode |
| `wait_until(predicate, timeout)` | Poll a condition |
| `position`, `velocity`, `heading`, `is_armed`, `is_offboard`, `is_landed`, `status` | Latest PX4 state |
| `core_state` | Latest `CoreState` from flight_core |

Rejected commands and timeouts raise `ControlError`.

## Build and run

From the monorepo root, with ROS 2 Jazzy sourced and submodules initialised:

```bash
colcon build --base-paths uas_ws/src --packages-up-to flight_core --symlink-install
source install/local_setup.bash
uas_ws/scripts/sitl run -- ros2 run flight_core example_mission   # SITL: start, run, stop
```

See the [ROS workspace README](../../README.md#sitl-testing) for SITL options.
On hardware, run `ros2 launch flight_core flight_core.launch.py` (default
`mode:=real`).

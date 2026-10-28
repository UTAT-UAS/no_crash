# flight_core_interfaces

Service and message definitions for the `flight_core` node. Following PX4's
`/fmu/in` and `/fmu/out` convention, inputs are under `/flight_core/in/` and
outputs under `/flight_core/out/`.

| Service | Type | Purpose |
|---|---|---|
| `/flight_core/in/acquire_control` | `AcquireControl` | Take the control lease |
| `/flight_core/in/release_control` | `ReleaseControl` | Give the lease back |
| `/flight_core/in/reset_control` | `ResetControl` | Clear any lease and hold position |
| `/flight_core/in/core_command` | `CoreCommand` | Set the core state: hold, goto, trajectory |
| `/flight_core/in/vehicle_command` | `CoreVehicleCommand` | Arm, disarm, offboard, land, position mode |
| `/flight_core/in/goto` | `Goto` | Set the goto target (GOTO state) |
| `/flight_core/in/trajectory` | `Trajectory` | Set the trajectory setpoint (TRAJECTORY state) |

| Topic | Type | Content |
|---|---|---|
| `/flight_core/out/core_state` | `CoreState` | Core state and lease holder, at the core's rate |

Vehicle state is not wrapped; clients read PX4's `/fmu/out/*` topics directly.

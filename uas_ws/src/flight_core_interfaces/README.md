# flight_core_interfaces

Service definitions used by Python clients to command the `flight_core` node.

| Service | Type | Purpose |
|---|---|---|
| `/flight_core/acquire_control` | `AcquireControl` | Take the control lease |
| `/flight_core/release_control` | `ReleaseControl` | Give the lease back |
| `/flight_core/reset_control` | `ResetControl` | Clear any lease and hold position |
| `/flight_core/command` | `Command` | Arm, disarm, offboard, hold, land |
| `/flight_core/goto` | `Goto` | Fly to a NED position |

Vehicle state is not wrapped; clients read PX4's `/fmu/out/*` topics directly.

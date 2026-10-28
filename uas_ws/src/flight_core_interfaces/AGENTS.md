# flight_core_interfaces agent guide

Context for changing the `flight_core` interfaces. The user-facing service
and topic tables are in [README.md](README.md).

- Follow PX4's naming: inputs are services under `/flight_core/in/`, outputs
  are topics under `/flight_core/out/`.
- Every request that needs control carries `lease_id`; `AcquireControl`
  returns it.
- Use NaN for "uncontrolled" or "default" float fields, as PX4 does.
  `Trajectory` fields map directly onto `px4_msgs/TrajectorySetpoint`, and
  `Goto` onto `GotoSetpoint`.
- `CoreState` state constants must match `CoreCommand`'s.
- Do not add messages that wrap PX4 vehicle state; clients read
  `/fmu/out/*` directly.
- Keep the comments in `.srv`/`.msg` files accurate: they are the field-level
  reference.
- Any change here also needs `flight_core` (node, `client.py`, READMEs)
  updated and rebuilt:
  `colcon build --base-paths uas_ws/src --packages-up-to flight_core --symlink-install`.

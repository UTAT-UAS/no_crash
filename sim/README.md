# sim

Simulation assets used by [`scripts/sim`](../scripts/sim). See
[Simulation](../docs/development/README.md#simulation) for how to run it.

## Worlds

`scripts/sim sitl start` loads `worlds/$PX4_GZ_WORLD.sdf` from this directory,
falling back to PX4's `Tools/simulation/gz/worlds` when no project world has
that name. `PX4_GZ_WORLD` defaults to `default`.

- `default.sdf`: PX4's default world (flat ground plane) with its origin at
  43.781680° N, 79.466434° W, 185 m elevation (WGS84, ENU). Gazebo's GPS and
  magnetometer derive their readings from this origin, so PX4's home position
  and magnetic declination match the site.

A world's `<world name="...">` must match its file name: the script and PX4
address Gazebo services as `/world/$PX4_GZ_WORLD/...`.

# ROS packages

ROS 2 Jazzy packages live here, each with its own `package.xml` and build
configuration.

- [`flight_core`](flight_core/README.md): central PX4 offboard node and the
  Python `Drone` client library.
- [`flight_core_interfaces`](flight_core_interfaces/README.md): services used to
  command `flight_core`.
- [`flight_visualizer_bridge`](flight_visualizer_bridge/README.md): on-drone
  TCP link between `flight_core` and the flight visualizer backend.
- `px4_msgs`: Git submodule pinned to PX4 v1.17.0 messages.

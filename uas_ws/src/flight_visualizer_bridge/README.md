# flight_visualizer_bridge

Runs on the drone and links `flight_core` to the
[flight visualizer backend](../../../flight_visualizer/backend/README.md) over
TCP. It streams vehicle and core state, and forwards visualizer commands to
`flight_core` as a `Drone` client named `flight_visualizer_bridge`.

```
flight_core / PX4 ◀──ROS──▶ flight_visualizer_bridge ◀──TCP (4G)──▶ backend ◀──WebSocket──▶ browser
```

```bash
ros2 run flight_visualizer_bridge flight_visualizer_bridge
ros2 run flight_visualizer_bridge flight_visualizer_bridge --ros-args -p port:=8765 -p rate_hz:=5.0
```

| Parameter | Default | |
|---|---|---|
| `host` | `0.0.0.0` | Listen address |
| `port` | `8765` | TCP port the backend connects to |
| `rate_hz` | `5.0` | State messages per second (about 230 bytes each) |

Commands: `acquire`, `reacquire`, `release`, `hold`, `arm`, `disarm`,
`offboard`, `position`, `land` and `goto [x, y, z]` (NED metres). Commands
that move the vehicle need the bridge to hold the control lease. After the
bridge restarts, its previous lease is still held, so use `reacquire`; it
also takes control from any other client.

The backend connects to the bridge, so the backend host must be able to reach
the drone's port. A 4G modem usually sits behind carrier NAT, so expect to
need a VPN or another route to the drone.

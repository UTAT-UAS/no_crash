# Flight visualizer frontend

SvelteKit dashboard showing the drone and flight_core state as text, plus a
top-down map and an altimeter with the drone and its target. It also sends
commands. It talks to the [backend](../../backend/README.md) over WebSocket.

```bash
cd ~/workspace/flight_visualizer/frontend/flight_visualizer
bun install --frozen-lockfile
bun run dev        # http://localhost:5173
```

The container publishes port 5173 on the host, so open
`http://localhost:5173` there. With a VS Code port forward instead, use
`http://127.0.0.1:5173` in Firefox.

To try it in simulation, run `scripts/sitl start`,
`ros2 run flight_visualizer_bridge flight_visualizer_bridge`, the backend, and
`bun run dev`.

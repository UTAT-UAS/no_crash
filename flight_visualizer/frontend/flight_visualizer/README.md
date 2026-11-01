# Flight visualizer frontend

SvelteKit dashboard showing the drone and flight_core state as text, plus a
top-down map and an altimeter with the drone and its target. It also sends
commands. It talks to the [backend](../../backend/README.md) over WebSocket.

```bash
cd ~/workspace/flight_visualizer/frontend/flight_visualizer
bun install --frozen-lockfile   # also generates src/lib/gen from the .proto
bun run dev        # http://localhost:5173
```

Message types are generated from the bridge's
[`flight_visualizer.proto`](../../../uas_ws/src/flight_visualizer_bridge/proto/flight_visualizer.proto)
with `protoc`; run `bun run generate` after it changes.

The container publishes port 5173 on the host, so open
`http://localhost:5173` there. With a VS Code port forward instead, use
`http://127.0.0.1:5173` in Firefox.

To try it in simulation, run `scripts/sim sitl start` and
`scripts/sim viz start` from the repository root.

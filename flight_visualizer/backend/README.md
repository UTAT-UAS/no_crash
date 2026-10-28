# Flight visualizer backend

FastAPI app that connects to
[`flight_visualizer_bridge`](../../uas_ws/src/flight_visualizer_bridge/README.md)
on the drone and relays it to the dashboard: state goes to browsers, commands
go to the bridge. `GET /api/state` returns the link status and latest state.

```bash
cd ~/workspace/flight_visualizer/backend
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

| Variable | Default |
|---|---|
| `BRIDGE_HOST` | `127.0.0.1` |
| `BRIDGE_PORT` | `8765` |

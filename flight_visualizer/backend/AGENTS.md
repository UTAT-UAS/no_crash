# Flight visualizer backend agent guide

User-facing usage is in [README.md](README.md). Keep it lean; put detail here.

## Design

- `app.py` is the whole app. A background task keeps one TCP connection to
  the bridge and reconnects every second (`RECONNECT_DELAY`). Every bridge
  line is forwarded to all browsers; the latest state is cached for new
  browsers and `/api/state`.
- `/ws`: on connect, a browser gets `{"type":"link","connected":bool}` and
  the cached state. Browser commands `{"id","name","args"}` get
  `"type":"command"` added and go to the bridge. Without a bridge connection,
  the backend replies with a failed result itself. Link changes are broadcast.
- Results go to every browser, not only the sender; browsers match on `id`.
- The protocol is defined by the bridge; see
  [`flight_visualizer_bridge/AGENTS.md`](../../uas_ws/src/flight_visualizer_bridge/AGENTS.md#protocol).
  Keep this app and the frontend in step with it.
- The backend connects to the bridge, so it must be able to reach the drone's
  port. Over 4G that usually needs a VPN.
- Keep it minimal: no auth, persistence or history until asked for.

## Environment

- uv project: `pyproject.toml` and committed `uv.lock`; the venv is `.venv`
  (ignored). Add dependencies with `uv add`.
- `[tool.uv] python-preference = "only-system"` keeps it on the container's
  Python 3.12. It does not need ROS.
- `--host 0.0.0.0` is needed for Docker's published port 8000 to reach
  uvicorn. Docker publishes it only on the host's loopback.

## Verification

```bash
python3 -m py_compile app.py
uv run uvicorn app:app --port 8010 &   # a spare port if 8000 is in use
curl -s localhost:8010/api/state
```

For WebSocket checks, use the `websockets` package from the venv
(`uv run python`), with SITL and the bridge running.

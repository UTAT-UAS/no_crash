# Flight visualizer backend agent guide

User-facing usage is in [README.md](README.md). Keep it lean; put detail here.

## Design

- `app.py` is the whole app. A background task keeps one TCP connection to
  the bridge and reconnects every second (`RECONNECT_DELAY`). It reads
  length-prefixed protobuf `BridgeMessage` frames and forwards each to all
  browsers as proto3 JSON (`to_json`); the latest state is cached for new
  browsers and `/api/state`.
- `/ws`: on connect, a browser gets `{"link":{"connected":bool}}` and the
  cached state. The link message is the backend's own and is not in the
  `.proto`. Everything else is proto3 JSON with `.proto` field names, e.g.
  `{"state":{...}}`, `{"result":{"id":1,"ok":true}}`, and from browsers
  `{"command":{"id":1,"name":"goto","args":[0,0,-3]}}`.
- proto3 JSON omits fields at their default (`ok: false`, `0`, `""` for
  non-`optional` fields) and writes NaN as `"NaN"`; the frontend's `fromJson`
  restores them.
- Browser commands are parsed with `json_format.ParseDict` and forwarded
  framed. Invalid JSON, or no bridge connection, gets a failed result from
  the backend itself. Link changes are broadcast.
- Results go to every browser, not only the sender; browsers match on `id`.
- The protocol is defined by the bridge in
  [`flight_visualizer.proto`](../../uas_ws/src/flight_visualizer_bridge/proto/flight_visualizer.proto);
  see [`flight_visualizer_bridge/AGENTS.md`](../../uas_ws/src/flight_visualizer_bridge/AGENTS.md#protocol).
- The backend connects to the bridge, so it must be able to reach the drone's
  port. Over 4G that usually needs a VPN.
- Keep it minimal: no auth, persistence or history until asked for.

## Environment

- uv project: `pyproject.toml` and committed `uv.lock`; the venv is `.venv`
  (ignored). Add dependencies with `uv add`.
- `generate.sh` writes `flight_visualizer_pb2.py(i)` (ignored) with the protoc
  bundled in the `grpcio-tools` dev dependency, so the generated code matches
  the venv's `protobuf` runtime. The system protoc is too old for it.
- `[tool.uv] python-preference = "only-system"` keeps it on the container's
  Python 3.12. It does not need ROS.
- `--host 0.0.0.0` is needed for Docker's published port 8000 to reach
  uvicorn. Docker publishes it only on the host's loopback.

## Verification

```bash
./generate.sh
python3 -m py_compile app.py
../../scripts/lint python
uv run uvicorn app:app --port 8010 &   # a spare port if 8000 is in use
curl -s localhost:8010/api/state
```

For WebSocket checks, use the `websockets` package from the venv
(`uv run python`), with SITL and the bridge running.

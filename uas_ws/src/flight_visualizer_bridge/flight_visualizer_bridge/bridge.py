"""TCP bridge between the flight visualizer backend and flight_core.

Serves one connection at a time; a new connection replaces the old one. Both
directions carry newline-delimited compact JSON:

- bridge -> backend: `{"type": "state", ...}` at `rate_hz`, and
  `{"type": "result", "id": ..., "ok": bool, "error": str | null}` for each
  command.
- backend -> bridge: `{"type": "command", "id": ..., "name": ..., "args": [...]}`.
"""

import json
import math
import socket
import threading
import time

from flight_core.client import Drone
from flight_core_interfaces.msg import CoreState
from px4_msgs.msg import VehicleStatus

# PX4 navigation state values to names, e.g. 14 -> 'OFFBOARD'.
NAV_STATES = {
    getattr(VehicleStatus, name): name.removeprefix('NAVIGATION_STATE_')
    for name in dir(type(VehicleStatus))
    if name.startswith('NAVIGATION_STATE_') and name != 'NAVIGATION_STATE_MAX'
}
CORE_STATES = {
    CoreState.HOLD: 'HOLD',
    CoreState.GOTO: 'GOTO',
    CoreState.TRAJECTORY: 'TRAJECTORY',
}
# Commands the visualizer may send. None of them wait for long, so a slow
# command cannot hold up a following one such as land.
COMMANDS = {
    'acquire': Drone.acquire,
    'reacquire': Drone.reacquire,
    'release': Drone.release,
    'hold': Drone.hold,
    'arm': Drone.arm,
    'disarm': Drone.disarm,
    'offboard': Drone.offboard_mode,
    'position': Drone.position_mode,
    'land': lambda drone: drone.land(wait=False),
    'goto': lambda drone, x, y, z: drone.goto(x, y, z, wait=False),
}
# Drop a connection whose send blocks this long, e.g. a stalled 4G link.
SEND_TIMEOUT = 5.0


class BridgeDrone(Drone):
    """Drone client that streams state to, and takes commands from, a socket."""

    def __init__(self):
        super().__init__('flight_visualizer_bridge')
        self.host = self._node.declare_parameter('host', '0.0.0.0').value
        self.port = self._node.declare_parameter('port', 8765).value
        self.rate_hz = self._node.declare_parameter('rate_hz', 5.0).value
        self._conn = None
        # Guards self._conn and serializes sends from the state and command
        # threads.
        self._lock = threading.Lock()

    def serve(self):
        """Accept visualizer connections until ROS shuts down (Ctrl-C)."""
        server = socket.create_server((self.host, self.port))
        # Wake up periodically to notice shutdown.
        server.settimeout(1.0)
        threading.Thread(target=self._stream_state, daemon=True).start()
        self._log.info(
            f'Listening on {self.host}:{self.port}, state at {self.rate_hz} Hz')
        while self._node.context.ok():
            try:
                conn, address = server.accept()
            except socket.timeout:
                continue
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.settimeout(SEND_TIMEOUT)
            self._log.info(f'Visualizer connected from {address[0]}')
            with self._lock:
                if self._conn is not None:
                    self._conn.close()
                self._conn = conn
            threading.Thread(
                target=self._read_commands, args=(conn,), daemon=True).start()
        server.close()

    def state(self):
        """Latest vehicle and core state as a JSON-ready dict."""
        status = self._status
        local = self._local_position
        land = self._land_detected
        core = self._core_status
        return {
            'type': 'state',
            'armed': None if status is None
            else status.arming_state == VehicleStatus.ARMING_STATE_ARMED,
            'mode': None if status is None
            else NAV_STATES.get(status.nav_state, str(status.nav_state)),
            'landed': None if land is None else land.landed,
            'position': None if local is None
            else _rounded([local.x, local.y, local.z]),
            'velocity': None if local is None
            else _rounded([local.vx, local.vy, local.vz]),
            'heading': None if local is None else _rounded([local.heading])[0],
            'core_state': None if core is None
            else CORE_STATES.get(core.state, str(core.state)),
            'lease_holder': None if core is None else core.lease_holder,
            'target': None if core is None
            else _rounded(core.target_position),
        }

    def _stream_state(self):
        while True:
            try:
                self._send(self.state())
            except Exception as error:  # Keep streaming after a bad snapshot.
                self._log.error(f'Failed to send state: {error}')
            time.sleep(1.0 / self.rate_hz)

    def _send(self, message):
        line = json.dumps(message, separators=(',', ':')) + '\n'
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.sendall(line.encode())
            except OSError as error:
                self._log.warning(f'Dropping visualizer connection: {error}')
                self._conn.close()
                self._conn = None

    def _read_commands(self, conn):
        buffer = b''
        while True:
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buffer += data
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                self._run_command(line)
        with self._lock:
            if self._conn is conn:
                self._log.info('Visualizer disconnected')
                conn.close()
                self._conn = None

    def _run_command(self, line):
        result = {'type': 'result', 'id': None, 'ok': False, 'error': None}
        try:
            message = json.loads(line)
            result['id'] = message.get('id')
            name = message['name']
            command = COMMANDS.get(name)
            if command is None:
                raise ValueError(f'Unknown command {name!r}')
            self._log.info(f'Visualizer command: {name} {message.get("args", [])}')
            command(self, *message.get('args', []))
            result['ok'] = True
        except Exception as error:  # Report every failure to the visualizer.
            result['error'] = str(error) or type(error).__name__
            self._log.warning(f'Visualizer command failed: {result["error"]}')
        self._send(result)


def _rounded(values):
    """Round to centimetres; NaN (invalid in JSON) becomes None."""
    # float() also converts numpy float32 from fixed-size message arrays.
    return [round(float(v), 2) if math.isfinite(v) else None for v in values]


def main():
    bridge = BridgeDrone()
    try:
        bridge.serve()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.close()

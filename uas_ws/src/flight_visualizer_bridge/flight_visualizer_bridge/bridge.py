"""TCP bridge between the flight visualizer backend and flight_core.

Serves one connection at a time; a new connection replaces the old one. Both
directions carry protobuf messages from `proto/flight_visualizer.proto`, each
prefixed by its length as a 4-byte big-endian uint32:

- bridge -> backend: `BridgeMessage` with a `State` at `rate_hz`, and a
  `Result` for each command.
- backend -> bridge: `BackendMessage` with a `Command`.
"""

from collections.abc import Callable, Iterable
import socket
import struct
import threading
import time
from typing import SupportsFloat

from px4_msgs.msg import VehicleStatus

from flight_core.client import Drone
from flight_core_interfaces.msg import CoreState
from flight_visualizer_bridge import flight_visualizer_pb2 as pb

# PX4 navigation state values to names, e.g. 14 -> 'OFFBOARD'.
NAV_STATES: dict[int, str] = {
    getattr(VehicleStatus, name): name.removeprefix('NAVIGATION_STATE_')
    for name in dir(type(VehicleStatus))
    if name.startswith('NAVIGATION_STATE_') and name != 'NAVIGATION_STATE_MAX'
}
CORE_STATES: dict[int, pb.CoreStateKind] = {
    CoreState.HOLD: pb.HOLD,
    CoreState.GOTO: pb.GOTO,
    CoreState.TRAJECTORY: pb.TRAJECTORY,
}
# Commands the visualizer may send. None of them wait for long, so a slow
# command cannot hold up a following one such as land.
COMMANDS: dict[str, Callable[..., None]] = {
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
# Frames are prefixed by their length as a big-endian uint32.
LENGTH = struct.Struct('>I')
# Commands are tiny; anything larger means a broken or foreign peer.
MAX_FRAME = 64 * 1024


class BridgeDrone(Drone):
    """Drone client that streams state to, and takes commands from, a socket."""

    def __init__(self) -> None:
        super().__init__('flight_visualizer_bridge')
        self.host = (
            self._node.declare_parameter('host', '0.0.0.0').get_parameter_value().string_value
        )
        self.port = self._node.declare_parameter('port', 8765).get_parameter_value().integer_value
        self.rate_hz = (
            self._node.declare_parameter('rate_hz', 5.0).get_parameter_value().double_value
        )
        self._conn: socket.socket | None = None
        # Guards self._conn and serializes sends from the state and command
        # threads.
        self._lock = threading.Lock()

    def serve(self) -> None:
        """Accept visualizer connections until ROS shuts down (Ctrl-C)."""
        server = socket.create_server((self.host, self.port))
        # Wake up periodically to notice shutdown.
        server.settimeout(1.0)
        threading.Thread(target=self._stream_state, daemon=True).start()
        self._log.info(f'Listening on {self.host}:{self.port}, state at {self.rate_hz} Hz')
        while self._node.context.ok():
            try:
                conn, address = server.accept()
            except TimeoutError:
                continue
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn.settimeout(SEND_TIMEOUT)
            self._log.info(f'Visualizer connected from {address[0]}')
            with self._lock:
                if self._conn is not None:
                    self._conn.close()
                self._conn = conn
            threading.Thread(target=self._read_commands, args=(conn,), daemon=True).start()
        server.close()

    def state(self) -> pb.State:
        """Latest vehicle and core state; fields are unset until received."""
        state = pb.State()
        if (status := self._status) is not None:
            state.armed = status.arming_state == VehicleStatus.ARMING_STATE_ARMED
            state.mode = NAV_STATES.get(status.nav_state, str(status.nav_state))
        if (land := self._land_detected) is not None:
            state.landed = land.landed
        if (local := self._local_position) is not None:
            _set_vector(state.position, [local.x, local.y, local.z])
            _set_vector(state.velocity, [local.vx, local.vy, local.vz])
            state.heading = float(local.heading)
        if (core := self._core_status) is not None:
            state.core_state = CORE_STATES.get(core.state, pb.CORE_STATE_UNKNOWN)
            state.lease_holder = core.lease_holder
            _set_vector(state.target, core.target_position)
        return state

    def _stream_state(self) -> None:
        while True:
            try:
                self._send(pb.BridgeMessage(state=self.state()))
            except Exception as error:  # Keep streaming after a bad snapshot.
                self._log.error(f'Failed to send state: {error}')
            time.sleep(1.0 / self.rate_hz)

    def _send(self, message: pb.BridgeMessage) -> None:
        payload = message.SerializeToString()
        frame = LENGTH.pack(len(payload)) + payload
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.sendall(frame)
            except OSError as error:
                self._log.warning(f'Dropping visualizer connection: {error}')
                self._conn.close()
                self._conn = None

    def _read_commands(self, conn: socket.socket) -> None:
        buffer = b''
        oversized = False
        while not oversized:
            try:
                data = conn.recv(4096)
            except TimeoutError:
                continue
            except OSError:
                break
            if not data:
                break
            buffer += data
            while len(buffer) >= LENGTH.size:
                (length,) = LENGTH.unpack_from(buffer)
                if length > MAX_FRAME:
                    self._log.warning(f'Dropping visualizer connection: {length} byte frame')
                    oversized = True
                    break
                if len(buffer) < LENGTH.size + length:
                    break
                frame = buffer[LENGTH.size : LENGTH.size + length]
                buffer = buffer[LENGTH.size + length :]
                self._run_command(frame)
        with self._lock:
            if self._conn is conn:
                self._log.info('Visualizer disconnected')
                conn.close()
                self._conn = None

    def _run_command(self, frame: bytes) -> None:
        result = pb.Result(ok=False)
        try:
            message = pb.BackendMessage.FromString(frame)
            if message.WhichOneof('message') != 'command':
                raise ValueError('Expected a command')
            result.id = message.command.id
            name = message.command.name
            args = list(message.command.args)
            command = COMMANDS.get(name)
            if command is None:
                raise ValueError(f'Unknown command {name!r}')
            self._log.info(f'Visualizer command: {name} {args}')
            command(self, *args)
            result.ok = True
        except Exception as error:  # Report every failure to the visualizer.
            result.error = str(error) or type(error).__name__
            self._log.warning(f'Visualizer command failed: {result.error}')
        self._send(pb.BridgeMessage(result=result))


def _set_vector(vector: pb.Vector3, values: Iterable[SupportsFloat]) -> None:
    """Fill a Vector3; float() also converts numpy float32 message arrays."""
    vector.x, vector.y, vector.z = (float(v) for v in values)


def main() -> None:
    bridge = BridgeDrone()
    try:
        bridge.serve()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.close()

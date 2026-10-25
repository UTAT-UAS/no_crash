"""Python client for commanding the vehicle through the flight_core node."""

import math
import re
import threading
import time

from flight_core_interfaces.srv import (
    AcquireControl, Command, Goto, ReleaseControl)
from px4_msgs.msg import VehicleLocalPosition, VehicleStatus
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import qos_profile_sensor_data


class ControlError(RuntimeError):
    """A command was rejected or did not take effect in time."""


class Drone:
    """Control the vehicle through flight_core while holding its control lease.

    Positions are NED metres in PX4's local frame; headings are radians from
    North. Use as a context manager to acquire control on entry and hold and
    release on exit::

        with Drone('square') as drone:
            drone.takeoff(5.0)
            drone.goto(5.0, 0.0, -5.0)
            drone.land()
    """

    def __init__(self, name='script', service_timeout=5.0):
        """Create the client node and start spinning it in the background."""
        self.name = name
        self.service_timeout = service_timeout
        self._lease_id = None
        self._status = None
        self._local_position = None

        self._owns_context = not rclpy.ok()
        if self._owns_context:
            rclpy.init()
        node_name = 'drone_' + re.sub(r'\W', '_', name)
        self._node = rclpy.create_node(node_name)

        self._node.create_subscription(
            VehicleStatus, '/fmu/out/vehicle_status_v1',
            self._on_status, qos_profile_sensor_data)
        self._node.create_subscription(
            VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1',
            self._on_local_position, qos_profile_sensor_data)

        self._acquire = self._node.create_client(
            AcquireControl, '/flight_core/acquire_control')
        self._release = self._node.create_client(
            ReleaseControl, '/flight_core/release_control')
        self._command = self._node.create_client(
            Command, '/flight_core/command')
        self._goto = self._node.create_client(Goto, '/flight_core/goto')

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(
            target=self._executor.spin, daemon=True)
        self._spin_thread.start()

    def __enter__(self):
        """Acquire control."""
        try:
            self.acquire()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        """Hold position if flying, release control, and stop the node."""
        try:
            if self._lease_id is not None:
                try:
                    if self.is_offboard:
                        self.hold()
                finally:
                    self.release()
        finally:
            self.close()

    def close(self):
        """Stop the background node. Does not release control."""
        self._executor.shutdown()
        self._spin_thread.join()
        self._node.destroy_node()
        if self._owns_context:
            rclpy.try_shutdown()

    # Control lease

    def acquire(self, timeout=10.0):
        """Take the control lease once PX4 state is being received."""
        self.wait_until(
            lambda: self._status is not None
            and self._local_position is not None,
            timeout, 'PX4 vehicle status and local position')
        request = AcquireControl.Request(client_name=self.name)
        self._lease_id = self._call(self._acquire, request).lease_id

    def release(self):
        """Give up the control lease; the vehicle keeps its current target."""
        request = ReleaseControl.Request(lease_id=self._lease_id)
        self._lease_id = None
        self._call(self._release, request)

    # Commands

    def arm(self, timeout=5.0):
        """Arm and wait until PX4 reports armed."""
        self._send_command(Command.Request.ARM)
        self.wait_until(lambda: self.is_armed, timeout, 'arming')

    def disarm(self, timeout=5.0):
        """Disarm and wait until PX4 reports disarmed."""
        self._send_command(Command.Request.DISARM)
        self.wait_until(lambda: not self.is_armed, timeout, 'disarming')

    def offboard(self, timeout=5.0):
        """Switch to offboard, holding the current position."""
        self._send_command(Command.Request.OFFBOARD)
        self.wait_until(lambda: self.is_offboard, timeout, 'offboard mode')

    def hold(self):
        """Hold the current position."""
        self._send_command(Command.Request.HOLD)

    def land(self, wait=True, timeout=60.0):
        """Land with PX4's land mode; optionally wait for auto-disarm."""
        self._send_command(Command.Request.LAND)
        if wait:
            self.wait_until(lambda: not self.is_armed, timeout, 'landing')

    def takeoff(self, altitude, timeout=30.0, tolerance=0.3):
        """Enter offboard, arm if needed, and climb `altitude` metres.

        In real mode flight_core rejects arming, so the pilot must arm first.
        """
        self.offboard()
        if not self.is_armed:
            self.arm()
        x, y, z = self.position
        self.goto(x, y, z - altitude, timeout=timeout, tolerance=tolerance)

    def goto(self, x, y, z, heading=None, max_speed=None, wait=True,
             tolerance=0.3, timeout=60.0):
        """Fly to a NED position; by default keep the current heading.

        With `wait`, block until within `tolerance` metres and nearly
        stopped. `max_speed` limits horizontal speed in m/s.
        """
        if heading is None:
            heading = self.heading
        request = Goto.Request(
            lease_id=self._lease_id,
            position=[float(x), float(y), float(z)],
            heading=float(heading),
            max_horizontal_speed=math.nan if max_speed is None
            else float(max_speed))
        self._call(self._goto, request)
        if wait:
            self.wait_until(
                lambda: math.dist(self.position, (x, y, z)) < tolerance
                and math.hypot(*self.velocity) < 0.3,
                timeout, f'reaching ({x}, {y}, {z})')

    def wait_until(self, predicate, timeout, description='condition'):
        """Poll `predicate` until true or raise ControlError after `timeout`."""
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise ControlError(f'Timed out waiting for {description}')
            time.sleep(0.05)

    # Vehicle state from PX4

    @property
    def status(self):
        """Latest raw px4_msgs VehicleStatus."""
        return self._require(self._status, 'vehicle status')

    @property
    def is_armed(self):
        """Whether PX4 reports the vehicle armed."""
        return self.status.arming_state == VehicleStatus.ARMING_STATE_ARMED

    @property
    def is_offboard(self):
        """Whether PX4 is in offboard mode."""
        return (self.status.nav_state
                == VehicleStatus.NAVIGATION_STATE_OFFBOARD)

    @property
    def position(self):
        """Local NED position (x, y, z) in metres."""
        p = self._require(self._local_position, 'local position')
        return (p.x, p.y, p.z)

    @property
    def velocity(self):
        """Local NED velocity (vx, vy, vz) in m/s."""
        p = self._require(self._local_position, 'local position')
        return (p.vx, p.vy, p.vz)

    @property
    def heading(self):
        """Heading in radians from North."""
        return self._require(self._local_position, 'local position').heading

    # Internals

    def _on_status(self, msg):
        self._status = msg

    def _on_local_position(self, msg):
        self._local_position = msg

    def _send_command(self, command):
        request = Command.Request(lease_id=self._lease_id, command=command)
        self._call(self._command, request)

    def _call(self, client, request):
        if not client.wait_for_service(timeout_sec=self.service_timeout):
            raise ControlError(f'Service {client.srv_name} is not available')
        done = threading.Event()
        future = client.call_async(request)
        future.add_done_callback(lambda _: done.set())
        if not done.wait(self.service_timeout):
            client.remove_pending_request(future)
            raise ControlError(f'Service {client.srv_name} timed out')
        response = future.result()
        if not response.success:
            raise ControlError(response.message)
        return response

    @staticmethod
    def _require(value, description):
        if value is None:
            raise ControlError(f'No {description} received from PX4')
        return value

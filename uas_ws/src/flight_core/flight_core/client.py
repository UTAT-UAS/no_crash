"""Python client for commanding the vehicle through the flight_core node."""

import math
import re
import threading
import time

from flight_core_interfaces.msg import CoreState
from flight_core_interfaces.srv import (
    AcquireControl, CoreCommand, CoreVehicleCommand, Goto, ReleaseControl,
    Trajectory)
from px4_msgs.msg import (
    VehicleLandDetected, VehicleLocalPosition, VehicleStatus)
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
        # Last core state set by this client; None until it sets one.
        self._core_state = None
        self._status = None
        self._core_status = None
        self._local_position = None
        self._land_detected = None

        self._owns_context = not rclpy.ok()
        if self._owns_context:
            rclpy.init()
        node_name = 'drone_' + re.sub(r'\W', '_', name)
        self._node = rclpy.create_node(node_name)
        self._log = self._node.get_logger()

        self._node.create_subscription(
            VehicleStatus, '/fmu/out/vehicle_status_v1',
            self._on_status, qos_profile_sensor_data)
        self._node.create_subscription(
            VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1',
            self._on_local_position, qos_profile_sensor_data)
        self._node.create_subscription(
            VehicleLandDetected, '/fmu/out/vehicle_land_detected',
            self._on_land_detected, qos_profile_sensor_data)

        self._node.create_subscription(
            CoreState, '/flight_core/out/core_state',
            self._on_core_state, 10)

        self._acquire = self._node.create_client(
            AcquireControl, '/flight_core/in/acquire_control')
        self._release = self._node.create_client(
            ReleaseControl, '/flight_core/in/release_control')
        self._core_command = self._node.create_client(
            CoreCommand, '/flight_core/in/core_command')
        self._vehicle_command = self._node.create_client(
            CoreVehicleCommand, '/flight_core/in/vehicle_command')
        self._goto = self._node.create_client(Goto, '/flight_core/in/goto')
        self._trajectory = self._node.create_client(
            Trajectory, '/flight_core/in/trajectory')

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
                    if self.is_offboard and self.is_armed:
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
        self._log.info(f'Requesting control as {self.name!r}')
        request = AcquireControl.Request(client_name=self.name)
        self._lease_id = self._call(self._acquire, request).lease_id
        self._log.info(f'Control acquired (lease {self._lease_id})')

    def release(self):
        """Give up the control lease; the vehicle keeps its current target."""
        self._log.info('Releasing control')
        request = ReleaseControl.Request(lease_id=self._lease_id)
        self._lease_id = None
        self._call(self._release, request)

    # Core states

    def hold(self):
        """Hold the current position and heading."""
        self._set_state(CoreCommand.Request.HOLD)

    # Vehicle commands

    def arm(self, timeout=5.0):
        """Arm and wait until PX4 reports armed."""
        self._log.info('Requesting arm')
        self._send_vehicle_command(CoreVehicleCommand.Request.ARM)
        self.wait_until(lambda: self.is_armed, timeout, 'arming')
        self._log.info('Armed')

    def disarm(self, timeout=5.0):
        """Disarm and wait until PX4 reports disarmed."""
        self._log.info('Requesting disarm')
        self._send_vehicle_command(CoreVehicleCommand.Request.DISARM)
        self.wait_until(lambda: not self.is_armed, timeout, 'disarming')
        self._log.info('Disarmed')

    def offboard_mode(self, timeout=5.0):
        """Switch to offboard and wait until PX4 reports it."""
        self._log.info('Requesting offboard mode')
        self._send_vehicle_command(CoreVehicleCommand.Request.OFFBOARD)
        self.wait_until(lambda: self.is_offboard, timeout, 'offboard mode')
        self._log.info('In offboard mode')

    def position_mode(self, timeout=5.0):
        """Switch to PX4 position mode and wait until PX4 reports it.

        flight_core returns to HOLD.
        """
        self._log.info('Requesting position mode')
        self._send_vehicle_command(CoreVehicleCommand.Request.POSITION)
        self._core_state = CoreCommand.Request.HOLD
        self.wait_until(
            lambda: self.status.nav_state
            == VehicleStatus.NAVIGATION_STATE_POSCTL,
            timeout, 'position mode')
        self._log.info('In position mode')

    def land(self, wait=True, timeout=60.0):
        """Land with PX4's land mode; flight_core returns to HOLD.

        With `wait`, block until PX4 reports landed, then disarm (unless PX4
        already has) and switch to position mode.
        """
        self._log.info('Requesting land')
        self._send_vehicle_command(CoreVehicleCommand.Request.LAND)
        self._core_state = CoreCommand.Request.HOLD
        if not wait:
            return
        self.wait_until(lambda: self.is_landed, timeout, 'landing')
        self._log.info('Landed')
        if self.is_armed:
            self.disarm()
        self.position_mode()

    def takeoff(self, altitude, timeout=30.0, tolerance=0.3):
        """Hold, enter offboard, arm if needed, and climb `altitude` metres.

        In real mode flight_core rejects arming, so the pilot must arm first.
        """
        self._log.info(f'Taking off {altitude} m')
        self.hold()
        self.offboard_mode()
        if not self.is_armed:
            self.arm()
        x, y, z = self.position
        self.goto(x, y, z - altitude, timeout=timeout, tolerance=tolerance)

    def goto(self, x, y, z, heading=None, max_speed=None, wait=True,
             tolerance=0.3, timeout=60.0):
        """Fly to a NED position; by default keep the current heading.

        Switches the core to GOTO if needed. The target is saved even outside
        offboard and flown once offboard. With `wait`, block until within
        `tolerance` metres and nearly stopped. `max_speed` limits horizontal
        speed in m/s.
        """
        if self._core_state != CoreCommand.Request.GOTO:
            self._set_state(CoreCommand.Request.GOTO)
        if heading is None:
            heading = self.heading
        self._log.info(
            f'Requesting goto ({x:.2f}, {y:.2f}, {z:.2f}), '
            f'heading {heading:.2f} rad'
            + ('' if max_speed is None else f', max speed {max_speed} m/s'))
        request = Goto.Request(
            lease_id=self._lease_id,
            position=[float(x), float(y), float(z)],
            heading=float(heading),
            max_horizontal_speed=math.nan if max_speed is None
            else float(max_speed))
        self._call(self._goto, request)
        if wait:
            self.wait_until(
                lambda: self.has_arrived(x, y, z, tolerance),
                timeout, f'reaching ({x}, {y}, {z})')
            self._log.info(f'Arrived at ({x:.2f}, {y:.2f}, {z:.2f})')

    def has_arrived(self, x, y, z, tolerance=0.2, max_speed=0.2):
        """Whether within `tolerance` m of (x, y, z) and nearly stopped.

        Nearly stopped means slower than `max_speed` m/s.
        """
        return (math.dist(self.position, (x, y, z)) < tolerance
                and math.hypot(*self.velocity) < max_speed)

    def trajectory(self, position=None, velocity=None, acceleration=None,
                   yaw=None, yawspeed=None):
        """Set the PX4 TrajectorySetpoint fields; None leaves one uncontrolled.

        Switches the core to TRAJECTORY if needed (starting at the current
        position) and returns immediately. Vectors are NED (x, y, z); each
        axis needs at least one controlled field. Keep the fields
        kinematically consistent and resend at the rate you plan at.
        """
        if self._core_state != CoreCommand.Request.TRAJECTORY:
            self._set_state(CoreCommand.Request.TRAJECTORY)
        # Debug only: trajectory setpoints are typically sent at a high rate.
        self._log.debug(
            f'Trajectory position={position} velocity={velocity} '
            f'acceleration={acceleration} yaw={yaw} yawspeed={yawspeed}')
        request = Trajectory.Request(
            lease_id=self._lease_id,
            position=_vector(position),
            velocity=_vector(velocity),
            acceleration=_vector(acceleration),
            yaw=math.nan if yaw is None else float(yaw),
            yawspeed=math.nan if yawspeed is None else float(yawspeed))
        self._call(self._trajectory, request)

    def wait_until(self, predicate, timeout, description='condition'):
        """Poll `predicate` until true or raise ControlError after `timeout`."""
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() > deadline:
                raise ControlError(f'Timed out waiting for {description}')
            time.sleep(0.05)

    # Vehicle state from PX4

    @property
    def core_state(self):
        """Latest flight_core CoreState (state and lease holder)."""
        return self._require(self._core_status, 'flight_core state')

    @property
    def status(self):
        """Latest raw px4_msgs VehicleStatus."""
        return self._require(self._status, 'PX4 vehicle status')

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
    def is_landed(self):
        """Whether PX4's land detector reports the vehicle landed."""
        return self._require(
            self._land_detected, 'PX4 land detection').landed

    @property
    def position(self):
        """Local NED position (x, y, z) in metres."""
        p = self._require(self._local_position, 'PX4 local position')
        return (p.x, p.y, p.z)

    @property
    def velocity(self):
        """Local NED velocity (vx, vy, vz) in m/s."""
        p = self._require(self._local_position, 'PX4 local position')
        return (p.vx, p.vy, p.vz)

    @property
    def heading(self):
        """Heading in radians from North."""
        return self._require(self._local_position, 'PX4 local position').heading

    # Internals

    def _on_core_state(self, msg):
        self._core_status = msg

    def _on_status(self, msg):
        self._status = msg

    def _on_local_position(self, msg):
        self._local_position = msg

    def _on_land_detected(self, msg):
        self._land_detected = msg

    def _set_state(self, state):
        self._log.info(f'Requesting core state {_STATE_NAMES[state]}')
        request = CoreCommand.Request(lease_id=self._lease_id, state=state)
        self._call(self._core_command, request)
        self._core_state = state

    def _send_vehicle_command(self, command):
        request = CoreVehicleCommand.Request(
            lease_id=self._lease_id, command=command)
        self._call(self._vehicle_command, request)

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
            self._log.error(f'{client.srv_name} rejected: {response.message}')
            raise ControlError(response.message)
        return response

    @staticmethod
    def _require(value, description):
        if value is None:
            raise ControlError(f'No {description} received')
        return value


_STATE_NAMES = {
    CoreCommand.Request.HOLD: 'HOLD',
    CoreCommand.Request.GOTO: 'GOTO',
    CoreCommand.Request.TRAJECTORY: 'TRAJECTORY',
}


def _vector(values):
    """Convert an optional (x, y, z) to floats, with None components as NaN."""
    if values is None:
        return [math.nan] * 3
    return [math.nan if v is None else float(v) for v in values]

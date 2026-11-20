"""Fly over a Task 2 sample, descend in steps while re-centring on it, grab it, and climb.

Usage: ros2 run target_retrieval pickup egg|dung|droppings

Descent logic follows land_on_pad.py. Gripper control follows last year's
pump_control.py (VehicleCommand DO_SET_ACTUATOR), until mechanical confirms
how the real gripper is driven.
"""

import sys
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.utilities import remove_ros_args

from flight_core.client import ControlError, Drone
from px4_msgs.msg import VehicleCommand
from task2_interfaces.msg import TargetEstimate

TARGET_TOPIC = '/target_detloc/out/targets'
SAMPLE_TYPES = {
    'egg': TargetEstimate.EGG,
    'dung': TargetEstimate.DUNG,
    'droppings': TargetEstimate.DROPPINGS,
}

TAKEOFF_ALTITUDE = 5.0  # [m] climb used when starting on the ground (sim testing)
STEP = 1.0  # [m] descent per step while high
FINE_STEP = 0.3  # [m] descent per step below FINE_HEIGHT
FINE_HEIGHT = 2.0  # [m] height above the sample where fine steps start
GRAB_HEIGHT = 0.5  # [m] height above the sample to grab at. TODO: from mechanical
SAFE_HEIGHT = 3.0  # [m] height above the sample to climb to after a grab
SETTLE = 1.0  # [s] wait after each step so the next estimate comes from a level camera
CLOSE_TIME = 1.5  # [s] time for the gripper to close. TODO: from mechanical
MAX_RETRIES = 3  # grab attempts before giving up
MAX_AGE = 0.5  # [s] estimates older than this are treated as lost
FIRST_TARGET_TIMEOUT = 30.0  # [s] wait for the first estimate
LOST_TARGET_TIMEOUT = 5.0  # [s] give up if the sample is lost this long

# Gripper on a PX4 output set to "Peripheral via Actuator Set N".
# TODO: confirm index and open/closed values with electrical.
GRIPPER_INDEX = 0  # 0-5 -> Actuator Set 1-6
GRIPPER_OPEN = -1.0
GRIPPER_CLOSED = 1.0


class TargetListener(Node):
    """Keep the latest estimate for one sample, locked to the first id seen."""

    def __init__(self, sample_type: int) -> None:
        super().__init__('pickup_listener')
        self._sample_type = sample_type
        self._lock = threading.Lock()
        self._id: int | None = None
        self._target: TargetEstimate | None = None
        self._received = 0.0
        self.create_subscription(TargetEstimate, TARGET_TOPIC, self._on_target, 10)

    def _on_target(self, msg: TargetEstimate) -> None:
        if msg.sample_type != self._sample_type:
            return
        with self._lock:
            if self._id is None:
                self._id = msg.id
            if msg.id != self._id:
                return
            self._target = msg
            self._received = time.monotonic()

    def fresh_target(self) -> tuple[float, float, float] | None:
        """Latest NED position of the locked sample, or None if stale."""
        with self._lock:
            if self._target is None or time.monotonic() - self._received > MAX_AGE:
                return None
            x, y, z = self._target.position
            return (float(x), float(y), float(z))


class Gripper(Node):
    """Stream the gripper setpoint to PX4, as last year's pump_control did."""

    def __init__(self) -> None:
        super().__init__('pickup_gripper')
        self._value = GRIPPER_OPEN
        self._pub = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', 10)
        self.create_timer(0.1, self._publish)

    def open(self) -> None:
        self._value = GRIPPER_OPEN

    def close(self) -> None:
        self._value = GRIPPER_CLOSED

    def is_holding(self) -> bool | None:
        """Whether the gripper holds the sample; None while there is no sensor.

        TODO: extraction_successful(), once mechanical/electrical decide how.
        """
        return None

    def _publish(self) -> None:
        msg = VehicleCommand()
        msg.timestamp = self.get_clock().now().nanoseconds // 1000
        msg.command = VehicleCommand.VEHICLE_CMD_DO_SET_ACTUATOR
        params = [float('nan')] * 6
        params[GRIPPER_INDEX] = self._value
        (msg.param1, msg.param2, msg.param3, msg.param4, msg.param5, msg.param6) = params
        msg.param7 = 0.0
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self._pub.publish(msg)


def wait_for_target(drone: Drone, listener: TargetListener,
                    timeout: float) -> tuple[float, float, float]:
    """Return a fresh sample position, or raise ControlError after `timeout`."""
    target = None

    def have_target() -> bool:
        nonlocal target
        target = listener.fresh_target()
        return target is not None

    drone.wait_until(have_target, timeout, 'a sample estimate')
    assert target is not None
    return target


def descend_to_grab_height(drone: Drone, listener: TargetListener) -> None:
    """Step down while re-centring until GRAB_HEIGHT above the sample.

    NED: z grows downward, so descending means increasing z.
    """
    while True:
        time.sleep(SETTLE)
        tx, ty, tz = wait_for_target(drone, listener, LOST_TARGET_TIMEOUT)
        grab_z = tz - GRAB_HEIGHT
        _, _, z = drone.position
        step = FINE_STEP if tz - z <= FINE_HEIGHT else STEP
        target_z = min(z + step, grab_z)
        drone.goto(tx, ty, target_z)
        if target_z >= grab_z:
            return


def pick_it(drone: Drone, listener: TargetListener, gripper: Gripper) -> bool:
    """Try up to MAX_RETRIES grabs. Return True once a grab succeeds."""
    for attempt in range(1, MAX_RETRIES + 1):
        drone._log.info(f'Pickup attempt {attempt}/{MAX_RETRIES}')
        gripper.open()
        descend_to_grab_height(drone, listener)

        gripper.close()
        time.sleep(CLOSE_TIME)

        tx, ty, tz = wait_for_target(drone, listener, LOST_TARGET_TIMEOUT)
        drone.goto(tx, ty, tz - SAFE_HEIGHT)

        holding = gripper.is_holding()
        if holding is None:
            drone._log.warning('No gripper sensor; assuming the grab succeeded')
            return True
        if holding:
            return True
        drone._log.warning('Grab failed')
    return False


def run(drone: Drone, listener: TargetListener, gripper: Gripper) -> None:
    if drone.is_landed:
        drone.takeoff(TAKEOFF_ALTITUDE)
    elif not drone.is_offboard:
        drone.hold()
        drone.offboard_mode()

    # Fly over the sample at the current altitude.
    tx, ty, _ = wait_for_target(drone, listener, FIRST_TARGET_TIMEOUT)
    _, _, z = drone.position
    drone.goto(tx, ty, z)

    if not pick_it(drone, listener, gripper):
        raise ControlError(f'Pickup failed after {MAX_RETRIES} attempts')
    drone._log.info('Pickup done')


def main() -> None:
    args = remove_ros_args(sys.argv)[1:]
    if len(args) != 1 or args[0] not in SAMPLE_TYPES:
        sys.exit(f'Usage: pickup {"|".join(SAMPLE_TYPES)}')

    rclpy.init()
    listener = TargetListener(SAMPLE_TYPES[args[0]])
    gripper = Gripper()
    executor = SingleThreadedExecutor()
    executor.add_node(listener)
    executor.add_node(gripper)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    try:
        # Leaving the with block (including on an error) holds position and releases control.
        with Drone('pickup') as drone:
            run(drone, listener, gripper)
    finally:
        executor.shutdown()
        listener.destroy_node()
        gripper.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
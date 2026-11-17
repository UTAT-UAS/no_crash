"""Fly over the blue landing pad, descend in steps while re-centring on it, and land.

Port of last year's flight_stack landing_pad.py to flight_core's Drone client.
Reads the pad position from TargetEstimate messages with sample_type LANDING_PAD.
"""

import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from flight_core.client import Drone
from task2_interfaces.msg import TargetEstimate

TARGET_TOPIC = '/target_detloc/out/targets'
TAKEOFF_ALTITUDE = 5.0  # [m] climb used when starting on the ground (sim testing)
STEP = 1.0  # [m] descent per step
LAND_HEIGHT = 1.0  # [m] height above the pad where PX4 land takes over
SETTLE = 1.0  # [s] wait after each step so the next estimate comes from a level camera
MAX_AGE = 0.5  # [s] pad estimates older than this are treated as lost
FIRST_PAD_TIMEOUT = 30.0  # [s] wait for the first pad estimate
LOST_PAD_TIMEOUT = 5.0  # [s] give up if the pad is lost this long during descent


class PadListener(Node):
    """Keep the latest landing pad estimate."""

    def __init__(self) -> None:
        super().__init__('land_on_pad_listener')
        self._lock = threading.Lock()
        self._pad: TargetEstimate | None = None
        self._received = 0.0
        self.create_subscription(TargetEstimate, TARGET_TOPIC, self._on_target, 10)

    def _on_target(self, msg: TargetEstimate) -> None:
        if msg.sample_type != TargetEstimate.LANDING_PAD:
            return
        with self._lock:
            self._pad = msg
            self._received = time.monotonic()

    def fresh_pad(self) -> tuple[float, float, float] | None:
        """Latest pad NED position, or None if none arrived within MAX_AGE."""
        with self._lock:
            if self._pad is None or time.monotonic() - self._received > MAX_AGE:
                return None
            x, y, z = self._pad.position
            return (float(x), float(y), float(z))


def wait_for_pad(drone: Drone, listener: PadListener, timeout: float) -> tuple[float, float, float]:
    """Return a fresh pad position, or raise ControlError after `timeout`."""
    pad = None

    def have_pad() -> bool:
        nonlocal pad
        pad = listener.fresh_pad()
        return pad is not None

    drone.wait_until(have_pad, timeout, 'a landing pad estimate')
    assert pad is not None
    return pad


def land_on_pad(drone: Drone, listener: PadListener) -> None:
    """Centre over the pad, step down while re-centring, then land."""
    if drone.is_landed:
        drone.takeoff(TAKEOFF_ALTITUDE)
    elif not drone.is_offboard:
        drone.hold()
        drone.offboard_mode()

    # Fly over the pad at the current altitude.
    pad_x, pad_y, _ = wait_for_pad(drone, listener, FIRST_PAD_TIMEOUT)
    _, _, z = drone.position
    drone.goto(pad_x, pad_y, z)

    # NED: z grows downward, so descending means increasing z.
    while True:
        time.sleep(SETTLE)
        pad_x, pad_y, pad_z = wait_for_pad(drone, listener, LOST_PAD_TIMEOUT)
        floor = pad_z - LAND_HEIGHT
        _, _, z = drone.position
        target_z = min(z + STEP, floor)
        drone.goto(pad_x, pad_y, target_z)
        if target_z >= floor:
            break

    drone.land()


def main() -> None:
    rclpy.init()
    listener = PadListener()
    executor = SingleThreadedExecutor()
    executor.add_node(listener)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    try:
        # Leaving the with block (including on an error, e.g. pad lost)
        # holds position and releases control.
        with Drone('land_on_pad') as drone:
            land_on_pad(drone, listener)
    finally:
        executor.shutdown()
        listener.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
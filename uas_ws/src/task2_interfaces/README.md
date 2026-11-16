Positions are local NED in metres, the same frame as `flight_core`'s `goto` (x north, y east, z down). NaN means unknown or unset.

## Topics


## Build

    colcon build --base-paths uas_ws/src --packages-select task2_interfaces
    source install/local_setup.bash
    ros2 interface show task2_interfaces/msg/TargetEstimate
# Detected Task 2 target, published by target_detloc on /target_detloc/out/targets.
uint8 EGG = 0
uint8 DUNG = 1
uint8 DROPPINGS = 2
uint8 LANDING_PAD = 3

std_msgs/Header header # stamp: time of the camera frame used; frame_id: "local_ned"
uint8 sample_type # one of the constants above
uint32 id # same physical object keeps the same id across frames
float32[3] position # [m] filtered NED position, same frame as flight_core goto
float32 position_std_m # [m] position uncertainty; NaN when unknown
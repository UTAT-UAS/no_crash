# flight_core status, published on /flight_core/out/core_state at the core's rate.
uint8 HOLD = 0
uint8 GOTO = 1
uint8 TRAJECTORY = 2

uint8 state # matches CoreCommand state values
string lease_holder # client name holding control; empty when none

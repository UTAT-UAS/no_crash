#include "flight_core/flight_core_node.hpp"

#include <chrono>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace flight_core
{

using px4_msgs::msg::GotoSetpoint;
using px4_msgs::msg::TrajectorySetpoint;
using px4_msgs::msg::VehicleCommand;
using px4_msgs::msg::VehicleCommandAck;
using px4_msgs::msg::VehicleLocalPosition;
using std::placeholders::_1;
using std::placeholders::_2;

namespace
{

/// Goto setpoint at the vehicle's current position and heading.
GotoSetpoint goto_at(const VehicleLocalPosition & position)
{
  GotoSetpoint setpoint{};
  setpoint.position = {position.x, position.y, position.z};
  setpoint.flag_control_heading = true;
  setpoint.heading = position.heading;
  setpoint.max_horizontal_speed = NAN;
  return setpoint;
}

/// Mirror PX4's PositionControl input checks so invalid setpoints are rejected
/// here rather than triggering PX4's failsafe setpoint.
std::string validate_trajectory(const flight_core_interfaces::srv::Trajectory::Request & request)
{
  for (int axis = 0; axis < 3; ++axis) {
    if (!std::isfinite(request.position[axis]) && !std::isfinite(request.velocity[axis]) &&
      !std::isfinite(request.acceleration[axis]))
    {
      return "Axis " + std::to_string(axis) + " needs a finite position, velocity or acceleration";
    }
  }
  for (const auto * field : {&request.position, &request.velocity, &request.acceleration}) {
    if (std::isfinite((*field)[0]) != std::isfinite((*field)[1])) {
      return "x and y must both be finite or both NaN";
    }
  }
  return "";
}

VehicleCommand make_vehicle_command(uint32_t command, float param1, float param2)
{
  VehicleCommand msg{};
  msg.command = command;
  msg.param1 = param1;
  msg.param2 = param2;
  msg.target_system = 1;
  msg.target_component = 1;
  msg.source_system = 1;
  msg.source_component = 1;
  msg.from_external = true;
  return msg;
}

const char * state_name(uint8_t state)
{
  static constexpr const char * names[] = {"HOLD", "GOTO", "TRAJECTORY"};
  return state < 3 ? names[state] : "UNKNOWN";
}

}  // namespace

FlightCoreNode::FlightCoreNode()
: Node("flight_core")
{
  const double rate_hz = declare_parameter("rate_hz", 20.0);

  rcl_interfaces::msg::ParameterDescriptor mode_descriptor;
  mode_descriptor.description = "'sim' allows arming requests; 'real' rejects them";
  mode_descriptor.read_only = true;
  const std::string mode = declare_parameter("mode", "real", mode_descriptor);
  if (mode != "sim" && mode != "real") {
    throw std::invalid_argument("Parameter 'mode' must be 'sim' or 'real', got '" + mode + "'");
  }
  sim_mode_ = mode == "sim";

  // PX4 publishes /fmu/out/* best effort.
  const auto px4_qos = rclcpp::SensorDataQoS();
  status_sub_ = create_subscription<px4_msgs::msg::VehicleStatus>(
    "/fmu/out/vehicle_status_v1", px4_qos,
    [this](px4_msgs::msg::VehicleStatus::SharedPtr msg) {status_ = *msg;});
  local_position_sub_ = create_subscription<px4_msgs::msg::VehicleLocalPosition>(
    "/fmu/out/vehicle_local_position_v1", px4_qos,
    [this](px4_msgs::msg::VehicleLocalPosition::SharedPtr msg) {local_position_ = *msg;});
  command_ack_sub_ = create_subscription<VehicleCommandAck>(
    "/fmu/out/vehicle_command_ack", px4_qos,
    [this](VehicleCommandAck::SharedPtr msg) {
      if (msg->result != VehicleCommandAck::VEHICLE_CMD_RESULT_ACCEPTED &&
      msg->result != VehicleCommandAck::VEHICLE_CMD_RESULT_IN_PROGRESS)
      {
        RCLCPP_WARN(
          get_logger(), "PX4 rejected command %u (result %u)", msg->command, msg->result);
      }
    });

  offboard_mode_pub_ =
    create_publisher<px4_msgs::msg::OffboardControlMode>("/fmu/in/offboard_control_mode", 10);
  goto_pub_ = create_publisher<GotoSetpoint>("/fmu/in/goto_setpoint", 10);
  trajectory_pub_ = create_publisher<TrajectorySetpoint>("/fmu/in/trajectory_setpoint", 10);
  command_pub_ = create_publisher<VehicleCommand>("/fmu/in/vehicle_command", 10);
  core_state_pub_ =
    create_publisher<flight_core_interfaces::msg::CoreState>("/flight_core/out/core_state", 10);

  acquire_srv_ = create_service<AcquireControl>(
    "/flight_core/in/acquire_control", std::bind(&FlightCoreNode::on_acquire, this, _1, _2));
  release_srv_ = create_service<ReleaseControl>(
    "/flight_core/in/release_control", std::bind(&FlightCoreNode::on_release, this, _1, _2));
  reset_srv_ = create_service<ResetControl>(
    "/flight_core/in/reset_control", std::bind(&FlightCoreNode::on_reset, this, _1, _2));
  core_command_srv_ = create_service<CoreCommand>(
    "/flight_core/in/core_command", std::bind(&FlightCoreNode::on_core_command, this, _1, _2));
  vehicle_command_srv_ = create_service<CoreVehicleCommand>(
    "/flight_core/in/vehicle_command", std::bind(&FlightCoreNode::on_vehicle_command, this, _1, _2));
  goto_srv_ = create_service<Goto>(
    "/flight_core/in/goto", std::bind(&FlightCoreNode::on_goto, this, _1, _2));
  trajectory_srv_ = create_service<Trajectory>(
    "/flight_core/in/trajectory", std::bind(&FlightCoreNode::on_trajectory, this, _1, _2));

  timer_ = create_wall_timer(
    std::chrono::duration<double>(1.0 / rate_hz), std::bind(&FlightCoreNode::on_timer, this));

  RCLCPP_INFO(get_logger(), "Flight core ready in %s mode at %.1f Hz.", mode.c_str(), rate_hz);
}

void FlightCoreNode::on_timer()
{
  const uint64_t now = timestamp_us();
  px4_msgs::msg::OffboardControlMode mode{};
  mode.timestamp = now;
  mode.position = true;
  offboard_mode_pub_->publish(mode);
  if (heartbeats_sent_ < kHeartbeatsBeforeOffboard) {
    ++heartbeats_sent_;
  }

  if (heartbeats_established()) {
    for (auto & command : pending_commands_) {
      command.timestamp = now;
      command_pub_->publish(command);
    }
    pending_commands_.clear();
  }

  // Hold where the vehicle is when it becomes armed in offboard, rather than
  // at a point captured earlier (e.g. before a manual flight or landing).
  const bool engaged = offboard() && armed();
  if (state_ == CoreCommand::Request::HOLD && engaged && !was_engaged_ && position_valid()) {
    hold_setpoint_ = goto_at(*local_position_);
  }
  was_engaged_ = engaged;

  flight_core_interfaces::msg::CoreState core_state;
  core_state.state = state_;
  core_state.lease_holder = lease_.holder_name();
  core_state.target_position = target_position();
  core_state_pub_->publish(core_state);

  // PX4 runs goto in any position-controlled mode on cycles where the active
  // flight task has not published, so only stream setpoints while in offboard.
  if (!offboard()) {
    return;
  }

  switch (state_) {
    case CoreCommand::Request::HOLD:
      if (hold_setpoint_) {
        hold_setpoint_->timestamp = now;
        goto_pub_->publish(*hold_setpoint_);
      }
      break;
    case CoreCommand::Request::GOTO:
      goto_setpoint_.timestamp = now;
      goto_pub_->publish(goto_setpoint_);
      break;
    case CoreCommand::Request::TRAJECTORY:
      trajectory_setpoint_.timestamp = now;
      trajectory_pub_->publish(trajectory_setpoint_);
      break;
  }
}

void FlightCoreNode::on_acquire(
  const AcquireControl::Request::SharedPtr request, AcquireControl::Response::SharedPtr response)
{
  const auto lease_id = lease_.acquire(request->client_name);
  if (!lease_id) {
    response->message = "Control is held by '" + lease_.holder_name() + "'";
    return;
  }
  response->success = true;
  response->lease_id = *lease_id;
  RCLCPP_INFO(get_logger(), "Control acquired by '%s'.", request->client_name.c_str());
}

void FlightCoreNode::on_release(
  const ReleaseControl::Request::SharedPtr request, ReleaseControl::Response::SharedPtr response)
{
  const std::string holder = lease_.holder_name();
  if (!lease_.release(request->lease_id)) {
    response->message = "Lease is not held";
    return;
  }
  response->success = true;
  RCLCPP_INFO(get_logger(), "Control released by '%s'.", holder.c_str());
}

void FlightCoreNode::on_reset(
  const ResetControl::Request::SharedPtr, ResetControl::Response::SharedPtr response)
{
  const std::string holder = lease_.holder_name();
  lease_.reset();
  if (position_valid()) {
    set_state(CoreCommand::Request::HOLD);
  }
  response->success = true;
  response->message = holder.empty() ? "No lease was held" : "Cleared lease of '" + holder + "'";
  RCLCPP_WARN(get_logger(), "Control reset. %s.", response->message.c_str());
}

void FlightCoreNode::on_core_command(
  const CoreCommand::Request::SharedPtr request, CoreCommand::Response::SharedPtr response)
{
  if (!lease_.is_holder(request->lease_id)) {
    response->message = "Lease is not held";
    return;
  }
  response->message = set_state(request->state);
  response->success = response->message.empty();
}

void FlightCoreNode::on_vehicle_command(
  const CoreVehicleCommand::Request::SharedPtr request,
  CoreVehicleCommand::Response::SharedPtr response)
{
  if (!lease_.is_holder(request->lease_id)) {
    response->message = "Lease is not held";
    return;
  }

  switch (request->command) {
    case CoreVehicleCommand::Request::ARM:
      if (!sim_mode_) {
        response->message = "Arming is disabled in real mode; arm from the RC or GCS";
        return;
      }
      if (!position_valid()) {
        response->message = "No valid local position";
        return;
      }
      send_after_heartbeats(VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0f);
      break;
    case CoreVehicleCommand::Request::DISARM:
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0f);
      break;
    case CoreVehicleCommand::Request::OFFBOARD:
      if (!position_valid()) {
        response->message = "No valid local position";
        return;
      }
      // MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, PX4 custom main mode OFFBOARD.
      send_after_heartbeats(VehicleCommand::VEHICLE_CMD_DO_SET_MODE, 1.0f, 6.0f);
      break;
    case CoreVehicleCommand::Request::LAND:
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_NAV_LAND);
      if (position_valid()) {
        set_state(CoreCommand::Request::HOLD);
      }
      break;
    case CoreVehicleCommand::Request::POSITION:
      // MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, PX4 custom main mode POSCTL.
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_DO_SET_MODE, 1.0f, 3.0f);
      if (position_valid()) {
        set_state(CoreCommand::Request::HOLD);
      }
      break;
    default:
      response->message = "Unknown command " + std::to_string(request->command);
      return;
  }
  response->success = true;
}

void FlightCoreNode::on_goto(
  const Goto::Request::SharedPtr request, Goto::Response::SharedPtr response)
{
  if (!lease_.is_holder(request->lease_id)) {
    response->message = "Lease is not held";
    return;
  }
  if (state_ != CoreCommand::Request::GOTO) {
    response->message = "Core is not in GOTO state";
    return;
  }
  for (const float value : request->position) {
    if (!std::isfinite(value)) {
      response->message = "Position must be finite";
      return;
    }
  }

  goto_setpoint_.position = request->position;
  goto_setpoint_.flag_control_heading = std::isfinite(request->heading);
  goto_setpoint_.heading = request->heading;
  goto_setpoint_.flag_set_max_horizontal_speed = request->max_horizontal_speed > 0.0f;
  goto_setpoint_.max_horizontal_speed =
    goto_setpoint_.flag_set_max_horizontal_speed ? request->max_horizontal_speed : NAN;
  response->success = true;
}

void FlightCoreNode::on_trajectory(
  const Trajectory::Request::SharedPtr request, Trajectory::Response::SharedPtr response)
{
  if (!lease_.is_holder(request->lease_id)) {
    response->message = "Lease is not held";
    return;
  }
  if (state_ != CoreCommand::Request::TRAJECTORY) {
    response->message = "Core is not in TRAJECTORY state";
    return;
  }
  response->message = validate_trajectory(*request);
  if (!response->message.empty()) {
    return;
  }

  trajectory_setpoint_.position = request->position;
  trajectory_setpoint_.velocity = request->velocity;
  trajectory_setpoint_.acceleration = request->acceleration;
  trajectory_setpoint_.yaw = request->yaw;
  trajectory_setpoint_.yawspeed = request->yawspeed;
  response->success = true;
}

bool FlightCoreNode::offboard() const
{
  return status_ && status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD;
}

bool FlightCoreNode::armed() const
{
  return status_ && status_->arming_state == px4_msgs::msg::VehicleStatus::ARMING_STATE_ARMED;
}

bool FlightCoreNode::position_valid() const
{
  return local_position_ && local_position_->xy_valid && local_position_->z_valid;
}

std::string FlightCoreNode::set_state(uint8_t state)
{
  if (state > CoreCommand::Request::TRAJECTORY) {
    return "Unknown state " + std::to_string(state);
  }
  if (!position_valid()) {
    return "No valid local position";
  }

  switch (state) {
    case CoreCommand::Request::HOLD:
      hold_setpoint_ = goto_at(*local_position_);
      break;
    case CoreCommand::Request::GOTO:
      goto_setpoint_ = goto_at(*local_position_);
      break;
    case CoreCommand::Request::TRAJECTORY:
      trajectory_setpoint_ = TrajectorySetpoint{};
      trajectory_setpoint_.position = {local_position_->x, local_position_->y, local_position_->z};
      trajectory_setpoint_.velocity = {NAN, NAN, NAN};
      trajectory_setpoint_.acceleration = {NAN, NAN, NAN};
      trajectory_setpoint_.jerk = {NAN, NAN, NAN};
      trajectory_setpoint_.yaw = local_position_->heading;
      trajectory_setpoint_.yawspeed = NAN;
      break;
  }
  if (state != state_) {
    RCLCPP_INFO(get_logger(), "Core state %s -> %s.", state_name(state_), state_name(state));
  }
  state_ = state;
  return "";
}

void FlightCoreNode::send_after_heartbeats(uint32_t command, float param1, float param2)
{
  if (heartbeats_established()) {
    send_vehicle_command(command, param1, param2);
    return;
  }
  pending_commands_.push_back(make_vehicle_command(command, param1, param2));
}

std::array<float, 3> FlightCoreNode::target_position() const
{
  switch (state_) {
    case CoreCommand::Request::HOLD:
      if (hold_setpoint_) {
        return hold_setpoint_->position;
      }
      break;
    case CoreCommand::Request::GOTO:
      return goto_setpoint_.position;
    case CoreCommand::Request::TRAJECTORY:
      return trajectory_setpoint_.position;
  }
  const float nan = std::numeric_limits<float>::quiet_NaN();
  return {nan, nan, nan};
}

bool FlightCoreNode::heartbeats_established() const
{
  return heartbeats_sent_ >= kHeartbeatsBeforeOffboard;
}

void FlightCoreNode::send_vehicle_command(uint32_t command, float param1, float param2)
{
  VehicleCommand msg = make_vehicle_command(command, param1, param2);
  msg.timestamp = timestamp_us();
  command_pub_->publish(msg);
}

uint64_t FlightCoreNode::timestamp_us() const
{
  return static_cast<uint64_t>(get_clock()->now().nanoseconds() / 1000);
}

}  // namespace flight_core

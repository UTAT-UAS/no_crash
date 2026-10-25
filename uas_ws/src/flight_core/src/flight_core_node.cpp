#include "flight_core/flight_core_node.hpp"

#include <chrono>
#include <cmath>
#include <stdexcept>
#include <string>

namespace flight_core
{

using px4_msgs::msg::VehicleCommand;
using px4_msgs::msg::VehicleCommandAck;
using std::placeholders::_1;
using std::placeholders::_2;

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
  goto_pub_ = create_publisher<px4_msgs::msg::GotoSetpoint>("/fmu/in/goto_setpoint", 10);
  command_pub_ = create_publisher<VehicleCommand>("/fmu/in/vehicle_command", 10);

  acquire_srv_ = create_service<AcquireControl>(
    "/flight_core/acquire_control", std::bind(&FlightCoreNode::on_acquire, this, _1, _2));
  release_srv_ = create_service<ReleaseControl>(
    "/flight_core/release_control", std::bind(&FlightCoreNode::on_release, this, _1, _2));
  reset_srv_ = create_service<ResetControl>(
    "/flight_core/reset_control", std::bind(&FlightCoreNode::on_reset, this, _1, _2));
  command_srv_ = create_service<Command>(
    "/flight_core/command", std::bind(&FlightCoreNode::on_command, this, _1, _2));
  goto_srv_ = create_service<Goto>(
    "/flight_core/goto", std::bind(&FlightCoreNode::on_goto, this, _1, _2));

  timer_ = create_wall_timer(
    std::chrono::duration<double>(1.0 / rate_hz), std::bind(&FlightCoreNode::on_timer, this));

  RCLCPP_INFO(get_logger(), "Flight core ready in %s mode at %.1f Hz.", mode.c_str(), rate_hz);
}

void FlightCoreNode::on_timer()
{
  // Outside offboard, track the vehicle so switching to offboard holds in place.
  if (!offboard()) {
    if (position_valid()) {
      hold_current_position();
    } else {
      target_.reset();
    }
  }

  px4_msgs::msg::OffboardControlMode mode{};
  mode.timestamp = timestamp_us();
  mode.position = true;
  offboard_mode_pub_->publish(mode);

  // PX4 runs goto in any position-controlled mode on cycles where the active
  // flight task has not published, so only stream it while in offboard.
  if (!offboard() || !target_) {
    return;
  }

  px4_msgs::msg::GotoSetpoint setpoint{};
  setpoint.timestamp = mode.timestamp;
  setpoint.position = *target_;
  setpoint.flag_control_heading = std::isfinite(target_heading_);
  setpoint.heading = target_heading_;
  setpoint.flag_set_max_horizontal_speed = std::isfinite(max_horizontal_speed_);
  setpoint.max_horizontal_speed = max_horizontal_speed_;
  goto_pub_->publish(setpoint);
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
    hold_current_position();
  }
  response->success = true;
  response->message = holder.empty() ? "No lease was held" : "Cleared lease of '" + holder + "'";
  RCLCPP_WARN(get_logger(), "Control reset. %s.", response->message.c_str());
}

void FlightCoreNode::on_command(
  const Command::Request::SharedPtr request, Command::Response::SharedPtr response)
{
  if (!lease_.is_holder(request->lease_id)) {
    response->message = "Lease is not held";
    return;
  }

  switch (request->command) {
    case Command::Request::ARM:
      if (!sim_mode_) {
        response->message = "Arming is disabled in real mode; arm from the RC or GCS";
        return;
      }
      if (!position_valid()) {
        response->message = "No valid local position";
        return;
      }
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0f);
      break;
    case Command::Request::DISARM:
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0f);
      break;
    case Command::Request::OFFBOARD:
      if (!position_valid()) {
        response->message = "No valid local position";
        return;
      }
      hold_current_position();
      // MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, PX4 custom main mode OFFBOARD.
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_DO_SET_MODE, 1.0f, 6.0f);
      break;
    case Command::Request::HOLD:
      if (!position_valid()) {
        response->message = "No valid local position";
        return;
      }
      hold_current_position();
      break;
    case Command::Request::LAND:
      send_vehicle_command(VehicleCommand::VEHICLE_CMD_NAV_LAND);
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
  if (!offboard()) {
    response->message = "Vehicle is not in offboard mode";
    return;
  }
  for (const float value : request->position) {
    if (!std::isfinite(value)) {
      response->message = "Position must be finite";
      return;
    }
  }

  target_ = request->position;
  target_heading_ = request->heading;
  max_horizontal_speed_ =
    request->max_horizontal_speed > 0.0f ? request->max_horizontal_speed : NAN;
  response->success = true;
}

bool FlightCoreNode::offboard() const
{
  return status_ && status_->nav_state == px4_msgs::msg::VehicleStatus::NAVIGATION_STATE_OFFBOARD;
}

bool FlightCoreNode::position_valid() const
{
  return local_position_ && local_position_->xy_valid && local_position_->z_valid;
}

void FlightCoreNode::hold_current_position()
{
  target_ = {local_position_->x, local_position_->y, local_position_->z};
  target_heading_ = NAN;
  max_horizontal_speed_ = NAN;
}

void FlightCoreNode::send_vehicle_command(uint32_t command, float param1, float param2)
{
  VehicleCommand msg{};
  msg.timestamp = timestamp_us();
  msg.command = command;
  msg.param1 = param1;
  msg.param2 = param2;
  msg.target_system = 1;
  msg.target_component = 1;
  msg.source_system = 1;
  msg.source_component = 1;
  msg.from_external = true;
  command_pub_->publish(msg);
}

uint64_t FlightCoreNode::timestamp_us() const
{
  return static_cast<uint64_t>(get_clock()->now().nanoseconds() / 1000);
}

}  // namespace flight_core

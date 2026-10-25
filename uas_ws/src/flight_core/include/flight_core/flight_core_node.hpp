#pragma once

#include <array>
#include <optional>

#include "flight_core/control_lease.hpp"
#include "flight_core_interfaces/srv/acquire_control.hpp"
#include "flight_core_interfaces/srv/command.hpp"
#include "flight_core_interfaces/srv/goto.hpp"
#include "flight_core_interfaces/srv/release_control.hpp"
#include "flight_core_interfaces/srv/reset_control.hpp"
#include "px4_msgs/msg/goto_setpoint.hpp"
#include "px4_msgs/msg/offboard_control_mode.hpp"
#include "px4_msgs/msg/vehicle_command.hpp"
#include "px4_msgs/msg/vehicle_command_ack.hpp"
#include "px4_msgs/msg/vehicle_local_position.hpp"
#include "px4_msgs/msg/vehicle_status.hpp"
#include "rclcpp/rclcpp.hpp"

namespace flight_core
{

/// Sole publisher of PX4 offboard inputs. Streams the offboard heartbeat and a
/// goto setpoint, and accepts commands only from the control lease holder.
class FlightCoreNode : public rclcpp::Node
{
public:
  FlightCoreNode();

private:
  using AcquireControl = flight_core_interfaces::srv::AcquireControl;
  using ReleaseControl = flight_core_interfaces::srv::ReleaseControl;
  using ResetControl = flight_core_interfaces::srv::ResetControl;
  using Command = flight_core_interfaces::srv::Command;
  using Goto = flight_core_interfaces::srv::Goto;

  void on_timer();

  void on_acquire(
    const AcquireControl::Request::SharedPtr request, AcquireControl::Response::SharedPtr response);
  void on_release(
    const ReleaseControl::Request::SharedPtr request, ReleaseControl::Response::SharedPtr response);
  void on_reset(
    const ResetControl::Request::SharedPtr request, ResetControl::Response::SharedPtr response);
  void on_command(const Command::Request::SharedPtr request, Command::Response::SharedPtr response);
  void on_goto(const Goto::Request::SharedPtr request, Goto::Response::SharedPtr response);

  bool offboard() const;
  bool position_valid() const;
  void hold_current_position();
  void send_vehicle_command(uint32_t command, float param1 = 0.0f, float param2 = 0.0f);
  uint64_t timestamp_us() const;

  ControlLease lease_;
  // In real mode the vehicle must be armed by the pilot (RC or GCS).
  bool sim_mode_{false};

  std::optional<px4_msgs::msg::VehicleStatus> status_;
  std::optional<px4_msgs::msg::VehicleLocalPosition> local_position_;

  // Current goto target; unset until a valid local position is known.
  std::optional<std::array<float, 3>> target_;
  float target_heading_{NAN};
  float max_horizontal_speed_{NAN};

  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr status_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr local_position_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleCommandAck>::SharedPtr command_ack_sub_;

  rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr offboard_mode_pub_;
  rclcpp::Publisher<px4_msgs::msg::GotoSetpoint>::SharedPtr goto_pub_;
  rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr command_pub_;

  rclcpp::Service<AcquireControl>::SharedPtr acquire_srv_;
  rclcpp::Service<ReleaseControl>::SharedPtr release_srv_;
  rclcpp::Service<ResetControl>::SharedPtr reset_srv_;
  rclcpp::Service<Command>::SharedPtr command_srv_;
  rclcpp::Service<Goto>::SharedPtr goto_srv_;

  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace flight_core

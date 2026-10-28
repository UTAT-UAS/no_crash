#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "flight_core/control_lease.hpp"
#include "flight_core_interfaces/msg/core_state.hpp"
#include "flight_core_interfaces/srv/acquire_control.hpp"
#include "flight_core_interfaces/srv/core_command.hpp"
#include "flight_core_interfaces/srv/core_vehicle_command.hpp"
#include "flight_core_interfaces/srv/goto.hpp"
#include "flight_core_interfaces/srv/release_control.hpp"
#include "flight_core_interfaces/srv/reset_control.hpp"
#include "flight_core_interfaces/srv/trajectory.hpp"
#include "px4_msgs/msg/goto_setpoint.hpp"
#include "px4_msgs/msg/offboard_control_mode.hpp"
#include "px4_msgs/msg/trajectory_setpoint.hpp"
#include "px4_msgs/msg/vehicle_command.hpp"
#include "px4_msgs/msg/vehicle_command_ack.hpp"
#include "px4_msgs/msg/vehicle_local_position.hpp"
#include "px4_msgs/msg/vehicle_status.hpp"
#include "rclcpp/rclcpp.hpp"

namespace flight_core
{

/// Sole publisher of PX4 offboard inputs. Its state selects which setpoint is
/// streamed; setpoints are published only while PX4 is in offboard. Commands
/// are accepted only from the control lease holder.
class FlightCoreNode : public rclcpp::Node
{
public:
  FlightCoreNode();

private:
  using AcquireControl = flight_core_interfaces::srv::AcquireControl;
  using ReleaseControl = flight_core_interfaces::srv::ReleaseControl;
  using ResetControl = flight_core_interfaces::srv::ResetControl;
  using CoreCommand = flight_core_interfaces::srv::CoreCommand;
  using CoreVehicleCommand = flight_core_interfaces::srv::CoreVehicleCommand;
  using Goto = flight_core_interfaces::srv::Goto;
  using Trajectory = flight_core_interfaces::srv::Trajectory;

  void on_timer();

  void on_acquire(
    const AcquireControl::Request::SharedPtr request, AcquireControl::Response::SharedPtr response);
  void on_release(
    const ReleaseControl::Request::SharedPtr request, ReleaseControl::Response::SharedPtr response);
  void on_reset(
    const ResetControl::Request::SharedPtr request, ResetControl::Response::SharedPtr response);
  void on_core_command(
    const CoreCommand::Request::SharedPtr request, CoreCommand::Response::SharedPtr response);
  void on_vehicle_command(
    const CoreVehicleCommand::Request::SharedPtr request,
    CoreVehicleCommand::Response::SharedPtr response);
  void on_goto(const Goto::Request::SharedPtr request, Goto::Response::SharedPtr response);
  void on_trajectory(
    const Trajectory::Request::SharedPtr request, Trajectory::Response::SharedPtr response);

  bool offboard() const;
  bool armed() const;
  bool position_valid() const;
  /// Enter `state`, resetting its setpoint to the current position.
  /// Returns an error message, or an empty string on success.
  std::string set_state(uint8_t state);
  void send_vehicle_command(uint32_t command, float param1 = 0.0f, float param2 = 0.0f);
  /// Send now, or queue until enough offboard heartbeats have been published
  /// if the core is streaming them.
  void send_after_heartbeats(uint32_t command, float param1 = 0.0f, float param2 = 0.0f);
  bool heartbeats_established() const;
  uint64_t timestamp_us() const;

  ControlLease lease_;
  // In real mode the vehicle must be armed by the pilot (RC or GCS).
  bool sim_mode_{false};

  std::optional<px4_msgs::msg::VehicleStatus> status_;
  std::optional<px4_msgs::msg::VehicleLocalPosition> local_position_;

  uint8_t state_{CoreCommand::Request::HOLD};
  // Saved setpoints; timestamps are filled in when published. The hold point
  // is unset until HOLD is entered or the vehicle becomes armed in offboard.
  std::optional<px4_msgs::msg::GotoSetpoint> hold_setpoint_;
  px4_msgs::msg::GotoSetpoint goto_setpoint_;
  px4_msgs::msg::TrajectorySetpoint trajectory_setpoint_;

  // Whether the vehicle was armed and in offboard on the previous timer tick.
  bool was_engaged_{false};

  // Offboard heartbeats published since startup, capped at the number PX4
  // needs to see before offboard switch and arm commands are sent.
  static constexpr int kHeartbeatsBeforeOffboard = 10;
  int heartbeats_sent_{0};
  std::vector<px4_msgs::msg::VehicleCommand> pending_commands_;

  rclcpp::Subscription<px4_msgs::msg::VehicleStatus>::SharedPtr status_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleLocalPosition>::SharedPtr local_position_sub_;
  rclcpp::Subscription<px4_msgs::msg::VehicleCommandAck>::SharedPtr command_ack_sub_;

  rclcpp::Publisher<px4_msgs::msg::OffboardControlMode>::SharedPtr offboard_mode_pub_;
  rclcpp::Publisher<px4_msgs::msg::GotoSetpoint>::SharedPtr goto_pub_;
  rclcpp::Publisher<px4_msgs::msg::TrajectorySetpoint>::SharedPtr trajectory_pub_;
  rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr command_pub_;
  rclcpp::Publisher<flight_core_interfaces::msg::CoreState>::SharedPtr core_state_pub_;

  rclcpp::Service<AcquireControl>::SharedPtr acquire_srv_;
  rclcpp::Service<ReleaseControl>::SharedPtr release_srv_;
  rclcpp::Service<ResetControl>::SharedPtr reset_srv_;
  rclcpp::Service<CoreCommand>::SharedPtr core_command_srv_;
  rclcpp::Service<CoreVehicleCommand>::SharedPtr vehicle_command_srv_;
  rclcpp::Service<Goto>::SharedPtr goto_srv_;
  rclcpp::Service<Trajectory>::SharedPtr trajectory_srv_;

  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace flight_core

#include "target_detloc/msg/overlay_state.hpp"
#include "rclcpp/rclcpp.hpp"
#include "target_detloc/srv/get_overlay_state.hpp"
#include "target_detloc/srv/set_overlay_state.hpp"
#include <memory>
#include <rclcpp/publisher.hpp>

#define OVERLAY_STATE_CHANGE_TOPIC "/target_detloc/internal/overlay_state"

using SetOverlayState = target_detloc::srv::SetOverlayState;
using GetOverlayState = target_detloc::srv::GetOverlayState;
using OverlayState = target_detloc::msg::OverlayState;

class OverlayStateServer : public rclcpp::Node {
public:
  OverlayStateServer()
    : Node("overlay_state_server") {
    set_service_
      = this->create_service<SetOverlayState>("set_overlay_state",
                                              std::bind(&OverlayStateServer::handle_set_request,
                                                        this,
                                                        std::placeholders::_1,
                                                        std::placeholders::_2));
    get_service_
      = this->create_service<GetOverlayState>("get_overlay_state",
                                              std::bind(&OverlayStateServer::handle_get_request,
                                                        this,
                                                        std::placeholders::_1,
                                                        std::placeholders::_2));
    state_change_publisher_ = this->create_publisher<OverlayState>(OVERLAY_STATE_CHANGE_TOPIC, 10);
  }

private:
  void handle_set_request(const std::shared_ptr<SetOverlayState::Request> request,
                          std::shared_ptr<SetOverlayState::Response> response) {
    state.show_detection = request->show_detection;
    state.show_depth_instead_of_color = request->show_depth_instead_of_color;
    response->success = true;

    state_change_publisher_->publish(state);

    RCLCPP_INFO(this->get_logger(),
                "Set:\nShow Detection: %d,\nShow Depth Instead of Color: %d.",
                state.show_detection,
                state.show_depth_instead_of_color);
  }
  void handle_get_request(const std::shared_ptr<GetOverlayState::Request> request,
                          std::shared_ptr<GetOverlayState::Response> response) {
    response->show_detection = state.show_detection;
    response->show_depth_instead_of_color = state.show_depth_instead_of_color;
    response->success = true;
  }

  rclcpp::Service<SetOverlayState>::SharedPtr set_service_;
  rclcpp::Service<GetOverlayState>::SharedPtr get_service_;
  rclcpp::Publisher<OverlayState>::SharedPtr state_change_publisher_;

  OverlayState state;
};

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<OverlayStateServer>());
  rclcpp::shutdown();
  return 0;
}
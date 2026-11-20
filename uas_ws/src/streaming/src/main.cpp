#include "streaming/streaming_node.hpp"

int main(int argc, char * argv[]) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<StreamingNode>());
  rclcpp::shutdown();
  return 0;
}
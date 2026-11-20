

#include "streaming/streaming_node.hpp"

void StreamingNode::on_color(sensor_msgs::msg::Image::ConstSharedPtr msg) {
  RCLCPP_INFO_THROTTLE(get_logger(), *get_clock(), 1000,
      "color: %ux%u, encoding %s", msg->width, msg->height, msg->encoding.c_str());
}

void StreamingNode::on_depth(sensor_msgs::msg::Image::ConstSharedPtr msg) {
  RCLCPP_INFO_THROTTLE(get_logger(), *get_clock(), 1000,
      "depth: %ux%u, encoding %s", msg->width, msg->height, msg->encoding.c_str());
}

void StreamingNode::on_mask(sensor_msgs::msg::Image::ConstSharedPtr msg) {
  RCLCPP_INFO_THROTTLE(get_logger(), *get_clock(), 1000,
      "mask: %ux%u, encoding %s", msg->width, msg->height, msg->encoding.c_str());
}
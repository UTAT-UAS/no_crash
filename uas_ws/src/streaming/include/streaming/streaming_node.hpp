#pragma once

#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"

#define COLOR_FRAME_TOPIC "/target_detloc/internal/color"
#define MASK_FRAME_TOPIC "/target_detloc/internal/mask"
#define DEPTH_FRAME_TOPIC "/target_detloc/internal/depth"

class StreamingNode : public rclcpp::Node {
public:
  StreamingNode()
    : Node("streaming_node") {
    color_sub_ = create_subscription<sensor_msgs::msg::Image>(
        COLOR_FRAME_TOPIC, rclcpp::SensorDataQoS(),
        [this](sensor_msgs::msg::Image::ConstSharedPtr msg) { on_color(msg); });

    depth_sub_ = create_subscription<sensor_msgs::msg::Image>(
        DEPTH_FRAME_TOPIC, rclcpp::SensorDataQoS(),
        [this](sensor_msgs::msg::Image::ConstSharedPtr msg) { on_depth(msg); });

    mask_sub_ = create_subscription<sensor_msgs::msg::Image>(
        MASK_FRAME_TOPIC, rclcpp::SensorDataQoS(),
        [this](sensor_msgs::msg::Image::ConstSharedPtr msg) { on_mask(msg); });
  }

private:
  void on_color(sensor_msgs::msg::Image::ConstSharedPtr msg);
  void on_depth(sensor_msgs::msg::Image::ConstSharedPtr msg);
  void on_mask(sensor_msgs::msg::Image::ConstSharedPtr msg);

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr color_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr mask_sub_;
};
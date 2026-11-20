#pragma once

#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "streaming/video_streamer.hpp"

// ROS side only: subscribes to an image topic and hands every frame to
// VideoStreamer. All GStreamer logic lives in VideoStreamer.
class StreamingNode : public rclcpp::Node
{
public:
  StreamingNode();

private:
  void on_frame(sensor_msgs::msg::Image::ConstSharedPtr msg);

  std::unique_ptr<VideoStreamer> streamer_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_;
  rclcpp::TimerBase::SharedPtr poll_timer_;
};
#include "streaming/streaming_node.hpp"

#include <chrono>

#include "streaming/utils.hpp"


constexpr char kInputTopic[] = "/target_detloc/internal/color";
//constexpr char kPipelineTail[] = "webrtcsink name=ws";

//THIS IS TEMPORARY
constexpr char kPipelineTail[] =
  "x264enc tune=zerolatency speed-preset=ultrafast ! h264parse ! avdec_h264 ! videoconvert ! autovideosink";

  constexpr int kFps = 30;


StreamingNode::StreamingNode()
: Node("streaming_node")
{
  streamer_ = std::make_unique<VideoStreamer>(
    kPipelineTail, kFps, streaming::make_ros_logger(get_logger()));

  
  sub_ = create_subscription<sensor_msgs::msg::Image>(
    kInputTopic, rclcpp::SensorDataQoS(),
    [this](sensor_msgs::msg::Image::ConstSharedPtr msg) {on_frame(msg);});

 
  poll_timer_ = create_wall_timer(std::chrono::milliseconds(100), [this]() {streamer_->poll();});

  RCLCPP_INFO(get_logger(), "Waiting for frames on %s", kInputTopic);
}

void StreamingNode::on_frame(sensor_msgs::msg::Image::ConstSharedPtr msg)
{
  const auto format = streaming::ros_to_gst_format(msg->encoding);
  if (!format) {
    RCLCPP_WARN_THROTTLE(
      get_logger(), *get_clock(), 5000,
      "Unsupported encoding '%s' (need rgb8/bgr8/rgba8/bgra8/mono8)", msg->encoding.c_str());
    return;
  }
  if (!streaming::is_well_formed(*msg)) {
    RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000, "Malformed image message, skipping");
    return;
  }

  const bool ok = streamer_->push_frame(
    msg->data.data(), static_cast<int>(msg->width), static_cast<int>(msg->height),
    static_cast<int>(msg->step), *format);
  if (!ok) {
    RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000, "Frame was not streamed");
  }
}
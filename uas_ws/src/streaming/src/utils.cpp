#include "streaming/utils.hpp"

#include <unordered_map>

#include "rclcpp/logging.hpp"

namespace streaming
{

std::optional<std::string> ros_to_gst_format(const std::string & encoding)
{
  static const std::unordered_map<std::string, std::string> kFormats = {
    {"rgb8", "RGB"},
    {"bgr8", "BGR"},
    {"rgba8", "RGBA"},
    {"bgra8", "BGRA"},
    {"mono8", "GRAY8"},
  };
  const auto it = kFormats.find(encoding);
  if (it == kFormats.end()) {
    return std::nullopt;
  }
  return it->second;
}

bool is_well_formed(const sensor_msgs::msg::Image & msg)
{
  return msg.data.size() >= static_cast<size_t>(msg.step) * msg.height;
}

VideoStreamer::Logger make_ros_logger(const rclcpp::Logger & logger)
{
  return [logger](VideoStreamer::LogLevel level, const std::string & text) {
           switch (level) {
             case VideoStreamer::LogLevel::Info:
               RCLCPP_INFO(logger, "%s", text.c_str());
               break;
             case VideoStreamer::LogLevel::Warn:
               RCLCPP_WARN(logger, "%s", text.c_str());
               break;
             case VideoStreamer::LogLevel::Error:
               RCLCPP_ERROR(logger, "%s", text.c_str());
               break;
           }
         };
}

} 
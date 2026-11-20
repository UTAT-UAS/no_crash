#pragma once

#include <optional>
#include <string>

#include "rclcpp/logger.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "streaming/video_streamer.hpp"

namespace streaming
{

std::optional<std::string> ros_to_gst_format(const std::string & encoding);

bool is_well_formed(const sensor_msgs::msg::Image & msg);


VideoStreamer::Logger make_ros_logger(const rclcpp::Logger & logger);

}  
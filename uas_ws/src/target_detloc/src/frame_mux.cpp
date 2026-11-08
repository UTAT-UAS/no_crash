#include <memory>
#include <rclcpp/logging.hpp>
#include <rclcpp/parameter_map.hpp>

#include "cv_bridge/cv_bridge.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
using std::placeholders::_1;

#define IS_SIMULATION 0

#if IS_SIMULATION
#define DEPTH_FRAME_SOURCE_TOPIC "/depth_camera"
#define COLOR_FRAME_SOURCE_TOPIC \
  "/world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image"
#else
#define DEPTH_FRAME_SOURCE_TOPIC "/camera/depth/image_raw"
#define COLOR_FRAME_SOURCE_TOPIC "/camera/color/image_raw"
#endif

#define DEPTH_FRAME_OUT_TOPIC "/target_detloc/internal/depth"
#define COLOR_FRAME_OUT_TOPIC "/target_detloc/internal/color"

class FrameMux : public rclcpp::Node
{
public:
  FrameMux()
  : Node("frame_muxer")
  {
    depth_publisher_ = this->create_publisher<sensor_msgs::msg::Image>(DEPTH_FRAME_OUT_TOPIC, 10);

    depth_subscription_ = this->create_subscription<sensor_msgs::msg::Image>(
      DEPTH_FRAME_SOURCE_TOPIC, 10, std::bind(&FrameMux::depth_topic_callback, this, _1));

    color_publisher_ = this->create_publisher<sensor_msgs::msg::Image>(COLOR_FRAME_OUT_TOPIC, 10);

    color_subscription_ = this->create_subscription<sensor_msgs::msg::Image>(
      COLOR_FRAME_SOURCE_TOPIC, 10, std::bind(&FrameMux::color_topic_callback, this, _1));
  }

private:
  void depth_topic_callback(const sensor_msgs::msg::Image::ConstSharedPtr frame_msg) const
  {
    try {
      RCLCPP_DEBUG(this->get_logger(), "Depth input encoding: '%s'", frame_msg->encoding.c_str());

      if (frame_msg->encoding.compare("16UC1") == 0) {
        depth_publisher_->publish(*frame_msg);
        return;
      }

      auto input = cv_bridge::toCvCopy(frame_msg, "32FC1");

      cv::Mat output(input->image.rows, input->image.cols, CV_16UC1);

      for (int y = 0; y < input->image.rows; ++y) {
        const float * src = input->image.ptr<float>(y);
        uint16_t * dst = output.ptr<uint16_t>(y);

        for (int x = 0; x < input->image.cols; ++x) {
          const float depth = src[x];

          if (!std::isfinite(depth) || depth <= 0.0f) {
            dst[x] = 0;
          } else {
            // dst[x] = static_cast<uint16_t>(std::clamp(std::round(depth), 1.0f, 65535.0f));
            dst[x] = static_cast<uint16_t>(std::clamp(std::round(depth * 1000.0f), 1.0f, 65535.0f));
          }
        }
      }

      auto converted = cv_bridge::CvImage(frame_msg->header, "16UC1", output);

      depth_publisher_->publish(*converted.toImageMsg());

    } catch (const cv_bridge::Exception & e) {
      RCLCPP_ERROR(this->get_logger(), "Depth conversion failed: %s", e.what());
    }
  }
  void color_topic_callback(const sensor_msgs::msg::Image::ConstSharedPtr frame_msg) const
  {
    try {
      RCLCPP_DEBUG(this->get_logger(), "Color input encoding: '%s'", frame_msg->encoding.c_str());

      if (frame_msg->encoding.compare("rgb8") == 0) {
        color_publisher_->publish(*frame_msg);  // we don't need to convert it if it's okay
        return;
      }

      // Convert to RGB8
      auto converted = cv_bridge::toCvCopy(frame_msg, "rgb8");
      auto output = converted->toImageMsg();
      color_publisher_->publish(*output);

    } catch (const cv_bridge::Exception & e) {
      RCLCPP_ERROR(this->get_logger(), "Color conversion failed: %s", e.what());
    }
  }

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr depth_subscription_;  // raw frame in
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr depth_publisher_;  // converted frame out
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr color_subscription_;  // raw frame in
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr color_publisher_;  // converted frame out
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<FrameMux>());
  rclcpp::shutdown();
  return 0;
}
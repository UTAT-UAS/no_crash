#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include <rclcpp/logging.hpp>
#include <rclcpp/parameter_map.hpp>

#include "cv_bridge/cv_bridge.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"

#include "target_detloc/msg/bounding_box.hpp"
#include "target_detloc/msg/overlay_state.hpp"
#include "target_detloc/msg/segmentation.hpp"
#include "target_detloc/msg/segmentation_array.hpp"
#include "types.h"
#include "utils.h"

using target_detloc::msg::OverlayState;
using target_detloc::msg::SegmentationArray;

using std::placeholders::_1;

#define OVERLAY_STATE_CHANGE_TOPIC "/target_detloc/internal/overlay_state"

#define COLOR_FRAME_TOPIC "/target_detloc/internal/color"
#define DEPTH_FRAME_OUT_TOPIC "/target_detloc/internal/depth"
#define SEG_RESULT_TOPIC "/target_detloc/internal/segmentation_result"

#define VISUALIZATION_FRAME_TOPIC "/target_detloc/internal/visualization"

class Visualize : public rclcpp::Node {
public:
  Visualize()
    : Node("visualize") {
    overlay_state.show_depth_instead_of_color = false;
    overlay_state.show_detection = true;

    visualization_publisher_
      = this->create_publisher<sensor_msgs::msg::Image>(VISUALIZATION_FRAME_TOPIC, 10);

    overlay_state_subscription
      = this->create_subscription<OverlayState>(OVERLAY_STATE_CHANGE_TOPIC,
                                                10,
                                                std::bind(&Visualize::overlay_state_change_callback,
                                                          this,
                                                          _1));

    segmentation_array_subscription = this->create_subscription<SegmentationArray>(
      SEG_RESULT_TOPIC, 10, std::bind(&Visualize::seg_result_topic_callback, this, _1));

    reset_raw_frame_subscription();
  }

private:
  void reset_raw_frame_subscription() {
    const std::string topic = overlay_state.show_depth_instead_of_color ? DEPTH_FRAME_OUT_TOPIC
                                                                        : COLOR_FRAME_TOPIC;

    raw_frame_subscription = this->create_subscription<sensor_msgs::msg::Image>(
      topic, 10, std::bind(&Visualize::raw_frame_topic_callback, this, _1));

    RCLCPP_INFO(this->get_logger(), "Switched raw frame subscription to: %s", topic.c_str());
  }

  void overlay_state_change_callback(const OverlayState::ConstSharedPtr state) {
    overlay_state.show_detection = state->show_detection;
    if (overlay_state.show_depth_instead_of_color != state->show_depth_instead_of_color) {
      overlay_state.show_depth_instead_of_color = state->show_depth_instead_of_color;
      reset_raw_frame_subscription();
    }
  }

  void seg_result_topic_callback(const SegmentationArray::ConstSharedPtr seg_result) {
    current_segmentation_result.resize(seg_result->detections.size());
    for (size_t i = 0; i < seg_result->detections.size(); i++) {
      current_segmentation_result[i].box.x = seg_result->detections[i].box.x;
      current_segmentation_result[i].box.y = seg_result->detections[i].box.y;
      current_segmentation_result[i].box.height = seg_result->detections[i].box.height;
      current_segmentation_result[i].box.width = seg_result->detections[i].box.width;
      current_segmentation_result[i].classId = seg_result->detections[i].class_id;
      current_segmentation_result[i].conf = seg_result->detections[i].conf;
      if (seg_result->detections[i].mask.height > 0 && seg_result->detections[i].mask.width > 0
          && !seg_result->detections[i].mask.data.empty()) {
        int cv_type = CV_8UC1;
        if (seg_result->detections[i].mask.encoding == "mono8"
            || seg_result->detections[i].mask.encoding == "8UC1") {
          cv_type = CV_8UC1;
        } else if (seg_result->detections[i].mask.encoding == "32FC1") {
          cv_type = CV_32FC1;
        } else if (seg_result->detections[i].mask.encoding == "bgr8") {
          cv_type = CV_8UC3;
        }

        cv::Mat wrapped(static_cast<int>(seg_result->detections[i].mask.height),
                        static_cast<int>(seg_result->detections[i].mask.width),
                        cv_type,
                        const_cast<uint8_t*>(seg_result->detections[i].mask.data.data()),
                        static_cast<size_t>(seg_result->detections[i].mask.step));
        current_segmentation_result[i].mask = wrapped.clone();
      }
    }
  }

  void raw_frame_topic_callback(const sensor_msgs::msg::Image::ConstSharedPtr frame_msg) {
    try {
      const bool want_depth = overlay_state.show_depth_instead_of_color;

      if ((frame_msg->encoding == "16UC1" && !want_depth)
          || (frame_msg->encoding == "rgb8" && want_depth)) {
        RCLCPP_DEBUG(this->get_logger(),
                     "Skipping stale frame with encoding '%s' (want_depth=%d)",
                     frame_msg->encoding.c_str(),
                     want_depth);
        return;
      }

      if (want_depth && frame_msg->encoding != "16UC1") {
        RCLCPP_WARN_THROTTLE(this->get_logger(),
                             *this->get_clock(),
                             2000,
                             "Expected 16UC1 depth frame, got '%s'",
                             frame_msg->encoding.c_str());
        return;
      }

      if (!want_depth && frame_msg->encoding != "rgb8") {
        RCLCPP_WARN_THROTTLE(this->get_logger(),
                             *this->get_clock(),
                             2000,
                             "Expected rgb8 color frame, got '%s'",
                             frame_msg->encoding.c_str());
        return;
      }

      auto raw_frame = cv_bridge::toCvCopy(frame_msg, want_depth ? "16UC1" : "rgb8");
      if (raw_frame->image.empty()) {
        return;
      }

      cv::Mat display_frame = want_depth ? depth_to_rgb8_viz(raw_frame->image) : raw_frame->image;

      if (!overlay_state.show_detection) {
        auto output = cv_bridge::CvImage(frame_msg->header, "rgb8", display_frame);
        visualization_publisher_->publish(*output.toImageMsg());
        return;
      }

      cv::Mat image = visualizeSegments(display_frame, current_segmentation_result);
      if (image.empty()) {
        return;
      }

      // Ensure output is 3-channel rgb8 in case visualizeSegments returns another format
      if (image.channels() == 4) {
        cv::cvtColor(image, image, cv::COLOR_BGRA2RGB);
      } else if (image.channels() == 1) {
        cv::cvtColor(image, image, cv::COLOR_GRAY2RGB);
      }

      auto output = cv_bridge::CvImage(frame_msg->header, "rgb8", image);
      visualization_publisher_->publish(*output.toImageMsg());

    } catch (const cv_bridge::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "cv_bridge error: %s", e.what());
    } catch (const cv::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "OpenCV error: %s", e.what());
    }
  }

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr raw_frame_subscription;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr visualization_publisher_;
  rclcpp::Subscription<OverlayState>::SharedPtr overlay_state_subscription;
  rclcpp::Subscription<SegmentationArray>::SharedPtr segmentation_array_subscription;
  OverlayState overlay_state;
  std::vector<Segmentation> current_segmentation_result;
};

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Visualize>());
  rclcpp::shutdown();
  return 0;
}
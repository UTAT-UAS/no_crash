#include <memory>
#include <rclcpp/logging.hpp>
#include <rclcpp/parameter_map.hpp>

#include "cv_bridge/cv_bridge.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"

#include "yolos/yolos.hpp"

using std::placeholders::_1;

#define COLOR_FRAME_TOPIC "/target_detloc/internal/color"
#define MASK_FRAME_TOPIC "/target_detloc/internal/mask"

#define YOLO_MODEL_PATH "/home/uas/workspace/uas_ws/src/target_detloc/yolo26n-seg.onnx"
#define LABEL_NAME_FILE_PATH "/home/uas/workspace/uas_ws/src/target_detloc/coco80.names"

class Detect : public rclcpp::Node {
public:
  Detect()
    : Node("detect") {

    yolo_detector = std::make_unique<yolos::seg::YOLOSegDetector>(YOLO_MODEL_PATH, LABEL_NAME_FILE_PATH, true);

    mask_publisher_ = this->create_publisher<sensor_msgs::msg::Image>(MASK_FRAME_TOPIC, 10);

    color_subscription = this->create_subscription<sensor_msgs::msg::Image>(
      COLOR_FRAME_TOPIC, 10, std::bind(&Detect::color_topic_callback, this, _1));
  }

private:
  void color_topic_callback(const sensor_msgs::msg::Image::ConstSharedPtr frame_msg) const {
    try {
      if (frame_msg->encoding != "rgb8") {
        RCLCPP_ERROR(this->get_logger(), "Wrong color frame input encoding: '%s'", frame_msg->encoding.c_str());
        return;
      }

      auto input = cv_bridge::toCvCopy(frame_msg, "rgb8");
      auto segments = yolo_detector->segment(input->image);
      yolo_detector->drawSegmentations(input->image, segments, 0.5f);

      mask_publisher_->publish(*input->toImageMsg());

    } catch (const cv_bridge::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "Object detection failed: %s", e.what());
    }
  }

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr color_subscription; // raw frame in
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr mask_publisher_; // converted frame out
  std::unique_ptr<yolos::seg::YOLOSegDetector> yolo_detector;
};

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Detect>());
  rclcpp::shutdown();
  return 0;
}
#include <memory>
#include <rclcpp/logging.hpp>
#include <rclcpp/parameter_map.hpp>

#include "cv_bridge/cv_bridge.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"

using std::placeholders::_1;

#define IS_JETSON 0

#if IS_JETSON
#include "YOLOSegmentationDetector.h"
#define YOLO_MODEL_PATH "/home/uas/model.engine"
#else

#include "yolos/yolos.hpp"
#define YOLO_MODEL_PATH "/home/uas/workspace/uas_ws/src/target_detloc/yolo26n-seg.onnx"
#define LABEL_NAME_FILE_PATH "/home/uas/workspace/uas_ws/src/target_detloc/coco80.names"

#endif

#define COLOR_FRAME_TOPIC "/target_detloc/internal/color"
#define MASK_FRAME_TOPIC "/target_detloc/internal/mask"

class Detect : public rclcpp::Node {
public:
  Detect()
    : Node("detect") {
#if IS_JETSON
    trt_detector = std::make_unique<YOLOSegmentationDetector>(YOLO_MODEL_PATH);
#else
    yolo_detector = std::make_unique<yolos::seg::YOLOSegDetector>(YOLO_MODEL_PATH,
                                                                  LABEL_NAME_FILE_PATH,
                                                                  true);
#endif

    mask_publisher_ = this->create_publisher<sensor_msgs::msg::Image>(MASK_FRAME_TOPIC, 10);

    color_subscription = this->create_subscription<sensor_msgs::msg::Image>(
      COLOR_FRAME_TOPIC, 10, std::bind(&Detect::color_topic_callback, this, _1));
  }

private:
  void color_topic_callback(const sensor_msgs::msg::Image::ConstSharedPtr frame_msg) const {
    try {
      if (frame_msg->encoding != "rgb8") {
        RCLCPP_ERROR(this->get_logger(),
                     "Wrong color frame input encoding: '%s'",
                     frame_msg->encoding.c_str());
        return;
      }

#if IS_JETSON
      auto converted = cv_bridge::toCvCopy(frame_msg, "rgb8");
      std::vector<Segmentation> segments = trt_detector->detect(converted->image, 0.25f, 0.45f);
      std::vector<std::string> labels(80);
      auto image = visualizeSegments(converted->image, segments, labels, 0.4);
      auto labeled = cv_bridge::CvImage(frame_msg->header, "rgb8", image);
      mask_publisher_->publish(*labeled.toImageMsg());

#else
      auto input = cv_bridge::toCvCopy(frame_msg, "rgb8");
      auto segments = yolo_detector->segment(input->image);
      yolo_detector->drawSegmentations(input->image, segments, 0.5f);

      mask_publisher_->publish(*input->toImageMsg());
#endif

    } catch (const cv_bridge::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "Object detection failed: %s", e.what());
    }
  }

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr color_subscription; // raw frame in
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr mask_publisher_; // converted frame out
#if IS_JETSON
  std::unique_ptr<YOLOSegmentationDetector> trt_detector;
#else
  std::unique_ptr<yolos::seg::YOLOSegDetector> yolo_detector;
#endif
};

int main(int argc, char* argv[]) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<Detect>());
  rclcpp::shutdown();
  return 0;
}
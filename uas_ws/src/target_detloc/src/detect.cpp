#include <memory>
#include <rclcpp/logging.hpp>
#include <rclcpp/parameter_map.hpp>

#include "cv_bridge/cv_bridge.hpp"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"

#include "types.h"

#include "target_detloc/msg/bounding_box.hpp"
#include "target_detloc/msg/segmentation.hpp"
#include "target_detloc/msg/segmentation_array.hpp"

using target_detloc::msg::BoundingBox;
using target_detloc::msg::SegmentationArray;

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
#define SEG_RESULT_TOPIC "/target_detloc/internal/segmentation_result"

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

    seg_result_publisher_ = this->create_publisher<SegmentationArray>(SEG_RESULT_TOPIC, 10);

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

#else
      auto input = cv_bridge::toCvCopy(frame_msg, "rgb8");
      auto segments = yolo_detector->segment(input->image);
#endif

      SegmentationArray out_msg;
      out_msg.header.stamp = this->now();
      out_msg.detections.reserve(segments.size());
      for (const auto& item : segments) {
        target_detloc::msg::Segmentation ros_seg_item;
        ros_seg_item.box.x = item.box.x;
        ros_seg_item.box.y = item.box.y;
        ros_seg_item.box.width = item.box.width;
        ros_seg_item.box.height = item.box.height;
        ros_seg_item.conf = item.conf;
        ros_seg_item.class_id = item.classId;

        auto img_msg = std::make_shared<sensor_msgs::msg::Image>();
        img_msg->header = frame_msg->header;
        img_msg->height = static_cast<uint32_t>(item.mask.rows);
        img_msg->width = static_cast<uint32_t>(item.mask.cols);
        img_msg->encoding = "mono8";
        img_msg->is_bigendian = 0;
        img_msg->step = static_cast<uint32_t>(item.mask.step);

        size_t size_bytes = item.mask.step * static_cast<size_t>(item.mask.rows);
        img_msg->data.resize(size_bytes);
        std::memcpy(img_msg->data.data(), item.mask.data, size_bytes);

        ros_seg_item.mask = *img_msg;

        out_msg.detections.push_back(std::move(ros_seg_item));
      }

      seg_result_publisher_->publish(out_msg);

    } catch (const cv_bridge::Exception& e) {
      RCLCPP_ERROR(this->get_logger(), "Object detection failed: %s", e.what());
    }
  }

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr color_subscription; // raw frame in
  rclcpp::Publisher<SegmentationArray>::SharedPtr seg_result_publisher_;       // result out
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
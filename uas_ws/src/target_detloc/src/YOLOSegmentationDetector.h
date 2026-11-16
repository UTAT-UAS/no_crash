#pragma once

#include <NvInfer.h>
#include <memory>
#include <opencv2/opencv.hpp>
#include <string>
#include <vector>

// --- TensorRT Logger ---
class DetectorLogger : public nvinfer1::ILogger {
public:
  void log(Severity severity, const char* msg) noexcept override;
};

// --- Detector Class ---
class YOLOSegmentationDetector {
private:
  DetectorLogger gLogger;
  std::unique_ptr<nvinfer1::IRuntime> runtime_;
  std::unique_ptr<nvinfer1::ICudaEngine> engine_;
  std::unique_ptr<nvinfer1::IExecutionContext> context_;

  // Device and host memory buffers
  void* d_input_{nullptr};
  void* d_output0_{nullptr};
  void* d_output1_{nullptr};
  float* h_output0_{nullptr};
  float* h_output1_{nullptr};

  const int netWidth_ = 640;
  const int netHeight_ = 640;
  const int numAnchors_ = 8400;

  void loadEngine(const std::string& enginePath);
  void allocateBuffers();
  std::vector<float> preprocess(const cv::Mat& img) const;

public:
  // Constructor initializes the TensorRT engine and allocates memory buffers
  explicit YOLOSegmentationDetector(const std::string& enginePath);

  // Destructor frees CUDA and host memory
  ~YOLOSegmentationDetector();

  // Prevent copying
  YOLOSegmentationDetector(const YOLOSegmentationDetector&) = delete;
  YOLOSegmentationDetector& operator=(const YOLOSegmentationDetector&) = delete;

  // Run inference and return segmented objects
  std::vector<Segmentation> detect(const cv::Mat& image,
                                   float confThreshold = 0.25f,
                                   float nmsThreshold = 0.45f);
};
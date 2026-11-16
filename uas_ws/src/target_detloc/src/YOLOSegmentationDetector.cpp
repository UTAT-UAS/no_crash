#include "YOLOSegmentationDetector.h"
#include "utils.h"
#include <cuda_runtime_api.h>
#include <fstream>
#include <stdexcept>

void DetectorLogger::log(Severity severity, const char* msg) noexcept {
  if (severity <= Severity::kWARNING) {
    std::cout << "[TRT] " << msg << std::endl;
  }
}

YOLOSegmentationDetector::YOLOSegmentationDetector(const std::string& enginePath) {
  loadEngine(enginePath);
  allocateBuffers();
}

YOLOSegmentationDetector::~YOLOSegmentationDetector() {
  if (d_input_)
    cudaFree(d_input_);
  if (d_output0_)
    cudaFree(d_output0_);
  if (d_output1_)
    cudaFree(d_output1_);
  delete[] h_output0_;
  delete[] h_output1_;
}

void YOLOSegmentationDetector::loadEngine(const std::string& enginePath) {
  std::ifstream file(enginePath, std::ios::binary);
  if (!file.good()) {
    throw std::runtime_error("Failed to open engine file: " + enginePath);
  }
  file.seekg(0, file.end);
  size_t size = file.tellg();
  file.seekg(0, file.beg);
  std::vector<char> engineData(size);
  file.read(engineData.data(), size);
  file.close();

  runtime_.reset(nvinfer1::createInferRuntime(gLogger));
  engine_.reset(runtime_->deserializeCudaEngine(engineData.data(), size));
  context_.reset(engine_->createExecutionContext());
}

void YOLOSegmentationDetector::allocateBuffers() {
  size_t inputSize = 1 * 3 * netWidth_ * netHeight_ * sizeof(float);
  size_t output0Size = 1 * 116 * numAnchors_ * sizeof(float);
  size_t output1Size = 1 * 32 * 160 * 160 * sizeof(float);

  cudaMalloc(&d_input_, inputSize);
  cudaMalloc(&d_output0_, output0Size);
  cudaMalloc(&d_output1_, output1Size);

  h_output0_ = new float[116 * numAnchors_];
  h_output1_ = new float[32 * 160 * 160];
}

std::vector<float> YOLOSegmentationDetector::preprocess(const cv::Mat& img) const {
  cv::Mat resized;
  cv::resize(img, resized, cv::Size(netWidth_, netHeight_));
  cv::cvtColor(resized, resized, cv::COLOR_BGR2RGB);
  resized.convertTo(resized, CV_32F, 1.0 / 255.0);

  std::vector<float> chw(3 * netWidth_ * netHeight_);
  std::vector<cv::Mat> channels
    = {cv::Mat(netHeight_, netWidth_, CV_32F, chw.data() + netWidth_ * netHeight_ * 0),
       cv::Mat(netHeight_, netWidth_, CV_32F, chw.data() + netWidth_ * netHeight_ * 1),
       cv::Mat(netHeight_, netWidth_, CV_32F, chw.data() + netWidth_ * netHeight_ * 2)};
  cv::split(resized, channels);
  return chw;
}

std::vector<Segmentation> YOLOSegmentationDetector::detect(const cv::Mat& image,
                                                           float confThreshold,
                                                           float nmsThreshold) {
  if (image.empty()) {
    return {};
  }

  int origWidth = image.cols;
  int origHeight = image.rows;

  // 1. Preprocess and copy to device
  std::vector<float> inputData = preprocess(image);
  cudaMemcpy(d_input_, inputData.data(), inputData.size() * sizeof(float), cudaMemcpyHostToDevice);

  // 2. Setup bindings and run inference
  void* bindings[] = {d_input_, d_output0_, d_output1_};
  context_->executeV2(bindings);

  // 3. Copy outputs back to host
  cudaMemcpy(h_output0_, d_output0_, 1 * 116 * numAnchors_ * sizeof(float), cudaMemcpyDeviceToHost);
  cudaMemcpy(h_output1_, d_output1_, 1 * 32 * 160 * 160 * sizeof(float), cudaMemcpyDeviceToHost);

  // 4. Parse output0
  std::vector<cv::Rect> cv_boxes;
  std::vector<float> confidences;
  std::vector<int> classIds;
  std::vector<std::vector<float>> maskCoeffsList;

  float x_factor = static_cast<float>(origWidth) / static_cast<float>(netWidth_);
  float y_factor = static_cast<float>(origHeight) / static_cast<float>(netHeight_);

  for (int i = 0; i < numAnchors_; ++i) {
    float cx = h_output0_[0 * numAnchors_ + i];
    float cy = h_output0_[1 * numAnchors_ + i];
    float w = h_output0_[2 * numAnchors_ + i];
    float h = h_output0_[3 * numAnchors_ + i];

    float maxClassScore = 0.0f;
    int bestClassId = -1;
    for (int c = 0; c < 80; ++c) {
      float score = h_output0_[(4 + c) * numAnchors_ + i];
      if (score > maxClassScore) {
        maxClassScore = score;
        bestClassId = c;
      }
    }

    if (maxClassScore > confThreshold) {
      float x1 = cx - w / 2.0f;
      float y1 = cy - h / 2.0f;

      int x = static_cast<int>(x1 * x_factor);
      int y = static_cast<int>(y1 * y_factor);
      int width = static_cast<int>(w * x_factor);
      int height = static_cast<int>(h * y_factor);

      cv_boxes.push_back(cv::Rect(x, y, width, height));
      confidences.push_back(maxClassScore);
      classIds.push_back(bestClassId);

      std::vector<float> coeffs(32);
      for (int k = 0; k < 32; ++k) {
        coeffs[k] = h_output0_[(84 + k) * numAnchors_ + i];
      }
      maskCoeffsList.push_back(coeffs);
    }
  }

  // 5. Run NMS
  std::vector<int> indices;
  cv::dnn::NMSBoxes(cv_boxes, confidences, confThreshold, nmsThreshold, indices);

  // 6. Generate final masks
  cv::Mat protos(32, 160 * 160, CV_32F, h_output1_);
  std::vector<Segmentation> results;

  for (int idx : indices) {
    Segmentation seg;
    seg.box.x = cv_boxes[idx].x;
    seg.box.y = cv_boxes[idx].y;
    seg.box.width = cv_boxes[idx].width;
    seg.box.height = cv_boxes[idx].height;
    seg.conf = confidences[idx];
    seg.classId = classIds[idx];

    cv::Mat coeffMat(1, 32, CV_32F, maskCoeffsList[idx].data());
    cv::Mat rawMask = coeffMat * protos;
    rawMask = rawMask.reshape(1, 160);

    // Sigmoid activation
    cv::exp(-rawMask, rawMask);
    rawMask = 1.0f / (1.0f + rawMask);

    // Resize mask back to original image dimensions
    cv::Mat resizedMask;
    cv::resize(rawMask, resizedMask, cv::Size(origWidth, origHeight), 0, 0, cv::INTER_LINEAR);

    // Binarize mask
    cv::Mat binaryMask;
    cv::threshold(resizedMask, binaryMask, 0.5f, 255.0f, cv::THRESH_BINARY);
    binaryMask.convertTo(seg.mask, CV_8UC1);

    results.push_back(seg);
  }

  return results;
}
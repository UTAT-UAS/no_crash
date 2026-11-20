#pragma once

#include "types.h"

cv::Scalar getColor(int classId);
cv::Mat visualizeSegments(const cv::Mat& inputImage,
                          const std::vector<Segmentation>& segments,
                          const std::vector<std::string>& classNames = {},
                          float maskAlpha = 0.4f);
cv::Mat depth_to_rgb8_viz(const cv::Mat& depth_16u, double min_mm = 200.0, double max_mm = 5000.0);
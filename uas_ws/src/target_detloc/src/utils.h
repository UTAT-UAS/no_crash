#pragma once

#include "types.h"

cv::Scalar getColor(int classId);
cv::Mat visualizeSegments(const cv::Mat& inputImage,
                          const std::vector<Segmentation>& segments,
                          const std::vector<std::string>& classNames = {},
                          float maskAlpha = 0.4f);
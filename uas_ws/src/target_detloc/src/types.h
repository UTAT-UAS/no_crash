#pragma once

#include "opencv2/opencv.hpp"

struct BoundingBox {
  int x{0};
  int y{0};
  int width{0};
  int height{0};
};

struct Segmentation {
  BoundingBox box;
  float conf{0.0f};
  int classId{0};
  cv::Mat mask;
};

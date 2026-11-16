#include "utils.h"

cv::Scalar getColor(int classId) {
  int r = (classId * 50 + 100) % 255;
  int g = (classId * 110 + 50) % 255;
  int b = (classId * 170 + 200) % 255;
  return cv::Scalar(b, g, r); // BGR
}

/**
 * Visualizes segmentation results on the input image frame.
 * 
 * @param inputImage The original frame/image (cv::Mat)
 * @param segments Vector of Segmentation structs returned by the inference function
 * @param classNames Optional list of class name strings (e.g., COCO classes)
 * @param maskAlpha Transparency factor for the mask overlay (0.0 to 1.0)
 * @return cv::Mat The annotated output image
 */
cv::Mat visualizeSegments(const cv::Mat& inputImage,
                          const std::vector<Segmentation>& segments,
                          const std::vector<std::string>& classNames = {},
                          float maskAlpha = 0.4f) {
  cv::Mat outputImage = inputImage.clone();
  cv::Mat maskOverlay = inputImage.clone();

  // 1. Apply translucent color overlays for all binary masks
  for (const auto& seg : segments) {
    if (seg.mask.empty())
      continue;

    cv::Scalar color = getColor(seg.classId);

    // Ensure the mask matches the input image dimensions
    cv::Mat resizedMask;
    if (seg.mask.size() != inputImage.size()) {
      cv::resize(seg.mask, resizedMask, inputImage.size(), 0, 0, cv::INTER_NEAREST);
    } else {
      resizedMask = seg.mask;
    }

    // Apply color only where the binary mask is active (> 0)
    cv::Mat coloredMask(inputImage.size(), CV_8UC3, color);
    coloredMask.copyTo(maskOverlay, resizedMask);
  }

  // Blend the colorized mask layer with the original image
  cv::addWeighted(maskOverlay, maskAlpha, outputImage, 1.0f - maskAlpha, 0, outputImage);

  // 2. Draw Bounding Boxes, Labels, and Confidence Scores
  for (const auto& seg : segments) {
    cv::Scalar color = getColor(seg.classId);

    // Map custom BoundingBox fields to cv::Rect
    cv::Rect box(seg.box.x, seg.box.y, seg.box.width, seg.box.height);

    // Clip box to image boundaries to prevent out-of-bounds drawing
    box &= cv::Rect(0, 0, outputImage.cols, outputImage.rows);
    if (box.area() <= 0)
      continue;

    // Draw the bounding box rectangle
    cv::rectangle(outputImage, box, color, 2);

    // Format label text (e.g., "person: 0.94")
    std::string className = "Class " + std::to_string(seg.classId);
    if (!classNames.empty() && seg.classId >= 0 && seg.classId < classNames.size()) {
      className = classNames[seg.classId];
    }

    char buf[64];
    std::snprintf(buf, sizeof(buf), "%s: %.2f", className.c_str(), seg.conf);
    std::string labelText(buf);

    // Calculate text size to create a clean background tag
    int baseline = 0;
    double fontScale = 0.5;
    int thickness = 1;
    cv::Size textSize = cv::getTextSize(labelText,
                                        cv::FONT_HERSHEY_SIMPLEX,
                                        fontScale,
                                        thickness,
                                        &baseline);

    int textX = box.x;
    int textY = std::max(box.y - 7, textSize.height + 5);

    // Background rectangle for text legibility
    cv::Rect textBg(textX,
                    textY - textSize.height - 4,
                    textSize.width + 6,
                    textSize.height + baseline + 4);
    textBg &= cv::Rect(0, 0, outputImage.cols, outputImage.rows);

    cv::rectangle(outputImage, textBg, color, cv::FILLED);

    // Put label text in white over the colored tag background
    cv::putText(outputImage,
                labelText,
                cv::Point(textX + 3, textY - 2),
                cv::FONT_HERSHEY_SIMPLEX,
                fontScale,
                cv::Scalar(255, 255, 255),
                thickness,
                cv::LINE_AA);
  }

  return outputImage;
}
#pragma once

#include <cstdint>
#include <functional>
#include <string>


typedef struct _GstElement GstElement;


class VideoStreamer
{
public:
  enum class LogLevel { Info, Warn, Error };
  using Logger = std::function<void(LogLevel, const std::string &)>;

  VideoStreamer(std::string pipeline_tail, int fps, Logger logger);
  ~VideoStreamer();


  VideoStreamer(const VideoStreamer &) = delete;
  VideoStreamer & operator=(const VideoStreamer &) = delete;

  bool push_frame(
    const uint8_t * data, int width, int height, int step, const std::string & format);


  void poll();

  bool is_running() const {return pipeline_ != nullptr;}

  static int bytes_per_pixel(const std::string & format);

private:
  bool start(int width, int height, const std::string & format);
  void stop();

  std::string pipeline_tail_;
  int fps_;
  Logger log_;

  GstElement * pipeline_ = nullptr;
  GstElement * appsrc_ = nullptr;
  int width_ = 0;
  int height_ = 0;
  std::string format_;
};
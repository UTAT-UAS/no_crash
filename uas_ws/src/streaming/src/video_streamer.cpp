#include "streaming/video_streamer.hpp"

#include <gst/app/gstappsrc.h>
#include <gst/gst.h>

#include <cstring>
#include <utility>

VideoStreamer::VideoStreamer(std::string pipeline_tail, int fps, Logger logger)
: pipeline_tail_(std::move(pipeline_tail)), fps_(fps), log_(std::move(logger))
{
  gst_init(nullptr, nullptr); 
}

VideoStreamer::~VideoStreamer()
{
  stop();
}

int VideoStreamer::bytes_per_pixel(const std::string & format)
{
  if (format == "RGB" || format == "BGR") {return 3;}
  if (format == "RGBA" || format == "BGRA") {return 4;}
  if (format == "GRAY8") {return 1;}
  return 0;
}

bool VideoStreamer::start(int width, int height, const std::string & format)
{
  
  const std::string desc =
    "appsrc name=src is-live=true do-timestamp=true format=time "
    "caps=video/x-raw,format=" + format +
    ",width=" + std::to_string(width) +
    ",height=" + std::to_string(height) +
    ",framerate=" + std::to_string(fps_) + "/1 "
    "! videoconvert ! queue leaky=downstream max-size-buffers=2 ! " + pipeline_tail_;

  GError * error = nullptr;
  pipeline_ = gst_parse_launch(desc.c_str(), &error);
  if (error != nullptr) {
    log_(LogLevel::Error, std::string("Pipeline error: ") + error->message);
    g_error_free(error);
    stop();
    return false;
  }

  appsrc_ = gst_bin_get_by_name(GST_BIN(pipeline_), "src");
  if (appsrc_ == nullptr) {
    log_(LogLevel::Error, "appsrc not found in pipeline");
    stop();
    return false;
  }

  if (gst_element_set_state(pipeline_, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE) {
    log_(LogLevel::Error, "Could not set pipeline to PLAYING");
    stop();
    return false;
  }

  width_ = width;
  height_ = height;
  format_ = format;
  log_(LogLevel::Info, "Pipeline started: " + desc);
  return true;
}

void VideoStreamer::stop()
{
  if (pipeline_ != nullptr) {
    gst_element_set_state(pipeline_, GST_STATE_NULL);
  }
  if (appsrc_ != nullptr) {
    gst_object_unref(appsrc_);
    appsrc_ = nullptr;
  }
  if (pipeline_ != nullptr) {
    gst_object_unref(pipeline_);
    pipeline_ = nullptr;
  }
  width_ = 0;
  height_ = 0;
  format_.clear();
}

bool VideoStreamer::push_frame(
  const uint8_t * data, int width, int height, int step, const std::string & format)
{
  const int bpp = bytes_per_pixel(format);
  if (data == nullptr || bpp == 0 || width <= 0 || height <= 0) {
    return false;
  }
  const size_t row_bytes = static_cast<size_t>(width) * bpp;
  if (static_cast<size_t>(step) < row_bytes) {
    return false;
  }

  if (pipeline_ == nullptr || width != width_ || height != height_ || format != format_) {
    if (pipeline_ != nullptr) {
      log_(LogLevel::Warn, "Frame size/format changed, restarting pipeline");
      stop();
    }
    if (!start(width, height, format)) {
      return false;
    }
  }

  const size_t size = row_bytes * height;
  GstBuffer * buffer = gst_buffer_new_allocate(nullptr, size, nullptr);
  GstMapInfo map;
  if (!gst_buffer_map(buffer, &map, GST_MAP_WRITE)) {
    gst_buffer_unref(buffer);
    return false;
  }
  for (int y = 0; y < height; ++y) {
    std::memcpy(
      map.data + static_cast<size_t>(y) * row_bytes,
      data + static_cast<size_t>(y) * step,
      row_bytes);
  }
  gst_buffer_unmap(buffer, &map);

  // appsrc takes ownership of the buffer.
  return gst_app_src_push_buffer(GST_APP_SRC(appsrc_), buffer) == GST_FLOW_OK;
}

void VideoStreamer::poll()
{
  if (pipeline_ == nullptr) {
    return;
  }
  GstBus * bus = gst_element_get_bus(pipeline_);
  GstMessage * msg = nullptr;
  const auto types = static_cast<GstMessageType>(
    GST_MESSAGE_ERROR | GST_MESSAGE_WARNING | GST_MESSAGE_EOS);


  while ((msg = gst_bus_pop_filtered(bus, types)) != nullptr) {
    GError * err = nullptr;
    gchar * dbg = nullptr;
    const std::string src = GST_OBJECT_NAME(msg->src);
    switch (GST_MESSAGE_TYPE(msg)) {
      case GST_MESSAGE_ERROR:
        gst_message_parse_error(msg, &err, &dbg);
        log_(
          LogLevel::Error, "GStreamer error from " + src + ": " + err->message +
          (dbg ? std::string(" (") + dbg + ")" : ""));
        break;
      case GST_MESSAGE_WARNING:
        gst_message_parse_warning(msg, &err, &dbg);
        log_(LogLevel::Warn, "GStreamer warning from " + src + ": " + err->message);
        break;
      case GST_MESSAGE_EOS:
        log_(LogLevel::Warn, "GStreamer end of stream");
        break;
      default:
        break;
    }
    if (err != nullptr) {g_error_free(err);}
    g_free(dbg);
    gst_message_unref(msg);
  }
  gst_object_unref(bus);
}
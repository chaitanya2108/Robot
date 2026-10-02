// camera_bridge: reads the RGB stream of the Deptrum Aurora 930 depth camera
// through the vendor SDK and writes JPEG frames to stdout.
//
// Output framing (stdout): [uint32 big-endian length][JPEG bytes] repeated.
// Logs go to stderr. Exits non-zero on fatal errors so the Python server can
// restart it.
//
// Usage: camera_bridge [--mode 0|1|2] [--quality 1-100] [--fps N] [--width W] [--list]
//   mode 0 = 320x200, 1 = 480x300, 2 = 640x400 (native RGB resolutions)
//   width  = optional downscale width (keeps aspect ratio), 0 = native

#include <arpa/inet.h>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <memory>
#include <string>
#include <tuple>
#include <vector>
#include <chrono>
#include <thread>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include "deptrum/aurora900_series.h"
#include "deptrum/device.h"
#include "deptrum/stream.h"

using namespace deptrum;
using namespace deptrum::stream;

static volatile std::sig_atomic_t g_running = 1;
static void OnSignal(int) { g_running = 0; }

static bool WriteAll(const void* buf, size_t len) {
  const char* p = static_cast<const char*>(buf);
  while (len > 0) {
    size_t n = fwrite(p, 1, len, stdout);
    if (n == 0) return false;
    p += n;
    len -= n;
  }
  return true;
}

int main(int argc, char** argv) {
  int mode_index = 2, quality = 70, max_fps = 15, out_width = 0;
  bool list_only = false;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto next = [&](int& v) { if (i + 1 < argc) v = std::atoi(argv[++i]); };
    if (a == "--mode") next(mode_index);
    else if (a == "--quality") next(quality);
    else if (a == "--fps") next(max_fps);
    else if (a == "--width") next(out_width);
    else if (a == "--list") list_only = true;
  }
  std::signal(SIGINT, OnSignal);
  std::signal(SIGTERM, OnSignal);
  std::signal(SIGPIPE, OnSignal);

  DeviceManager::GetInstance()->RegisterDeviceConnectedCallback();
  std::vector<DeviceInformation> devices;
  int ret = DeviceManager::GetInstance()->GetDeviceList(devices);
  if (ret != 0 || devices.empty()) {
    std::cerr << "[camera_bridge] no camera found (ret=" << ret << ")" << std::endl;
    return 2;
  }
  std::shared_ptr<Device> device = DeviceManager::GetInstance()->CreateDevice(devices[0]);
  if (!device) { std::cerr << "[camera_bridge] CreateDevice failed" << std::endl; return 2; }
  ret = device->Open();
  if (ret != 0) { std::cerr << "[camera_bridge] Open failed ret=" << ret << std::endl; return 2; }
  std::cerr << "[camera_bridge] device " << device->GetDeviceName() << " sdk " << device->GetSdkVersion() << std::endl;

  std::vector<std::tuple<FrameMode, FrameMode, FrameMode>> modes;
  device->GetSupportedFrameMode(modes);
  if (list_only || mode_index < 0 || mode_index >= (int)modes.size()) {
    for (size_t i = 0; i < modes.size(); ++i)
      std::cerr << "mode " << i << ": ir=" << std::get<0>(modes[i]) << " rgb=" << std::get<1>(modes[i])
                << " depth=" << std::get<2>(modes[i]) << std::endl;
    device->Close();
    return list_only ? 0 : 3;
  }
  ret = device->SetMode(std::get<0>(modes[mode_index]), std::get<1>(modes[mode_index]), std::get<2>(modes[mode_index]));
  if (ret != 0) { std::cerr << "[camera_bridge] SetMode failed ret=" << ret << std::endl; return 2; }

  auto aurora = std::dynamic_pointer_cast<Aurora900>(device);
  if (aurora) {
    aurora->SetIrFps(15);
    HeartbeatParam hb;
    hb.allowable_failures_counts = 8;
    hb.timeout = 500;
    hb.is_enabled = true;
    aurora->SetHeartbeat(hb, [](int flag) {
      if (flag != 1) std::cerr << "[camera_bridge] heartbeat " << flag << std::endl;
    });
  }

  Stream* stream = nullptr;
  ret = device->CreateStream(stream, {StreamType::kRgb});
  if (ret != 0 || !stream) { std::cerr << "[camera_bridge] CreateStream failed ret=" << ret << std::endl; return 2; }
  ret = stream->Start();
  if (ret != 0) { std::cerr << "[camera_bridge] Start failed ret=" << ret << std::endl; return 2; }

  std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, quality};
  std::vector<uchar> jpeg;
  const auto min_interval = std::chrono::milliseconds(max_fps > 0 ? 1000 / max_fps : 0);
  auto last_sent = std::chrono::steady_clock::now() - min_interval;
  int consecutive_errors = 0;
  long sent = 0;

  while (g_running) {
    StreamFrames frames;
    ret = stream->GetFrames(frames, 2000);
    if (ret != 0) {
      if (++consecutive_errors > 10) { std::cerr << "[camera_bridge] too many GetFrames errors" << std::endl; break; }
      continue;
    }
    consecutive_errors = 0;
    for (auto& f : frames.frame_ptr) {
      if (!f || f->frame_type != FrameType::kRgbFrame) continue;
      auto now = std::chrono::steady_clock::now();
      if (now - last_sent < min_interval) continue;
      cv::Mat bgr;
      int expected_nv12 = f->rows * f->cols * 3 / 2;
      if (f->size >= expected_nv12 && f->size < f->rows * f->cols * 3) {
        cv::Mat nv12(f->rows * 3 / 2, f->cols, CV_8UC1, f->data.get());
        cv::cvtColor(nv12, bgr, cv::COLOR_YUV2BGR_NV12);
      } else {
        bgr = cv::Mat(f->rows, f->cols, CV_8UC3, f->data.get()).clone();
      }
      if (out_width > 0 && out_width != bgr.cols) {
        cv::resize(bgr, bgr, cv::Size(out_width, bgr.rows * out_width / bgr.cols), 0, 0, cv::INTER_AREA);
      }
      cv::imencode(".jpg", bgr, jpeg, params);
      uint32_t len = htonl(static_cast<uint32_t>(jpeg.size()));
      if (!WriteAll(&len, 4) || !WriteAll(jpeg.data(), jpeg.size())) { g_running = 0; break; }
      fflush(stdout);
      last_sent = now;
      if (++sent == 1) std::cerr << "[camera_bridge] streaming " << bgr.cols << "x" << bgr.rows << std::endl;
    }
  }

  stream->Stop();
  device->DestroyStream(stream);
  if (aurora) aurora->StopHeartbeat();
  device->Close();
  std::cerr << "[camera_bridge] stopped after " << sent << " frames" << std::endl;
  return 0;
}

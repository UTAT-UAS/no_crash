# Dependency Installation

figure it out yourself!! :)
[Orbbec ROS2 Wrapper](https://orbbec.github.io/OrbbecSDK_ROS2/en/index.html)

compose.yaml
```
{
  "services": {
    "uas": {
      "image": "ghcr.io/utat-uas/no_crash:2026-10-28-cpu",
      "pull_policy": "missing",
      "privileged": true,
      "volumes": [
        "/dev:/dev"
      ]
    }
  }
}
```


# Target Detection and Localization


## Simulation

Start the PX4 simulation:

```bash
PX4_SIM_MODEL=gz_x500_depth ./scripts/sim sitl start
```

Start the topic bridge in a separate terminal:

```bash
bash topic_bridge.sh
```

## Physical Camera

Launch the Orbbec camera:

```bash
ros2 launch orbbec_camera gemini_330_series.launch.py
```

## Adapter

Start the frame multiplexer:

```bash
ros2 run target_detloc frame_mux
```

## Detector

CMakeLists.txt is for two platforms: ONNX runtime (for CPU machines) and TensorRT (for Jetson).
```
colcon build --base-paths uas_ws/src --symlink-install --cmake-args -DBACKEND=TRT
colcon build --base-paths uas_ws/src --symlink-install --cmake-args -DBACKEND=ONNX
```

Start the detector:

```bash
ros2 run target_detloc detect
```
## Visualizer

Start the visualizer:


```bash
python visualization.py
```

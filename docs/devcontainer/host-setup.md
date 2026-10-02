# Host graphics, GPUs, and equipment

The host initializer detects Linux versus WSL2, reads the selected machine
profile, and writes an ignored Compose override. It only configures containers;
it does not install host drivers or change X11 access controls.

## Linux GUI

Run VS Code from a session with `DISPLAY` set. The initializer binds the X11
socket and, when present, the file indicated by `XAUTHORITY` (or `~/.Xauthority`).
It exposes `/dev/dri` and its device groups for graphics when available.
Wayland desktops can use their XWayland display.

If your desktop requires an explicit X11 grant, use a scoped grant for the
container user and revoke it when finished; the scripts do not run `xhost +`.
Verify GUI access with `xeyes` before diagnosing QGC or Gazebo.

## NVIDIA

Install a supported NVIDIA driver and
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
on the Docker host. CUDA 13.2 requires a CUDA-13-capable GPU and driver; CUDA 12.6
retains support for additional older architectures. Use the
[NVIDIA driver compatibility documentation](https://docs.nvidia.com/deploy/cuda-compatibility/)
and [PyTorch's release matrix](https://pytorch.org/blog/pytorch-2-14-release-blog/)
to match your card. The toolkit on a native Linux host and the Windows driver
in WSL supply host access; the image supplies the selected PyTorch runtime.

The initializer selects CDI if a JSON or YAML spec with kind `nvidia.com/gpu`
exists under `/etc/cdi` or `/var/run/cdi`; otherwise it
requests GPUs through the NVIDIA runtime. To select explicitly, create ignored
`.devcontainer/runtime-options.json`:

```json
{"nvidia_mode": "cdi"}
```

Valid modes are `auto`, `cdi`, and `runtime`. On NixOS, enable your distribution's
NVIDIA container tooling and generate its CDI specification. For WSL2, follow
[NVIDIA's WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html);
do not install a Linux display driver into WSL.

## AMD on Linux

Use the `amd` profile. The host must provide `/dev/kfd` and `/dev/dri` with a
supported kernel/driver combination from
[AMD's ROCm 7.14.1 compatibility matrix](https://rocm.docs.amd.com/en/docs-7.14.1/compatibility/compatibility-matrix.html).
The initializer passes those devices and their numeric groups to the non-root
user. It does not enable privileged mode. The userspace ROCm libraries are
dependencies of the image's PyTorch wheel.

Run `no-crash-check --gpu` after entering the container. If your GPU is outside
the supported matrix, use the CPU profile until you have a separately validated
configuration.

## WSLg and AMD on WSL2

Use a current WSL2 installation with WSLg, and run VS Code through Remote - WSL.
The initializer passes the WSLg socket directory, display/audio environment,
`/dev/dxg`, and the WSL graphics libraries into the container when available.

For AMD compute select `amd-wsl`. Install the supported Windows AMD driver for
your card and use a Docker Engine in that WSL distribution. The initializer
requires `/dev/dxg` and `/usr/lib/wsl/lib/libdxcore.so`. The image includes
ROCDXG 1.2.2 in userspace and a compatibility link for its device configuration;
the Microsoft DXCore library is mounted read-only from the host. ROCDXG's
compatibility matrix and container requirements are documented in
[the pinned AMD release](https://github.com/ROCm/librocdxg/tree/v1.2.2).

This uses the ROCDXG integration for ROCm 7.14 rather than the legacy WSL runtime
replacement instructions. Confirm actual GPU compute with `no-crash-check --gpu`
and GUI acceleration separately with Gazebo. Hardware coverage is limited to
AMD's supported GPUs and drivers.

## Flight controllers, cameras, and joysticks

Devices are opt-in. Create ignored `.devcontainer/runtime-options.json`:

```json
{
  "hardware_devices": ["/dev/ttyACM0", "/dev/video0", "/dev/input"]
}
```

List only the paths needed on your machine; missing paths produce a clear
initialization error. A `/dev/input` directory passes its current device nodes
to Docker, including more than one controller; use a specific node where
possible. Hardware group access is added to the container. Hotplug may require
recreating the container because Docker device mappings are established at
creation. For Windows USB equipment, attach the device to WSL first using
[Microsoft's USB connection instructions](https://learn.microsoft.com/en-us/windows/wsl/connect-usb).

Set `SDL_GAMECONTROLLERCONFIG` in your custom installer's shell configuration
if QGC needs a custom joystick mapping. The `qgc` wrapper preserves that variable.

## Networking and headless use

Simulation, QGC, and the DDS Agent run in the same container by default.

For external ROS discovery or a native host QGC on Linux, add
`"host_network": true` to `runtime-options.json`. Recreate the container and
check the host firewall and ROS domain settings. This override is restricted
to native Linux.

For headless use, start VS Code or `enter.sh` without `DISPLAY`. The CPU profile
needs no GPU or display device. To preview the generated settings without
writing files:

```bash
python3 .devcontainer/scripts/prepare-host.py --profile cpu --headless --dry-run
```

The host setup files are regenerated during container initialization. After
editing ignored options or changing display/driver settings, recreate the
container to apply them.

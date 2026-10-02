#!/usr/bin/env bash
set -euo pipefail
source /usr/local/lib/no-crash/helpers.sh
export DEBIAN_FRONTEND=noninteractive

# Keep copyright files while excluding apt-installed manuals and documentation.
printf 'path-exclude=/usr/share/doc/*\npath-include=/usr/share/doc/*/copyright\npath-exclude=/usr/share/man/*\npath-exclude=/usr/share/info/*\n' > /etc/dpkg/dpkg.cfg.d/no-crash-no-docs

# Noble images may already contain the ubuntu user at UID 1000.
uid=$1
gid=$2
existing_user=$(getent passwd "$uid" | cut -d: -f1 || true)
if ! getent group "$gid" >/dev/null; then groupadd --gid "$gid" uas; fi
if [[ -n $existing_user ]]; then
    usermod --login uas --home /home/uas --move-home --shell /bin/bash "$existing_user"
else
    useradd --uid "$uid" --gid "$gid" --create-home --shell /bin/bash uas
fi
existing_group=$(getent group "$gid" | cut -d: -f1)
if [[ $existing_group != uas ]]; then groupmod --new-name uas "$existing_group"; fi
usermod --gid "$gid" --append --groups dialout,video uas

apt-get update
apt-get upgrade -y --no-install-recommends
apt-get install -y --no-install-recommends ca-certificates curl sudo
printf 'uas ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/uas
chmod 0440 /etc/sudoers.d/uas
download "$GAZEBO_KEY_URL" "$GAZEBO_KEY_SHA256" /usr/share/keyrings/no-crash-gazebo.gpg
printf 'deb [arch=amd64 signed-by=/usr/share/keyrings/no-crash-gazebo.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable noble main\n' > /etc/apt/sources.list.d/no-crash-gazebo.list

apt-get update
# Include the firmware and simulation dependencies previously installed by
# PX4's ubuntu.sh. Manage them here so setup never modifies system Python.
apt-get install -y --no-install-recommends \
    astyle automake bash-completion bc binutils-dev bison bmon build-essential bzip2 \
    ccache clang clang-format clang-tidy cmake cppcheck cppzmq-dev \
    dmidecode dos2unix file flex g++-multilib gcc-arm-none-eabi gcc-multilib \
    gdb gdb-multiarch genromfs geographiclib-tools gettext gfortran git gnupg \
    gperf gstreamer1.0-gl gstreamer1.0-libav \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-ugly gstreamer1.0-tools gz-harmonic htop iotop \
    iputils-ping jq kconfig-frontends lcov less \
    libasio-dev libatlas-base-dev libavcodec-dev libavfilter-dev libavformat-dev \
    libavutil-dev libdrm-dev libegl1-mesa-dev libeigen3-dev libelf-dev \
    libexpat1-dev libffi-dev \
    libgl1-mesa-dri libglx-mesa0 libgmp-dev libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev libgtk-3-dev libjpeg-dev \
    libimage-exiftool-perl libisl-dev libmpc-dev libmpfr-dev libncurses-dev \
    libnewlib-arm-none-eabi libnice-dev libogg-dev libopencv-dev libopus-dev liborc-0.4-dev \
    libpng-dev libsndfile1-dev libsoup-3.0-dev libspdlog-dev libspeechd2 \
    libsrtp2-dev libssl-dev libstdc++-arm-none-eabi-newlib libswscale-dev \
    libtheora-dev libtiff-dev libtool libunwind-dev libv4l-dev libvorbis-dev \
    libvpx-dev libx264-dev libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 \
    libxml2-dev libxml2-utils libxvidcore-dev mesa-utils mesa-vulkan-drivers \
    lld lldb nano net-tools ninja-build openssh-client patchelf pipewire pkg-config \
    protobuf-compiler \
    python-is-python3 python3-colcon-clean python3-dev python3-empy \
    python3-matplotlib python3-numpy python3-pandas python3-pillow python3-pip \
    python3-scipy python3-seaborn python3-setuptools python3-vcstool python3-venv \
    python3-wheel ros-dev-tools ros-jazzy-cv-bridge ros-jazzy-fastcdr \
    ros-jazzy-fastrtps ros-jazzy-mavros ros-jazzy-mavros-extras \
    ros-jazzy-mavros-msgs ros-jazzy-rosbridge-server ros-jazzy-ros-gz \
    rsync screen shellcheck texinfo tmux tmuxinator tree u-boot-tools unzip \
    usbutils util-linux vim vim-common wget x11-apps \
    xz-utils zip

# GeographicLib is a system dataset used by the apt-managed MAVROS package.
download "$GEOGRAPHICLIB_SCRIPT_URL" "$GEOGRAPHICLIB_SCRIPT_SHA256" /tmp/geographiclib.sh
bash /tmp/geographiclib.sh
test -f /usr/share/GeographicLib/geoids/egm96-5.pgm
rm /tmp/geographiclib.sh
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
install -d -o uas -g uas /home/uas/build /home/uas/.local/bin \
    /home/uas/.local/opt /home/uas/.local/share/no-crash /home/uas/.venvs

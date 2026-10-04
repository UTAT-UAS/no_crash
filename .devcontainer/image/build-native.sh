#!/usr/bin/env bash
set -euo pipefail
source /usr/local/lib/no-crash/helpers.sh
source_ros
source /usr/local/lib/no-crash/environment.sh
cd "$HOME/build"

checkout "$GSTREAMER_URL" "$GSTREAMER_REVISION" gstreamer
meson setup gstreamer/builddir gstreamer \
    --prefix="$GST_PREFIX" --libdir=lib --buildtype=release \
    -Dgpl=enabled -Dtests=disabled -Dexamples=disabled -Ddoc=disabled \
    -Dgtk_doc=disabled -Ddevtools=disabled -Dges=disabled \
    -Dgst-examples=disabled -Dpython=disabled -Dintrospection=disabled \
    -Dtools=enabled -Dwebrtc=enabled -Dlibnice=enabled -Dlibav=enabled \
    -Dqt5=disabled -Dqt6=disabled -Drtsp_server=disabled -Dsharp=disabled \
    -Dgst-full=disabled -Dbenchmarks=disabled
meson compile -C gstreamer/builddir -j "$BUILD_JOBS"
meson install -C gstreamer/builddir

checkout "$GST_PLUGINS_RS_URL" "$GST_PLUGINS_RS_REVISION" gst-plugins-rs
(
    cd gst-plugins-rs
    cargo cinstall --locked --release -p gst-plugin-webrtc \
        --prefix="$GST_PREFIX" --libdir="$GST_PREFIX/lib"
    cargo build --locked --release -p gst-plugin-webrtc-signalling --bin gst-webrtc-signalling-server
    install -m 0755 "$CARGO_TARGET_DIR/release/gst-webrtc-signalling-server" "$GST_PREFIX/bin/"
)

checkout "$OPENCV_URL" "$OPENCV_REVISION" opencv
checkout "$OPENCV_CONTRIB_URL" "$OPENCV_CONTRIB_REVISION" opencv_contrib
wheel_stage="$HOME/build/opencv-wheel"
mkdir -p "$wheel_stage"
cmake -S opencv -B opencv/build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$OPENCV_PREFIX" \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_INSTALL_RPATH="$OPENCV_PREFIX/lib;$GST_PREFIX/lib" \
    -DOPENCV_EXTRA_MODULES_PATH="$HOME/build/opencv_contrib/modules" \
    -DWITH_GSTREAMER=ON -DWITH_FFMPEG=ON -DWITH_V4L=ON -DWITH_GTK=ON \
    -DBUILD_TESTS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_EXAMPLES=OFF \
    -DBUILD_DOCS=OFF -DBUILD_JAVA=OFF -DBUILD_opencv_apps=OFF \
    -DBUILD_opencv_viz=OFF -DBUILD_opencv_python2=OFF \
    -DBUILD_opencv_python3=ON -DPYTHON3_EXECUTABLE=/usr/bin/python3 \
    -DPYTHON3_NUMPY_INCLUDE_DIRS="$(python3 -c 'import numpy; print(numpy.get_include())')" \
    -DPYTHON3_PACKAGES_PATH="$wheel_stage" \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake --build opencv/build --parallel "$BUILD_JOBS"
cmake --install opencv/build
mkdir -p "$HOME/.local/share/no-crash/wheels"
"$HOME/.venvs/build-tools/bin/python" /usr/local/lib/no-crash/package-opencv.py \
    "$wheel_stage" "$HOME/.local/share/no-crash/wheels" "$OPENCV_VERSION"

checkout "$AGENT_URL" "$AGENT_REVISION" Micro-XRCE-DDS-Agent
# Agent 2.x logs endpoint types through operator<<. Noble's fmt 9 requires
# its compatibility flag to retain this behavior with the system spdlog.
# https://github.com/fmtlib/fmt/blob/9.1.0/ChangeLog.md
cmake -S Micro-XRCE-DDS-Agent -B Micro-XRCE-DDS-Agent/build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$XRCE_PREFIX" \
    -DCMAKE_CXX_FLAGS=-DFMT_DEPRECATED_OSTREAM \
    -DCMAKE_INSTALL_LIBDIR=lib -DCMAKE_INSTALL_RPATH="$XRCE_PREFIX/lib;/opt/ros/jazzy/lib" \
    -DUAGENT_SUPERBUILD=OFF -DUAGENT_USE_SYSTEM_FASTDDS=ON \
    -DUAGENT_USE_SYSTEM_FASTCDR=ON -DUAGENT_USE_SYSTEM_LOGGER=ON \
    -DUAGENT_P2P_PROFILE=OFF -DUAGENT_BUILD_TESTS=OFF -DUAGENT_BUILD_USAGE_EXAMPLES=OFF
cmake --build Micro-XRCE-DDS-Agent/build --parallel "$BUILD_JOBS"
cmake --install Micro-XRCE-DDS-Agent/build

# The retained checkout lives in /build, outside home-directory UID remapping.
# Keep sources and generated build files editable after a host UID change.
(
    umask 0000
    checkout "$PX4_URL" "$PX4_REVISION" PX4-Autopilot
    git -C PX4-Autopilot submodule update --init --recursive --depth 1
    python3 -m venv "$HOME/.venvs/px4"
    "$HOME/.venvs/px4/bin/python" -m pip install \
        -r PX4-Autopilot/Tools/setup/requirements.txt 'empy==3.3.4'
    (
        cd PX4-Autopilot
        source "$HOME/.venvs/px4/bin/activate"
        DONT_RUN=1 make -j "$BUILD_JOBS" px4_sitl
    )
    "$HOME/.venvs/px4/bin/python" -m pip freeze > "$HOME/build/PX4-Autopilot/no-crash-python-requirements.txt"
)
# The permissive build umask ends with the subshell above.
make_user_storage_writable

# Sources and headers of PX4 remain editable; other temporary trees are omitted
# by the final-stage COPY instructions rather than hidden in deletion layers.

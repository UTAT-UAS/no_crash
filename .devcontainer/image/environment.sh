#!/usr/bin/env bash
# Safe to source repeatedly; system Python remains the default interpreter.
export GST_PREFIX="$HOME/.local/opt/gstreamer"
export OPENCV_PREFIX="$HOME/.local/opt/opencv"
export XRCE_PREFIX="$HOME/.local/opt/xrce-agent"
export BUN_INSTALL="$HOME/.bun"
export CARGO_TARGET_DIR=/build/cargo-target
export CCACHE_DIR=/build/ccache
export TMPDIR=/build/tmp
export COLCON_DEFAULTS_FILE="$HOME/.colcon/defaults.yaml"

no_crash_prepend() {
    local variable=$1 directory=$2 current
    current=${!variable-}
    case ":$current:" in
        *":$directory:"*) ;;
        *) export "$variable=$directory${current:+:$current}" ;;
    esac
}
for directory in "$HOME/.local/bin" "$BUN_INSTALL/bin" "$HOME/.local/opt/node/bin" "$HOME/.cargo/bin" \
    "$GST_PREFIX/bin" "$XRCE_PREFIX/bin"; do
    no_crash_prepend PATH "$directory"
done
for directory in "$GST_PREFIX/lib" "$XRCE_PREFIX/lib"; do
    no_crash_prepend LD_LIBRARY_PATH "$directory"
done
if [[ -d $HOME/.local/opt/rocdxg/lib ]]; then
    no_crash_prepend LD_LIBRARY_PATH "$HOME/.local/opt/rocdxg/lib"
fi
no_crash_prepend PKG_CONFIG_PATH "$GST_PREFIX/lib/pkgconfig"
no_crash_prepend CMAKE_PREFIX_PATH "$GST_PREFIX"
export GST_PLUGIN_SYSTEM_PATH_1_0="$GST_PREFIX/lib/gstreamer-1.0"
export GST_PLUGIN_PATH_1_0="$GST_PREFIX/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER_1_0="$GST_PREFIX/libexec/gstreamer-1.0/gst-plugin-scanner"
unset -f no_crash_prepend

if [[ $- == *i* ]]; then
    source /opt/ros/jazzy/setup.bash
    if [[ -f $HOME/workspace/install/local_setup.bash ]]; then
        source "$HOME/workspace/install/local_setup.bash"
    fi
    for hook in /usr/share/colcon_cd/function/colcon_cd.sh \
        /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash; do
        # shellcheck disable=SC1090
        if [[ -f $hook ]]; then source "$hook"; fi
    done
    export _colcon_cd_root=/opt/ros/jazzy
fi

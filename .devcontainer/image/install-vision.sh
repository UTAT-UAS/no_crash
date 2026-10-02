#!/usr/bin/env bash
set -euo pipefail
source /usr/local/lib/no-crash/helpers.sh
backend=$1
case "$backend" in cpu|cu126|cu132|rocm7.14) ;; *) exit 2 ;; esac
python3 -m venv --system-site-packages "$HOME/.venvs/vision"
python="$HOME/.venvs/vision/bin/python"
constraints="$HOME/.local/share/no-crash/vision-constraints.txt"
printf 'numpy==1.26.4\nopencv-python==%s+gstreamer\ntorch==%s+%s\ntorchvision==%s+%s\n' \
    "$OPENCV_VERSION" "$TORCH_VERSION" "$backend" "$TORCHVISION_VERSION" "$backend" > "$constraints"
"$python" -m pip install "$HOME"/.local/share/no-crash/wheels/opencv_python-*.whl
"$python" -m pip install -c "$constraints" \
    "torch==$TORCH_VERSION+$backend" "torchvision==$TORCHVISION_VERSION+$backend" \
    --index-url "https://download.pytorch.org/whl/$backend"
"$python" -m pip install -c "$constraints" "ultralytics==$ULTRALYTICS_VERSION"
"$python" -m pip check
"$python" -m pip freeze > "$HOME/.local/share/no-crash/vision-python-requirements.txt"
bash /usr/local/lib/no-crash/bin/no-crash-check --build

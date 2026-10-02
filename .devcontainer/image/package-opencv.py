#!/usr/bin/env python3
"""Package our CMake-installed cv2 as an actual opencv-python distribution.

The wheel uses the image's userspace OpenCV/GStreamer libraries. It is for
projects inside these images, not a portable wheel for arbitrary machines.
"""
import os
from pathlib import Path
import sys

def relocate_extension_config(stage):
    # CMake writes an absolute staging path into config-3.12.py. A wheel moves
    # cv2 into a venv, so its extension lookup must be package-relative.
    package = Path(stage) / 'cv2'
    extension_dirs = sorted({str(p.parent.relative_to(package)) for p in package.rglob('cv2*.so')})
    if not extension_dirs:
        raise SystemExit("OpenCV's cv2 extension is missing")
    extension_paths = ', '.join(f'os.path.join(LOADER_DIR, {directory!r})' for directory in extension_dirs)
    for config in package.glob('config-*.py'):
        config.write_text(f'PYTHON_EXTENSIONS_PATHS = [{extension_paths}] + PYTHON_EXTENSIONS_PATHS\n')


def main():
    from setuptools import Distribution, find_packages, setup

    class NativeDistribution(Distribution):
        def has_ext_modules(self):
            return True

    stage, destination, version = sys.argv[1:]
    os.chdir(stage)
    relocate_extension_config('.')
    setup(
        name="opencv-python",
        version=version + "+gstreamer",
        description="no_crash OpenCV with GStreamer (container-local native libraries)",
        packages=find_packages(),
        package_data={"cv2": [str(p.relative_to("cv2")) for p in Path("cv2").rglob("*") if p.is_file()]},
        install_requires=["numpy>=1.26,<2"],
        python_requires=">=3.12,<3.13",
        distclass=NativeDistribution,
        script_args=["bdist_wheel", "--dist-dir", destination],
    )


if __name__ == '__main__':
    main()

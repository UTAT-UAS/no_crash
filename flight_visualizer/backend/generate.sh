#!/usr/bin/env bash
# Generate flight_visualizer_pb2.py(i) from the bridge's protocol definition.
# grpcio-tools bundles a protoc that matches the venv's protobuf runtime.
set -euo pipefail
cd "$(dirname "$0")"
uv run python -m grpc_tools.protoc \
    --proto_path=../../uas_ws/src/flight_visualizer_bridge/proto \
    --python_out=. --pyi_out=. \
    flight_visualizer.proto

#!/usr/bin/env bash
set -eo pipefail
source "$HOME/.local/share/no-crash/environment.sh"
exec /ros_entrypoint.sh "$@"

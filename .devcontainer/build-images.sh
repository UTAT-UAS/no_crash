#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf 'Usage: .devcontainer/build-images.sh [cpu|nvidia|nvidia-compat|amd|amd-wsl|all] [image-tag]\n'
    exit 0
fi
if (($# > 2)); then printf 'Too many arguments\n' >&2; exit 2; fi
profile=${1:-cpu}
case "$profile" in
    all)
        if (($# > 1)); then printf 'A custom image tag requires a single profile\n' >&2; exit 2; fi
        profiles=(cpu nvidia nvidia-compat amd amd-wsl) ;;
    cpu|nvidia|nvidia-compat|amd|amd-wsl) profiles=("$profile") ;;
    *) printf 'Unknown profile: %s\n' "$profile" >&2; exit 2 ;;
esac
jobs=${NO_CRASH_BUILD_JOBS:-4}
if [[ ! $jobs =~ ^[1-9][0-9]*$ ]]; then printf 'NO_CRASH_BUILD_JOBS must be a positive integer\n' >&2; exit 2; fi
for profile in "${profiles[@]}"; do
    image=${2:-no_crash:local-$profile}
    docker buildx build --load --platform linux/amd64 --target "$profile" \
        --build-arg "BUILD_JOBS=$jobs" --tag "$image" \
        --file .devcontainer/Dockerfile .
    docker image inspect "$image" --format 'Image: {{.RepoTags}} Size: {{.Size}} bytes'
done

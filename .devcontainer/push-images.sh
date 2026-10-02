#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    printf 'Usage: .devcontainer/push-images.sh [all|cpu|nvidia|nvidia-compat|amd|amd-wsl]\n'
    printf 'Uses NO_CRASH_IMAGE_PREFIX (default ghcr.io/utat-uas/no_crash) and NO_CRASH_IMAGE_TAG (default release snapshot).\n'
    exit 0
fi
if (($# > 1)); then printf 'Too many arguments\n' >&2; exit 2; fi
profile=${1:-all}
case "$profile" in
    all) profiles=(cpu nvidia nvidia-compat amd amd-wsl) ;;
    cpu|nvidia|nvidia-compat|amd|amd-wsl) profiles=("$profile") ;;
    *) printf 'Unknown profile: %s\n' "$profile" >&2; exit 2 ;;
esac
# shellcheck source=.devcontainer/versions.env
source .devcontainer/versions.env
image_prefix=${NO_CRASH_IMAGE_PREFIX:-ghcr.io/utat-uas/no_crash}
release_tag=${NO_CRASH_IMAGE_TAG:-$SNAPSHOT_DATE}
if [[ ! $image_prefix =~ ^ghcr\.io/[a-z0-9._-]+/[a-z0-9._/-]+$ ]]; then
    printf 'NO_CRASH_IMAGE_PREFIX must be a lowercase ghcr.io/<owner>/<image> reference without a tag or digest\n' >&2
    exit 2
fi

# Check every local image before publishing any, and retain the exact image IDs.
image_ids=()
destinations=()
for profile in "${profiles[@]}"; do
    tag="$release_tag-$profile"
    if [[ ! $tag =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]]; then
        printf 'Invalid release/profile tag: %s\n' "$tag" >&2
        exit 2
    fi
    local_image="no_crash:local-$profile"
    if ! image_id=$(docker image inspect "$local_image" --format '{{.Id}}'); then
        printf 'Missing local image: %s. Run .devcontainer/build-images.sh %s first.\n' "$local_image" "$profile" >&2
        exit 1
    fi
    image_ids+=("$image_id")
    destinations+=("$image_prefix:$tag")
done
for index in "${!profiles[@]}"; do
    printf 'Pushing no_crash:local-%s to %s\n' "${profiles[$index]}" "${destinations[$index]}"
    docker tag "${image_ids[$index]}" "${destinations[$index]}"
    docker push "${destinations[$index]}"
done

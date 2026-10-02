#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
profile=cpu
prebuilt=false
build=false
while (($#)); do
    case "$1" in
        --profile) profile=${2:?--profile needs a value}; shift 2 ;;
        --prebuilt) prebuilt=true; shift ;;
        --build) build=true; shift ;;
        --help|-h)
            printf 'Usage: ./enter.sh [--profile cpu|nvidia|nvidia-compat|amd|amd-wsl] [--prebuilt | --build]\n'
            exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done
case "$profile" in cpu|nvidia|nvidia-compat|amd|amd-wsl) ;; *) printf 'Unknown profile: %s\n' "$profile" >&2; exit 2 ;; esac
if $prebuilt && $build; then
    printf '%s\n' '--prebuilt and --build cannot be combined.' >&2
    exit 2
fi
config=".devcontainer/$profile/devcontainer.json"
if $prebuilt; then
    config=".devcontainer/$profile-prebuilt/devcontainer.json"
else
    image="no_crash:local-$profile"
    if $build; then
        ./.devcontainer/build-images.sh "$profile"
    elif docker image inspect "$image" >/dev/null 2>&1; then
        printf 'Using existing local image: %s\n' "$image"
    else
        printf 'Local image missing: %s. Building it now.\n' "$image"
        ./.devcontainer/build-images.sh "$profile"
    fi
fi
printf 'Dev Containers may create a cached UID/GID mapping layer for this host.\n'
up_options=(--workspace-folder "$PWD" --config "$config")
if $build; then up_options+=(--remove-existing-container); fi
devcontainer up "${up_options[@]}"
exec devcontainer exec --workspace-folder "$PWD" --config "$config" bash

#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if (($# == 0)); then set -- --help; fi
profile=cpu
local_image=false
rebuild=false
while (($#)); do
    case "$1" in
        --profile) profile=${2:?--profile needs a value}; shift 2 ;;
        --local) local_image=true; shift ;;
        --rebuild) rebuild=true; shift ;;
        --help|-h)
            printf 'Usage: ./enter.sh [--profile cpu|nvidia|nvidia-compat|amd|amd-wsl] [--local] [--rebuild]\n'
            printf 'No arguments prints this help. Profile defaults to cpu; images default to prebuilt.\n'
            printf '%s\n' '--local builds from source through Dev Containers.'
            printf '%s\n' '--rebuild removes the existing profile container and reruns container setup.'
            exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done
case "$profile" in cpu|nvidia|nvidia-compat|amd|amd-wsl) ;; *) printf 'Unknown profile: %s\n' "$profile" >&2; exit 2 ;; esac
# Check host tools before starting a potentially long image build.
for tool in docker python3 devcontainer; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Missing host tool: %s. See README.md for setup instructions.\n' "$tool" >&2
        exit 1
    fi
done
suffix=-prebuilt
if $local_image; then suffix=; fi
config=".devcontainer/$profile$suffix/devcontainer.json"
printf 'Dev Containers may create a cached UID/GID mapping layer for this host.\n'
up_options=(--workspace-folder "$PWD" --config "$config")
if $rebuild; then up_options+=(--remove-existing-container); fi
devcontainer up "${up_options[@]}"
exec devcontainer exec --workspace-folder "$PWD" --config "$config" bash

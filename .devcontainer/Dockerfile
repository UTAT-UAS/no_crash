# syntax=docker/dockerfile:1
FROM osrf/ros:jazzy-desktop-full@sha256:ae7ad3ac243da1dfd8bd402a2fa08e149ffbf7a385013bd8ef798d0800accdc8 AS system

ARG TARGETARCH
ARG USER_UID=1000
ARG USER_GID=1000
ARG BUILD_JOBS=4
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY .devcontainer/image/helpers.sh .devcontainer/image/install-system.sh /usr/local/lib/no-crash/
COPY .devcontainer/versions.env /usr/local/share/no-crash/versions.env
RUN test "${TARGETARCH:-amd64}" = amd64 && \
    bash /usr/local/lib/no-crash/install-system.sh "$USER_UID" "$USER_GID"

ENV HOME=/home/uas \
    USER=uas \
    SHELL=/bin/bash \
    BUN_INSTALL=/home/uas/.bun \
    LANG=en_US.UTF-8 \
    PYTHONNOUSERSITE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BUILD_JOBS=${BUILD_JOBS} \
    CMAKE_BUILD_PARALLEL_LEVEL=${BUILD_JOBS} \
    CARGO_BUILD_JOBS=${BUILD_JOBS} \
    PATH=/home/uas/.local/bin:/home/uas/.bun/bin:/home/uas/.local/opt/node/bin:/home/uas/.cargo/bin:${PATH}
USER uas
WORKDIR /home/uas/build

FROM system AS toolchain
USER root
WORKDIR /build
RUN chmod 0777 /build && rmdir /home/uas/build && ln -s /build /home/uas/build && \
    install -d -m 0777 /build/cargo-target /build/ccache /build/colcon /build/tmp
ENV CARGO_TARGET_DIR=/build/cargo-target \
    CCACHE_DIR=/build/ccache \
    TMPDIR=/build/tmp
USER uas
COPY .devcontainer/image/install-tools.sh /usr/local/lib/no-crash/
# Cache mounts create missing parents as root. Create those parents as uas.
RUN mkdir -p "$HOME/.cargo" "$HOME/.cache"
RUN --mount=type=cache,id=/home/uas/.cache/pip,target=/home/uas/.cache/pip,uid=1000,gid=1000 \
    --mount=type=cache,id=/home/uas/.cargo/registry,target=/opt/uas/.cargo/registry,uid=1000,gid=1000 \
    --mount=type=cache,id=/home/uas/.cargo/git,target=/opt/uas/.cargo/git,uid=1000,gid=1000 \
    --mount=type=cache,id=/home/uas/.cache/cargo-target,target=/build/cargo-target,uid=1000,gid=1000,mode=0777 \
    bash /usr/local/lib/no-crash/install-tools.sh

# Temporary native compilation trees never enter the final development image.
FROM toolchain AS native-builder
COPY .devcontainer/image/build-native.sh .devcontainer/image/package-opencv.py .devcontainer/image/environment.sh /usr/local/lib/no-crash/
RUN --mount=type=cache,id=/home/uas/.cache/pip,target=/home/uas/.cache/pip,uid=1000,gid=1000 \
    --mount=type=cache,id=/home/uas/.cargo/registry,target=/opt/uas/.cargo/registry,uid=1000,gid=1000 \
    --mount=type=cache,id=/home/uas/.cargo/git,target=/opt/uas/.cargo/git,uid=1000,gid=1000 \
    --mount=type=cache,id=/home/uas/.cache/cargo-target,target=/build/cargo-target,uid=1000,gid=1000,mode=0777 \
    --mount=type=cache,id=/home/uas/.cache/ccache,target=/build/ccache,uid=1000,gid=1000,mode=0777 \
    bash /usr/local/lib/no-crash/build-native.sh
# Some upstream install rules override umask. Normalize the retained tree in
# the builder so this does not add a second copy of its contents to final images.
RUN find /build/PX4-Autopilot \
    \( -type d ! -perm -0777 -o -type f ! -perm -0666 \) \
    -exec chmod a+rwX {} +

FROM toolchain AS common
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=native-builder --chown=uas:uas /opt/uas/.local/opt/gstreamer/ /opt/uas/.local/opt/gstreamer/
COPY --from=native-builder --chown=uas:uas /opt/uas/.local/opt/opencv/ /opt/uas/.local/opt/opencv/
COPY --from=native-builder --chown=uas:uas /opt/uas/.local/opt/xrce-agent/ /opt/uas/.local/opt/xrce-agent/
COPY --from=native-builder --chown=uas:uas /opt/uas/.local/share/no-crash/wheels/ /opt/uas/.local/share/no-crash/wheels/
COPY --from=native-builder --chown=uas:uas /opt/uas/.venvs/px4/ /opt/uas/.venvs/px4/
COPY --from=native-builder --chown=uas:uas /build/PX4-Autopilot/ /build/PX4-Autopilot/
COPY .devcontainer/image/environment.sh .devcontainer/image/install-vision.sh /usr/local/lib/no-crash/
COPY .devcontainer/image/colcon-defaults.yaml /usr/local/lib/no-crash/
COPY --chmod=755 .devcontainer/image/entrypoint.sh /usr/local/lib/no-crash/
COPY --chmod=755 .devcontainer/image/bin/ /usr/local/lib/no-crash/bin/
# Keep $HOME literal in .bashrc so it expands when the user's shell starts.
# hadolint ignore=SC2016
RUN source /usr/local/lib/no-crash/helpers.sh && \
    chmod 0777 /build/PX4-Autopilot && \
    mkdir -p "$HOME/.config" "$HOME/.colcon" && \
    cp /usr/local/lib/no-crash/colcon-defaults.yaml "$HOME/.colcon/defaults.yaml" && \
    cp /usr/local/lib/no-crash/bin/* "$HOME/.local/bin/" && \
    cp /usr/local/lib/no-crash/environment.sh "$HOME/.local/share/no-crash/environment.sh" && \
    printf '\nsource "$HOME/.local/share/no-crash/environment.sh"\n' >> "$HOME/.bashrc" && \
    make_user_storage_writable
# Ubuntu's unused users group occupies the usual NixOS host GID (100).
# Dev Containers refuses a GID change if another group already has that ID.
USER root
RUN if [[ $(getent group users || true) == 'users:x:100:' ]] && \
    ! getent passwd | cut -d: -f4 | grep -qx 100; then groupdel users; fi
USER uas
WORKDIR /home/uas/workspace
ENTRYPOINT ["/usr/local/lib/no-crash/entrypoint.sh"]
CMD ["sleep", "infinity"]
LABEL org.opencontainers.image.title="no_crash ROS Jazzy development environment" \
      org.opencontainers.image.description="Ubuntu 24.04, PX4, ROS 2 Jazzy and selectable vision backends"

FROM common AS cpu
ENV NO_CRASH_PROFILE=cpu
RUN --mount=type=cache,id=/home/uas/.cache/pip,target=/home/uas/.cache/pip,uid=1000,gid=1000 \
    bash /usr/local/lib/no-crash/install-vision.sh cpu

FROM common AS nvidia
ENV NO_CRASH_PROFILE=nvidia
RUN --mount=type=cache,id=/home/uas/.cache/pip,target=/home/uas/.cache/pip,uid=1000,gid=1000 \
    bash /usr/local/lib/no-crash/install-vision.sh cu132

FROM common AS nvidia-compat
ENV NO_CRASH_PROFILE=nvidia-compat
RUN --mount=type=cache,id=/home/uas/.cache/pip,target=/home/uas/.cache/pip,uid=1000,gid=1000 \
    bash /usr/local/lib/no-crash/install-vision.sh cu126

FROM common AS amd
ENV NO_CRASH_PROFILE=amd
RUN --mount=type=cache,id=/home/uas/.cache/pip,target=/home/uas/.cache/pip,uid=1000,gid=1000 \
    bash /usr/local/lib/no-crash/install-vision.sh rocm7.14

FROM amd AS amd-wsl
ENV NO_CRASH_PROFILE=amd-wsl
COPY .devcontainer/image/install-rocdxg.sh /usr/local/lib/no-crash/
RUN bash /usr/local/lib/no-crash/install-rocdxg.sh

# Agent guide

## Repository

`no_crash` is a monorepo for drone software. Its project directories currently
contain README placeholders; do not assume application manifests or packages
exist yet.

- `uas_ws/src/`: ROS 2 Jazzy packages.
- `flight_visualizer/frontend/`: Svelte frontend managed with Bun.
- `flight_visualizer/backend/`: Python backend with its own dependencies.
- `hardware_manager/`: Bash and Python hardware scripts.

Keep application source and dependency manifests in their owning project.
Build ROS packages with colcon from the monorepo root so the install overlay
remains at `install/`. Avoid introducing nested repository imports.

## Project conventions

- Use Bun for JavaScript/TypeScript dependencies and scripts. Commit `bun.lock`
  and use `bun install --frozen-lockfile` with an existing lockfile.
- Manage Python dependencies in project manifests and dedicated virtual
  environments. Use the system Python interpreter with `--system-site-packages`
  when a ROS project needs apt-managed modules such as `rclpy`.
- Declare ROS dependencies in `package.xml` and the project's build files.
  Keep `px4_msgs` compatible with the PX4 release used by the project.
- Project dependencies are installed explicitly by developers; container
  lifecycle hooks do not discover application manifests.
- Keep generated output, local environments, and personal configuration out
  of source control.
- Run checks relevant to the changed project. Distinguish syntax checks,
  compilation, runtime tests, and hardware tests when reporting results.

## Documentation and environment work

The root README describes the monorepo and its project layout. General project
workflows belong in `docs/development/`; container setup, image builds, host
configuration, and environment validation belong in `docs/devcontainer/`.
Keep each project's README current as implementation begins.

Read [the scoped container agent guide](.devcontainer/AGENTS.md) before changing
`.devcontainer/`, `docs/devcontainer/`, `enter.sh`, `flake.nix`,
or `flake.lock`. Container-specific compatibility, ownership, profile, and
validation rules are maintained there.

# no_crash

A monorepo for drone software projects, including ROS 2 flight software,
flight visualization, and hardware management.

## Project layout

- [`uas_ws/src/`](uas_ws/README.md): ROS 2 Jazzy packages built with colcon from the monorepo root.
- [`flight_visualizer/frontend/`](flight_visualizer/frontend/README.md): Svelte frontend using Bun.
- [`flight_visualizer/backend/`](flight_visualizer/backend/README.md): Python backend with its own environment and dependencies.
- [`hardware_manager/`](hardware_manager/README.md): Bash and Python hardware scripts.

These directories currently contain README placeholders. Each project will
declare its dependencies when implementation begins.

## Development

Start with [the development guide](docs/development/README.md) for project
workflows and dependency management.

- [Development container](docs/devcontainer/README.md): setup, machine profiles,
  local images, and the included tools.
- [Documentation](docs/README.md): guides and validation reports.
- [Agent guide](AGENTS.md): repository conventions for coding agents.

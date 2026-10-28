# Flight visualizer frontend agent guide

User-facing usage is in [README.md](README.md). Keep it lean; put detail here.

## Layout

- `src/routes/+page.svelte`: the dashboard. It opens one WebSocket to `/ws`
  (`wss` on https), reconnects every second, shows link status, state as text
  and the last command result, and sends `{"id", "name", "args"}` commands.
- `src/lib/PositionMap.svelte`: SVG map and altimeter. The map is North up,
  East right, ±10 m around the origin (`HALF_WIDTH`). The altimeter spans
  0–10 m (`MAX_ALTITUDE`). Positions are PX4 local NED, so altitude is `-z`.
  Values outside the bounds are drawn at the edge.
- `vite.config.ts`: the dev server proxies `/ws` to the backend at
  `127.0.0.1:8000`. `server.host: true` makes it listen on the container's
  interfaces, which Docker's published port needs.
- `src/lib/vitest-examples/` and `src/routes/page.svelte.e2e.ts` are scaffold
  examples.

Message shapes come from the bridge protocol in
[`flight_visualizer_bridge/AGENTS.md`](../../../uas_ws/src/flight_visualizer_bridge/AGENTS.md#protocol);
keep the `State` type in `+page.svelte` in step with it. Fields can be null.

## Conventions

- Svelte 5 runes mode, TypeScript, Bun. Commit `bun.lock`.
- Keep the UI plain and minimal until more is asked for.
- Run `bun x prettier --write` on changed files, then check:

  ```bash
  bun run check   # svelte-check
  bun run lint    # prettier --check and eslint
  ```

- ESLint's Svelte rules reject a mutable `Map` in components (use a plain
  object or `SvelteMap`) and string-literal mustaches like `{' '}`.

## Networking notes

- Docker publishes 5173 on the host's `127.0.0.1` and `::1`; see
  [host setup](../../../docs/devcontainer/host-setup.md#equipment-and-networking).
- A VS Code port forward listens on IPv4 only. Firefox resolves `localhost`
  to `::1` first, and its WebSockets do not fall back to IPv4, so the page
  loads but `/ws` and Vite's HMR socket fail. Use `127.0.0.1` in that case.
- A tab served by an earlier Vite instance has a stale HMR token, and Vite
  rejects its HMR socket. Reload the tab.

## Verification

With SITL, the bridge and the backend running, drive the page in headless
Chromium through Playwright (`bun x playwright install chromium` once). Click
the command buttons and read the `<pre>` text or take a screenshot.

To recreate the scaffold:
`bun x sv@1.1.1 create --template minimal --types ts --add prettier eslint vitest="usages:unit,component" playwright="demo:no" --install bun flight_visualizer`.

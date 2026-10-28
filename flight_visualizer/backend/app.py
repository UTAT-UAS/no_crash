"""FastAPI backend linking the browser dashboard to flight_visualizer_bridge.

Keeps one TCP connection to the bridge, reconnecting when it drops. Bridge
messages (state and command results) are forwarded to every browser on
`/ws`; commands from browsers are forwarded to the bridge. While the bridge is
unreachable, browsers get `{"type": "link", "connected": false}`.
"""

import asyncio
import contextlib
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

BRIDGE_HOST = os.environ.get('BRIDGE_HOST', '127.0.0.1')
BRIDGE_PORT = int(os.environ.get('BRIDGE_PORT', '8765'))
RECONNECT_DELAY = 1.0

browsers: set[WebSocket] = set()
bridge_writer: asyncio.StreamWriter | None = None
latest_state: dict | None = None
link = {'type': 'link', 'connected': False}


async def broadcast(message: dict) -> None:
    for browser in list(browsers):
        try:
            await browser.send_json(message)
        except Exception:
            browsers.discard(browser)


async def bridge_link() -> None:
    """Connect to the bridge and forward its messages, forever."""
    global bridge_writer, latest_state
    while True:
        try:
            reader, writer = await asyncio.open_connection(BRIDGE_HOST, BRIDGE_PORT)
        except OSError:
            await asyncio.sleep(RECONNECT_DELAY)
            continue
        bridge_writer = writer
        link['connected'] = True
        await broadcast(link)
        try:
            while line := await reader.readline():
                message = json.loads(line)
                if message.get('type') == 'state':
                    latest_state = message
                await broadcast(message)
        except (OSError, ValueError):
            pass
        bridge_writer = None
        link['connected'] = False
        writer.close()
        await broadcast(link)
        await asyncio.sleep(RECONNECT_DELAY)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(bridge_link())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get('/api/state')
async def get_state() -> dict:
    """Link status and the latest state, for debugging."""
    return {'connected': link['connected'], 'state': latest_state}


@app.websocket('/ws')
async def websocket(browser: WebSocket) -> None:
    await browser.accept()
    browsers.add(browser)
    await browser.send_json(link)
    if latest_state is not None:
        await browser.send_json(latest_state)
    try:
        while True:
            command = await browser.receive_json()
            if bridge_writer is None:
                await browser.send_json({
                    'type': 'result', 'id': command.get('id'), 'ok': False,
                    'error': 'Bridge is not connected'})
                continue
            command['type'] = 'command'
            bridge_writer.write(json.dumps(command, separators=(',', ':')).encode() + b'\n')
            await bridge_writer.drain()
    except WebSocketDisconnect:
        pass
    finally:
        browsers.discard(browser)

"""FastAPI backend linking the browser dashboard to flight_visualizer_bridge.

Keeps one TCP connection to the bridge, reconnecting when it drops. The bridge
speaks length-prefixed binary protobuf (`flight_visualizer.proto`); browsers on
`/ws` get the proto3 JSON form of each `BridgeMessage` and send `BackendMessage`
JSON, which is forwarded to the bridge. Bridge link changes are sent as
`{"link": {"connected": bool}}`.
"""

import asyncio
from collections.abc import AsyncIterator
import contextlib
import os
import struct
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google.protobuf import json_format
from google.protobuf.message import DecodeError

import flight_visualizer_pb2 as pb

BRIDGE_HOST = os.environ.get('BRIDGE_HOST', '127.0.0.1')
BRIDGE_PORT = int(os.environ.get('BRIDGE_PORT', '8765'))
RECONNECT_DELAY = 1.0
# Frames are prefixed by their length as a big-endian uint32.
LENGTH = struct.Struct('>I')
# Bridge messages are a few hundred bytes; anything larger is a broken link.
MAX_FRAME = 64 * 1024

browsers: set[WebSocket] = set()
bridge_writer: asyncio.StreamWriter | None = None
latest_state: dict[str, Any] | None = None
connected = False


def to_json(message: pb.BridgeMessage) -> dict[str, Any]:
    """Proto3 JSON form, with field names as in the .proto."""
    return json_format.MessageToDict(message, preserving_proto_field_name=True)


def link_message() -> dict[str, Any]:
    return {'link': {'connected': connected}}


def failed_result(command_id: int, error: str) -> dict[str, Any]:
    return to_json(pb.BridgeMessage(result=pb.Result(id=command_id, ok=False, error=error)))


async def broadcast(message: dict[str, Any]) -> None:
    for browser in list(browsers):
        try:
            await browser.send_json(message)
        except Exception:
            browsers.discard(browser)


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    (length,) = LENGTH.unpack(await reader.readexactly(LENGTH.size))
    if length > MAX_FRAME:
        raise ValueError(f'{length} byte frame')
    return await reader.readexactly(length)


async def bridge_link() -> None:
    """Connect to the bridge and forward its messages, forever."""
    global bridge_writer, latest_state, connected
    while True:
        try:
            reader, writer = await asyncio.open_connection(BRIDGE_HOST, BRIDGE_PORT)
        except OSError:
            await asyncio.sleep(RECONNECT_DELAY)
            continue
        bridge_writer = writer
        connected = True
        await broadcast(link_message())
        try:
            while True:
                message = to_json(pb.BridgeMessage.FromString(await read_frame(reader)))
                if 'state' in message:
                    latest_state = message
                await broadcast(message)
        except (OSError, ValueError, DecodeError, asyncio.IncompleteReadError):
            pass
        bridge_writer = None
        connected = False
        writer.close()
        await broadcast(link_message())
        await asyncio.sleep(RECONNECT_DELAY)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(bridge_link())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get('/api/state')
async def get_state() -> dict[str, Any]:
    """Link status and the latest state message, for debugging."""
    return {'connected': connected, 'state': latest_state}


@app.websocket('/ws')
async def websocket(browser: WebSocket) -> None:
    await browser.accept()
    browsers.add(browser)
    await browser.send_json(link_message())
    if latest_state is not None:
        await browser.send_json(latest_state)
    try:
        while True:
            data = await browser.receive_json()
            message = pb.BackendMessage()
            try:
                json_format.ParseDict(data, message)
            except json_format.ParseError as error:
                await browser.send_json(failed_result(_command_id(data), str(error)))
                continue
            if bridge_writer is None:
                await browser.send_json(
                    failed_result(message.command.id, 'Bridge is not connected')
                )
                continue
            payload = message.SerializeToString()
            bridge_writer.write(LENGTH.pack(len(payload)) + payload)
            await bridge_writer.drain()
    except WebSocketDisconnect:
        pass
    finally:
        browsers.discard(browser)


def _command_id(data: Any) -> int:
    """Best-effort command id from an invalid message, for its failed result."""
    try:
        command_id = data['command']['id']
    except (KeyError, TypeError):
        return 0
    return command_id if isinstance(command_id, int) and 0 <= command_id < 2**32 else 0

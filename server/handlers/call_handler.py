"""Voice call signaling handler."""

from __future__ import annotations

import json
from aiohttp import web


async def calls_ws(request: web.Request) -> web.WebSocketResponse:
    """Relay P2P voice call signaling over WebSocket."""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    db = request.app["db"]
    user = db.user_for_token(request.query.get("token", ""))
    connections: dict[int, web.WebSocketResponse] = request.app["call_connections"]
    connections[user["id"]] = ws
    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            receiver = int(data["receiver"])
            event = {"type": data.get("type", "call_signal"), "sender": user["id"], "payload": data.get("payload", {})}
            if receiver in connections and not connections[receiver].closed:
                await connections[receiver].send_json(event)
            else:
                await ws.send_json({"type": "error", "error": "callee offline"})
    finally:
        if connections.get(user["id"]) is ws:
            connections.pop(user["id"], None)
    return ws

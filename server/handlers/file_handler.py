"""File transfer signaling handler."""

from __future__ import annotations

import json
from aiohttp import web


async def file_transfer_ws(request: web.Request) -> web.WebSocketResponse:
    """Relay encrypted P2P file transfer metadata between peers."""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    db = request.app["db"]
    user = db.user_for_token(request.query.get("token", ""))
    connections: dict[int, web.WebSocketResponse] = request.app["file_connections"]
    connections[user["id"]] = ws
    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            receiver = int(data["receiver"])
            if receiver in connections and not connections[receiver].closed:
                await connections[receiver].send_json({"type": "file_offer", "sender": user["id"], "payload": data.get("payload", {})})
            else:
                await ws.send_json({"type": "error", "error": "receiver offline"})
    finally:
        if connections.get(user["id"]) is ws:
            connections.pop(user["id"], None)
    return ws

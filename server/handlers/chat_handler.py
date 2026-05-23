"""Realtime chat WebSocket handler."""

from __future__ import annotations

import json
from aiohttp import web


async def broadcast_presence(request: web.Request, user: dict[str, object]) -> None:
    """Broadcast a presence update to connected chat clients."""
    event = {
        "type": "presence",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "status": user["status"],
            "last_seen": user["last_seen"],
        },
    }
    connections: dict[int, web.WebSocketResponse] = request.app["connections"]
    for socket in list(connections.values()):
        if not socket.closed:
            await socket.send_json(event)


async def chat_ws(request: web.Request) -> web.WebSocketResponse:
    """Handle authenticated chat WebSocket connections."""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    db = request.app["db"]
    user = db.user_for_token(request.query.get("token", ""))
    connections: dict[int, web.WebSocketResponse] = request.app["connections"]
    connections[user["id"]] = ws
    user = db.set_presence(user["id"], "online")
    await ws.send_json({"type": "ready", "user": user})
    await broadcast_presence(request, user)
    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            if data.get("type") == "message":
                receiver = int(data["receiver"])
                payload = data.get("payload", {})
                saved = db.save_message(
                    user["id"],
                    receiver,
                    str(payload.get("encrypted") or data.get("content", "")),
                    str(data.get("message_type", "text")),
                    str(payload.get("nonce", "")),
                    str(payload.get("tag", "")),
                )
                envelope = {"type": "message", "message": saved}
                await ws.send_json({"type": "ack", "message_id": saved["id"]})
                if receiver in connections and not connections[receiver].closed:
                    await connections[receiver].send_json(envelope)
            elif data.get("type") == "history":
                await ws.send_json({"type": "conversations", "items": db.list_conversations(user["id"])})
            elif data.get("type") == "typing":
                receiver = int(data["receiver"])
                if receiver in connections and not connections[receiver].closed:
                    await connections[receiver].send_json({"type": "typing", "sender": user["id"]})
    finally:
        if connections.get(user["id"]) is ws:
            connections.pop(user["id"], None)
            offline_user = db.set_presence(user["id"], "offline")
            await broadcast_presence(request, offline_user)
    return ws

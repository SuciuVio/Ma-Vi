"""Small REST helpers used by the desktop Kivy client."""

from __future__ import annotations

from aiohttp import web


def _authenticated_user(request: web.Request) -> dict[str, object]:
    """Resolve the bearer token or token query parameter."""
    header = request.headers.get("Authorization", "")
    token = request.query.get("token", "")
    if header.startswith("Bearer "):
        token = header.removeprefix("Bearer ").strip()
    return request.app["db"].user_for_token(token)


async def search_users(request: web.Request) -> web.Response:
    """Search users through REST for the Kivy client."""
    user = _authenticated_user(request)
    query = request.query.get("query", "").strip()
    if not query:
        return web.json_response({"ok": True, "results": []})
    return web.json_response({"ok": True, "results": request.app["db"].search_users(int(user["id"]), query)})


async def conversations(request: web.Request) -> web.Response:
    """Return conversations for the authenticated user."""
    user = _authenticated_user(request)
    return web.json_response({"ok": True, "items": request.app["db"].list_conversations(int(user["id"]))})


async def contacts(request: web.Request) -> web.Response:
    """Return contacts for the authenticated user."""
    user = _authenticated_user(request)
    return web.json_response({"ok": True, "items": request.app["db"].list_contacts(int(user["id"]))})


async def add_contact(request: web.Request) -> web.Response:
    """Add a contact for the authenticated user."""
    user = _authenticated_user(request)
    data = await request.json()
    contact = request.app["db"].add_contact(
        int(user["id"]),
        int(data["contact_id"]),
        data.get("nickname"),
    )
    return web.json_response({"ok": True, "contact": contact}, status=201)


async def favorite_contact(request: web.Request) -> web.Response:
    """Set favorite state for a contact."""
    user = _authenticated_user(request)
    data = await request.json()
    contact = request.app["db"].set_contact_favorite(
        int(user["id"]),
        int(data["contact_id"]),
        bool(data.get("favorite", True)),
    )
    return web.json_response({"ok": True, "contact": contact})


async def messages(request: web.Request) -> web.Response:
    """Return messages exchanged with one peer."""
    user = _authenticated_user(request)
    user_id = int(user["id"])
    peer_id = int(request.query["peer_id"])
    limit = min(int(request.query.get("limit", "100")), 200)
    mark_read = request.query.get("mark_read", "1") != "0"
    read_message_ids = request.app["db"].mark_messages_read(user_id, peer_id) if mark_read else []
    items = request.app["db"].list_messages(user_id, peer_id, limit, False)
    if read_message_ids:
        connections = request.app["connections"]
        if peer_id in connections and not connections[peer_id].closed:
            await connections[peer_id].send_json(
                {
                    "type": "read_receipt",
                    "reader_id": user_id,
                    "message_ids": read_message_ids,
                }
            )
    return web.json_response({"ok": True, "items": items, "read_message_ids": read_message_ids})


async def send_message(request: web.Request) -> web.Response:
    """Persist and optionally deliver a message from the Kivy client."""
    user = _authenticated_user(request)
    data = await request.json()
    receiver_id = int(data["receiver"])
    content = str(data.get("content", "")).strip()
    encrypted = str(data.get("encrypted", "")).strip()
    if not content:
        content = encrypted
    if not content:
        raise web.HTTPBadRequest(reason="Message content is required")
    message = request.app["db"].save_message(
        int(user["id"]),
        receiver_id,
        content,
        str(data.get("message_type", "text")),
        str(data.get("nonce", "")),
        str(data.get("tag", "")),
    )
    connections = request.app["connections"]
    if receiver_id in connections and not connections[receiver_id].closed:
        await connections[receiver_id].send_json({"type": "message", "message": message})
    return web.json_response({"ok": True, "message": message})


async def offer_file(request: web.Request) -> web.Response:
    """Create a file-transfer offer and notify the receiver."""
    user = _authenticated_user(request)
    data = await request.json()
    receiver_id = int(data["receiver"])
    offer = request.app["db"].save_file_offer(int(user["id"]), receiver_id, data)
    event = {"type": "file_offer", "sender": int(user["id"]), "offer": offer}
    connections = request.app["connections"]
    if receiver_id in connections and not connections[receiver_id].closed:
        await connections[receiver_id].send_json(event)
    return web.json_response({"ok": True, "offer": offer}, status=201)


async def respond_file(request: web.Request) -> web.Response:
    """Accept or refuse a file-transfer offer."""
    user = _authenticated_user(request)
    data = await request.json()
    offer = request.app["db"].respond_to_file_offer(
        int(user["id"]),
        int(data["file_id"]),
        bool(data.get("accepted", False)),
    )
    if "peer_host" in data:
        offer["peer_host"] = data["peer_host"]
    if "peer_port" in data:
        offer["peer_port"] = int(data["peer_port"])
    event = {"type": "file_response", "responder": int(user["id"]), "offer": offer}
    sender_id = int(offer["sender_id"])
    connections = request.app["connections"]
    if sender_id in connections and not connections[sender_id].closed:
        await connections[sender_id].send_json(event)
    return web.json_response({"ok": True, "offer": offer})


async def start_call(request: web.Request) -> web.Response:
    """Start a voice-call offer."""
    user = _authenticated_user(request)
    data = await request.json()
    callee_id = int(data["callee_id"])
    call = request.app["db"].create_call(int(user["id"]), callee_id)
    event = {"type": "call_offer", "caller": int(user["id"]), "call": call}
    connections = request.app["connections"]
    if callee_id in connections and not connections[callee_id].closed:
        await connections[callee_id].send_json(event)
    return web.json_response({"ok": True, "call": call}, status=201)


async def respond_call(request: web.Request) -> web.Response:
    """Accept or decline a voice-call offer."""
    user = _authenticated_user(request)
    data = await request.json()
    accepted = bool(data.get("accepted", False))
    status = "active" if accepted else "declined"
    call = request.app["db"].update_call(int(data["call_id"]), int(user["id"]), status)
    if "audio_host" in data:
        call["audio_host"] = data["audio_host"]
    if "audio_port" in data:
        call["audio_port"] = int(data["audio_port"])
    if "audio_key" in data:
        call["audio_key"] = data["audio_key"]
    event = {"type": "call_response", "responder": int(user["id"]), "accepted": accepted, "call": call}
    caller_id = int(call["caller_id"])
    connections = request.app["connections"]
    if caller_id in connections and not connections[caller_id].closed:
        await connections[caller_id].send_json(event)
    return web.json_response({"ok": True, "call": call})


async def end_call(request: web.Request) -> web.Response:
    """End an active or ringing call."""
    user = _authenticated_user(request)
    data = await request.json()
    call = request.app["db"].update_call(int(data["call_id"]), int(user["id"]), "ended")
    peer_id = int(call["callee_id"]) if int(call["caller_id"]) == int(user["id"]) else int(call["caller_id"])
    event = {"type": "call_ended", "ender": int(user["id"]), "call": call}
    connections = request.app["connections"]
    if peer_id in connections and not connections[peer_id].closed:
        await connections[peer_id].send_json(event)
    return web.json_response({"ok": True, "call": call})

"""User search WebSocket handler."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from aiohttp import web


class SearchLimiter:
    """Simple per-user sliding-window limiter."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        """Return whether the user can perform a search now."""
        now = time.monotonic()
        events = self.events[user_id]
        while events and now - events[0] > self.window_seconds:
            events.popleft()
        if len(events) >= self.max_requests:
            return False
        events.append(now)
        return True


async def search_ws(request: web.Request) -> web.WebSocketResponse:
    """Serve live user search requests."""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    db = request.app["db"]
    limiter: SearchLimiter = request.app["search_limiter"]
    user = db.user_for_token(request.query.get("token", ""))
    async for msg in ws:
        if msg.type != web.WSMsgType.TEXT:
            continue
        data = json.loads(msg.data)
        query = str(data.get("query", "")).strip()
        if not limiter.allow(user["id"]):
            await ws.send_json({"type": "error", "error": "search rate limit exceeded"})
            continue
        await asyncio.sleep(0.3)
        await ws.send_json({"type": "search_results", "results": db.search_users(user["id"], query)})
    return ws

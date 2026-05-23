"""Async WebSocket client manager for the Kivy frontend."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

LOGGER = logging.getLogger(__name__)


class WebSocketClient:
    """Reconnectable WebSocket client with exponential backoff."""

    def __init__(self, url: str, on_message: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        self.url = url
        self.on_message = on_message
        self.socket: websockets.WebSocketClientProtocol | None = None
        self.running = False

    async def connect_forever(self) -> None:
        """Connect and reconnect until stopped."""
        self.running = True
        delay = 1.0
        while self.running:
            try:
                async with websockets.connect(self.url, ping_interval=30) as socket:
                    self.socket = socket
                    delay = 1.0
                    async for raw in socket:
                        await self.on_message(json.loads(raw))
            except Exception as exc:
                LOGGER.warning("WebSocket disconnected: %s", exc)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def send(self, payload: dict[str, Any]) -> None:
        """Send a JSON payload if connected."""
        if self.socket is None:
            raise ConnectionError("WebSocket is not connected")
        await self.socket.send(json.dumps(payload))

    def stop(self) -> None:
        """Stop reconnect attempts."""
        self.running = False

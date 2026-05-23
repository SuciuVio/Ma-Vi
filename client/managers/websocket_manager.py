"""Client WebSocket orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from threading import Thread
from typing import Any

from kivy.clock import Clock

from client.utils.constants import SERVER_WS_URL
from network.websocket_client import WebSocketClient


class ClientWebSocketManager:
    """Manage chat WebSocket lifecycle from the client."""

    def __init__(self, token: str) -> None:
        self.inbox: list[dict[str, Any]] = []
        self.listeners: list[Callable[[dict[str, Any]], None]] = []
        self.client = WebSocketClient(f"{SERVER_WS_URL}/ws/chat?token={token}", self._on_message)
        self.thread: Thread | None = None

    async def _on_message(self, payload: dict[str, Any]) -> None:
        """Store incoming messages and notify Kivy listeners on the UI thread."""
        self.inbox.append(payload)
        for listener in list(self.listeners):
            Clock.schedule_once(lambda _dt, item=payload, callback=listener: callback(item), 0)

    def add_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        """Register a UI listener for incoming WebSocket payloads."""
        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        """Remove a UI listener."""
        if listener in self.listeners:
            self.listeners.remove(listener)

    def start_background(self) -> None:
        """Start the WebSocket connection on a daemon thread."""
        if self.thread and self.thread.is_alive():
            return
        self.thread = Thread(target=lambda: asyncio.run(self.client.connect_forever()), daemon=True)
        self.thread.start()

    def send_json(self, payload: dict[str, Any]) -> None:
        """Send a payload from synchronous Kivy code."""

        def target() -> None:
            try:
                asyncio.run(self.client.send(payload))
            except Exception:
                return

        Thread(target=target, daemon=True).start()

    def stop(self) -> None:
        """Stop reconnect attempts."""
        self.client.stop()

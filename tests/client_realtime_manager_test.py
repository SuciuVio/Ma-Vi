"""Small test for client realtime listener dispatch."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\mavi_project")
sys.path.insert(0, str(PROJECT_ROOT))

from client.managers.websocket_manager import ClientWebSocketManager  # noqa: E402


def main() -> None:
    """Verify listener registration without opening a socket."""
    manager = ClientWebSocketManager("test-token")
    received: list[dict[str, object]] = []

    def listener(payload: dict[str, object]) -> None:
        received.append(payload)

    manager.add_listener(listener)
    manager.add_listener(listener)
    assert len(manager.listeners) == 1
    manager.remove_listener(listener)
    assert not manager.listeners
    print("CLIENT_REALTIME_MANAGER_OK")


if __name__ == "__main__":
    main()

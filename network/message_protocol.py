"""JSON protocol helpers shared by client and server."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ProtocolMessage(BaseModel):
    """Validated WebSocket message envelope."""

    type: str
    sender: int | None = None
    receiver: int | None = None
    content: str | None = None
    message_id: int | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)


def make_message(message_type: str, **payload: Any) -> dict[str, Any]:
    """Build a JSON-ready message dictionary."""
    return ProtocolMessage(type=message_type, payload=payload).model_dump()

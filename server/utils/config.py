"""Server configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _host_from_env() -> str:
    """Return a bind host accepted by local and hosted environments."""
    host = os.getenv("MAVI_HOST", "127.0.0.1").strip()
    if host.count("0.0.0.0") > 1:
        return "0.0.0.0"
    return host


@dataclass(frozen=True)
class ServerConfig:
    """Runtime configuration for the WebSocket and REST server."""

    host: str = _host_from_env()
    port: int = int(os.getenv("MAVI_PORT") or os.getenv("PORT", "8765"))
    database_path: Path = Path(os.getenv("MAVI_DB", "mavi.sqlite3"))
    token_ttl_seconds: int = int(os.getenv("MAVI_TOKEN_TTL", "86400"))
    refresh_ttl_seconds: int = int(os.getenv("MAVI_REFRESH_TTL", "604800"))
    log_level: str = os.getenv("MAVI_LOG_LEVEL", "INFO")


CONFIG = ServerConfig()

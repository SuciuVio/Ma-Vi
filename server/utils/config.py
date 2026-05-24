"""Server configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    """Runtime configuration for the WebSocket and REST server."""

    host: str = os.getenv("MAVI_HOST", "127.0.0.1")
    port: int = int(os.getenv("MAVI_PORT") or os.getenv("PORT", "8765"))
    database_path: Path = Path(os.getenv("MAVI_DB", "mavi.sqlite3"))
    token_ttl_seconds: int = int(os.getenv("MAVI_TOKEN_TTL", "86400"))
    refresh_ttl_seconds: int = int(os.getenv("MAVI_REFRESH_TTL", "604800"))
    log_level: str = os.getenv("MAVI_LOG_LEVEL", "INFO")


CONFIG = ServerConfig()

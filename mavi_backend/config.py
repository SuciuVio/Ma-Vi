"""Runtime configuration for the FastAPI Ma:Vi backend."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    database_path: Path = Path(os.getenv("MAVI_DB", "mavi.sqlite3"))
    upload_dir: Path = Path(os.getenv("MAVI_UPLOAD_DIR", "uploads"))
    token_ttl_seconds: int = int(os.getenv("MAVI_TOKEN_TTL", "86400"))
    refresh_ttl_seconds: int = int(os.getenv("MAVI_REFRESH_TTL", "604800"))


SETTINGS = Settings()

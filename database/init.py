"""Initialize the Ma:Vi SQLite database."""

from __future__ import annotations

from server.db.database import Database
from server.utils.config import CONFIG


if __name__ == "__main__":
    Database(CONFIG.database_path)
    print(f"Initialized {CONFIG.database_path}")

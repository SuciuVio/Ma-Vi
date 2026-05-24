"""SQLite helpers for Ma:Vi's FastAPI backend."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from mavi_backend.config import SETTINGS


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  public_key TEXT DEFAULT '',
  avatar_path TEXT,
  status TEXT DEFAULT 'offline',
  last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_login DATETIME
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  token TEXT UNIQUE NOT NULL,
  refresh_token TEXT UNIQUE NOT NULL,
  expires_at DATETIME NOT NULL,
  refresh_expires_at DATETIME NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  contact_id INTEGER NOT NULL,
  nickname TEXT,
  favorite INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(contact_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id, contact_id)
);

CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user1_id INTEGER NOT NULL,
  user2_id INTEGER NOT NULL,
  last_message_id INTEGER,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user1_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(user2_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user1_id, user2_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  sender_id INTEGER NOT NULL,
  receiver_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  message_type TEXT DEFAULT 'text',
  attachment_id INTEGER,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  delivered INTEGER DEFAULT 0,
  read INTEGER DEFAULT 0,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
  FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  file_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  content_type TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
"""


def init_db() -> None:
    """Create database directories and tables."""
    SETTINGS.database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript(SCHEMA)


def connect() -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    db = sqlite3.connect(SETTINGS.database_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    """Yield a transaction-scoped SQLite connection."""
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """Convert a SQLite row to a plain dictionary."""
    return dict(row) if row is not None else None


def user_public(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Return a public user payload."""
    user = dict(row)
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user.get("email", ""),
        "public_key": user.get("public_key") or "",
        "avatar_path": user.get("avatar_path"),
        "status": user.get("status", "offline"),
        "last_seen": user.get("last_seen"),
        "created_at": user.get("created_at"),
    }


def conversation_id(db: sqlite3.Connection, user_id: int, peer_id: int) -> int:
    """Return the stable two-user conversation id."""
    first, second = sorted((user_id, peer_id))
    row = db.execute(
        "SELECT id FROM conversations WHERE user1_id = ? AND user2_id = ?",
        (first, second),
    ).fetchone()
    if row:
        return int(row["id"])
    cursor = db.execute(
        "INSERT INTO conversations (user1_id, user2_id) VALUES (?, ?)",
        (first, second),
    )
    return int(cursor.lastrowid)

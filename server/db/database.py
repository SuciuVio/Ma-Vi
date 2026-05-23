"""SQLite data access layer for Ma:Vi."""

from __future__ import annotations

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import bcrypt

from server.db.schema import SCHEMA_SQL


class Database:
    """Small SQLite repository with parameterized operations."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection with row dictionaries and foreign keys enabled."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create all database tables and indexes."""
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(files)").fetchall()]
            if "status" not in columns:
                conn.execute("ALTER TABLE files ADD COLUMN status TEXT DEFAULT 'offered'")
            if "encrypted_file" not in columns:
                conn.execute("ALTER TABLE files ADD COLUMN encrypted_file BOOLEAN DEFAULT 0")
            if "original_file_name" not in columns:
                conn.execute("ALTER TABLE files ADD COLUMN original_file_name TEXT")
            if "plaintext_checksum" not in columns:
                conn.execute("ALTER TABLE files ADD COLUMN plaintext_checksum TEXT")

    def register_user(self, username: str, email: str, password: str, public_key: str = "") -> dict[str, Any]:
        """Create a user with bcrypt password hashing."""
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO users(username, email, password_hash, public_key) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, public_key),
            )
            user_id = int(cur.lastrowid)
            if public_key:
                conn.execute(
                    "INSERT INTO user_keys(user_id, public_key, key_fingerprint) VALUES (?, ?, ?)",
                    (user_id, public_key, public_key[-32:]),
                )
            return self.get_user(user_id, conn)

    def get_user(self, user_id: int, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
        """Fetch a user by id."""
        own = conn is None
        if own:
            ctx = self.connect()
            conn = ctx.__enter__()
        try:
            row = conn.execute(
                "SELECT id, username, email, public_key, status, last_seen, created_at, last_login FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise ValueError("User not found")
            return dict(row)
        finally:
            if own:
                ctx.__exit__(None, None, None)

    def authenticate(self, username: str, password: str, token_ttl: int, refresh_ttl: int) -> dict[str, Any]:
        """Authenticate credentials and return access and refresh tokens."""
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            attempt = conn.execute("SELECT * FROM login_attempts WHERE username = ?", (username,)).fetchone()
            if attempt and attempt["locked_until"] and datetime.fromisoformat(attempt["locked_until"]) > now:
                raise PermissionError("Account temporarily locked")
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            valid = bool(row and bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")))
            if not valid:
                self._record_failed_login(conn, username, now)
                raise PermissionError("Invalid credentials")
            conn.execute("DELETE FROM login_attempts WHERE username = ?", (username,))
            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP, status = 'online' WHERE id = ?", (row["id"],))
            token = secrets.token_urlsafe(32)
            refresh = secrets.token_urlsafe(32)
            expires = now + timedelta(seconds=token_ttl)
            refresh_expires = now + timedelta(seconds=refresh_ttl)
            conn.execute(
                "INSERT INTO sessions(user_id, token, refresh_token, expires_at, refresh_expires_at) VALUES (?, ?, ?, ?, ?)",
                (row["id"], token, refresh, expires.isoformat(), refresh_expires.isoformat()),
            )
            return {"token": token, "refresh_token": refresh, "expires_at": expires.isoformat(), "user": self.get_user(row["id"], conn)}

    def refresh_session(self, refresh_token: str, token_ttl: int, refresh_ttl: int) -> dict[str, Any]:
        """Rotate a refresh token and issue a new access token."""
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE refresh_token = ? AND refresh_expires_at > ?",
                (refresh_token, now.isoformat()),
            ).fetchone()
            if row is None:
                raise PermissionError("Invalid or expired refresh token")
            token = secrets.token_urlsafe(32)
            new_refresh = secrets.token_urlsafe(32)
            expires = now + timedelta(seconds=token_ttl)
            refresh_expires = now + timedelta(seconds=refresh_ttl)
            conn.execute(
                """
                UPDATE sessions
                SET token = ?, refresh_token = ?, expires_at = ?, refresh_expires_at = ?
                WHERE id = ?
                """,
                (token, new_refresh, expires.isoformat(), refresh_expires.isoformat(), row["id"]),
            )
            return {
                "token": token,
                "refresh_token": new_refresh,
                "expires_at": expires.isoformat(),
                "user": self.get_user(int(row["user_id"]), conn),
            }

    def _record_failed_login(self, conn: sqlite3.Connection, username: str, now: datetime) -> None:
        """Track login failures and lock after five failures."""
        row = conn.execute("SELECT * FROM login_attempts WHERE username = ?", (username,)).fetchone()
        if row is None or (row["first_failed_at"] and datetime.fromisoformat(row["first_failed_at"]) < now - timedelta(minutes=15)):
            conn.execute(
                "INSERT OR REPLACE INTO login_attempts(username, failed_count, first_failed_at, locked_until) VALUES (?, 1, ?, NULL)",
                (username, now.isoformat()),
            )
            return
        failed_count = int(row["failed_count"]) + 1
        locked_until = (now + timedelta(hours=1)).isoformat() if failed_count >= 5 else None
        conn.execute(
            "UPDATE login_attempts SET failed_count = ?, locked_until = ? WHERE username = ?",
            (failed_count, locked_until, username),
        )

    def user_for_token(self, token: str) -> dict[str, Any]:
        """Resolve an unexpired session token to a user."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE token = ? AND expires_at > ?",
                (token, now),
            ).fetchone()
            if row is None:
                raise PermissionError("Invalid or expired token")
            return self.get_user(row["id"], conn)

    def set_presence(self, user_id: int, status: str) -> dict[str, Any]:
        """Update a user's presence and last seen timestamp."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE users SET status = ?, last_seen = CURRENT_TIMESTAMP WHERE id = ?",
                (status, user_id),
            )
            return self.get_user(user_id, conn)

    def search_users(self, user_id: int, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search users by username or email, excluding the current user."""
        like = f"%{query.strip()}%"
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, username, email, public_key, status, last_seen
                FROM users
                WHERE id != ? AND (username LIKE ? OR email LIKE ?)
                ORDER BY username
                LIMIT ?
                """,
                (user_id, like, like, limit),
            ).fetchall()
            results = [dict(row) for row in rows]
            conn.execute(
                "INSERT INTO search_cache(user_id, query, results) VALUES (?, ?, ?)",
                (user_id, query, json.dumps(results)),
            )
            return results

    def add_contact(self, user_id: int, contact_id: int, nickname: str | None = None) -> dict[str, Any]:
        """Add or update a contact for a user."""
        if user_id == contact_id:
            raise ValueError("Cannot add yourself as a contact")
        with self.connect() as conn:
            contact = conn.execute(
                "SELECT id, username, email, public_key, status, last_seen FROM users WHERE id = ?",
                (contact_id,),
            ).fetchone()
            if contact is None:
                raise ValueError("Contact user not found")
            conn.execute(
                """
                INSERT INTO contacts(user_id, contact_id, nickname)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, contact_id) DO UPDATE SET nickname = excluded.nickname
                """,
                (user_id, contact_id, nickname),
            )
            return dict(contact)

    def list_contacts(self, user_id: int) -> list[dict[str, Any]]:
        """List contacts for a user."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  contacts.id,
                  contacts.contact_id,
                  contacts.nickname,
                  contacts.favorite,
                  users.username,
                  users.email,
                  users.public_key,
                  users.status,
                  users.last_seen
                FROM contacts
                JOIN users ON users.id = contacts.contact_id
                WHERE contacts.user_id = ?
                ORDER BY contacts.favorite DESC, users.username ASC
                """,
                (user_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def set_contact_favorite(self, user_id: int, contact_id: int, favorite: bool) -> dict[str, Any]:
        """Set a contact as favorite or not."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE contacts SET favorite = ? WHERE user_id = ? AND contact_id = ?",
                (1 if favorite else 0, user_id, contact_id),
            )
            row = conn.execute(
                """
                SELECT contacts.contact_id, contacts.nickname, contacts.favorite, users.username, users.public_key, users.status, users.last_seen
                FROM contacts
                JOIN users ON users.id = contacts.contact_id
                WHERE contacts.user_id = ? AND contacts.contact_id = ?
                """,
                (user_id, contact_id),
            ).fetchone()
            if row is None:
                raise ValueError("Contact not found")
            return dict(row)

    def respond_to_file_offer(self, user_id: int, file_id: int, accepted: bool) -> dict[str, Any]:
        """Accept or refuse a file offer addressed to the user."""
        status = "accepted" if accepted else "refused"
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT files.*, messages.sender_id, messages.receiver_id, messages.nonce, messages.tag
                FROM files
                JOIN messages ON messages.id = files.message_id
                WHERE files.id = ?
                """,
                (file_id,),
            ).fetchone()
            if row is None:
                raise ValueError("File offer not found")
            if int(row["receiver_id"]) != user_id:
                raise PermissionError("File offer is not addressed to this user")
            conn.execute("UPDATE files SET status = ? WHERE id = ?", (status, file_id))
            updated = conn.execute(
                """
                SELECT files.*, messages.sender_id, messages.receiver_id, messages.nonce, messages.tag, messages.timestamp
                FROM files
                JOIN messages ON messages.id = files.message_id
                WHERE files.id = ?
                """,
                (file_id,),
            ).fetchone()
            return dict(updated)

    def conversation_for(self, user1_id: int, user2_id: int) -> int:
        """Return the stable conversation id for two users."""
        left, right = sorted((user1_id, user2_id))
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM conversations WHERE user1_id = ? AND user2_id = ?",
                (left, right),
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO conversations(user1_id, user2_id) VALUES (?, ?)",
                (left, right),
            )
            return int(cur.lastrowid)

    def save_message(self, sender_id: int, receiver_id: int, content: str, message_type: str = "text", nonce: str = "", tag: str = "") -> dict[str, Any]:
        """Persist a chat message and update conversation metadata."""
        conv_id = self.conversation_for(sender_id, receiver_id)
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO messages(conversation_id, sender_id, receiver_id, content, message_type, nonce, tag, delivered)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (conv_id, sender_id, receiver_id, content, message_type, nonce, tag),
            )
            message_id = int(cur.lastrowid)
            conn.execute(
                "UPDATE conversations SET last_message_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (message_id, conv_id),
            )
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
            return dict(row)

    def save_file_offer(self, sender_id: int, receiver_id: int, metadata: dict[str, Any]) -> dict[str, Any]:
        """Persist file offer metadata as a file message."""
        message = self.save_message(
            sender_id,
            receiver_id,
            str(metadata.get("file_name", "file")),
            "file",
            str(metadata.get("nonce", "")),
            str(metadata.get("tag", "")),
        )
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO files(message_id, file_name, file_path, file_size, file_type, checksum, encrypted_file, original_file_name, plaintext_checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["id"],
                    str(metadata.get("file_name", "file")),
                    str(metadata.get("file_path", "")),
                    int(metadata.get("file_size", 0)),
                    str(metadata.get("file_type", "")),
                    str(metadata.get("checksum", "")),
                    1 if metadata.get("encrypted_file") else 0,
                    str(metadata.get("original_file_name", "")),
                    str(metadata.get("plaintext_checksum", "")),
                ),
            )
            row = conn.execute(
                """
                SELECT files.*, messages.sender_id, messages.receiver_id, messages.nonce, messages.tag, messages.timestamp
                FROM files
                JOIN messages ON messages.id = files.message_id
                WHERE files.id = ?
                """,
                (int(cur.lastrowid),),
            ).fetchone()
            return dict(row)

    def create_call(self, caller_id: int, callee_id: int) -> dict[str, Any]:
        """Create a ringing call record."""
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO calls(caller_id, callee_id, status) VALUES (?, ?, 'ringing')",
                (caller_id, callee_id),
            )
            row = conn.execute("SELECT * FROM calls WHERE id = ?", (int(cur.lastrowid),)).fetchone()
            return dict(row)

    def update_call(self, call_id: int, user_id: int, status: str) -> dict[str, Any]:
        """Update a call status, validating that the user participates."""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
            if row is None:
                raise ValueError("Call not found")
            if user_id not in {int(row["caller_id"]), int(row["callee_id"])}:
                raise PermissionError("User is not part of this call")
            if status in {"ended", "declined"}:
                conn.execute("UPDATE calls SET status = ?, end_time = CURRENT_TIMESTAMP WHERE id = ?", (status, call_id))
            else:
                conn.execute("UPDATE calls SET status = ? WHERE id = ?", (status, call_id))
            updated = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
            return dict(updated)

    def list_conversations(self, user_id: int) -> list[dict[str, Any]]:
        """List conversations visible to a user."""
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  c.*,
                  m.content AS last_message,
                  other_user.id AS peer_id,
                  other_user.username AS peer_username,
                  other_user.public_key AS peer_public_key,
                  other_user.status AS peer_status,
                  other_user.last_seen AS peer_last_seen
                FROM conversations c
                LEFT JOIN messages m ON m.id = c.last_message_id
                JOIN users other_user ON other_user.id = CASE
                  WHEN c.user1_id = ? THEN c.user2_id
                  ELSE c.user1_id
                END
                WHERE c.user1_id = ? OR c.user2_id = ?
                ORDER BY c.updated_at DESC
                """,
                (user_id, user_id, user_id),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_messages_read(self, user_id: int, peer_id: int) -> list[int]:
        """Mark messages from peer to user as read and return affected ids."""
        conv_id = self.conversation_for(user_id, peer_id)
        with self.connect() as conn:
            unread_rows = conn.execute(
                """
                SELECT id
                FROM messages
                WHERE conversation_id = ? AND sender_id = ? AND receiver_id = ? AND read = 0
                """,
                (conv_id, peer_id, user_id),
            ).fetchall()
            conn.execute(
                """
                UPDATE messages
                SET read = 1
                WHERE conversation_id = ? AND sender_id = ? AND receiver_id = ?
                """,
                (conv_id, peer_id, user_id),
            )
            return [int(row["id"]) for row in unread_rows]

    def list_messages(self, user_id: int, peer_id: int, limit: int = 100, mark_read: bool = True) -> list[dict[str, Any]]:
        """List recent messages between a user and a peer."""
        conv_id = self.conversation_for(user_id, peer_id)
        if mark_read:
            self.mark_messages_read(user_id, peer_id)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC, id ASC
                LIMIT ?
                """,
                (conv_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

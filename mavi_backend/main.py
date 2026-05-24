"""FastAPI entry point for the redesigned Ma:Vi backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from mavi_backend.config import SETTINGS
from mavi_backend.db import conversation_id, init_db, row_to_dict, session, user_public
from mavi_backend.security import hash_password, session_payload, verify_password


app = FastAPI(title="Ma:Vi API", version="2.0.0")
connections: dict[int, set[WebSocket]] = {}


class RegisterRequest(BaseModel):
    """Registration payload."""

    username: str = Field(min_length=3, max_length=32)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=6, max_length=128)
    public_key: str = ""


class LoginRequest(BaseModel):
    """Login payload."""

    username: str
    password: str


class RefreshRequest(BaseModel):
    """Refresh token payload."""

    refresh_token: str


class MessageRequest(BaseModel):
    """Text or attachment message payload."""

    receiver_id: int
    content: str = ""
    message_type: str = "text"
    attachment_id: int | None = None


class ContactRequest(BaseModel):
    """Contact add payload."""

    contact_id: int
    nickname: str | None = None


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Load the authenticated user from a bearer token."""
    token = _bearer_token(authorization)
    with session() as db:
        row = db.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid token")
    return dict(row)


def _create_session(user_id: int) -> dict[str, Any]:
    payload = session_payload(user_id)
    with session() as db:
        db.execute(
            """
            INSERT INTO sessions (user_id, token, refresh_token, expires_at, refresh_expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["user_id"],
                payload["token"],
                payload["refresh_token"],
                payload["expires_at"],
                payload["refresh_expires_at"],
            ),
        )
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return {
        "token": payload["token"],
        "refresh_token": payload["refresh_token"],
        "expires_at": payload["expires_at"],
        "user": user_public(user),
    }


@app.on_event("startup")
def startup() -> None:
    """Initialize SQLite and upload storage."""
    init_db()
    SETTINGS.upload_dir.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, Any]:
    """Return service health."""
    return {"ok": True, "service": "mavi-fastapi", "database": "sqlite"}


@app.post("/api/auth/register")
def register(payload: RegisterRequest) -> dict[str, Any]:
    """Create a user and return a session."""
    with session() as db:
        try:
            cursor = db.execute(
                """
                INSERT INTO users (username, email, password_hash, public_key, status)
                VALUES (?, ?, ?, ?, 'online')
                """,
                (payload.username, payload.email, hash_password(payload.password), payload.public_key),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Username or email already exists") from exc
        user_id = int(cursor.lastrowid)
    return _create_session(user_id)


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    """Authenticate and return a session."""
    with session() as db:
        user = db.execute("SELECT * FROM users WHERE username = ?", (payload.username,)).fetchone()
        if not user or not verify_password(payload.password, str(user["password_hash"])):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        db.execute("UPDATE users SET status = 'online', last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
    return _create_session(int(user["id"]))


@app.post("/api/auth/refresh")
def refresh(payload: RefreshRequest) -> dict[str, Any]:
    """Refresh a saved session."""
    with session() as db:
        row = db.execute("SELECT user_id FROM sessions WHERE refresh_token = ?", (payload.refresh_token,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _create_session(int(row["user_id"]))


@app.get("/api/users/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Return the current user."""
    return {"user": user_public(user)}


@app.get("/api/search")
def search_users(query: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Search users by username."""
    with session() as db:
        rows = db.execute(
            """
            SELECT * FROM users
            WHERE id != ? AND username LIKE ?
            ORDER BY username
            LIMIT 30
            """,
            (user["id"], f"%{query}%"),
        ).fetchall()
    return {"results": [user_public(row) for row in rows]}


@app.post("/api/contacts")
def add_contact(payload: ContactRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Add a contact."""
    with session() as db:
        peer = db.execute("SELECT * FROM users WHERE id = ?", (payload.contact_id,)).fetchone()
        if not peer:
            raise HTTPException(status_code=404, detail="User not found")
        db.execute(
            """
            INSERT OR IGNORE INTO contacts (user_id, contact_id, nickname)
            VALUES (?, ?, ?)
            """,
            (user["id"], payload.contact_id, payload.nickname),
        )
    return {"contact": user_public(peer)}


@app.get("/api/contacts")
def contacts(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """List saved contacts."""
    with session() as db:
        rows = db.execute(
            """
            SELECT users.*, contacts.nickname, contacts.favorite
            FROM contacts
            JOIN users ON users.id = contacts.contact_id
            WHERE contacts.user_id = ?
            ORDER BY contacts.favorite DESC, users.username
            """,
            (user["id"],),
        ).fetchall()
    return {"items": [user_public(row) | {"nickname": row["nickname"], "favorite": bool(row["favorite"])} for row in rows]}


@app.get("/api/conversations")
def conversations(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """List conversations with last message preview."""
    with session() as db:
        rows = db.execute(
            """
            SELECT conversations.*, messages.content AS last_content, messages.message_type AS last_type,
                   CASE WHEN conversations.user1_id = ? THEN conversations.user2_id ELSE conversations.user1_id END AS peer_id
            FROM conversations
            LEFT JOIN messages ON messages.id = conversations.last_message_id
            WHERE conversations.user1_id = ? OR conversations.user2_id = ?
            ORDER BY conversations.updated_at DESC
            """,
            (user["id"], user["id"], user["id"]),
        ).fetchall()
        items = []
        for row in rows:
            peer = db.execute("SELECT * FROM users WHERE id = ?", (row["peer_id"],)).fetchone()
            items.append({"id": row["id"], "peer": user_public(peer), "last_content": row["last_content"], "last_type": row["last_type"], "updated_at": row["updated_at"]})
    return {"items": items}


@app.get("/api/messages")
def messages(peer_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Return messages with a peer."""
    with session() as db:
        convo_id = conversation_id(db, int(user["id"]), peer_id)
        rows = db.execute(
            """
            SELECT messages.*, attachments.file_name, attachments.content_type, attachments.file_size
            FROM messages
            LEFT JOIN attachments ON attachments.id = messages.attachment_id
            WHERE conversation_id = ?
            ORDER BY messages.timestamp ASC
            LIMIT 200
            """,
            (convo_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/messages")
async def send_message(payload: MessageRequest, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Send a message and notify the receiver via WebSocket."""
    with session() as db:
        convo_id = conversation_id(db, int(user["id"]), payload.receiver_id)
        cursor = db.execute(
            """
            INSERT INTO messages (conversation_id, sender_id, receiver_id, content, message_type, attachment_id, delivered)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (convo_id, user["id"], payload.receiver_id, payload.content, payload.message_type, payload.attachment_id),
        )
        message_id = int(cursor.lastrowid)
        db.execute("UPDATE conversations SET last_message_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (message_id, convo_id))
        message = row_to_dict(
            db.execute(
                """
                SELECT messages.*, attachments.file_name, attachments.content_type, attachments.file_size
                FROM messages
                LEFT JOIN attachments ON attachments.id = messages.attachment_id
                WHERE messages.id = ?
                """,
                (message_id,),
            ).fetchone()
        )
    await broadcast(payload.receiver_id, {"event": "message", "message": message})
    return {"message": message}


@app.post("/api/attachments")
async def upload_attachment(file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    """Upload a file to server storage and record metadata in SQLite."""
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")
    safe_name = Path(file.filename or "file").name
    stored_name = f"{user['id']}_{len(content)}_{safe_name}"
    target = SETTINGS.upload_dir / stored_name
    target.write_bytes(content)
    with session() as db:
        cursor = db.execute(
            """
            INSERT INTO attachments (owner_id, file_name, stored_name, content_type, file_size)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user["id"], safe_name, stored_name, file.content_type or "application/octet-stream", len(content)),
        )
        attachment = row_to_dict(db.execute("SELECT * FROM attachments WHERE id = ?", (int(cursor.lastrowid),)).fetchone())
    return {"attachment": attachment}


@app.get("/api/attachments/{attachment_id}")
def download_attachment(attachment_id: int, user: dict[str, Any] = Depends(current_user)) -> FileResponse:
    """Download an uploaded attachment."""
    with session() as db:
        row = db.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = SETTINGS.upload_dir / str(row["stored_name"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path, filename=str(row["file_name"]), media_type=str(row["content_type"]))


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, token: str) -> None:
    """Realtime chat socket."""
    with session() as db:
        row = db.execute(
            "SELECT users.id FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = ?",
            (token,),
        ).fetchone()
    if not row:
        await websocket.close(code=4401)
        return
    user_id = int(row["id"])
    await websocket.accept()
    connections.setdefault(user_id, set()).add(websocket)
    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        connections.get(user_id, set()).discard(websocket)


async def broadcast(user_id: int, payload: dict[str, Any]) -> None:
    """Send a realtime payload to every socket for a user."""
    for websocket in list(connections.get(user_id, set())):
        try:
            await websocket.send_json(payload)
        except Exception:
            connections[user_id].discard(websocket)

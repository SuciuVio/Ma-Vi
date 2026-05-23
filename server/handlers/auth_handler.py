"""HTTP authentication handlers."""

from __future__ import annotations

import re
from aiohttp import web

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


def validate_registration(username: str, email: str, password: str) -> None:
    """Validate registration input."""
    if not USERNAME_RE.match(username):
        raise ValueError("Username must be 3-32 chars and use letters, numbers, underscore")
    if "@" not in email or len(email) > 254:
        raise ValueError("Invalid email")
    if len(password) < 8 or password.isalpha() or password.isdigit():
        raise ValueError("Weak password")


async def register(request: web.Request) -> web.Response:
    """Register a new user."""
    data = await request.json()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    public_key = str(data.get("public_key", ""))
    validate_registration(username, email, password)
    user = request.app["db"].register_user(username, email, password, public_key)
    return web.json_response({"ok": True, "user": user}, status=201)


async def login(request: web.Request) -> web.Response:
    """Authenticate a user and issue tokens."""
    data = await request.json()
    result = request.app["db"].authenticate(
        str(data.get("username", "")).strip(),
        str(data.get("password", "")),
        request.app["config"].token_ttl_seconds,
        request.app["config"].refresh_ttl_seconds,
    )
    return web.json_response({"ok": True, **result})


async def refresh(request: web.Request) -> web.Response:
    """Refresh an access token using a refresh token."""
    data = await request.json()
    result = request.app["db"].refresh_session(
        str(data.get("refresh_token", "")),
        request.app["config"].token_ttl_seconds,
        request.app["config"].refresh_ttl_seconds,
    )
    return web.json_response({"ok": True, **result})

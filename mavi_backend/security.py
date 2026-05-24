"""Authentication helpers for Ma:Vi's FastAPI backend."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from mavi_backend.config import SETTINGS


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a password matches a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def new_token() -> str:
    """Generate a URL-safe session token."""
    return secrets.token_urlsafe(32)


def utc_expiry(seconds: int) -> str:
    """Return an ISO UTC expiry timestamp."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def session_payload(user_id: int) -> dict[str, str | int]:
    """Build a new token pair payload."""
    return {
        "user_id": user_id,
        "token": new_token(),
        "refresh_token": new_token(),
        "expires_at": utc_expiry(SETTINGS.token_ttl_seconds),
        "refresh_expires_at": utc_expiry(SETTINGS.refresh_ttl_seconds),
    }

"""Client-side validation helpers."""

from __future__ import annotations

import re

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


def validate_username(username: str) -> str | None:
    """Return an error message for invalid usernames."""
    return None if USERNAME_RE.match(username) else "Use 3-32 letters, numbers, or underscores"


def validate_password(password: str) -> str | None:
    """Return an error message for weak passwords."""
    return None if len(password) >= 8 and not password.isdigit() else "Use at least 8 mixed characters"


def validate_email(email: str) -> str | None:
    """Return an error message for invalid email addresses."""
    return None if "@" in email and "." in email.rsplit("@", 1)[-1] else "Enter a valid email"

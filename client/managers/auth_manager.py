"""Authentication manager used by the Kivy client."""

from __future__ import annotations

import json
from pathlib import Path
import urllib.request
from typing import Any

from client.utils.constants import SERVER_BASE_URL
from network.encryption import encrypt_private_key, generate_keypair, get_key_fingerprint


class AuthManager:
    """Synchronous HTTP auth wrapper for simple Kivy integration."""

    def __init__(self) -> None:
        self.token: str | None = None
        self.refresh_token: str | None = None
        self.expires_at: str | None = None
        self.user: dict[str, Any] | None = None
        self.password: str | None = None
        self.session_path = Path.home() / ".mavi" / "session.json"
        self.keys_path = Path.home() / ".mavi" / "keys.json"
        self.load_session()

    def register(self, username: str, email: str, password: str, public_key: str = "") -> dict[str, Any]:
        """Register a user through the server REST API."""
        keys = generate_keypair()
        result = self._post("/api/auth/register", {"username": username, "email": email, "password": password, "public_key": keys["public_key"]})
        self.save_keys(result["user"]["id"], keys, password)
        return result

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Login and store session state."""
        result = self._post("/api/auth/login", {"username": username, "password": password})
        self.password = password
        self.token = result["token"]
        self.refresh_token = result.get("refresh_token")
        self.expires_at = result.get("expires_at")
        self.user = result["user"]
        self.save_session(result)
        return result

    def refresh_session(self) -> bool:
        """Refresh the access token with the saved refresh token."""
        if not self.refresh_token:
            return False
        try:
            result = self._post("/api/auth/refresh", {"refresh_token": self.refresh_token})
        except Exception:
            self.logout()
            return False
        self.token = result["token"]
        self.refresh_token = result.get("refresh_token")
        self.expires_at = result.get("expires_at")
        self.user = result["user"]
        self.save_session(result)
        return True

    def logout(self) -> None:
        """Clear local session state."""
        self.token = None
        self.refresh_token = None
        self.expires_at = None
        self.user = None
        self.password = None
        if self.session_path.exists():
            self.session_path.unlink()

    def save_session(self, result: dict[str, Any]) -> None:
        """Persist the local session for next app launch."""
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(
            json.dumps(
                {
                    "token": result["token"],
                    "refresh_token": result.get("refresh_token"),
                    "expires_at": result.get("expires_at"),
                    "user": result["user"],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_session(self) -> bool:
        """Load a previously saved local session if present."""
        if not self.session_path.exists():
            return False
        try:
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        self.token = data.get("token")
        self.refresh_token = data.get("refresh_token")
        self.expires_at = data.get("expires_at")
        self.user = data.get("user")
        return bool(self.token and self.user)

    def save_keys(self, user_id: int, keys: dict[str, str], password: str) -> None:
        """Save encrypted private keys locally."""
        self.keys_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.load_all_keys()
        data[str(user_id)] = {
            "public_key": keys["public_key"],
            "encrypted_private_key": encrypt_private_key(keys["private_key"], password),
            "signing_public_key": keys["signing_public_key"],
            "encrypted_signing_private_key": encrypt_private_key(keys["signing_private_key"], password),
            "fingerprint": get_key_fingerprint(keys["public_key"]),
        }
        self.keys_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_all_keys(self) -> dict[str, Any]:
        """Load all local encrypted key records."""
        if not self.keys_path.exists():
            return {}
        try:
            return json.loads(self.keys_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def local_key_record(self) -> dict[str, Any] | None:
        """Return the key record for the active user."""
        if not self.user:
            return None
        return self.load_all_keys().get(str(self.user["id"]))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(SERVER_BASE_URL + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

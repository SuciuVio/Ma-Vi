"""Test local client session persistence."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\mavi_project")
sys.path.insert(0, str(PROJECT_ROOT))

from client.managers.auth_manager import AuthManager  # noqa: E402
from network.encryption import generate_keypair  # noqa: E402


def main() -> None:
    """Verify AuthManager can save, load, and clear a local session."""
    path = PROJECT_ROOT / "test_session.json"
    if path.exists():
        path.unlink()

    auth = AuthManager()
    auth.session_path = path
    auth.keys_path = PROJECT_ROOT / "test_keys.json"
    if auth.keys_path.exists():
        auth.keys_path.unlink()
    auth.save_session(
        {
            "token": "token-123",
            "refresh_token": "refresh-123",
            "expires_at": "2099-01-01T00:00:00",
            "user": {"id": 1, "username": "alice"},
        }
    )

    loaded = AuthManager()
    loaded.session_path = path
    assert loaded.load_session()
    assert loaded.token == "token-123"
    assert loaded.refresh_token == "refresh-123"
    assert loaded.expires_at == "2099-01-01T00:00:00"
    assert loaded.user == {"id": 1, "username": "alice"}
    loaded.logout()
    assert not path.exists()
    auth.save_keys(1, generate_keypair(), "Password123!")
    record = auth.local_key_record()
    assert record is None
    auth.user = {"id": 1, "username": "alice"}
    record = auth.local_key_record()
    assert record and record["fingerprint"]
    auth.keys_path.unlink()
    print("CLIENT_SESSION_OK")


if __name__ == "__main__":
    main()

"""End-to-end encrypted message smoke test."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, web
from aiohttp.test_utils import unused_port

PROJECT_ROOT = Path(r"C:\mavi_project")
TEST_DB = PROJECT_ROOT / "test_e2e_encrypted.sqlite3"
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["MAVI_DB"] = str(TEST_DB)
os.environ["MAVI_PORT"] = "0"

from network.encryption import compute_shared_secret, decrypt_message, derive_aes_key, encrypt_message, generate_keypair  # noqa: E402
from server.server import create_app  # noqa: E402


async def _post_json(session: ClientSession, url: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    """POST JSON and return decoded body."""
    headers = {"Authorization": f"Bearer {token}"} if token else None
    async with session.post(url, json=payload, headers=headers) as response:
        body = await response.json()
        if response.status >= 400:
            raise AssertionError(f"POST {url} failed: {response.status} {body}")
        return body


async def run() -> None:
    """Register two keyed users and exchange one encrypted message."""
    if TEST_DB.exists():
        TEST_DB.unlink()
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    port = unused_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    base_url = f"http://127.0.0.1:{port}"
    suffix = int(time.time())
    alice_keys = generate_keypair()
    bob_keys = generate_keypair()

    try:
        async with ClientSession() as session:
            alice = await _post_json(
                session,
                f"{base_url}/api/auth/register",
                {
                    "username": f"alice_enc_{suffix}",
                    "email": f"alice_enc_{suffix}@example.com",
                    "password": "Password123!",
                    "public_key": alice_keys["public_key"],
                },
            )
            bob = await _post_json(
                session,
                f"{base_url}/api/auth/register",
                {
                    "username": f"bob_enc_{suffix}",
                    "email": f"bob_enc_{suffix}@example.com",
                    "password": "Password123!",
                    "public_key": bob_keys["public_key"],
                },
            )
            alice_login = await _post_json(
                session,
                f"{base_url}/api/auth/login",
                {"username": alice["user"]["username"], "password": "Password123!"},
            )
            shared = compute_shared_secret(alice_keys["private_key"], bob_keys["public_key"])
            encrypted = encrypt_message("secret hello", derive_aes_key(shared))
            sent = await _post_json(
                session,
                f"{base_url}/api/messages",
                {
                    "receiver": bob["user"]["id"],
                    "content": encrypted.encrypted,
                    "encrypted": encrypted.encrypted,
                    "nonce": encrypted.nonce,
                    "tag": encrypted.tag,
                },
                alice_login["token"],
            )
            message = sent["message"]
            bob_shared = compute_shared_secret(bob_keys["private_key"], alice_keys["public_key"])
            plaintext = decrypt_message(message["content"], message["nonce"], message["tag"], derive_aes_key(bob_shared))
            assert plaintext == "secret hello", message
            print("E2E_ENCRYPTED_MESSAGE_OK")
    finally:
        await runner.cleanup()
        if TEST_DB.exists():
            TEST_DB.unlink()


if __name__ == "__main__":
    asyncio.run(run())

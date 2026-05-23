"""End-to-end smoke test for Ma:Vi register, login, and WebSocket chat."""

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
TEST_DB = Path(r"C:\mavi_project\test_e2e.sqlite3")
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["MAVI_DB"] = str(TEST_DB)
os.environ["MAVI_PORT"] = "0"

from server.server import create_app  # noqa: E402


async def _post_json(session: ClientSession, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON and return the decoded body, raising on errors."""
    async with session.post(url, json=payload) as response:
        body = await response.json()
        if response.status >= 400:
            raise AssertionError(f"POST {url} failed: {response.status} {body}")
        return body


async def _receive_type(ws: Any, event_type: str) -> dict[str, Any]:
    """Receive WebSocket JSON messages until the requested event type appears."""
    for _ in range(10):
        payload = await ws.receive_json(timeout=5)
        if payload.get("type") == event_type:
            return payload
    raise AssertionError(f"Did not receive WebSocket event type {event_type}")


async def run() -> None:
    """Run the register/login/chat flow against a real local server."""
    if TEST_DB.exists():
        TEST_DB.unlink()

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    port = unused_port()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    base_url = f"http://127.0.0.1:{port}"
    ws_url = f"ws://127.0.0.1:{port}"
    suffix = int(time.time())

    try:
        async with ClientSession() as session:
            alice = {
                "username": f"alice_{suffix}",
                "email": f"alice_{suffix}@example.com",
                "password": "Password123!",
            }
            bob = {
                "username": f"bob_{suffix}",
                "email": f"bob_{suffix}@example.com",
                "password": "Password123!",
            }

            await _post_json(session, f"{base_url}/api/auth/register", alice)
            await _post_json(session, f"{base_url}/api/auth/register", bob)
            alice_login = await _post_json(session, f"{base_url}/api/auth/login", alice)
            bob_login = await _post_json(session, f"{base_url}/api/auth/login", bob)

            alice_token = alice_login["token"]
            bob_token = bob_login["token"]
            bob_id = bob_login["user"]["id"]

            async with session.post(
                f"{base_url}/api/auth/refresh",
                json={"refresh_token": alice_login["refresh_token"]},
            ) as response:
                refresh_body = await response.json()
                assert response.status == 200, refresh_body
                assert refresh_body["token"] != alice_token, refresh_body
                alice_token = refresh_body["token"]
                alice_login = {**alice_login, **refresh_body}

            async with session.get(
                f"{base_url}/api/search",
                params={"query": bob["username"]},
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                search_body = await response.json()
                assert response.status == 200, search_body
                assert search_body["results"][0]["username"] == bob["username"], search_body

            async with session.post(
                f"{base_url}/api/contacts",
                json={"contact_id": bob_id, "nickname": "Bob"},
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                contact_body = await response.json()
                assert response.status == 201, contact_body
                assert contact_body["contact"]["username"] == bob["username"], contact_body

            async with session.post(
                f"{base_url}/api/contacts/favorite",
                json={"contact_id": bob_id, "favorite": True},
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                favorite_body = await response.json()
                assert response.status == 200, favorite_body
                assert favorite_body["contact"]["favorite"] == 1, favorite_body

            async with session.get(
                f"{base_url}/api/contacts",
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                contacts_body = await response.json()
                assert response.status == 200, contacts_body
                assert contacts_body["items"][0]["contact_id"] == bob_id, contacts_body

            async with session.post(
                f"{base_url}/api/messages",
                json={"receiver": bob_id, "content": "hello through rest"},
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                rest_message = await response.json()
                assert response.status == 200, rest_message
                assert rest_message["message"]["content"] == "hello through rest", rest_message

            async with session.get(
                f"{base_url}/api/conversations",
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                conversations = await response.json()
                assert response.status == 200, conversations
                assert conversations["items"], conversations
                assert conversations["items"][0]["peer_id"] == bob_id, conversations
                assert conversations["items"][0]["peer_username"] == bob["username"], conversations

            async with session.get(
                f"{base_url}/api/messages",
                params={"peer_id": bob_id},
                headers={"Authorization": f"Bearer {alice_token}"},
            ) as response:
                history = await response.json()
                assert response.status == 200, history
                assert history["items"][0]["content"] == "hello through rest", history

            alice_id = alice_login["user"]["id"]
            async with session.ws_connect(f"{ws_url}/ws/chat?token={alice_token}") as alice_receipt_ws:
                receipt_ready = await alice_receipt_ws.receive_json(timeout=5)
                assert receipt_ready["type"] == "ready", receipt_ready
                assert receipt_ready["user"]["status"] == "online", receipt_ready
                presence_online = await _receive_type(alice_receipt_ws, "presence")
                assert presence_online["user"]["status"] == "online", presence_online

                async with session.get(
                    f"{base_url}/api/messages",
                    params={"peer_id": alice_id},
                    headers={"Authorization": f"Bearer {bob_token}"},
                ) as response:
                    bob_history = await response.json()
                    assert response.status == 200, bob_history
                    assert bob_history["items"][0]["read"] == 1, bob_history
                    assert bob_history["read_message_ids"], bob_history

                receipt = await _receive_type(alice_receipt_ws, "read_receipt")
                assert receipt["reader_id"] == bob_id, receipt
                assert bob_history["read_message_ids"][0] in receipt["message_ids"], receipt

                async with session.get(
                    f"{base_url}/api/messages",
                    params={"peer_id": bob_id, "mark_read": "0"},
                    headers={"Authorization": f"Bearer {alice_token}"},
                ) as response:
                    alice_history_after_read = await response.json()
                    assert response.status == 200, alice_history_after_read
                    assert alice_history_after_read["items"][0]["read"] == 1, alice_history_after_read

            async with session.ws_connect(f"{ws_url}/ws/chat?token={alice_token}") as alice_ws:
                async with session.ws_connect(f"{ws_url}/ws/chat?token={bob_token}") as bob_ws:
                    alice_ready = await alice_ws.receive_json(timeout=5)
                    bob_ready = await bob_ws.receive_json(timeout=5)
                    assert alice_ready["type"] == "ready"
                    assert bob_ready["type"] == "ready"
                    await _receive_type(alice_ws, "presence")
                    await _receive_type(bob_ws, "presence")

                    await alice_ws.send_json({"type": "typing", "receiver": bob_id})
                    typing = await _receive_type(bob_ws, "typing")
                    assert typing["sender"] == alice_ready["user"]["id"], typing

                    async with session.post(
                        f"{base_url}/api/calls/start",
                        json={"callee_id": bob_id},
                        headers={"Authorization": f"Bearer {alice_token}"},
                    ) as response:
                        call_start_body = await response.json()
                        assert response.status == 201, call_start_body
                        call_id = call_start_body["call"]["id"]
                    call_offer_event = await _receive_type(bob_ws, "call_offer")
                    assert call_offer_event["call"]["id"] == call_id, call_offer_event

                    async with session.post(
                        f"{base_url}/api/calls/respond",
                        json={"call_id": call_id, "accepted": True, "audio_host": "127.0.0.1", "audio_port": 56789, "audio_key": "00" * 32},
                        headers={"Authorization": f"Bearer {bob_token}"},
                    ) as response:
                        call_response_body = await response.json()
                        assert response.status == 200, call_response_body
                        assert call_response_body["call"]["status"] == "active", call_response_body
                    call_response_event = await _receive_type(alice_ws, "call_response")
                    assert call_response_event["accepted"] is True, call_response_event
                    assert call_response_event["call"]["audio_port"] == 56789, call_response_event

                    async with session.post(
                        f"{base_url}/api/calls/end",
                        json={"call_id": call_id},
                        headers={"Authorization": f"Bearer {alice_token}"},
                    ) as response:
                        call_end_body = await response.json()
                        assert response.status == 200, call_end_body
                        assert call_end_body["call"]["status"] == "ended", call_end_body
                    call_end_event = await _receive_type(bob_ws, "call_ended")
                    assert call_end_event["call"]["id"] == call_id, call_end_event

                    transfer_path = TEST_DB.with_suffix(".offer.txt")
                    transfer_path.write_text("file offer payload", encoding="utf-8")
                    try:
                        async with session.post(
                            f"{base_url}/api/files/offer",
                            json={
                                "receiver": bob_id,
                                "file_name": transfer_path.name,
                                "file_path": str(transfer_path),
                                "file_size": transfer_path.stat().st_size,
                                "file_type": "text/plain",
                                "checksum": "test-checksum",
                            },
                            headers={"Authorization": f"Bearer {alice_token}"},
                        ) as response:
                            file_offer_body = await response.json()
                            assert response.status == 201, file_offer_body
                            assert file_offer_body["offer"]["file_name"] == transfer_path.name, file_offer_body
                        file_offer_event = await _receive_type(bob_ws, "file_offer")
                        assert file_offer_event["offer"]["file_name"] == transfer_path.name, file_offer_event
                        async with session.post(
                            f"{base_url}/api/files/respond",
                            json={"file_id": file_offer_event["offer"]["id"], "accepted": True, "peer_host": "127.0.0.1", "peer_port": 55555},
                            headers={"Authorization": f"Bearer {bob_token}"},
                        ) as response:
                            file_response_body = await response.json()
                            assert response.status == 200, file_response_body
                            assert file_response_body["offer"]["status"] == "accepted", file_response_body
                        file_response_event = await _receive_type(alice_ws, "file_response")
                        assert file_response_event["offer"]["status"] == "accepted", file_response_event
                        assert file_response_event["offer"]["peer_port"] == 55555, file_response_event
                    finally:
                        if transfer_path.exists():
                            transfer_path.unlink()

                    await alice_ws.send_json(
                        {
                            "type": "message",
                            "receiver": bob_id,
                            "content": "hello from alice",
                            "message_type": "text",
                        }
                    )

                    ack = await _receive_type(alice_ws, "ack")
                    delivered = await _receive_type(bob_ws, "message")
                    assert delivered["message"]["content"] == "hello from alice", delivered
                    print("E2E_OK register login refresh contacts rest_search rest_message conversations history read_receipts typing presence calls file_offer file_response websocket_chat")
    finally:
        await runner.cleanup()
        if TEST_DB.exists():
            TEST_DB.unlink()


if __name__ == "__main__":
    asyncio.run(run())

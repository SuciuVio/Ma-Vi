"""Client chat state manager."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from client.utils.constants import SERVER_BASE_URL
from network.encryption import compute_shared_secret, decrypt_message, decrypt_private_key, derive_aes_key, encrypt_message


class ChatManager:
    """Store conversation state for the active client session."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.conversations: list[dict[str, Any]] = []
        self.presence: dict[int, dict[str, Any]] = {}

    def add_message(self, message: dict[str, Any]) -> None:
        """Append a message to local state."""
        self.messages.append(message)

    def set_conversations(self, items: list[dict[str, Any]]) -> None:
        """Replace conversation state."""
        self.conversations = items

    def set_presence(self, user: dict[str, Any]) -> None:
        """Store a realtime presence update."""
        self.presence[int(user["id"])] = user

    def list_conversations(self, token: str) -> list[dict[str, Any]]:
        """Fetch conversations from the server."""
        response = self._get("/api/conversations", token)
        self.set_conversations(response["items"])
        return self.conversations

    def search_users(self, token: str, query: str) -> list[dict[str, Any]]:
        """Search users from the server."""
        encoded = urllib.parse.urlencode({"query": query})
        return self._get(f"/api/search?{encoded}", token)["results"]

    def send_message(self, token: str, receiver_id: int, content: str, encrypted_payload: dict[str, str] | None = None) -> dict[str, Any]:
        """Send a message through the server."""
        payload = {"receiver": receiver_id, "content": content, "message_type": "text"}
        if encrypted_payload:
            payload["encrypted"] = encrypted_payload["encrypted"]
            payload["nonce"] = encrypted_payload["nonce"]
            payload["tag"] = encrypted_payload["tag"]
        response = self._post("/api/messages", token, payload)
        self.add_message(response["message"])
        return response["message"]

    def encrypt_for_user(self, plaintext: str, private_key: str, peer_public_key: str) -> dict[str, str]:
        """Encrypt plaintext for a peer public key."""
        aes_key = self.shared_aes_key(private_key, peer_public_key)
        payload = encrypt_message(plaintext, aes_key)
        return {"encrypted": payload.encrypted, "nonce": payload.nonce, "tag": payload.tag}

    def shared_aes_key(self, private_key: str, peer_public_key: str) -> bytes:
        """Derive the shared AES key for a peer."""
        shared = compute_shared_secret(private_key, peer_public_key)
        return derive_aes_key(shared)

    def decrypt_from_user(self, message: dict[str, Any], private_key: str, peer_public_key: str) -> str:
        """Decrypt a message from a peer if it has encrypted fields."""
        if not message.get("nonce") or not message.get("tag"):
            return str(message.get("content", ""))
        shared = compute_shared_secret(private_key, peer_public_key)
        aes_key = derive_aes_key(shared)
        return decrypt_message(str(message["content"]), str(message["nonce"]), str(message["tag"]), aes_key)

    def decrypt_private_key(self, encrypted_private_key: str, password: str) -> str:
        """Decrypt the local private key."""
        return decrypt_private_key(encrypted_private_key, password)

    def list_messages(self, token: str, peer_id: int) -> list[dict[str, Any]]:
        """Fetch messages exchanged with a peer."""
        encoded = urllib.parse.urlencode({"peer_id": peer_id})
        self.messages = self._get(f"/api/messages?{encoded}", token)["items"]
        return self.messages

    def list_contacts(self, token: str) -> list[dict[str, Any]]:
        """Fetch saved contacts."""
        return self._get("/api/contacts", token)["items"]

    def add_contact(self, token: str, contact_id: int, nickname: str | None = None) -> dict[str, Any]:
        """Add a user as contact."""
        payload: dict[str, Any] = {"contact_id": contact_id}
        if nickname:
            payload["nickname"] = nickname
        return self._post("/api/contacts", token, payload)["contact"]

    def set_favorite(self, token: str, contact_id: int, favorite: bool) -> dict[str, Any]:
        """Set contact favorite state."""
        return self._post("/api/contacts/favorite", token, {"contact_id": contact_id, "favorite": favorite})["contact"]

    def offer_file(self, token: str, receiver_id: int, metadata: dict[str, Any]) -> dict[str, Any]:
        """Create a file-transfer offer."""
        payload = {"receiver": receiver_id, **metadata}
        return self._post("/api/files/offer", token, payload)["offer"]

    def respond_file(self, token: str, file_id: int, accepted: bool, peer: dict[str, Any] | None = None) -> dict[str, Any]:
        """Accept or refuse a file-transfer offer."""
        payload = {"file_id": file_id, "accepted": accepted}
        if peer:
            payload.update(peer)
        return self._post("/api/files/respond", token, payload)["offer"]

    def start_call(self, token: str, callee_id: int) -> dict[str, Any]:
        """Start a voice call."""
        return self._post("/api/calls/start", token, {"callee_id": callee_id})["call"]

    def respond_call(self, token: str, call_id: int, accepted: bool, audio: dict[str, Any] | None = None) -> dict[str, Any]:
        """Accept or decline a voice call."""
        payload = {"call_id": call_id, "accepted": accepted}
        if audio:
            payload.update(audio)
        return self._post("/api/calls/respond", token, payload)["call"]

    def end_call(self, token: str, call_id: int) -> dict[str, Any]:
        """End a voice call."""
        return self._post("/api/calls/end", token, {"call_id": call_id})["call"]

    def _get(self, path: str, token: str) -> dict[str, Any]:
        request = urllib.request.Request(SERVER_BASE_URL + path, headers={"Authorization": f"Bearer {token}"}, method="GET")
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            SERVER_BASE_URL + path,
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

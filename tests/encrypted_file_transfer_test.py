"""Encrypted file transfer smoke test through FileManager."""

from __future__ import annotations

import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\mavi_project")
sys.path.insert(0, str(PROJECT_ROOT))

from client.managers.file_manager import FileManager  # noqa: E402
from network.encryption import compute_shared_secret, derive_aes_key, generate_keypair  # noqa: E402


def main() -> None:
    """Encrypt, transfer, decrypt, and verify one file."""
    source_root = PROJECT_ROOT / "encrypted_sender"
    receiver_root = PROJECT_ROOT / "encrypted_receiver"
    source_root.mkdir(exist_ok=True)
    receiver_root.mkdir(exist_ok=True)
    source = source_root / "secret.txt"
    source.write_text("encrypted file payload", encoding="utf-8")

    alice = generate_keypair()
    bob = generate_keypair()
    alice_key = derive_aes_key(compute_shared_secret(alice["private_key"], bob["public_key"]))
    bob_key = derive_aes_key(compute_shared_secret(bob["private_key"], alice["public_key"]))

    sender = FileManager(source_root)
    receiver = FileManager(receiver_root)
    metadata = sender.encrypted_metadata_for(source, alice_key)
    transfer_id = "encrypted-test"
    peer = receiver.start_receive(
        transfer_id,
        decrypt_info={
            "aes_key": bob_key,
            "nonce": metadata["nonce"],
            "tag": metadata["tag"],
            "original_file_name": metadata["original_file_name"],
        },
    )
    time.sleep(0.2)
    sender.start_send(transfer_id, metadata["file_path"], peer["peer_host"], peer["peer_port"])

    deadline = time.time() + 10
    while time.time() < deadline:
        status = receiver.transfer_status(transfer_id)
        if status["status"] in {"received", "failed"}:
            break
        time.sleep(0.1)
    assert receiver.transfer_status(transfer_id)["status"] == "received", receiver.transfer_status(transfer_id)
    received = receiver_root / "secret.txt"
    assert received.read_text(encoding="utf-8") == "encrypted file payload"

    for path in [source, received, Path(metadata["file_path"])]:
        if path.exists():
            path.unlink()
    for folder in [source_root / "outgoing", source_root, receiver_root]:
        if folder.exists():
            try:
                folder.rmdir()
            except OSError:
                pass
    print("ENCRYPTED_FILE_TRANSFER_OK")


if __name__ == "__main__":
    main()

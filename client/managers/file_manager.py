"""File manager facade for Android storage paths."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import random
from threading import Thread
from pathlib import Path
from typing import Any

from p2p.file_transfer import receive_file, send_file
from network.encryption import decrypt_file, encrypt_file
from client.utils.paths import mavi_data_dir


class FileManager:
    """Resolve Ma:Vi file storage locations."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or mavi_data_dir() / "files"
        self.root.mkdir(parents=True, exist_ok=True)
        self.transfers: dict[str, dict[str, Any]] = {}

    def target_for(self, filename: str) -> Path:
        """Return a safe local target path for a downloaded file."""
        return self.root / Path(filename).name

    def metadata_for(self, path: str | Path) -> dict[str, Any]:
        """Build file metadata for a transfer offer."""
        file_path = Path(path)
        checksum = hashlib.md5()
        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                checksum.update(chunk)
        file_type, _encoding = mimetypes.guess_type(file_path.name)
        return {
            "file_name": file_path.name,
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "file_type": file_type or "application/octet-stream",
            "checksum": checksum.hexdigest(),
        }

    def encrypted_metadata_for(self, path: str | Path, aes_key: bytes) -> dict[str, Any]:
        """Encrypt a file locally and return metadata for the encrypted transfer."""
        source = Path(path)
        target = self.root / "outgoing" / f"{source.name}.mavi.enc"
        payload = encrypt_file(source, target, aes_key)
        metadata = self.metadata_for(target)
        metadata.update(
            {
                "encrypted_file": True,
                "original_file_name": source.name,
                "plaintext_checksum": self._md5(source),
                "nonce": payload.nonce,
                "tag": payload.tag,
            }
        )
        return metadata

    def start_receive(self, transfer_id: str, host: str = "127.0.0.1", decrypt_info: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a background TCP receiver and return connection metadata."""
        port = random.randint(50000, 60000)
        self.transfers[transfer_id] = {"status": "waiting", "host": host, "port": port, "progress": 0}

        def progress(done: int, total: int) -> None:
            self.transfers[transfer_id].update({"status": "receiving", "progress": int(done * 100 / max(total, 1))})

        def target() -> None:
            try:
                result = asyncio.run(receive_file(self.root, host, port, progress))
                if decrypt_info:
                    encrypted_path = Path(str(result["file"]))
                    target = self.root / str(decrypt_info["original_file_name"])
                    decrypt_file(encrypted_path, target, str(decrypt_info["nonce"]), str(decrypt_info["tag"]), decrypt_info["aes_key"])
                    result = {"file": str(target), "size": target.stat().st_size, "md5": self._md5(target)}
                self.transfers[transfer_id] = {"status": "received", "progress": 100, **result}
            except Exception as exc:
                self.transfers[transfer_id] = {"status": "failed", "progress": self.transfers.get(transfer_id, {}).get("progress", 0), "error": str(exc)}

        Thread(target=target, daemon=True).start()
        return {"peer_host": host, "peer_port": port}

    def start_send(self, transfer_id: str, file_path: str | Path, host: str, port: int) -> None:
        """Start a background TCP sender for an accepted offer."""
        path = Path(file_path)
        self.transfers[transfer_id] = {"status": "sending", "progress": 0, "file": str(path), "host": host, "port": port}

        def progress(done: int, total: int) -> None:
            self.transfers[transfer_id].update({"status": "sending", "progress": int(done * 100 / max(total, 1))})

        def target() -> None:
            try:
                result = asyncio.run(send_file(path, host, port, progress))
                self.transfers[transfer_id] = {"status": "sent", "progress": 100, **result}
            except Exception as exc:
                self.transfers[transfer_id] = {"status": "failed", "progress": self.transfers.get(transfer_id, {}).get("progress", 0), "error": str(exc)}

        Thread(target=target, daemon=True).start()

    def transfer_status(self, transfer_id: str) -> dict[str, Any]:
        """Return current transfer status."""
        return self.transfers.get(transfer_id, {"status": "unknown", "progress": 0})

    def _md5(self, path: Path) -> str:
        """Return an MD5 checksum for a local file."""
        checksum = hashlib.md5()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                checksum.update(chunk)
        return checksum.hexdigest()

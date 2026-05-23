"""Encrypted peer-to-peer file transfer over TCP."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from collections.abc import Callable
from zlib import crc32

CHUNK_SIZE = 1024 * 1024
ProgressCallback = Callable[[int, int], None]


async def send_file(path: Path, host: str, port: int, on_progress: ProgressCallback | None = None) -> dict[str, str | int]:
    """Send a file to a peer with metadata, CRC32 per chunk, and MD5 checksum."""
    reader, writer = await asyncio.open_connection(host, port)
    checksum = hashlib.md5()
    size = path.stat().st_size
    header = {"name": path.name, "size": size}
    writer.write(json.dumps(header).encode("utf-8") + b"\n")
    await writer.drain()
    with path.open("rb") as file:
        sent = 0
        while chunk := file.read(CHUNK_SIZE):
            checksum.update(chunk)
            writer.write(len(chunk).to_bytes(4, "big") + crc32(chunk).to_bytes(4, "big") + chunk)
            await writer.drain()
            sent += len(chunk)
            if on_progress:
                on_progress(sent, size)
    writer.close()
    await writer.wait_closed()
    return {"file": path.name, "size": size, "md5": checksum.hexdigest()}


async def receive_file(destination: Path, host: str = "0.0.0.0", port: int = 55000, on_progress: ProgressCallback | None = None) -> dict[str, str | int]:
    """Receive one file from a peer and verify chunk CRC32 values."""
    destination.mkdir(parents=True, exist_ok=True)
    result: dict[str, str | int] = {}

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal result
        header = json.loads((await reader.readline()).decode("utf-8"))
        target = destination / Path(header["name"]).name
        checksum = hashlib.md5()
        remaining = int(header["size"])
        with target.open("wb") as file:
            received = 0
            while remaining > 0:
                length = int.from_bytes(await reader.readexactly(4), "big")
                expected_crc = int.from_bytes(await reader.readexactly(4), "big")
                chunk = await reader.readexactly(length)
                if crc32(chunk) != expected_crc:
                    raise ValueError("CRC32 mismatch")
                file.write(chunk)
                checksum.update(chunk)
                remaining -= length
                received += length
                if on_progress:
                    on_progress(received, int(header["size"]))
        result = {"file": str(target), "size": int(header["size"]), "md5": checksum.hexdigest()}
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, host, port)
    async with server:
        await server.start_serving()
        while not result:
            await asyncio.sleep(0.1)
    return result

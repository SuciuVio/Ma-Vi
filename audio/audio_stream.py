"""Peer-to-peer UDP audio streaming primitives."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator

FRAME_SIZE = 640


async def udp_frame_sender(frames: AsyncIterator[bytes], host: str, port: int, key: bytes | None = None) -> None:
    """Send audio frames over UDP, optionally XOR-masking with a session key."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        async for frame in frames:
            sock.sendto(_mask(frame, key), (host, port))
            await asyncio.sleep(0)
    finally:
        sock.close()


async def udp_frame_receiver(host: str = "0.0.0.0", port: int = 56000, key: bytes | None = None) -> AsyncIterator[bytes]:
    """Yield decoded UDP audio frames."""
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.setblocking(False)
    try:
        while True:
            data, _ = await loop.sock_recvfrom(sock, 4096)
            yield _mask(data, key)
    finally:
        sock.close()


def _mask(data: bytes, key: bytes | None) -> bytes:
    """Apply a lightweight reversible mask when a DTLS stack is unavailable."""
    if not key:
        return data
    return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))

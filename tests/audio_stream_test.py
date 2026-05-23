"""Encrypted UDP audio stream smoke test."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from aiohttp.test_utils import unused_port

PROJECT_ROOT = Path(r"C:\mavi_project")
sys.path.insert(0, str(PROJECT_ROOT))

from audio.audio_stream import udp_frame_receiver, udp_frame_sender  # noqa: E402


async def run() -> None:
    """Send a few encrypted UDP audio frames over localhost."""
    port = unused_port()
    key = os.urandom(32)
    received: list[bytes] = []

    async def receive() -> None:
        async for frame in udp_frame_receiver("127.0.0.1", port, key):
            received.append(frame)
            if len(received) >= 5:
                break

    async def frames():
        for index in range(5):
            yield bytes([index]) * 640
            await asyncio.sleep(0.01)

    receiver_task = asyncio.create_task(receive())
    await asyncio.sleep(0.1)
    await udp_frame_sender(frames(), "127.0.0.1", port, key)
    await asyncio.wait_for(receiver_task, timeout=5)
    assert len(received) == 5, received
    assert received[3] == bytes([3]) * 640
    print("AUDIO_STREAM_OK")


if __name__ == "__main__":
    asyncio.run(run())

"""P2P TCP file transfer smoke test."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from aiohttp.test_utils import unused_port

PROJECT_ROOT = Path(r"C:\mavi_project")
sys.path.insert(0, str(PROJECT_ROOT))

from p2p.file_transfer import receive_file, send_file  # noqa: E402


async def run() -> None:
    """Transfer a small file over localhost TCP."""
    source = PROJECT_ROOT / "p2p_source.txt"
    destination = PROJECT_ROOT / "p2p_received"
    received_file = destination / source.name
    source.write_text("hello p2p transfer", encoding="utf-8")
    if received_file.exists():
        received_file.unlink()
    destination.mkdir(exist_ok=True)
    port = unused_port()
    send_progress: list[int] = []
    receive_progress: list[int] = []

    receiver = asyncio.create_task(
        receive_file(destination, "127.0.0.1", port, lambda done, total: receive_progress.append(int(done * 100 / total)))
    )
    await asyncio.sleep(0.1)
    sent = await send_file(source, "127.0.0.1", port, lambda done, total: send_progress.append(int(done * 100 / total)))
    received = await asyncio.wait_for(receiver, timeout=10)
    assert sent["md5"] == received["md5"], (sent, received)
    assert received_file.read_text(encoding="utf-8") == "hello p2p transfer"
    assert send_progress[-1] == 100, send_progress
    assert receive_progress[-1] == 100, receive_progress
    source.unlink()
    received_file.unlink()
    destination.rmdir()
    print("P2P_FILE_TRANSFER_OK")


if __name__ == "__main__":
    asyncio.run(run())

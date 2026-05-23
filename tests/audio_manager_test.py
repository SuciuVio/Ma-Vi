"""AudioManager fallback behavior test."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\mavi_project")
sys.path.insert(0, str(PROJECT_ROOT))

from client.managers.audio_manager import AudioManager  # noqa: E402


def main() -> None:
    """Verify fallback audio session controls without hardware audio."""
    manager = AudioManager()
    assert manager.toggle_mute() is True
    assert manager.toggle_mute() is False
    peer = manager.prepare_receiver(42, playback=False)
    assert "audio_port" in peer
    manager.start_sender(42, peer["audio_host"], peer["audio_port"], peer["audio_key"], microphone=False)
    deadline = time.time() + 5
    while time.time() < deadline:
        if manager.sessions["42"].get("status") in {"sent_probe", "failed"}:
            break
        time.sleep(0.1)
    manager.end_call()
    assert manager.sessions["42"].get("sent_frames", 0) > 0 or manager.sessions["42"].get("received_frames", 0) > 0
    print("AUDIO_MANAGER_OK")


if __name__ == "__main__":
    main()

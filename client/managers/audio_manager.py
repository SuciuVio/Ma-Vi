"""Voice call state manager."""

from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import AsyncIterator
from threading import Thread
from typing import Any

from audio.audio_stream import udp_frame_receiver, udp_frame_sender
from audio.codec_manager import DEFAULT_CODEC


class AudioManager:
    """Track call state and audio toggles."""

    def __init__(self) -> None:
        self.in_call = False
        self.muted = False
        self.speaker = False
        self.sessions: dict[str, dict[str, Any]] = {}
        self.use_microphone = False

    def start_call(self) -> None:
        """Mark a call as active."""
        self.in_call = True

    def end_call(self) -> None:
        """Mark a call as ended."""
        self.in_call = False

    def toggle_mute(self) -> bool:
        """Toggle microphone mute."""
        self.muted = not self.muted
        return self.muted

    def prepare_receiver(self, call_id: int, host: str = "127.0.0.1", playback: bool = False) -> dict[str, Any]:
        """Prepare a UDP receiver for a call and return connection metadata."""
        port = random.randint(56000, 60000)
        key = os.urandom(32)
        self.sessions[str(call_id)] = {"status": "listening", "host": host, "port": port, "key": key, "received_frames": 0}

        def target() -> None:
            async def consume() -> None:
                player = self._open_output_stream() if playback else None
                async for frame in udp_frame_receiver(host, port, key):
                    self.sessions[str(call_id)]["received_frames"] += 1
                    if player:
                        player.write(frame)
                    if not self.in_call:
                        break
                if player:
                    player.stop_stream()
                    player.close()

            try:
                asyncio.run(consume())
            except Exception as exc:
                self.sessions[str(call_id)].update({"status": "failed", "error": str(exc)})

        self.in_call = True
        Thread(target=target, daemon=True).start()
        return {"audio_host": host, "audio_port": port, "audio_key": key.hex()}

    def start_sender(self, call_id: int, host: str, port: int, key_hex: str, microphone: bool | None = None) -> None:
        """Start a placeholder encrypted UDP audio sender."""
        key = bytes.fromhex(key_hex)
        self.sessions[str(call_id)] = {"status": "sending", "host": host, "port": port, "sent_frames": 0}
        self.in_call = True

        use_microphone = self.use_microphone if microphone is None else microphone
        frames = self._microphone_frames(call_id) if use_microphone else self._silent_frames(call_id)

        def target() -> None:
            try:
                asyncio.run(udp_frame_sender(frames, host, port, key))
                self.sessions[str(call_id)]["status"] = "sent_probe"
            except Exception as exc:
                self.sessions[str(call_id)].update({"status": "failed", "error": str(exc)})

        Thread(target=target, daemon=True).start()

    async def _silent_frames(self, call_id: int) -> AsyncIterator[bytes]:
        """Generate placeholder audio frames."""
        while self.in_call and self.sessions.get(str(call_id), {}).get("sent_frames", 0) < 50:
            self.sessions[str(call_id)]["sent_frames"] += 1
            yield b"\x00" * 640
            await asyncio.sleep(0.02)

    async def _microphone_frames(self, call_id: int) -> AsyncIterator[bytes]:
        """Capture audio frames from PyAudio when available."""
        stream = self._open_input_stream()
        try:
            while self.in_call:
                if self.muted:
                    frame = b"\x00" * 640
                    time.sleep(DEFAULT_CODEC.frame_ms / 1000)
                else:
                    frame = stream.read(320, exception_on_overflow=False)
                self.sessions[str(call_id)]["sent_frames"] += 1
                yield frame
                await asyncio.sleep(0)
        finally:
            stream.stop_stream()
            stream.close()

    def _open_input_stream(self) -> Any:
        """Open a PyAudio input stream."""
        import pyaudio

        audio = pyaudio.PyAudio()
        return audio.open(format=pyaudio.paInt16, channels=1, rate=DEFAULT_CODEC.sample_rate, input=True, frames_per_buffer=320)

    def _open_output_stream(self) -> Any:
        """Open a PyAudio output stream."""
        import pyaudio

        audio = pyaudio.PyAudio()
        return audio.open(format=pyaudio.paInt16, channels=1, rate=DEFAULT_CODEC.sample_rate, output=True, frames_per_buffer=320)

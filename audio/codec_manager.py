"""Audio codec configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioCodecConfig:
    """Runtime audio codec settings."""

    codec: str = "opus"
    bitrate: str = "24k"
    sample_rate: int = 16000
    frame_ms: int = 20


DEFAULT_CODEC = AudioCodecConfig()

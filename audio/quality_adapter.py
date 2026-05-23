"""Audio quality adaptation helpers."""

from __future__ import annotations


def choose_bitrate(packet_loss: float, latency_ms: int) -> str:
    """Choose an Opus bitrate from network quality metrics."""
    if packet_loss > 0.08 or latency_ms > 350:
        return "16k"
    if packet_loss > 0.03 or latency_ms > 180:
        return "24k"
    return "32k"

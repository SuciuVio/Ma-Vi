"""Platform-aware local paths for the Ma:Vi client."""

from __future__ import annotations

import os
from pathlib import Path


def mavi_data_dir() -> Path:
    """Return a writable directory for Ma:Vi client data."""
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        return Path(android_private) / ".mavi"

    android_argument = os.environ.get("ANDROID_ARGUMENT")
    if android_argument:
        return Path(android_argument).parent / ".mavi"

    cwd = Path.cwd()
    if cwd.as_posix().startswith("/data/user/") and cwd.name == "app":
        return cwd.parent / ".mavi"

    return Path.home() / ".mavi"

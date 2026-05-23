"""Client logging setup."""

from __future__ import annotations

import logging


def configure_client_logging() -> None:
    """Configure logging for the Kivy client."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

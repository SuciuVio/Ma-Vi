"""Helpers for running blocking client calls from Kivy screens."""

from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import TypeVar

from kivy.clock import Clock

T = TypeVar("T")


def run_in_thread(work: Callable[[], T], on_success: Callable[[T], None], on_error: Callable[[Exception], None]) -> None:
    """Run blocking work in a daemon thread and marshal callbacks to Kivy."""

    def target() -> None:
        try:
            result = work()
        except Exception as exc:
            Clock.schedule_once(lambda _dt, error=exc: on_error(error), 0)
            return
        Clock.schedule_once(lambda _dt: on_success(result), 0)

    Thread(target=target, daemon=True).start()

"""Feedback auditivo via plataforma. Cada función lanza un daemon thread."""

from __future__ import annotations

import threading

from whisperkey.platform import get_platform

_platform = get_platform()
_enabled = True


def set_enabled(val: bool) -> None:
    global _enabled
    _enabled = val


def _beep(freq: int, duration: int) -> None:
    _platform.play_beep(freq, duration / 1000.0)


def play_start() -> None:
    """1200Hz / 100ms — inicio de grabación."""
    if not _enabled:
        return
    threading.Thread(target=_beep, args=(1200, 100), daemon=True).start()


def play_stop() -> None:
    """800Hz / 100ms — fin de grabación."""
    if not _enabled:
        return
    threading.Thread(target=_beep, args=(800, 100), daemon=True).start()


def play_ready() -> None:
    """1000Hz/80ms + 1200Hz/80ms — modelo listo."""
    if not _enabled:
        return

    def _double():
        _platform.play_beep(1000, 0.080)
        _platform.play_beep(1200, 0.080)

    threading.Thread(target=_double, daemon=True).start()


def play_error() -> None:
    """400Hz / 300ms — error."""
    if not _enabled:
        return
    threading.Thread(target=_beep, args=(400, 300), daemon=True).start()

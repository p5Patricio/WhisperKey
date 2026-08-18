"""AppState: estado compartido entre threads."""

from __future__ import annotations

import gc
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

# Extra capture window after the hotkey is released. The PortAudio callback
# still holds the last block(s) when the key comes up; without this margin the
# final word of every dictation is truncated.
PTT_TAIL_GRACE_SECONDS = 0.2


@dataclass
class AppState:
    ptt_active: bool = False
    toggle_active: bool = False
    model: Any = None
    is_loading: bool = False
    load_model_requested: bool = False
    unload_model_requested: bool = False
    audio_queue_maxsize: int = 0
    audio_queue: queue.Queue = field(init=False)
    lock: threading.RLock = field(default_factory=threading.RLock)
    shutdown_event: threading.Event = field(default_factory=threading.Event)
    dropped_chunks: int = 0
    _capture_until: float = 0.0

    def __post_init__(self) -> None:
        self.audio_queue = queue.Queue(maxsize=self.audio_queue_maxsize or 0)

    # ------------------------------------------------------------------
    # Getters / setters atómicos
    # ------------------------------------------------------------------

    def set_ptt(self, v: bool) -> None:
        with self.lock:
            self.ptt_active = v

    def get_ptt(self) -> bool:
        with self.lock:
            return self.ptt_active

    def set_toggle(self, v: bool) -> None:
        with self.lock:
            self.toggle_active = v

    def get_toggle(self) -> bool:
        with self.lock:
            return self.toggle_active

    def set_loading(self, v: bool) -> None:
        with self.lock:
            self.is_loading = v

    def get_loading(self) -> bool:
        with self.lock:
            return self.is_loading

    def is_recording(self) -> bool:
        """True while the user is holding/toggling the hotkey."""
        with self.lock:
            return self.ptt_active or self.toggle_active

    def is_capturing(self) -> bool:
        """True while audio should still be captured, tail grace included."""
        with self.lock:
            if self.ptt_active or self.toggle_active:
                return True
            return time.monotonic() < self._capture_until

    def begin_stop_grace(self, seconds: float = PTT_TAIL_GRACE_SECONDS) -> float:
        """Clear the recording flags but keep capturing for *seconds* more.

        Returns the grace duration so the caller can schedule the sentinel.
        """
        with self.lock:
            self.ptt_active = False
            self.toggle_active = False
            self._capture_until = time.monotonic() + seconds
        return seconds

    def stop_recording(self) -> None:
        """Stop capturing immediately, keeping the audio already queued."""
        with self.lock:
            self.ptt_active = False
            self.toggle_active = False
            self._capture_until = 0.0

    def note_dropped_chunk(self) -> int:
        """Record a discarded audio chunk and return the running total."""
        with self.lock:
            self.dropped_chunks += 1
            return self.dropped_chunks

    def set_load_requested(self, v: bool) -> None:
        with self.lock:
            self.load_model_requested = v

    def get_load_requested(self) -> bool:
        with self.lock:
            return self.load_model_requested

    def set_unload_requested(self, v: bool) -> None:
        with self.lock:
            self.unload_model_requested = v

    def get_unload_requested(self) -> bool:
        with self.lock:
            return self.unload_model_requested

    # ------------------------------------------------------------------
    # Modelo
    # ------------------------------------------------------------------

    def set_model(self, model: Any) -> None:
        with self.lock:
            self.model = model

    def get_model(self) -> Any:
        """Read the engine under the lock; it can be swapped out concurrently."""
        with self.lock:
            return self.model

    def clear_model(self) -> None:
        with self.lock:
            self.model = None
        gc.collect()

    def reset_recording(self) -> None:
        """Discard the in-flight recording after a capture stall.

        Only for the case where the audio stream itself stopped delivering (the
        machine slept, the device was yanked): the buffered audio no longer
        corresponds to anything the user just said.
        """
        self.stop_recording()

        discarded = 0
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                discarded += 1
            except queue.Empty:
                break

        if discarded:
            log.warning("Grabación descartada tras un corte de captura: %d chunks", discarded)

        try:
            self.audio_queue.put_nowait("RESET")
        except queue.Full:
            pass

    def put_sentinel(self) -> None:
        """Pone un sentinel None en la cola de forma no bloqueante, liberando espacio si está llena."""
        try:
            self.audio_queue.put_nowait(None)
        except queue.Full:
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(None)
            except queue.Empty:
                pass

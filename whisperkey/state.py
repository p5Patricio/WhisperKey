"""AppState: estado compartido entre threads."""

from __future__ import annotations

import gc
import queue
import threading
from dataclasses import dataclass, field
from typing import Any


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
    lock: threading.Lock = field(default_factory=threading.Lock)
    shutdown_event: threading.Event = field(default_factory=threading.Event)

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
        with self.lock:
            return self.ptt_active or self.toggle_active

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

    def clear_model(self) -> None:
        import torch

        with self.lock:
            self.model = None
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

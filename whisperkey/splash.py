"""Splash screen de carga para WhisperKey."""

from __future__ import annotations

import logging
import tkinter as tk

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

log = logging.getLogger(__name__)


class SplashScreen:
    """Ventana splash modal que muestra el progreso de inicialización.

    Thread-safe: ``set_status`` delega al hilo de tkinter vía ``after(0, ...)``.
    Si *customtkinter* no está disponible, la clase actúa como no-op.
    """

    def __init__(self, master: tk.Tk | None = None) -> None:
        if ctk is None:
            self._window = None
            self._label = None
            self._progress = None
            log.warning("customtkinter no disponible; splash screen desactivado")
            return

        self._window = ctk.CTkToplevel(master)
        self._window.title("WhisperKey — Cargando...")
        self._window.geometry("400x200")
        self._window.resizable(False, False)
        self._window.overrideredirect(True)
        if master is not None:
            self._window.transient(master)

        self._center_window()

        self._label = ctk.CTkLabel(
            self._window,
            text="Inicializando...",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._label.pack(pady=(30, 10))

        self._progress = ctk.CTkProgressBar(self._window, mode="indeterminate")
        self._progress.pack(pady=10, padx=40, fill="x")
        self._progress.start()

    def _center_window(self) -> None:
        """Centra la ventana en la pantalla."""
        if self._window is None:
            return
        self._window.update_idletasks()
        w = 400
        h = 200
        sw = self._window.winfo_screenwidth()
        sh = self._window.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self._window.geometry(f"{w}x{h}+{x}+{y}")

    def set_status(self, text: str) -> None:
        """Actualiza el texto de estado (thread-safe)."""
        if self._window is not None and self._label is not None:
            self._window.after(0, lambda t=text: self._label.configure(text=t))

    def close(self) -> None:
        """Cierra el splash (thread-safe)."""
        if self._window is not None:
            self._window.after(0, self._window.destroy)

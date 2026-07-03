"""Splash screen de carga para WhisperKey."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from PIL import Image

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
        self._window.geometry("400x250")
        self._window.resizable(False, False)
        self._window.overrideredirect(True)
        if master is not None:
            self._window.transient(master)

        self._center_window()

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                logo_image = ctk.CTkImage(
                    light_image=Image.open(logo_path),
                    dark_image=Image.open(logo_path),
                    size=(80, 80)
                )
                self._logo_label = ctk.CTkLabel(self._window, text="", image=logo_image)
                self._logo_label.pack(pady=(20, 0))
            except Exception as e:
                log.warning("No se pudo cargar el logo: %s", e)

        self._label = ctk.CTkLabel(
            self._window,
            text="Inicializando...",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._label.pack(pady=(15, 10))

        self._progress = ctk.CTkProgressBar(self._window, mode="indeterminate")
        self._progress.pack(pady=10, padx=40, fill="x")
        self._progress.start()

        # Registrar callback de progreso de descarga
        try:
            from whisperkey.transcription import CustomProgressBar
            CustomProgressBar.register(self._on_download_progress)
        except ImportError:
            pass

    def _on_download_progress(self, n: int, total: int, pct: float) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.after(0, lambda: self._update_progress_ui(n, total, pct))

    def _update_progress_ui(self, n: int, total: int, pct: float) -> None:
        if self._progress is not None:
            if self._progress.cget("mode") == "indeterminate":
                self._progress.stop()
                self._progress.configure(mode="determinate")
            self._progress.set(pct / 100.0)
        if self._label is not None:
            self._label.configure(text=f"Descargando modelo... {pct:.1f}%")

    def _center_window(self) -> None:
        """Centra la ventana en la pantalla."""
        if self._window is None:
            return
        self._window.update_idletasks()
        w = 400
        h = 250
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
        try:
            from whisperkey.transcription import CustomProgressBar
            CustomProgressBar.unregister(self._on_download_progress)
        except ImportError:
            pass
        if self._window is not None:
            self._window.after(0, self._window.destroy)

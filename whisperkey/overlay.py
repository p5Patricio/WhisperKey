"""Overlay visual de grabación via tkinter.

Corre en su propio thread daemon. Todas las actualizaciones al widget
deben hacerse via `root.after(0, fn)` — NUNCA directamente desde otro thread.

LIMITACIÓN CONOCIDA: el overlay NO aparece sobre aplicaciones en fullscreen
exclusivo (juegos DirectX/OpenGL con exclusive fullscreen). Esto es una
restricción del sistema de composición de Windows y no tiene solución desde
tkinter. El overlay sí funciona en modo ventana y borderless fullscreen.
"""

from __future__ import annotations

import logging
import threading
import sys
import tkinter as tk

log = logging.getLogger(__name__)

# Estados visuales del overlay — paleta alineada con dark theme de customtkinter
STATES: dict[str, dict | None] = {
    "ptt":     {"text": "\u2b24  REC PTT",    "bg": "#EF4444", "fg": "white"},
    "toggle":  {"text": "\u2b24  REC",         "bg": "#F97316", "fg": "white"},
    "loading": {"text": "\u23f3 Cargando...", "bg": "#6B7280", "fg": "white"},
    "error":   {"text": "",                    "bg": "#DC2626", "fg": "white"},
    "hidden":  None,
}

# Fuente compatible con customtkinter / Windows 11
_OVERLAY_FONT = (
    "Segoe UI Variable" if sys.platform == "win32" else "Segoe UI",
    14,
    "bold",
)


class RecordingOverlay:
    """Overlay de grabación flotante sobre el escritorio.

    Corre tkinter en un thread daemon separado. La API pública es
    completamente thread-safe: cada método usa `root.after(0, fn)` para
    delegar la actualización al thread de tkinter.
    """

    def __init__(self, config: dict) -> None:
        self._config = config.get("overlay", {})
        self._enabled: bool = self._config.get("enabled", True)
        self._position: str = self._config.get("position", "bottom-right")
        self._opacity: float = self._config.get("opacity", 0.85)
        self._font_size: int = self._config.get("font_size", 14)
        self.root: tk.Tk | None = None
        self._label: tk.Label | None = None
        self._ready = threading.Event()

        if self._enabled:
            t = threading.Thread(target=self._run, daemon=True, name="overlay")
            t.start()
            self._ready.wait(timeout=3.0)  # esperar a que tkinter inicie

    # ------------------------------------------------------------------
    # Thread de tkinter
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Crea la ventana tkinter y arranca el mainloop (thread overlay)."""
        self.root = tk.Tk()
        self.root.overrideredirect(True)           # sin bordes ni decoraciones
        self.root.wm_attributes("-topmost", True)  # siempre encima
        self.root.wm_attributes("-alpha", self._opacity)
        self.root.configure(bg="#E53E3E")

        self._label = tk.Label(
            self.root,
            text="",
            font=(_OVERLAY_FONT[0], self._font_size, _OVERLAY_FONT[2]),
            fg="white",
            bg="#EF4444",
            padx=12,
            pady=6,
        )
        self._label.pack()

        # Ocultar hasta que se solicite un estado
        self.root.withdraw()
        self._ready.set()
        self.root.mainloop()

    def _set_state(self, state_key: str, text: str | None = None) -> None:
        """Actualiza el estado visual. SOLO llamar desde el thread de tkinter."""
        if not self._enabled or self.root is None:
            return
        state = STATES.get(state_key)
        if state is None:
            self.root.withdraw()
            return
        assert self._label is not None
        display_text = text if text is not None else state["text"]
        self._label.config(text=display_text, fg=state["fg"], bg=state["bg"])
        self.root.configure(bg=state["bg"])
        self._position_window()
        self.root.deiconify()

    def _position_window(self) -> None:
        """Calcula y aplica la posición según la configuración."""
        assert self.root is not None
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        margin = 20

        positions = {
            "bottom-right": (sw - w - margin, sh - h - margin - 48),
            "bottom-left":  (margin,           sh - h - margin - 48),
            "top-right":    (sw - w - margin,  margin),
            "top-left":     (margin,           margin),
        }
        x, y = positions.get(self._position, positions["bottom-right"])
        self.root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # API pública — thread-safe via root.after(0, fn)
    # ------------------------------------------------------------------

    def show_ptt(self) -> None:
        """Mostrar indicador PTT (rojo). Llamar desde cualquier thread."""
        if self._enabled and self.root:
            self.root.after(0, lambda: self._set_state("ptt"))

    def show_toggle(self) -> None:
        """Mostrar indicador toggle (naranja). Llamar desde cualquier thread."""
        if self._enabled and self.root:
            self.root.after(0, lambda: self._set_state("toggle"))

    def show_loading(self) -> None:
        """Mostrar indicador de carga. Llamar desde cualquier thread."""
        if self._enabled and self.root:
            self.root.after(0, lambda: self._set_state("loading"))

    def show_error(self, message: str) -> None:
        """Mostrar indicador de error (rojo oscuro). Llamar desde cualquier thread."""
        if self._enabled and self.root:
            self.root.after(0, lambda: self._set_state("error", message))

    def hide(self) -> None:
        """Ocultar el overlay. Llamar desde cualquier thread."""
        if self._enabled and self.root:
            self.root.after(0, lambda: self._set_state("hidden"))

    def destroy(self) -> None:
        """Destruir la ventana tkinter al cerrar la app. Thread-safe."""
        if self._enabled and self.root:
            self.root.after(0, self.root.destroy)

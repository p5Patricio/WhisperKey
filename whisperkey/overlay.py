"""Overlay visual de grabación via tkinter.

Corre en su propio thread daemon. Todas las actualizaciones al widget
deben hacerse via `root.after(0, fn)` — NUNCA directamente desde otro thread.

El indicador es una píldora oscura con un punto de estado a la izquierda. En
Windows las esquinas son redondeadas de verdad: la ventana declara un color
transparente y la píldora se dibuja sobre un canvas con ese color de fondo. En
el resto de plataformas degrada a un rectángulo con el mismo aspecto.

LIMITACIÓN CONOCIDA: el overlay NO aparece sobre aplicaciones en fullscreen
exclusivo (juegos DirectX/OpenGL con exclusive fullscreen). Esto es una
restricción del sistema de composición de Windows y no tiene solución desde
tkinter. El overlay sí funciona en modo ventana y borderless fullscreen.
"""

from __future__ import annotations

import logging
import threading
import sys
import time
import tkinter as tk

from whisperkey import pill

log = logging.getLogger(__name__)

# — Paleta: azul sobre negro —
SURFACE = "#0B1020"       # fondo de la píldora, casi negro con matiz azul
BORDER = "#1E293B"        # borde apenas perceptible, da profundidad sin ruido
TEXT = "#E6EDFB"
TEXT_MUTED = "#94A3B8"
# Color clave para transparencia en Windows; no debe aparecer en el diseño.
_TRANSPARENT_KEY = "#FF00FE"

# Estados visuales. `dot` es el punto de estado; `pulse` anima su intensidad.
STATES: dict[str, dict | None] = {
    "ptt":        {"text": "Escuchando",    "dot": "#3B82F6", "fg": TEXT,       "pulse": True},
    "toggle":     {"text": "Grabando",      "dot": "#60A5FA", "fg": TEXT,       "pulse": True},
    "processing": {"text": "Transcribiendo", "dot": "#38BDF8", "fg": TEXT,       "pulse": False},
    "loading":    {"text": "Preparando",    "dot": "#64748B", "fg": TEXT_MUTED, "pulse": True},
    "cancelled":  {"text": "Cancelado",     "dot": "#64748B", "fg": TEXT_MUTED, "pulse": False},
    "error":      {"text": "Error",         "dot": "#F87171", "fg": TEXT,       "pulse": False},
    "hidden":     None,
}

# Respiración del punto de estado: del color pleno a una versión apagada. Más
# rápido o más profundo deja de leerse como respiración y pasa a parpadeo.
_PULSE_INTERVAL_MS = 140
_PULSE_STEPS = 12
_PULSE_DEPTH = 0.55

# Animación del estado "processing": sin ella una transcripción larga parece una
# app colgada, porque el usuario suelta la tecla y no ve nada hasta que llega el
# texto.
_PROCESSING_INTERVAL_MS = 400
# A partir de acá el indicador suma los segundos transcurridos, para que una
# espera larga se lea como progreso y no como algo trabado.
_PROCESSING_ELAPSED_AFTER_S = 3.0
# Un aviso puntual no debe dejar un cartel fijo sobre el escritorio.
_ERROR_AUTO_HIDE_MS = 5000
_CANCELLED_AUTO_HIDE_MS = 1200
# Margen para que arranque el thread de tkinter.
_STARTUP_TIMEOUT_S = 3.0

# Geometría de la píldora. El alto sale del alto de línea de la fuente más el
# relleno; el de Pillow es más generoso que el de tkinter, así que el relleno se
# ajustó para que la píldora conserve el tamaño que tenía con el Canvas.
_PAD_X = 13
_PAD_Y = 5
_DOT_RADIUS = 4
_DOT_GAP = 10

_OVERLAY_FONT = (
    "Segoe UI Variable" if sys.platform == "win32" else "Segoe UI",
    14,
    "normal",
)


def _blend(color: str, background: str, t: float) -> str:
    """Interpola *color* hacia *background*. t=0 color pleno, t=1 fondo."""
    def parts(c: str) -> tuple[int, int, int]:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    fr, fg, fb = parts(color)
    br, bg, bb = parts(background)
    r = round(fr + (br - fr) * t)
    g = round(fg + (bg - fg) * t)
    b = round(fb + (bb - fb) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


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
        self._canvas: tk.Canvas | None = None
        self._label: tk.Label | None = None
        self._ready = threading.Event()

        self._anim_job: str | None = None
        self._pulse_job: str | None = None
        self._pulse_tick = 0
        self._anim_tick = 0
        self._anim_started = 0.0
        self._dot_color = SURFACE
        self._dot_item: int | None = None
        # Camino preferido: imagen suavizada con alfa por píxel. El Canvas de
        # tkinter dibuja sin antialiasing y las esquinas salen en escalones.
        self._layered = pill.supports_per_pixel_alpha()
        self._scale = 1.0
        # Qué se está mostrando: el pulso redibuja la píldora entera en el
        # camino suavizado, así que necesita saber qué texto y estado repintar.
        self._pulse_state = "hidden"
        self._pulse_text = ""
        # Tamaño con el que la ventana está mostrada. Redimensionar y volver a
        # mapear en cada fotograma del pulso es lo que se veía como parpadeo.
        self._shown_size: tuple[int, int] | None = None

        if self._enabled:
            t = threading.Thread(target=self._run, daemon=True, name="overlay")
            t.start()
            # Si tkinter tarda más que esto, el overlay queda a medio construir.
            # Antes se seguía en silencio y el usuario se quedaba sin indicador
            # sin ninguna pista de por qué.
            if not self._ready.wait(timeout=_STARTUP_TIMEOUT_S):
                log.warning(
                    "El overlay no terminó de iniciar en %.0fs; puede no aparecer.",
                    _STARTUP_TIMEOUT_S,
                )

    # ------------------------------------------------------------------
    # Thread de tkinter
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Crea la ventana tkinter y arranca el mainloop (thread overlay)."""
        self.root = tk.Tk()
        self.root.overrideredirect(True)           # sin bordes ni decoraciones
        self.root.wm_attributes("-topmost", True)  # siempre encima
        if not self._layered:
            # -alpha de tkinter llama por dentro a SetLayeredWindowAttributes,
            # que es EXCLUYENTE con UpdateLayeredWindow: usar una inhabilita la
            # otra. En modo suavizado la opacidad va en el canal alfa.
            self.root.wm_attributes("-alpha", self._opacity)

        try:
            # Píxeles por punto, igual que usa tkinter para medir sus fuentes.
            # Es lo que hace que la píldora conserve su tamaño de siempre.
            self._scale = float(self.root.tk.call("tk", "scaling"))
            if not (0.5 <= self._scale <= 4.0):
                self._scale = pill.device_scale(self.root.winfo_screenwidth())
        except Exception:  # pragma: no cover - depende del sistema
            self._scale = 1.0

        canvas_bg = SURFACE
        if self._layered:
            # El color clave y el alfa por píxel también son excluyentes: con
            # color clave el borde suavizado se mezclaría contra el color de
            # transparencia y dejaría una aureola alrededor de la píldora.
            pass
        elif sys.platform == "win32":
            try:
                self.root.wm_attributes("-transparentcolor", _TRANSPARENT_KEY)
                canvas_bg = _TRANSPARENT_KEY
            except Exception as exc:  # pragma: no cover - depende del compositor
                log.debug("Sin transparencia por color clave: %s", exc)

        self.root.configure(bg=canvas_bg)
        self._canvas = tk.Canvas(
            self.root, bg=canvas_bg, highlightthickness=0, bd=0
        )
        self._canvas.pack()

        self._label = tk.Label(
            self._canvas,
            text="",
            font=(_OVERLAY_FONT[0], self._font_size, _OVERLAY_FONT[2]),
            fg=TEXT,
            bg=SURFACE,
            bd=0,
        )

        self.root.withdraw()
        self._ready.set()
        self.root.mainloop()

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------

    def _rounded_pill(self, w: int, h: int, fill: str, outline: str) -> None:
        """Dibuja una píldora de esquinas completamente redondeadas."""
        assert self._canvas is not None
        r = h // 2
        c = self._canvas
        c.create_oval(0, 0, 2 * r, h, fill=fill, outline=outline)
        c.create_oval(w - 2 * r, 0, w, h, fill=fill, outline=outline)
        c.create_rectangle(r, 0, w - r, h, fill=fill, outline=fill)
        c.create_line(r, 0, w - r, 0, fill=outline)
        c.create_line(r, h - 1, w - r, h - 1, fill=outline)

    def _render(self, text: str, fg: str, dot: str) -> None:
        """Redibuja la píldora completa. SOLO desde el thread de tkinter."""
        if self.root is None:
            return
        if self._layered and self._render_layered(text, fg, dot):
            return
        if self._canvas is None or self._label is None:
            return

        self._label.config(text=text, fg=fg, bg=SURFACE)
        self._label.update_idletasks()
        tw = self._label.winfo_reqwidth()
        th = self._label.winfo_reqheight()

        w = _PAD_X + _DOT_RADIUS * 2 + _DOT_GAP + tw + _PAD_X
        h = th + _PAD_Y * 2

        self._canvas.delete("all")
        self._dot_item = None
        self._canvas.config(width=w, height=h)
        self._rounded_pill(w, h, SURFACE, BORDER)

        cx = _PAD_X + _DOT_RADIUS
        cy = h // 2
        # Se guarda el id del punto: buscarlo por posición en la lista de
        # figuras se rompe en cuanto cambia el dibujo de la píldora.
        self._dot_item = self._canvas.create_oval(
            cx - _DOT_RADIUS, cy - _DOT_RADIUS,
            cx + _DOT_RADIUS, cy + _DOT_RADIUS,
            fill=dot, outline=dot,
        )
        self._canvas.create_window(
            _PAD_X + _DOT_RADIUS * 2 + _DOT_GAP, cy, anchor="w", window=self._label
        )
        self._position_window(w, h)
        self.root.deiconify()

    def _render_layered(self, text: str, fg: str, dot: str) -> bool:
        """Dibuja la píldora suavizada y la sube como contenido de la ventana.

        Devuelve False si el camino no está disponible, para caer al Canvas.
        """
        assert self.root is not None
        try:
            imagen = pill.render_pill(
                text, fg, dot, SURFACE, BORDER,
                font_size=self._font_size,
                scale=self._scale,
                pad_x=_PAD_X, pad_y=_PAD_Y,
                dot_radius=_DOT_RADIUS, dot_gap=_DOT_GAP,
            )
            if self._opacity < 1.0:
                canal = imagen.getchannel("A").point(
                    lambda v: int(v * self._opacity)
                )
                imagen.putalpha(canal)

            # UpdateLayeredWindow trabaja en píxeles físicos y fija tamaño y
            # posición por su cuenta; tkinter razona en lógicos.
            x, y = self._physical_position(imagen.width, imagen.height)
            tamano = (
                max(1, int(imagen.width / self._scale)),
                max(1, int(imagen.height / self._scale)),
            )
            # Sólo cuando cambia de verdad: UpdateLayeredWindow ya fija tamaño y
            # posición, así que remapear en cada fotograma sólo produce parpadeo.
            if tamano != self._shown_size:
                self.root.geometry(f"{tamano[0]}x{tamano[1]}")
                self.root.deiconify()
                self.root.update_idletasks()
                self._shown_size = tamano

            hwnd = pill.top_level_hwnd(self.root.winfo_id())
            if not pill.push_layered(hwnd, imagen, x, y):
                self._layered = False
                return False
            return True
        except Exception as exc:  # pragma: no cover - depende de la plataforma
            log.warning("Sin dibujo suavizado del overlay (%s); usando Canvas.", exc)
            self._layered = False
            return False

    def _physical_position(self, w: int, h: int) -> tuple[int, int]:
        """Esquina donde va la píldora, en píxeles físicos."""
        sw, sh = pill.screen_size_physical()
        if sw <= 0 or sh <= 0:  # pragma: no cover - fuera de Windows
            return self._screen_position(w, h)
        margen = int(round(20 * self._scale))
        barra = int(round(48 * self._scale))
        posiciones = {
            "bottom-right": (sw - w - margen, sh - h - margen - barra),
            "bottom-left":  (margen,           sh - h - margen - barra),
            "top-right":    (sw - w - margen,  margen),
            "top-left":      (margen,          margen),
        }
        return posiciones.get(self._position, posiciones["bottom-right"])

    def _screen_position(self, w: int, h: int) -> tuple[int, int]:
        """Esquina donde va la píldora, en coordenadas lógicas de tkinter."""
        assert self.root is not None
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        margen = 20
        posiciones = {
            "bottom-right": (sw - w - margen, sh - h - margen - 48),
            "bottom-left":  (margen,           sh - h - margen - 48),
            "top-right":    (sw - w - margen,  margen),
            "top-left":     (margen,           margen),
        }
        return posiciones.get(self._position, posiciones["bottom-right"])

    def _set_state(self, state_key: str, text: str | None = None) -> None:
        """Actualiza el estado visual. SOLO llamar desde el thread de tkinter."""
        if not self._enabled or self.root is None:
            return
        state = STATES.get(state_key)
        if state is None:
            self.root.withdraw()
            self._shown_size = None
            return
        self._dot_color = state["dot"]
        self._pulse_state = state_key
        self._pulse_text = text if text is not None else state["text"]
        self._render(self._pulse_text, state["fg"], state["dot"])
        if state.get("pulse"):
            self._start_pulse()

    def _position_window(self, w: int, h: int) -> None:
        """Calcula y aplica la posición según la configuración."""
        assert self.root is not None
        x, y = self._screen_position(w, h)
        self.root.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Animaciones — sólo en el thread de tkinter
    # ------------------------------------------------------------------

    def _cancel_jobs(self) -> None:
        for attr in ("_anim_job", "_pulse_job"):
            job = getattr(self, attr)
            if job is not None and self.root is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:  # pragma: no cover - el job ya expiró
                    pass
            setattr(self, attr, None)

    def _start_pulse(self) -> None:
        self._pulse_tick = 0
        self._tick_pulse()

    def _tick_pulse(self) -> None:
        """Respira el punto de estado entre su color pleno y uno apagado."""
        if self.root is None or self._canvas is None:
            return
        phase = self._pulse_tick % (_PULSE_STEPS * 2)
        step = phase if phase < _PULSE_STEPS else (_PULSE_STEPS * 2 - phase)
        shade = _blend(self._dot_color, SURFACE, (step / _PULSE_STEPS) * _PULSE_DEPTH)

        if self._layered:
            estado = STATES.get(self._pulse_state) or {}
            self._render(self._pulse_text, estado.get("fg", TEXT), shade)
        elif self._dot_item is not None:
            try:
                self._canvas.itemconfig(self._dot_item, fill=shade, outline=shade)
            except Exception:  # pragma: no cover - la figura ya no existe
                return
        self._pulse_tick += 1
        self._pulse_job = self.root.after(_PULSE_INTERVAL_MS, self._tick_pulse)

    def _start_processing(self) -> None:
        self._cancel_jobs()
        self._anim_tick = 0
        self._anim_started = time.monotonic()
        self._tick_processing()

    def _tick_processing(self) -> None:
        if self.root is None:
            return
        base = STATES["processing"]["text"]
        dots = "." * (self._anim_tick % 3 + 1)
        elapsed = time.monotonic() - self._anim_started
        suffix = f"   {int(elapsed)}s" if elapsed >= _PROCESSING_ELAPSED_AFTER_S else ""
        self._set_state("processing", f"{base}{dots}{suffix}")
        self._anim_tick += 1
        self._anim_job = self.root.after(_PROCESSING_INTERVAL_MS, self._tick_processing)

    def _show_transient(self, state_key: str, message: str | None, hide_ms: int) -> None:
        self._cancel_jobs()
        self._set_state(state_key, message)
        if hide_ms > 0 and self.root is not None:
            self._anim_job = self.root.after(hide_ms, lambda: self._set_state("hidden"))

    # ------------------------------------------------------------------
    # API pública — thread-safe via root.after(0, fn)
    # ------------------------------------------------------------------

    def _dispatch(self, fn) -> None:
        if self._enabled and self.root:
            self.root.after(0, fn)

    def _plain(self, state_key: str) -> None:
        self._cancel_jobs()
        self._set_state(state_key)

    def show_ptt(self) -> None:
        """Mostrar indicador PTT. Llamar desde cualquier thread."""
        self._dispatch(lambda: self._plain("ptt"))

    def show_toggle(self) -> None:
        """Mostrar indicador toggle. Llamar desde cualquier thread."""
        self._dispatch(lambda: self._plain("toggle"))

    def show_processing(self) -> None:
        """Mostrar indicador animado de transcripción en curso.

        Cubre la ventana entre soltar la tecla y ver el texto pegado, que sin
        indicador se percibe como que la aplicación dejó de funcionar.
        """
        self._dispatch(self._start_processing)

    def show_loading(self) -> None:
        """Mostrar indicador de carga. Llamar desde cualquier thread."""
        self._dispatch(lambda: self._plain("loading"))

    def show_cancelled(self) -> None:
        """Confirmar que el dictado se descartó, y desaparecer."""
        self._dispatch(
            lambda: self._show_transient("cancelled", None, _CANCELLED_AUTO_HIDE_MS)
        )

    def show_error(self, message: str, auto_hide_ms: int = _ERROR_AUTO_HIDE_MS) -> None:
        """Mostrar aviso de error. Llamar desde cualquier thread.

        Se oculta solo: un error puntual no debe dejar un cartel permanente
        sobre el escritorio. Pasar ``auto_hide_ms=0`` para que quede fijo.
        """
        self._dispatch(lambda: self._show_transient("error", message, auto_hide_ms))

    def hide(self) -> None:
        """Ocultar el overlay. Llamar desde cualquier thread."""
        self._dispatch(lambda: self._plain("hidden"))

    def destroy(self) -> None:
        """Destruir la ventana tkinter al cerrar la app. Thread-safe."""
        self._dispatch(lambda: (self._cancel_jobs(), self.root.destroy()))

"""Icono de bandeja del sistema via pystray."""

from __future__ import annotations

import logging
import pathlib
import sys
import threading
import time
import tkinter as tk
from typing import Callable

from PIL import Image, ImageDraw

from whisperkey.state import AppState

logger = logging.getLogger(__name__)


def _assets_dir() -> pathlib.Path:
    """Devuelve el directorio de íconos, compatible con PyInstaller y desarrollo."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller bundle (onedir — _MEIPASS apunta a _internal/)
        return pathlib.Path(sys._MEIPASS) / "assets" / "icons"
    return pathlib.Path(__file__).parent.parent / "assets" / "icons"


def _load_icon(name: str, fallback_color: str) -> Image.Image:
    """Carga un ícono desde *assets/icons/* o genera un cuadrado de fallback."""
    path = _assets_dir() / name
    if path.exists():
        return Image.open(path).convert("RGBA")
    image = Image.new("RGB", (64, 64), fallback_color)
    d = ImageDraw.Draw(image)
    d.rectangle([16, 16, 48, 48], fill="white")
    return image


def _update_tray_icon(icon, state: AppState, config: dict | None = None) -> None:
    ptt_key = config["hotkeys"]["ptt"] if config else "PTT"
    if state.get_loading():
        icon.icon = _load_icon("tray_loading.png", "yellow")
        icon.title = "WhisperKey \u2014 Cargando modelo..."
    elif state.model is not None:
        icon.icon = _load_icon("tray_ready.png", "green")
        icon.title = f"WhisperKey \u2014 Listo | PTT: {ptt_key}"
    else:
        icon.icon = _load_icon("tray_idle.png", "gray")
        icon.title = "WhisperKey \u2014 Sin modelo (clic derecho para cargar)"


def start_tray(
    state: AppState,
    config: dict,
    on_load: Callable[[], None],
    on_unload: Callable[[], None],
    on_quit: Callable[[object], None],
    master: tk.Tk | None = None,
) -> None:
    """Crea el icono de bandeja y lo ejecuta. NO bloquea — debe llamarse desde un thread daemon."""

    import pystray

    icon = pystray.Icon(
        "WhisperKey",
        _load_icon("tray_idle.png", "gray"),
        "WhisperKey \u2014 Sin modelo (clic derecho para cargar)",
    )

    def _load(_icon, _item):
        on_load()

    def _unload(_icon, _item):
        on_unload()

    def _quit(_icon, _item):
        state.shutdown_event.set()
        on_quit(_icon)

    def _settings(_icon, _item):
        if master is not None:
            master.after(0, _open_settings)

    def _open_settings() -> None:
        try:
            from whisperkey.settings_gui import SettingsGUI
            SettingsGUI(master=master, config=config)
        except Exception as exc:
            logger.warning("No se pudo abrir SettingsGUI: %s", exc)

    def _build_menu() -> pystray.Menu:
        """Construye el menú dinámicamente según el estado del modelo."""
        items: list = []
        if state.model is not None:
            items.append(pystray.MenuItem("Descargar modelo", _unload))
        else:
            items.append(pystray.MenuItem("Cargar modelo", _load))
        items.append(pystray.MenuItem("Configuración", _settings))
        items.append(pystray.MenuItem("Salir", _quit))
        return pystray.Menu(*items)

    # Menú inicial
    icon.menu = _build_menu()

    def _poll_state() -> None:
        """Actualiza el ícono y el menú de bandeja cuando cambia el estado del modelo."""
        last_status: str | None = None
        while not state.shutdown_event.is_set():
            if state.get_loading():
                current = "loading"
            elif state.model is not None:
                current = "ready"
            else:
                current = "idle"
            if current != last_status:
                try:
                    _update_tray_icon(icon, state, config)
                    icon.menu = _build_menu()
                except Exception:
                    pass
                last_status = current
            time.sleep(0.5)

    poller = threading.Thread(target=_poll_state, daemon=True, name="tray-poller")
    poller.start()
    logger.info("Tray iniciado.")
    try:
        icon.run()
    except Exception as exc:
        logger.warning(
            "No se pudo iniciar el icono de bandeja: %s. Continuando sin tray...",
            exc,
        )
        state.shutdown_event.wait()

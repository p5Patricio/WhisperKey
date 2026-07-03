"""Listener de teclado via pynput."""

from __future__ import annotations

import logging
import os

from pynput import keyboard as kb

from whisperkey.state import AppState

logger = logging.getLogger(__name__)

if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    logger.warning(
        "Wayland detectado. Los atajos globales pueden no funcionar correctamente."
    )

_active_keys: set = set()
_toggle_lock = False


def resolve_key(key_str: str):
    """Convierte string a pynput Key o KeyCode. Lanza ValueError si no reconoce la tecla."""
    key_str = key_str.strip().lower()
    try:
        return kb.Key[key_str]  # teclas especiales: caps_lock, f9, alt, shift, ctrl...
    except KeyError:
        pass
    if len(key_str) == 1:
        return kb.KeyCode.from_char(key_str)
    raise ValueError(
        f"Hotkey no reconocida: '{key_str}'. "
        "Opciones: caps_lock, f1-f12, alt, shift, ctrl, scroll_lock, etc."
    )


def start_listener(
    state: AppState,
    config: dict,
    overlay,
    sounds,
) -> kb.Listener:
    """Crea e inicia el Listener de teclado.

    PTT y toggle se leen desde config["hotkeys"].
    """
    global _active_keys, _toggle_lock
    _active_keys = set()
    _toggle_lock = False

    # — Resolver teclas desde config —
    ptt_key = resolve_key(config["hotkeys"]["ptt"])

    toggle_raw = config["hotkeys"]["toggle"]
    if isinstance(toggle_raw, list):
        toggle_key = resolve_key(toggle_raw[0]) if toggle_raw else None
    else:
        toggle_key = resolve_key(toggle_raw) if toggle_raw else None

    load_model_key_str = config["hotkeys"].get("load_model_key", "").strip()
    load_model_key = resolve_key(load_model_key_str) if load_model_key_str else None

    logger.debug("PTT key: %s | Toggle key: %s | Load model key: %s", ptt_key, toggle_key, load_model_key)

    def on_press(key):
        global _toggle_lock

        if state.shutdown_event.is_set():
            return

        if state.model is None:
            if key == toggle_key or key == ptt_key:
                sounds.play_error()
            return

        # — PTT: push-to-talk —
        if key == ptt_key:
            if not state.get_ptt():
                state.set_ptt(True)
                sounds.play_start()
                overlay.show_ptt()

        # — Toggle single key —
        if toggle_key is not None and key == toggle_key and not _toggle_lock:
            _toggle_lock = True
            new_toggle = not state.get_toggle()
            state.set_toggle(new_toggle)
            if new_toggle:
                sounds.play_start()
                overlay.show_toggle()
                logger.info("Toggle ON")
            else:
                state.put_sentinel()
                sounds.play_stop()
                overlay.hide()
                logger.info("Toggle OFF")

        # — Load/unload model key —
        if load_model_key is not None and key == load_model_key:
            if state.model is None:
                logger.info("Cargando modelo por hotkey...")
                state.set_load_requested(True)
            else:
                logger.info("Descargando modelo por hotkey...")
                state.set_unload_requested(True)

    def on_release(key):
        global _toggle_lock

        if state.shutdown_event.is_set():
            return

        # — PTT: fin push-to-talk —
        if key == ptt_key and state.get_ptt():
            state.set_ptt(False)
            state.put_sentinel()
            sounds.play_stop()
            overlay.hide()

        # — Resetear toggle lock al soltar la tecla —
        if toggle_key is not None and key == toggle_key:
            _toggle_lock = False

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener

"""Inyección de texto via pyperclip + atajo de plataforma."""

from __future__ import annotations

import logging
import time

import pyperclip
from pynput import keyboard

from whisperkey.errors import InjectionError
from whisperkey.platform import get_platform

log = logging.getLogger(__name__)
_CLIPBOARD_SIZE_LIMIT = 5 * 1024 * 1024

_KEY_MAP = {
    "ctrl": keyboard.Key.ctrl,
    "command": keyboard.Key.cmd,
    "alt": keyboard.Key.alt,
    "shift": keyboard.Key.shift,
}

_platform = get_platform()


def inject_text(text: str, pre_delay_ms: int = 150, post_delay_ms: int = 400) -> None:
    """Inyecta *text* en la aplicación activa via clipboard + atajo de plataforma.

    1. No-op si *text* es vacío.
    2. Guarda el contenido previo del clipboard (si es texto y <= 5 MB).
    3. Copia *text* al clipboard.
    4. Espera *pre_delay_ms* ms para que el clipboard se registre.
    5. Envía el atajo de pegar según la plataforma via pynput.
    6. Espera *post_delay_ms* ms para que la app procese el paste antes de continuar.
    7. Restaura el clipboard previo si se había guardado.
    """
    if not text:
        return

    previous = None
    should_restore = False
    try:
        previous = pyperclip.paste()
        if previous is not None and isinstance(previous, str):
            size = len(previous.encode("utf-8"))
            should_restore = size <= _CLIPBOARD_SIZE_LIMIT
    except Exception:
        pass

    try:
        pyperclip.copy(text)
        time.sleep(pre_delay_ms / 1000)

        shortcut = _platform.get_paste_shortcut()
        modifier = _KEY_MAP[shortcut[0]]
        char_key = shortcut[1]

        controller = keyboard.Controller()
        with controller.pressed(modifier):
            controller.press(char_key)
            controller.release(char_key)

        time.sleep(post_delay_ms / 1000)
    except Exception as exc:
        raise InjectionError(f"Fallo al inyectar texto: {exc}") from exc
    finally:
        if should_restore:
            try:
                pyperclip.copy(previous)
            except Exception:
                pass

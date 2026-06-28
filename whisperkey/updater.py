"""Verificación de actualizaciones desde GitHub Releases."""

from __future__ import annotations

import logging
import tkinter as tk
import webbrowser
from typing import Any

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

VERSION = "1.0.0"
_REPO = "p5Patricio/WhisperKey"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"


def check_update() -> tuple[bool, str, str, str]:
    """Consulta GitHub Releases y compara con VERSION.

    Retorna:
        (hay_actualizacion, version_nueva, url, changelog)
    """
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests no está instalado") from exc

    resp = requests.get(_API_URL, timeout=15)
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()

    latest_tag: str = data.get("tag_name", "")
    latest_version = latest_tag.lstrip("v")
    html_url: str = data.get("html_url", "")
    body: str = data.get("body", "Sin notas de release.")

    def _parse(v: str) -> tuple[int, ...]:
        parts = v.split(".")
        return tuple(int(p) for p in parts if p.isdigit())

    current = _parse(VERSION)
    latest = _parse(latest_version)

    # Rellenar con ceros para comparar igual longitud
    length = max(len(current), len(latest))
    current = current + (0,) * (length - len(current))
    latest = latest + (0,) * (length - len(latest))

    is_newer = latest > current
    return is_newer, latest_version, html_url, body


def show_update_dialog(
    root: tk.Tk | None,
    version: str,
    url: str,
    changelog: str = "",
) -> None:
    """Muestra un diálogo modal con información de la actualización."""
    if ctk is None:
        log.warning("customtkinter no disponible; no se puede mostrar diálogo de actualización")
        return

    dialog = ctk.CTkToplevel(root)
    dialog.title("Actualización disponible")
    dialog.geometry("450x350")
    dialog.resizable(False, False)
    if root is not None:
        dialog.transient(root)
        dialog.grab_set()

    ctk.CTkLabel(dialog, text=f"Nueva versión: {version}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
    ctk.CTkLabel(dialog, text=f"Versión actual: {VERSION}", font=ctk.CTkFont(size=12)).pack(pady=2)

    textbox = ctk.CTkTextbox(dialog, width=400, height=150)
    textbox.pack(padx=10, pady=10)
    textbox.insert("0.0", changelog or "Sin notas de release.")
    textbox.configure(state="disabled")

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=10)

    def _download() -> None:
        webbrowser.open(url)
        dialog.destroy()

    ctk.CTkButton(btn_frame, text="Descargar", command=_download, width=120).pack(side="left", padx=10)
    ctk.CTkButton(btn_frame, text="Más tarde", command=dialog.destroy, width=120).pack(side="left", padx=10)

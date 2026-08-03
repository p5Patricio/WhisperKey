"""Verificación de actualizaciones desde GitHub Releases."""

from __future__ import annotations

import hashlib
import logging
import pathlib
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
from typing import Any

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    ctk = None  # type: ignore[assignment]

from whisperkey.version import __version__ as VERSION

log = logging.getLogger(__name__)

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

    length = max(len(current), len(latest))
    current = current + (0,) * (length - len(current))
    latest = latest + (0,) * (length - len(latest))

    is_newer = latest > current
    return is_newer, latest_version, html_url, body


def _get_release_assets() -> list[dict[str, Any]]:
    """Fetch release assets from GitHub API."""
    try:
        import requests
    except ImportError:
        return []

    try:
        resp = requests.get(_API_URL, timeout=15)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data.get("assets", [])
    except Exception as exc:
        log.error("Failed to fetch release assets: %s", exc)
        return []


def _get_installer_url_and_hash() -> tuple[str, str]:
    """Get installer download URL and SHA256 hash from release assets.

    Returns:
        (download_url, sha256_hash) — hash may be empty if not found.
    """
    assets = _get_release_assets()
    download_url = ""
    sha256_hash = ""

    for asset in assets:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            download_url = asset.get("browser_download_url", "")
        if name.lower().endswith(".sha256") or "sha256" in name.lower():
            try:
                import requests
                sha_url = asset.get("browser_download_url", "")
                if sha_url:
                    resp = requests.get(sha_url, timeout=15)
                    resp.raise_for_status()
                    sha256_hash = resp.text.strip().split()[0]
            except Exception as exc:
                log.error("Failed to fetch SHA256 file: %s", exc)

    return download_url, sha256_hash


def download_installer(url: str, dest: pathlib.Path) -> bool:
    """Download installer from URL to dest path with progress."""
    try:
        import requests
    except ImportError as exc:
        log.error("requests not installed: %s", exc)
        return False

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        log.info("Downloading: %.1f%%", progress)

        log.info("Download completed: %s", dest)
        return True
    except Exception as exc:
        log.error("Download failed: %s", exc)
        return False


def verify_sha256(filepath: pathlib.Path, expected_hash: str) -> bool:
    """Verify SHA256 hash of downloaded file."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        actual_hash = sha256_hash.hexdigest()
        if actual_hash == expected_hash:
            log.info("SHA256 verification passed")
            return True
        else:
            log.error("SHA256 mismatch: expected %s, got %s", expected_hash, actual_hash)
            return False
    except Exception as exc:
        log.error("SHA256 verification failed: %s", exc)
        return False


def launch_silent_install(installer_path: pathlib.Path) -> bool:
    """Launch installer with silent flags and exit app."""
    try:
        current_dir = pathlib.Path(sys.executable).parent

        cmd = [
            str(installer_path),
            "/SILENT",
            f"/DIR=\"{current_dir}\"",
            "/CLOSEAPPLICATIONS",
        ]

        log.info("Launching silent install: %s", " ".join(cmd))
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)

        log.info("Exiting app for update...")
        sys.exit(0)
        return True
    except Exception as exc:
        log.error("Failed to launch installer: %s", exc)
        return False


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

    dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    if root is not None:
        dialog.transient(root)
        dialog.grab_set()

    ctk.CTkLabel(dialog, text=f"Nueva versión: {version}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
    ctk.CTkLabel(dialog, text=f"Versión actual: {VERSION}", font=ctk.CTkFont(size=12)).pack(pady=2)

    textbox = ctk.CTkTextbox(dialog, width=400, height=100)
    textbox.pack(padx=10, pady=10)
    textbox.insert("0.0", changelog or "Sin notas de release.")
    textbox.configure(state="disabled")

    progress_label = ctk.CTkLabel(dialog, text="")
    progress_label.pack(pady=5)

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=10)

    def _on_update_now() -> None:
        installer_url, expected_hash = _get_installer_url_and_hash()
        if not installer_url:
            installer_url = url

        temp_dir = pathlib.Path(tempfile.gettempdir())
        installer_path = temp_dir / "WhisperKey-Setup.exe"

        progress_label.configure(text="Downloading...")
        dialog.update_idletasks()

        if not download_installer(installer_url, installer_path):
            progress_label.configure(text="Download failed!", text_color="red")
            return

        if expected_hash:
            progress_label.configure(text="Verifying...")
            dialog.update_idletasks()
            if not verify_sha256(installer_path, expected_hash):
                progress_label.configure(text="Verification failed!", text_color="red")
                return

        progress_label.configure(text="Launching installer...")
        dialog.update_idletasks()

        if not launch_silent_install(installer_path):
            progress_label.configure(text="Installation failed!", text_color="red")

    def _download_manual() -> None:
        webbrowser.open(url)
        dialog.destroy()

    ctk.CTkButton(btn_frame, text="Update now", command=_on_update_now, width=200).pack(pady=5)
    ctk.CTkButton(
        btn_frame,
        text="Download manually",
        command=_download_manual,
        width=200,
        fg_color="gray40",
    ).pack(pady=2)

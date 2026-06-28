"""Implementación de BasePlatform para Windows."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from whisperkey.platform.base import BasePlatform

log = logging.getLogger(__name__)


class WindowsPlatform(BasePlatform):
    """Plataforma Windows: winsound, Ctrl+V, nvidia-smi, .vbs."""

    def play_beep(self, freq: int, duration: float) -> None:
        import winsound

        winsound.Beep(freq, int(duration * 1000))

    def get_paste_shortcut(self) -> tuple[str, str]:
        return ("ctrl", "v")

    def detect_gpu(self) -> tuple[str, str]:
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            return ("cpu", "int8")
        try:
            result = subprocess.run(
                [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return ("cuda", "int8_float16")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return ("cpu", "int8")

    def get_project_root(self) -> Path:
        return Path(__file__).parent.parent.parent.resolve()

    def get_venv_python(self) -> Path:
        return self.get_project_root() / ".venv" / "Scripts" / "python.exe"

    def generate_launcher(self) -> None:
        """Generar lanzador.vbs en la raíz del proyecto."""
        here = self.get_project_root()
        pythonw = self.get_venv_python().with_name("pythonw.exe")
        launcher_vbs = here / "lanzador.vbs"

        if not pythonw.exists():
            log.warning(
                "pythonw.exe no encontrado en %s. El lanzador puede no funcionar.",
                pythonw,
            )

        lines = [
            "' WhisperKey — Lanzador sin ventana de consola",
            "' Generado por install.py — no editar manualmente.",
            'Set WshShell = CreateObject("WScript.Shell")',
            f'WshShell.CurrentDirectory = "{here}"',
            f'WshShell.Run """{pythonw}""" & " -m whisperkey", 0, False',
            "Set WshShell = Nothing",
        ]
        content = "\n".join(lines) + "\n"
        launcher_vbs.write_text(content, encoding="utf-8")
        log.info("lanzador.vbs generado en %s", launcher_vbs)

    def _get_startup_path(self) -> Path:
        return (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / "WhisperKey.vbs"
        )

    def setup_autostart(self) -> None:
        """Copiar lanzador.vbs al directorio de inicio automático de Windows."""
        here = self.get_project_root()
        launcher_vbs = here / "lanzador.vbs"
        if not launcher_vbs.exists():
            self.generate_launcher()

        startup_dest = self._get_startup_path()
        startup_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(launcher_vbs, startup_dest)
        log.info("Copiado a Inicio automático: %s", startup_dest)

    def remove_autostart(self) -> None:
        """Eliminar lanzador.vbs del directorio de inicio automático."""
        startup_dest = self._get_startup_path()
        if startup_dest.exists():
            try:
                startup_dest.unlink()
                log.info("Eliminado de Inicio automático: %s", startup_dest)
            except Exception as exc:
                log.warning("No se pudo eliminar de Inicio automático: %s", exc)

    def is_autostart_enabled(self) -> bool:
        """Retorna True si WhisperKey.vbs existe en el directorio de Startup."""
        return self._get_startup_path().exists()

"""Implementación de BasePlatform para macOS."""

from __future__ import annotations

import logging
import platform as plat
import subprocess
from pathlib import Path

from whisperkey.platform.base import BasePlatform

log = logging.getLogger(__name__)


class MacPlatform(BasePlatform):
    """Plataforma macOS: osascript, Cmd+V, launchd plist + run.sh."""

    def play_beep(self, freq: int, duration: float) -> None:
        import os

        try:
            os.system("osascript -e 'beep'")
        except Exception:
            print("\a")

    def get_paste_shortcut(self) -> tuple[str, str]:
        return ("command", "v")

    def detect_gpu(self) -> tuple[str, str]:
        if plat.machine() == "arm64":
            try:
                import torch

                if torch.backends.mps.is_available():
                    return ("mps", "float16")
            except Exception:
                # torch no instalado todavía (install.py)
                return ("mps", "float16")
        return ("cpu", "int8")

    def get_project_root(self) -> Path:
        return Path(__file__).parent.parent.parent.resolve()

    def get_venv_python(self) -> Path:
        return self.get_project_root() / ".venv" / "bin" / "python"

    def generate_launcher(self) -> None:
        """Generar run.sh en la raíz del proyecto."""
        here = self.get_project_root()
        python = self.get_venv_python()
        run_sh = here / "run.sh"

        lines = [
            "#!/bin/bash",
            "# WhisperKey — Lanzador",
            "# Generado por install.py — no editar manualmente.",
            f"cd '{here}'",
            f"nohup '{python}' -m whisperkey >/dev/null 2>&1 &",
            "echo $! > whisperkey.pid",
        ]
        content = "\n".join(lines) + "\n"
        run_sh.write_text(content, encoding="utf-8")
        run_sh.chmod(0o755)
        log.info("run.sh generado en %s", run_sh)

    def _get_plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / "com.whisperkey.plist"

    def setup_autostart(self) -> None:
        """Crear y cargar LaunchAgent."""
        here = self.get_project_root()
        python = self.get_venv_python()

        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist_path = self._get_plist_path()

        plist_content = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whisperkey</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>whisperkey</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{here}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
        plist_path.write_text(plist_content, encoding="utf-8")

        try:
            subprocess.run(
                ["launchctl", "load", str(plist_path)],
                check=True,
                capture_output=True,
            )
            log.info("LaunchAgent cargado: %s", plist_path)
        except Exception as exc:
            log.warning("No se pudo cargar el LaunchAgent: %s", exc)

    def remove_autostart(self) -> None:
        """Descargar y eliminar LaunchAgent."""
        plist_path = self._get_plist_path()
        try:
            if plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(plist_path)],
                    check=True,
                    capture_output=True,
                )
                plist_path.unlink()
                log.info("LaunchAgent descargado")
        except Exception as exc:
            log.warning("No se pudo descargar el LaunchAgent: %s", exc)

    def is_autostart_enabled(self) -> bool:
        """Retorna True si el plist existe."""
        return self._get_plist_path().exists()

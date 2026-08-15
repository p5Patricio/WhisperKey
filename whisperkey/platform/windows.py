"""Implementación de BasePlatform para Windows."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
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

    def get_install_dir(self) -> Path:
        """Return install directory (frozen) or project root (dev)."""
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent
        return self.get_project_root()

    def get_appdata_dir(self) -> Path:
        """Return %APPDATA%/WhisperKey/ (frozen) or project root (dev)."""
        if getattr(sys, 'frozen', False):
            return Path(os.environ['APPDATA']) / 'WhisperKey'
        return self.get_project_root()

    def get_cuda_bin_dir(self) -> Path:
        """Writable dir for the on-demand CUDA engine.

        Frozen: %APPDATA%/WhisperKey/bin-cuda (install dir is read-only).
        Dev: <project_root>/assets/bin-cuda.
        """
        if getattr(sys, 'frozen', False):
            return Path(os.environ['APPDATA']) / 'WhisperKey' / 'bin-cuda'
        return self.get_project_root() / 'assets' / 'bin-cuda'

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

    # Nombre del valor en HKCU\...\Run (debe coincidir con installer/whisperkey.iss).
    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _RUN_VALUE = "WhisperKey"

    def _is_frozen(self) -> bool:
        return getattr(sys, "frozen", False)

    def setup_autostart(self) -> None:
        """Habilitar inicio automático.

        Congelado: escribe HKCU\\...\\Run apuntando al .exe (igual que el instalador).
        Dev: copia lanzador.vbs al directorio de Startup.
        """
        if self._is_frozen():
            import winreg

            exe = str(Path(sys.executable).resolve())
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, self._RUN_VALUE, 0, winreg.REG_SZ, f'"{exe}"')
            log.info("Inicio automático habilitado (registro): %s", exe)
            return

        here = self.get_project_root()
        launcher_vbs = here / "lanzador.vbs"
        if not launcher_vbs.exists():
            self.generate_launcher()

        startup_dest = self._get_startup_path()
        startup_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(launcher_vbs, startup_dest)
        log.info("Copiado a Inicio automático: %s", startup_dest)

    def remove_autostart(self) -> None:
        """Deshabilitar inicio automático (registro si congelado, si no el .vbs)."""
        if self._is_frozen():
            import winreg

            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.DeleteValue(key, self._RUN_VALUE)
                log.info("Inicio automático deshabilitado (registro).")
            except FileNotFoundError:
                pass
            except Exception as exc:
                log.warning("No se pudo eliminar el autostart del registro: %s", exc)
            return

        startup_dest = self._get_startup_path()
        if startup_dest.exists():
            try:
                startup_dest.unlink()
                log.info("Eliminado de Inicio automático: %s", startup_dest)
            except Exception as exc:
                log.warning("No se pudo eliminar de Inicio automático: %s", exc)

    def is_autostart_enabled(self) -> bool:
        """True si el autostart está configurado (registro si congelado, si no el .vbs)."""
        if self._is_frozen():
            import winreg

            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, self._RUN_KEY, 0, winreg.KEY_QUERY_VALUE
                ) as key:
                    winreg.QueryValueEx(key, self._RUN_VALUE)
                return True
            except FileNotFoundError:
                return False
            except Exception:
                return False

        return self._get_startup_path().exists()

    def acquire_single_instance_lock(
        self, app_name: str = "WhisperKey_SingleInstance_Mutex"
    ) -> tuple[bool, object | None]:
        """Adquiere un mutex con nombre en Windows para prevenir instancias duplicadas."""
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            ERROR_ALREADY_EXISTS = 183

            # Usar prefijo Local\ para aislar a la sesión de usuario actual
            mutex_name = f"Local\\{app_name}"
            mutex = kernel32.CreateMutexW(None, False, mutex_name)
            last_error = kernel32.GetLastError()
            if last_error == ERROR_ALREADY_EXISTS:
                if mutex:
                    kernel32.CloseHandle(mutex)
                return (False, None)
            return (True, mutex)
        except Exception as exc:
            log.warning("No se pudo verificar el mutex de instancia única: %s", exc)
            return (True, None)

    def release_single_instance_lock(self, handle: object | None) -> None:
        """Libera el mutex de instancia única en Windows."""
        if handle is not None:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass


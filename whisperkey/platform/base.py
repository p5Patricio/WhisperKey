"""BasePlatform: interfaz abstracta para comportamiento OS-specific."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BasePlatform(ABC):
    """Abstracción de plataforma que aísla hacks específicos de cada OS."""

    @abstractmethod
    def play_beep(self, freq: int, duration: float) -> None:
        """Emitir un beep de *freq* Hz durante *duration* segundos."""

    @abstractmethod
    def get_paste_shortcut(self) -> tuple[str, str]:
        """Retornar el atajo de teclado para pegar como tupla (modifier, key)."""

    @abstractmethod
    def detect_gpu(self) -> tuple[str, str]:
        """Detectar GPU y retornar (device, compute_type)."""

    @abstractmethod
    def setup_autostart(self) -> None:
        """Configurar inicio automático del sistema."""

    @abstractmethod
    def remove_autostart(self) -> None:
        """Deshabilitar inicio automático del sistema."""

    @abstractmethod
    def is_autostart_enabled(self) -> bool:
        """Retorna True si el inicio automático está configurado."""

    @abstractmethod
    def get_venv_python(self) -> Path:
        """Retornar el path al ejecutable de Python del entorno virtual."""

    @abstractmethod
    def get_project_root(self) -> Path:
        """Retornar el directorio raíz del proyecto."""

    # ------------------------------------------------------------------
    # Binary locations (whisper.cpp engine)
    # ------------------------------------------------------------------

    def get_bundled_bin_dir(self) -> Path:
        """Directorio del motor CPU incluido en el bundle (solo lectura al congelar).

        Frozen: <_MEIPASS>/assets/bin

        En dev se prefiere build/engine-cpu/Release, que es exactamente el
        directorio que WhisperKey.spec empaqueta. Si dev y prod no apuntan al
        mismo motor se depuran bugs que los usuarios no tienen — o se publican
        bugs que no se pueden reproducir.
        """
        import sys

        from whisperkey.engine import resolve_server_exe

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "assets" / "bin"

        root = self.get_project_root()
        shipped = root / "build" / "engine-cpu" / "Release"
        if resolve_server_exe(shipped) is not None:
            return shipped
        return root / "assets" / "bin"

    def get_cuda_bin_dir(self) -> Path:
        """Directorio ESCRIBIBLE para el motor CUDA descargado bajo demanda.

        Por defecto coincide con el bundle (dev / plataformas sin instalador).
        Windows lo sobrescribe hacia %APPDATA% cuando la app está congelada,
        porque el directorio de instalación (Program Files) es de solo lectura.
        """
        return self.get_project_root() / "assets" / "bin-cuda"

    # ------------------------------------------------------------------
    # Single Instance Locking
    # ------------------------------------------------------------------

    def acquire_single_instance_lock(
        self, app_name: str = "WhisperKey_SingleInstance_Mutex"
    ) -> tuple[bool, object | None]:
        """Adquiere un lock para asegurar instancia única.

        Retorna (True, handle) si es la única instancia, o (False, None) si ya existe otra.
        """
        return (True, None)

    def release_single_instance_lock(self, handle: object | None) -> None:
        """Libera el lock de instancia única si aplica."""
        pass


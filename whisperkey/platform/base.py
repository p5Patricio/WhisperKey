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

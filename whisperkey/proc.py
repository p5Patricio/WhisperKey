"""Lanzar procesos hijos sin que aparezca una ventana de consola.

En Windows, ejecutar una aplicación de consola desde un proceso sin consola
—como esta, que vive en la bandeja del sistema— **abre una ventana negra**,
aunque se redirija toda su salida. Redirigir los flujos no alcanza: hace falta
el flag CREATE_NO_WINDOW.

Se veía como un parpadeo de terminal al encender Windows, porque al arrancar se
consulta nvidia-smi dos veces (para detectar la GPU y para elegir el modelo).

Todo subproceso del paquete pasa por acá; hay un test que lo verifica.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

# 0 fuera de Windows: el flag no existe y sumarlo sería un error.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _sin_ventana(kwargs: dict[str, Any]) -> dict[str, Any]:
    if sys.platform == "win32":
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
    return kwargs


def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess:
    """`subprocess.run` que nunca muestra una consola."""
    return subprocess.run(*args, **_sin_ventana(kwargs))


def popen(*args: Any, **kwargs: Any) -> subprocess.Popen:
    """`subprocess.Popen` que nunca muestra una consola."""
    return subprocess.Popen(*args, **_sin_ventana(kwargs))

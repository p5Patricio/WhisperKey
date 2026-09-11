"""Ningún subproceso debe abrir una ventana de consola en Windows.

La aplicación vive en la bandeja del sistema y no tiene consola. En Windows,
lanzar desde ahí una aplicación de consola ABRE una ventana negra aunque se
redirija toda su salida: hace falta CREATE_NO_WINDOW. Se veía como un parpadeo
de terminal al encender la computadora, porque al arrancar se consulta
nvidia-smi dos veces (detección de GPU y elección del modelo).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from whisperkey import proc

PAQUETE = pathlib.Path(proc.__file__).parent
# Los módulos de macOS y Linux quedan fuera: ahí no existe el concepto.
EXENTOS = {"proc.py", "macos.py", "linux.py"}


def _modulos():
    return [
        p for p in PAQUETE.rglob("*.py")
        if "__pycache__" not in str(p) and p.name not in EXENTOS
    ]


@pytest.mark.parametrize("ruta", _modulos(), ids=lambda p: p.name)
def test_ningun_subproceso_directo(ruta: pathlib.Path) -> None:
    """Todo lanzamiento pasa por whisperkey.proc, que agrega el flag."""
    fuente = ruta.read_text(encoding="utf-8")
    for linea_n, linea in enumerate(fuente.splitlines(), 1):
        limpia = linea.strip()
        if limpia.startswith("#"):
            continue
        for llamada in ("subprocess.run(", "subprocess.Popen(", "subprocess.call("):
            if llamada in linea:
                pytest.fail(
                    f"{ruta.name}:{linea_n} llama a {llamada} directamente; "
                    f"usar proc.run / proc.popen para no abrir una consola"
                )


class TestFlagDeConsola:
    def test_en_windows_agrega_create_no_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        capturado = {}

        def falso(*args, **kwargs):
            capturado.update(kwargs)
            return MagicMock()

        monkeypatch.setattr(proc.sys, "platform", "win32")
        monkeypatch.setattr(proc, "CREATE_NO_WINDOW", 0x08000000)
        monkeypatch.setattr(subprocess, "run", falso)
        proc.run(["algo"], capture_output=True)

        assert capturado["creationflags"] & 0x08000000

    def test_conserva_los_flags_que_ya_venian(self, monkeypatch: pytest.MonkeyPatch) -> None:
        capturado = {}

        def falso(*args, **kwargs):
            capturado.update(kwargs)
            return MagicMock()

        monkeypatch.setattr(proc.sys, "platform", "win32")
        monkeypatch.setattr(proc, "CREATE_NO_WINDOW", 0x08000000)
        monkeypatch.setattr(subprocess, "Popen", falso)
        proc.popen(["algo"], creationflags=0x00000200)

        assert capturado["creationflags"] & 0x08000000
        assert capturado["creationflags"] & 0x00000200

    def test_fuera_de_windows_no_toca_nada(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """El flag no existe en otras plataformas; pasarlo sería un error."""
        capturado = {}

        def falso(*args, **kwargs):
            capturado.update(kwargs)
            return MagicMock()

        monkeypatch.setattr(proc.sys, "platform", "linux")
        monkeypatch.setattr(subprocess, "run", falso)
        proc.run(["algo"])

        assert "creationflags" not in capturado

    @pytest.mark.skipif(sys.platform != "win32", reason="sólo aplica en Windows")
    def test_la_constante_es_la_de_windows(self) -> None:
        assert proc.CREATE_NO_WINDOW == 0x08000000

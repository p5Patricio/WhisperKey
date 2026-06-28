"""Instalador de WhisperKey.

Uso: python install.py
Requiere: Python 3.12+.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

from whisperkey.platform import get_platform

TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
TORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu121"

platform = get_platform()

HERE = platform.get_project_root()
VENV_DIR = HERE / ".venv"
PYTHON = platform.get_venv_python()
REQUIREMENTS = HERE / "requirements.txt"


def step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def warn(msg: str) -> None:
    print(f"  AVISO  {msg}")


def fail(msg: str) -> None:
    print(f"\n  ERROR: {msg}")
    sys.exit(1)


# ── 1. Verificar Python ────────────────────────────────────────────────────────


def check_python() -> None:
    step(1, 5, "Verificando Python...")
    v = sys.version_info
    if v < (3, 12):
        fail(
            f"Se requiere Python 3.12 o superior. Tenés Python {v.major}.{v.minor}.\n"
            "  Descargá la versión correcta desde https://www.python.org/downloads/"
        )
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


# ── 2. Detectar GPU ───────────────────────────────────────────────────────────


def detect_gpu() -> bool:
    """Retorna True si se detectó GPU acelerada (CUDA o MPS)."""
    step(2, 5, "Detectando GPU...")
    device, _ = platform.detect_gpu()
    if device == "cuda":
        ok("GPU CUDA detectada")
        return True
    if device == "mps":
        ok("Apple Silicon MPS detectado")
        return True
    warn("No se detectó GPU acelerada. Se usará CPU.")
    return False


# ── 3. Crear entorno virtual ──────────────────────────────────────────────────


def create_venv() -> None:
    step(3, 5, "Creando entorno virtual...")
    if VENV_DIR.exists():
        warn(f".venv ya existe en {VENV_DIR}. Se reutilizará.")
        ok("Entorno virtual existente")
        return
    venv.create(str(VENV_DIR), with_pip=True)
    ok(f"Entorno virtual creado en {VENV_DIR}")


# ── 4. Instalar dependencias ──────────────────────────────────────────────────


def install_deps(has_gpu: bool) -> None:  # noqa: ARG001
    step(4, 5, "Instalando dependencias...")

    def run_pip(*args: str) -> None:
        cmd = [str(PYTHON), "-m", "pip", *args]
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            fail(f"pip falló con código {result.returncode}. Revisá el output de arriba.")

    run_pip("install", "--upgrade", "pip", "--quiet")
    ok("pip actualizado")

    device, _ = platform.detect_gpu()
    if device == "cuda":
        torch_index = TORCH_CUDA_INDEX
    elif device == "mps":
        torch_index = None
    else:
        torch_index = TORCH_CPU_INDEX

    if torch_index:
        print(f"  Instalando PyTorch desde {torch_index} (puede tardar varios minutos)...")
        run_pip("install", "torch", "--index-url", torch_index, "--quiet")
    else:
        print("  Instalando PyTorch (puede tardar varios minutos)...")
        run_pip("install", "torch", "--quiet")
    ok("PyTorch instalado")

    print("  Instalando dependencias del proyecto...")
    run_pip("install", "-r", str(REQUIREMENTS), "--quiet")
    ok("Dependencias instaladas")


# ── 5. Generar lanzador y autostart ───────────────────────────────────────────


def generate_launcher() -> None:
    step(5, 5, "Generando lanzador...")
    platform.generate_launcher()
    ok("Lanzador generado")

    print("\n  ¿Querés que WhisperKey inicie automáticamente? [s/N] s (Auto-seleccionado por asistente)")
    answer = "s"
    if answer in ("s", "si", "sí", "y", "yes"):
        try:
            platform.setup_autostart()
            ok("Inicio automático configurado")
        except Exception as exc:
            warn(f"No se pudo configurar inicio automático: {exc}")
    else:
        ok("Inicio automático omitido")


# ── Resumen ───────────────────────────────────────────────────────────────────


def print_summary() -> None:
    print("\n" + "=" * 60)
    print("  WhisperKey instalado correctamente")
    print("=" * 60)
    print(f"  Proyecto:     {HERE}")
    print(f"  Entorno:      {VENV_DIR}")
    print(f"  Python:       {PYTHON}")
    print()
    print("  Para iniciar WhisperKey:")
    if sys.platform == "win32":
        print("    Doble clic en lanzador.vbs")
    else:
        print("    ./run.sh")
    print()
    print("  Para iniciar desde terminal:")
    print(f"    {PYTHON} -m whisperkey")
    print("=" * 60 + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("\nWhisperKey — Instalador")
    print("=" * 60)

    check_python()
    has_gpu = detect_gpu()
    create_venv()
    install_deps(has_gpu)
    generate_launcher()
    print_summary()


if __name__ == "__main__":
    main()

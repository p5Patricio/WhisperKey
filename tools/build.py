"""Build script for WhisperKey using PyInstaller.

Canonical builder (invoked by installer/build.bat). Stages ONLY the lightweight
CPU whisper.cpp engine into the bundle; the CUDA engine (~670 MB) is downloaded
on first run when an NVIDIA GPU is detected, so the installer stays small.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Running `python tools/build.py` puts tools/ on sys.path, not the project root,
# so the `whisperkey` package would not be importable. Add the root explicitly.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from whisperkey.version import __version__

log = logging.getLogger(__name__)
DIST_DIR = PROJECT_ROOT / "dist" / "WhisperKey"

# CPU engine bundled with the installer (~8 MB). Must match transcription.py.
WHISPER_CPP_VERSION = "v1.9.2"
CPU_ENGINE_URL = (
    f"https://github.com/ggml-org/whisper.cpp/releases/download/"
    f"{WHISPER_CPP_VERSION}/whisper-bin-x64.zip"
)
ENGINE_STAGING = PROJECT_ROOT / "build" / "engine-cpu"
SERVER_EXE = "whisper-server.exe"


def stage_cpu_engine() -> Path:
    """Download + extract the CPU engine into a staging dir; return the bin dir."""
    bin_dir = _find_server_dir(ENGINE_STAGING)
    if bin_dir is None:
        ENGINE_STAGING.mkdir(parents=True, exist_ok=True)
        log.info("Descargando motor CPU whisper.cpp %s...", WHISPER_CPP_VERSION)
        req = urllib.request.Request(
            CPU_ENGINE_URL, headers={"User-Agent": "WhisperKey-build"}
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310 - trusted GitHub release
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(ENGINE_STAGING)
        bin_dir = _find_server_dir(ENGINE_STAGING)
        if bin_dir is None:
            raise RuntimeError(
                f"{SERVER_EXE} no encontrado en el zip del motor CPU ({CPU_ENGINE_URL})."
            )

    # Always trim (idempotent) so a previously-staged dir is cleaned too.
    _trim_engine(bin_dir)
    log.info("Motor CPU preparado en %s", bin_dir)
    return bin_dir


def _keep_engine_file(name: str) -> bool:
    """Keep only what whisper-server needs: the server/cli exes and the
    ggml/whisper DLLs. Drops example tools (stream, talk, parakeet, tests...)."""
    low = name.lower()
    if low in ("whisper-server.exe", "whisper-cli.exe"):
        return True
    if low.endswith(".dll") and (low.startswith("ggml") or low == "whisper.dll"):
        return True
    return False


def _trim_engine(bin_dir: Path) -> None:
    for entry in bin_dir.iterdir():
        if entry.is_file() and not _keep_engine_file(entry.name):
            try:
                entry.unlink()
            except OSError as exc:
                log.warning("No se pudo descartar %s: %s", entry.name, exc)


def _find_server_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    for match in root.rglob(SERVER_EXE):
        return match.parent
    return None


def build() -> None:
    """Run PyInstaller with optimal parameters for WhisperKey."""
    sep = os.pathsep

    engine_bin = stage_cpu_engine()

    # Bundle app resources + the CPU engine ONLY (never the on-disk CUDA build).
    add_data = [
        f"{PROJECT_ROOT / 'assets' / 'icons'}{sep}assets/icons",
        f"{PROJECT_ROOT / 'assets' / 'logo.png'}{sep}assets",
        f"{engine_bin}{sep}assets/bin",
    ]

    hidden_imports = [
        "whisperkey.platform.windows",
        "whisperkey.platform.linux",
        "whisperkey.platform.macos",
        "whisperkey.engine",
        "whisperkey.splash",
        "whisperkey.settings_gui",
        "whisperkey.onboarding",
        "whisperkey.updater",
    ]

    excludes = [
        "tests",
        "docs",
        "notebooks",
        "IPython",
        "matplotlib",
        "pytest",
        # Heavy faster-whisper-era packages that may linger in a dev venv but
        # are never imported by the C++ (whisper.cpp) engine. Excluding them
        # keeps the bundle small regardless of what is installed.
        "torch",
        "torchaudio",
        "torchvision",
        "onnxruntime",
        "ctranslate2",
        "faster_whisper",
        "transformers",
    ]

    icon_path = PROJECT_ROOT / "assets" / "icons" / "app.ico"
    icon_arg = f"--icon={icon_path}" if icon_path.exists() else ""

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--name=WhisperKey",
        f"--distpath={PROJECT_ROOT / 'dist'}",
        f"--workpath={PROJECT_ROOT / 'build'}",
        f"--specpath={PROJECT_ROOT}",
    ]
    if icon_arg:
        cmd.append(icon_arg)

    for data in add_data:
        cmd.append(f"--add-data={data}")

    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")

    for exc in excludes:
        cmd.append(f"--exclude-module={exc}")

    # customtkinter ships JSON themes/assets that PyInstaller does not pick up
    # automatically; without this the frozen app crashes loading its theme.
    for pkg in ("customtkinter",):
        cmd.append(f"--collect-all={pkg}")

    cmd.append(str(PROJECT_ROOT / "whisperkey" / "__main__.py"))

    log.info("Building WhisperKey v%s", __version__)
    log.info("Command: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    log.info("Build completed in %s", DIST_DIR)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        build()
    except subprocess.CalledProcessError as exc:
        log.error("PyInstaller failed with code %s", exc.returncode)
        sys.exit(1)
    except FileNotFoundError:
        log.error("PyInstaller not found. Install with: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    main()

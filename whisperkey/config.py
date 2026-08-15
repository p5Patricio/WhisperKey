"""Carga y validación de configuración desde config.toml."""

from __future__ import annotations

import copy
import logging
import os
import pathlib
import tomllib

log = logging.getLogger(__name__)

DEFAULTS = {
    "app": {
        "first_run": True,
    },
    "model": {
        "name": "tiny",
        "device": "auto",
        "compute_type": "int8_float16",
        "use_cpu_fallback": False,
    },
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "dtype": "float32",
        "queue_maxsize": 100,
        "notification_sounds": True,
    },
    "hotkeys": {
        "ptt": "f9",
        "toggle": "f10",
        "load_model_key": "",
    },
    "overlay": {
        "enabled": True,
        "position": "bottom-right",
        "opacity": 0.85,
        "font_size": 14,
    },
    "transcription": {
        "language": "",
        "prompt": "Nota técnica. Testing code, PRs, backend logs. Spanglish mode.",
        "min_duration": 0.3,
        "threads": 0,
    },
}

DEFAULT_TOML_CONTENT = """\
# WhisperKey — Configuración
# Editá este archivo para personalizar la herramienta.
# Los cambios se aplican al reiniciar la aplicación.

[model]
# Modelo de Whisper a usar. Opciones: tiny, base, small, medium, large-v2, large-v3
name = "tiny"
# Motor a usar: "auto" detecta GPU NVIDIA; "cuda" fuerza GPU; "cpu" fuerza CPU.
device = "auto"
# Si falla la ejecución con GPU/CUDA, se usará automáticamente la versión de CPU
use_cpu_fallback = false

[audio]
# Frecuencia de muestreo en Hz. No cambiar salvo que tengas problemas de audio.
sample_rate = 16000
# Canales de audio (1 = mono, recomendado)
channels = 1
# Tipo de dato del audio interno
dtype = "float32"
# Tamaño máximo de la cola de audio; los chunks más viejos se descartan cuando se llena
queue_maxsize = 100
# Sonidos de notificación para inicio/parada/errores/listo
notification_sounds = true

[hotkeys]
# Tecla para Push-to-Talk (mantener presionada mientras hablás)
# Opciones comunes: "caps_lock", "f9", "f10", "f11", "f12", "scroll_lock"
ptt = "f9"
# Tecla para Toggle (presionar para iniciar grabación, volver a presionar para detener)
# Opciones comunes: "f10", "f11", "f12", "scroll_lock", "pause"
toggle = "f10"
# (Opcional) Tecla para cargar/descargar el modelo manualmente. Dejar vacío para desactivar.
load_model_key = ""

[overlay]
# Mostrar indicador visual de grabación en pantalla
enabled = true
# Posición del indicador. Opciones: "bottom-right", "bottom-left", "top-right", "top-left"
position = "bottom-right"
# Opacidad del indicador (0.1 = casi invisible, 1.0 = sólido)
opacity = 0.85
# Tamaño de la fuente del indicador
font_size = 14

[app]
# Indica si es la primera vez que se ejecuta la aplicación.
first_run = true

[transcription]
# Idioma de transcripción. "" = detección automática (recomendado para Spanglish)
language = ""
# Prompt para guiar la transcripción bilingüe
prompt = "Nota técnica. Testing code, PRs, backend logs. Spanglish mode."
# Mínimo de segundos de audio para transcribir (evita transcribir ruido)
min_duration = 0.3
# Hilos de CPU para la transcripción. 0 = automático (todos los núcleos).
threads = 0
"""


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively. Override wins on conflicts."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _validate(config: dict) -> None:
    """Raise ValueError on invalid config values."""

    valid_positions = ("bottom-right", "bottom-left", "top-right", "top-left")
    if config["overlay"]["position"] not in valid_positions:
        raise ValueError(f"overlay.position debe ser uno de {valid_positions}")

    opacity = config["overlay"]["opacity"]
    if not (0.1 <= opacity <= 1.0):
        raise ValueError(
            f"overlay.opacity debe estar entre 0.1 y 1.0, se recibió: {opacity}"
        )

    if not isinstance(config["hotkeys"]["ptt"], str) or not config["hotkeys"]["ptt"].strip():
        raise ValueError("hotkeys.ptt debe ser un string no vacío")

    toggle = config["hotkeys"]["toggle"]
    if isinstance(toggle, list):
        if not toggle:
            raise ValueError("hotkeys.toggle no puede ser una lista vacía")
        for k in toggle:
            if not isinstance(k, str):
                raise ValueError(f"hotkeys.toggle debe contener strings, se recibió: {type(k)}")
        # Warn on dangerous combos
        if set(k.lower() for k in toggle) == {"win", "l"}:
            log.warning("hotkeys.toggle = ['win', 'l'] conflicta con el bloqueo de pantalla de Windows")
    elif isinstance(toggle, str):
        if not toggle.strip():
            raise ValueError("hotkeys.toggle debe ser un string no vacío")
    else:
        raise ValueError("hotkeys.toggle debe ser un string o una lista de strings")


def _write_default_config(path: pathlib.Path) -> None:
    """Write a commented default config.toml."""
    path.write_text(DEFAULT_TOML_CONTENT, encoding="utf-8")


def detect_optimal_model(config: dict) -> str:
    """Detectar modelo óptimo según VRAM disponible (GPU) o RAM total (CPU/MPS).

    Mapeo:
        < 4 GB  -> tiny
        4-6 GB  -> base
        6-10 GB -> small
        10-16 GB-> medium
        > 16 GB -> large-v3
    """
    from whisperkey.platform import get_platform
    import subprocess
    import shutil

    platform = get_platform()
    device, _ = platform.detect_gpu()

    try:
        import psutil

        total_gb = 8.0  # default safe fallback
        if device == "cuda":
            nvidia_smi = shutil.which("nvidia-smi")
            if nvidia_smi is not None:
                try:
                    res = subprocess.run(
                        [nvidia_smi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if res.returncode == 0:
                        total_gb = float(res.stdout.strip()) / 1024.0
                        log.info("VRAM detectada via nvidia-smi: %.1f GB", total_gb)
                except Exception:
                    pass
        else:
            total_bytes = psutil.virtual_memory().total
            total_gb = total_bytes / (1024 ** 3)
            log.info("RAM detectada: %.1f GB (CPU)", total_gb)
    except Exception as exc:
        log.warning("No se pudo detectar memoria: %s. Usando 'tiny'.", exc)
        return "tiny"

    if total_gb < 4:
        return "tiny"
    elif total_gb < 6:
        return "base"
    elif total_gb < 10:
        return "small"
    elif total_gb < 16:
        return "medium"
    else:
        return "large-v3"


def _legacy_repo_config_path() -> pathlib.Path:
    """Ruta legacy: config.toml en la raíz del repositorio (usada solo para migración)."""
    from whisperkey.platform import get_platform
    return get_platform().get_project_root() / "config.toml"


def get_config_path() -> str:
    """Return config path: %APPDATA%/WhisperKey/config.toml when frozen, else project root."""
    import sys
    if getattr(sys, 'frozen', False):
        from whisperkey.platform import get_platform
        platform = get_platform()
        appdata_dir = platform.get_appdata_dir()
        appdata_dir.mkdir(parents=True, exist_ok=True)
        return str(appdata_dir / 'config.toml')
    else:
        from whisperkey.platform import get_platform
        return str(get_platform().get_project_root() / 'config.toml')


def migrate_config_if_needed() -> None:
    """Copy config from project root to AppData on first frozen run."""
    import sys
    import shutil

    if not getattr(sys, 'frozen', False):
        return

    appdata_config = pathlib.Path(os.environ['APPDATA']) / 'WhisperKey' / 'config.toml'
    if appdata_config.exists():
        return

    from whisperkey.platform import get_platform
    old_config = get_platform().get_project_root() / 'config.toml'

    if old_config.exists():
        appdata_config.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(old_config, appdata_config)
            log.info("Migrated config to %s", appdata_config)
        except Exception as exc:
            log.warning("Failed to migrate config: %s", exc)


def _migrate_legacy_config() -> None:
    """Migra config.toml desde la raíz del repo hacia ~/.whisperkey/config.toml una sola vez."""
    legacy = _legacy_repo_config_path()
    canonical = pathlib.Path(get_config_path())
    if canonical.exists():
        return
    if legacy.exists():
        try:
            import shutil
            shutil.copy2(legacy, canonical)
            log.info("Configuración migrada de %s a %s", legacy, canonical)
        except Exception as exc:
            log.warning("No se pudo migrar config legacy %s: %s", legacy, exc)


def is_first_run(path: str | None = None) -> bool:
    """Retorna True si no hay config o si app.first_run es True."""
    if path is None:
        path = get_config_path()
    _migrate_legacy_config()
    p = pathlib.Path(path)
    if not p.exists():
        return True
    try:
        with open(p, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("app", {}).get("first_run", True)
    except Exception:
        return True


def write_config(path: str | None, config_dict: dict) -> None:
    """Escribe config.toml preservando comentarios de DEFAULT_TOML_CONTENT.

    Actualiza únicamente los valores presentes en *config_dict*; el resto
    del contenido (incluyendo comentarios y estructura) se conserva tal cual.
    """
    if path is None:
        path = get_config_path()
        _migrate_legacy_config()
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = DEFAULT_TOML_CONTENT.splitlines(keepends=True)
    current_section: str | None = None
    out_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped[1:-1].strip()
            out_lines.append(line)
            continue

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out_lines.append(line)
            continue

        key = stripped.split("=", 1)[0].strip()
        if (
            current_section
            and current_section in config_dict
            and key in config_dict[current_section]
        ):
            value = config_dict[current_section][key]
            indent = line[: len(line) - len(line.lstrip())]
            if isinstance(value, str):
                formatted = f'"{value}"'
            elif isinstance(value, bool):
                formatted = str(value).lower()
            else:
                formatted = str(value)
            out_lines.append(f"{indent}{key} = {formatted}\n")
        else:
            out_lines.append(line)

    p.write_text("".join(out_lines), encoding="utf-8")


def load_config(path: str | None = None) -> dict:
    """Carga config.toml, fusiona con DEFAULTS y valida. Crea el archivo si no existe."""
    if path is None:
        path = get_config_path()
    _migrate_legacy_config()

    p = pathlib.Path(path)
    if not p.exists():
        log.info(
            "config.toml no encontrado, creando con valores por defecto en %s",
            p.resolve(),
        )
        _write_default_config(p)
        return copy.deepcopy(DEFAULTS)

    with open(p, "rb") as f:
        user_config = tomllib.load(f)

    config = _deep_merge(DEFAULTS, user_config)
    _validate(config)
    return config


def is_model_downloaded(model_name: str) -> bool:
    """Verifica si los archivos del modelo ya están descargados en ~/.whisperkey/models/."""
    if model_name == "auto":
        model_name = "tiny"
    models_dir = pathlib.Path.home() / ".whisperkey" / "models"
    model_file = models_dir / f"ggml-{model_name}.bin"
    return model_file.exists()

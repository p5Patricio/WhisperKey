"""Persistencia de historial de transcripciones en JSONL."""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

_HISTORY_DIR = pathlib.Path.home() / ".whisperkey"
_HISTORY_FILE = _HISTORY_DIR / "history.jsonl"
_MAX_ENTRIES = 500


def _ensure_dir() -> None:
    _HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def add_entry(text: str) -> None:
    """Agrega una transcripción al historial con timestamp UTC."""
    if not text or not text.strip():
        return
    _ensure_dir()
    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text.strip(),
    }
    try:
        with open(_HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.warning("No se pudo guardar historial: %s", exc)


def get_entries(limit: int = 100) -> list[dict[str, Any]]:
    """Retorna las últimas *limit* entradas del historial (más recientes primero)."""
    if not _HISTORY_FILE.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as exc:
        log.warning("No se pudo leer historial: %s", exc)
        return []
    # Más recientes primero, limitadas
    return list(reversed(entries[-limit:]))


def clear() -> None:
    """Borra todo el historial."""
    if _HISTORY_FILE.exists():
        try:
            _HISTORY_FILE.unlink()
            log.info("Historial borrado")
        except Exception as exc:
            log.warning("No se pudo borrar historial: %s", exc)


def trim() -> None:
    """Recorta el archivo a _MAX_ENTRIES si excede."""
    if not _HISTORY_FILE.exists():
        return
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        if len(lines) > _MAX_ENTRIES:
            with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-_MAX_ENTRIES:])
            log.info("Historial recortado a %s entradas", _MAX_ENTRIES)
    except Exception as exc:
        log.warning("No se pudo recortar historial: %s", exc)

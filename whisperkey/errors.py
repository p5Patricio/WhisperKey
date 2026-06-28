"""Jerarquía de excepciones propias de WhisperKey."""

from __future__ import annotations


class WhisperKeyError(Exception):
    """Excepción base para todos los errores de WhisperKey."""


class ModelLoadError(WhisperKeyError):
    """Error al cargar el modelo de Whisper."""


class TranscriptionError(WhisperKeyError):
    """Error durante la transcripción de audio."""


class AudioDeviceError(WhisperKeyError):
    """Error relacionado con el dispositivo de audio."""


class InjectionError(WhisperKeyError):
    """Error al inyectar texto en la aplicación activa."""


class UnsupportedPlatformError(WhisperKeyError):
    """Plataforma no soportada."""

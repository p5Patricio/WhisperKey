"""Captura de audio via sounddevice."""

from __future__ import annotations

import logging
import queue

import sounddevice as sd

from whisperkey.errors import AudioDeviceError
from whisperkey.state import AppState

log = logging.getLogger(__name__)


def start_stream(state: AppState, config: dict) -> sd.InputStream:
    """Crea e inicia el InputStream de PortAudio.

    El callback es O(1): sólo encola si está grabando.
    Si la cola está llena descarta el chunk más viejo (drop-oldest).
    """
    sample_rate: int = config["audio"]["sample_rate"]
    channels: int = config["audio"]["channels"]
    dtype: str = config["audio"]["dtype"]

    def _callback(indata, frames, time_info, status):  # noqa: ARG001
        if state.is_recording():
            try:
                state.audio_queue.put_nowait(indata.copy())
            except queue.Full:
                try:
                    state.audio_queue.get_nowait()
                    state.audio_queue.put_nowait(indata.copy())
                except queue.Empty:
                    pass

    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype=dtype,
        callback=_callback,
    )
    stream.start()
    return stream


def stop_stream(stream: sd.InputStream) -> None:
    """Detiene y cierra el stream de audio."""
    try:
        stream.stop()
        stream.close()
    except Exception as exc:
        log.warning("Error al detener stream de audio: %s", exc)
        raise AudioDeviceError(f"No se pudo detener el stream de audio: {exc}") from exc

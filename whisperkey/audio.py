"""Captura de audio via sounddevice."""

from __future__ import annotations

import logging
import queue

import sounddevice as sd

from whisperkey.errors import AudioDeviceError
from whisperkey.state import AppState

log = logging.getLogger(__name__)


def start_stream(state: AppState, config: dict, overlay=None) -> sd.InputStream:
    """Crea e inicia el InputStream de PortAudio.

    El callback es O(1): sólo encola si está grabando.
    Si la cola está llena descarta el chunk más viejo (drop-oldest).
    """
    import time
    sample_rate: int = config["audio"]["sample_rate"]
    channels: int = config["audio"]["channels"]
    dtype: str = config["audio"]["dtype"]
    device_name: str = config["audio"].get("device", "")

    # Resolver índice de dispositivo de entrada por nombre
    device_id = None
    if device_name:
        try:
            devices = sd.query_devices()
            for idx, dev in enumerate(devices):
                if dev["max_input_channels"] > 0 and device_name in dev["name"]:
                    device_id = idx
                    break
            if device_id is None:
                log.warning("Dispositivo de audio '%s' no encontrado. Usando predeterminado.", device_name)
        except Exception as exc:
            log.warning("Error al buscar dispositivo de audio '%s': %s. Usando predeterminado.", device_name, exc)

    last_callback_time = 0.0

    def _callback(indata, frames, time_info, status):  # noqa: ARG001
        nonlocal last_callback_time
        current_time = time.time()

        if last_callback_time > 0 and (current_time - last_callback_time) > 4.0:
            log.info(
                "Gran salto de tiempo detectado (%.2fs). Reiniciando estado de grabación.",
                current_time - last_callback_time,
            )
            state.reset_recording()
            if overlay is not None:
                overlay.hide()

        last_callback_time = current_time

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
        device=device_id,
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

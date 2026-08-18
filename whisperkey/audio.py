"""Captura de audio via sounddevice."""

from __future__ import annotations

import logging
import queue

import sounddevice as sd

from whisperkey.errors import AudioDeviceError
from whisperkey.state import AppState

log = logging.getLogger(__name__)

# Gap between capture callbacks that means the stream stalled (sleep, device
# change) rather than merely ran late.
_STALL_SECONDS = 4.0
# Rate-limit the drop warning so a sustained overflow cannot flood the log.
_DROP_LOG_EVERY = 25


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
        # Monotonic: a wall-clock delta moves with NTP corrections and DST, so
        # time.time() can trip this watchdog on a perfectly healthy machine.
        current_time = time.monotonic()

        if last_callback_time > 0 and (current_time - last_callback_time) > _STALL_SECONDS:
            log.warning(
                "Captura de audio interrumpida %.2fs. Descartando la grabación en curso.",
                current_time - last_callback_time,
            )
            state.reset_recording()
            if overlay is not None:
                overlay.hide()

        last_callback_time = current_time

        if state.is_capturing():
            try:
                state.audio_queue.put_nowait(indata.copy())
            except queue.Full:
                # Dropping audio is data loss and must never be silent: it
                # reaches the user as words spliced together mid-sentence.
                total = state.note_dropped_chunk()
                if total == 1 or total % _DROP_LOG_EVERY == 0:
                    log.warning(
                        "Cola de audio llena: %d chunks descartados. "
                        "Se está perdiendo audio de la grabación.",
                        total,
                    )

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

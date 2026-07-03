"""Carga de modelo y worker de transcripción."""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

from whisperkey.errors import ModelLoadError, TranscriptionError
from whisperkey.history import add_entry, trim
from whisperkey.state import AppState

from tqdm import tqdm

class CustomProgressBar(tqdm):
    _callbacks: list[Callable[[int, int, float], None]] = []

    @classmethod
    def register(cls, cb: Callable[[int, int, float], None]) -> None:
        if cb not in cls._callbacks:
            cls._callbacks.append(cb)

    @classmethod
    def unregister(cls, cb: Callable[[int, int, float], None] | None = None) -> None:
        if cb is None:
            cls._callbacks.clear()
        elif cb in cls._callbacks:
            cls._callbacks.remove(cb)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._notify()

    def update(self, n: int = 1) -> bool | None:
        ret = super().update(n)
        self._notify()
        return ret

    def close(self) -> None:
        super().close()
        self._notify()

    def _notify(self) -> None:
        total = self.total if self.total else 0
        n = self.n if self.n else 0
        pct = (n / total * 100) if total > 0 else 0
        for cb in list(self._callbacks):
            try:
                cb(n, total, pct)
            except Exception as e:
                logger.warning("Error in CustomProgressBar callback: %s", e)


def load_model(state: AppState, config: dict, sounds, overlay=None) -> None:
    """Carga WhisperModel en GPU y avisa via sounds.play_ready().

    overlay: instancia de RecordingOverlay (opcional). Si se provee, muestra
    el estado "loading" durante la carga y lo oculta al terminar.
    """
    if state.model is not None or state.get_loading():
        return

    state.set_loading(True)
    model_cfg = config["model"]
    model_name = model_cfg["name"]

    if model_name == "auto":
        from whisperkey.config import detect_optimal_model

        model_name = detect_optimal_model(config)

    from whisperkey.config import is_model_downloaded
    if not is_model_downloaded(model_name):
        logger.info("El modelo %s no está descargado. Iniciando descarga interceptada...", model_name)
        if overlay is not None:
            overlay.show_loading()
        try:
            import huggingface_hub
            huggingface_hub.snapshot_download(
                "Systran/faster-whisper-" + model_name,
                tqdm_class=CustomProgressBar
            )
        except Exception as exc:
            logger.exception("Error al descargar el modelo %s", model_name)
            state.set_loading(False)
            if overlay is not None:
                overlay.show_error(f"Error de descarga: {exc}")
            raise ModelLoadError(f"Error al descargar el modelo {model_name}: {exc}") from exc

    logger.info("Cargando modelo %s en %s...", model_name, model_cfg["device"])

    if overlay is not None:
        overlay.show_loading()

    success = False
    try:
        model = WhisperModel(
            model_name,
            device=model_cfg["device"],
            compute_type=model_cfg["compute_type"],
        )
        state.set_model(model)
        sounds.play_ready()
        logger.info("Modelo cargado y listo.")
        success = True
    except Exception as exc:
        logger.exception("Error al cargar el modelo")
        sounds.play_error()
        if overlay is not None:
            overlay.show_error(f"Error al cargar modelo: {exc}")
        raise ModelLoadError(f"Error al cargar el modelo {model_name}: {exc}") from exc
    finally:
        state.set_loading(False)
        if overlay is not None:
            if not success:
                pass  # overlay.show_error ya fue llamado; no ocultar
            else:
                overlay.hide()


def unload_model(state: AppState) -> None:
    """Libera el modelo de VRAM."""
    if state.model is None:
        return
    logger.info("Liberando modelo de VRAM...")
    state.clear_model()
    logger.info("VRAM liberada.")


def transcription_worker(
    state: AppState,
    config: dict,
    injection_fn: Callable[[str], None],
    sounds,
) -> None:
    """Worker daemon: acumula chunks de audio y transcribe al recibir sentinel None."""
    sample_rate: int = config["audio"]["sample_rate"]
    transcription_cfg = config["transcription"]
    min_duration: float = transcription_cfg["min_duration"]
    min_frames = int(sample_rate * min_duration)
    language: str | None = transcription_cfg["language"] or None
    prompt: str = transcription_cfg["prompt"]
    beam_size: int = transcription_cfg["beam_size"]
    vad_parameters: dict = transcription_cfg.get("vad_parameters", {})

    buffer: list = []
    while not state.shutdown_event.is_set():
        chunk = state.audio_queue.get()
        if chunk is None:
            # Sentinel: procesar buffer acumulado
            if buffer and state.model is not None:
                audio_np = np.concatenate(buffer, axis=0).flatten()
                if len(audio_np) >= min_frames:
                    # Normalizar
                    peak = np.max(np.abs(audio_np))
                    if peak > 0:
                        audio_np = audio_np / peak

                    try:
                        segments, _ = state.model.transcribe(
                            audio_np,
                            language=language,
                            task="transcribe",
                            beam_size=beam_size,
                            initial_prompt=prompt,
                            vad_filter=True,
                            vad_parameters=vad_parameters,
                        )
                    except Exception as exc:
                        logger.warning("VAD falló (%s), reintentando sin VAD...", exc)
                        try:
                            segments, _ = state.model.transcribe(
                                audio_np,
                                language=language,
                                task="transcribe",
                                beam_size=beam_size,
                                initial_prompt=prompt,
                            )
                        except Exception as exc2:
                            logger.exception("Error en transcripción")
                            sounds.play_error()
                            raise TranscriptionError(
                                f"Error en transcripción: {exc2}"
                            ) from exc2

                    text = "".join(seg.text for seg in segments).strip()
                    if text:
                        logger.info("Transcripción: %s", text)
                        injection_fn(text)
                        add_entry(text)
                        trim()
            buffer = []
        elif isinstance(chunk, str) and chunk == "RESET":
            logger.info("Recibida señal de RESET: vaciando buffer de transcripción sin procesar.")
            buffer = []
        else:
            buffer.append(chunk)

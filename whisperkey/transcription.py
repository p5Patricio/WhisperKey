"""Carga de modelo y worker de transcripción."""

from __future__ import annotations

import logging
import os
import subprocess
import pathlib
import wave
import tempfile
import requests
from typing import Callable

import numpy as np

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
    """Verifica si el modelo GGML existe y lo 'carga' (registra en AppState)."""
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
        logger.info("El modelo %s no está descargado. Iniciando descarga...", model_name)
        if overlay is not None:
            overlay.show_loading()
        try:
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model_name}.bin"
            models_dir = pathlib.Path.home() / ".whisperkey" / "models"
            models_dir.mkdir(parents=True, exist_ok=True)
            dest_file = models_dir / f"ggml-{model_name}.bin"
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_length = response.headers.get('content-length')
            if total_length is not None:
                total_length = int(total_length)
            
            with open(dest_file, 'wb') as f:
                if total_length is None:
                    f.write(response.content)
                else:
                    with CustomProgressBar(total=total_length, unit='B', unit_scale=True, desc=f"ggml-{model_name}.bin") as pbar:
                        for chunk in response.iter_content(chunk_size=4096):
                            f.write(chunk)
                            pbar.update(len(chunk))
            logger.info("Modelo descargado correctamente.")
        except Exception as exc:
            logger.exception("Error al descargar el modelo %s", model_name)
            state.set_loading(False)
            if overlay is not None:
                overlay.show_error(f"Error de descarga: {exc}")
            raise ModelLoadError(f"Error al descargar el modelo {model_name}: {exc}") from exc

    success = False
    try:
        state.set_model(model_name)
        sounds.play_ready()
        logger.info("Modelo %s listo para transcripción.", model_name)
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
                pass
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

    buffer: list = []
    while not state.shutdown_event.is_set():
        chunk = state.audio_queue.get()
        if chunk is None:
            # Sentinel: procesar buffer acumulado
            logger.info("Recibida señal de parada (sentinel None). Tamaño del buffer: %d chunks", len(buffer))
            if not buffer:
                logger.warning("No hay audio acumulado para transcribir (buffer vacío).")
            elif state.model is None:
                logger.error("No se puede transcribir: el modelo de Whisper no está cargado.")
            else:
                audio_np = np.concatenate(buffer, axis=0).flatten()
                if len(audio_np) < min_frames:
                    logger.warning("Audio demasiado corto (%d muestras, mínimo requerido: %d). Ignorando transcripción.", len(audio_np), min_frames)
                else:
                    # Normalizar
                    peak = np.max(np.abs(audio_np))
                    if peak > 0:
                        audio_np = audio_np / peak

                    audio_int16 = (audio_np * 32767.0).astype(np.int16)
                    
                    temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
                    try:
                        with os.fdopen(temp_fd, 'wb') as f:
                            with wave.open(f, 'wb') as wav_file:
                                wav_file.setnchannels(1)
                                wav_file.setsampwidth(2)
                                wav_file.setframerate(sample_rate)
                                wav_file.writeframes(audio_int16.tobytes())

                        # Ejecutar main.exe
                        from whisperkey.platform import get_platform
                        platform = get_platform()
                        project_root = platform.get_project_root()
                        main_exe_path = project_root / "assets" / "bin" / "main.exe"
                        
                        model_name = state.model
                        model_path = pathlib.Path.home() / ".whisperkey" / "models" / f"ggml-{model_name}.bin"
                        
                        cmd = [
                            str(main_exe_path),
                            "-m", str(model_path),
                            "-f", str(temp_path),
                            "-l", language or "auto",
                        ]
                        if prompt:
                            cmd.extend(["-p", prompt])
                            
                        # Subprocess execution with window creation suppressed
                        try:
                            logger.info("Ejecutando whisper.cpp en subproceso: %s", " ".join(cmd))
                            result = subprocess.run(
                                cmd,
                                capture_output=True,
                                text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                            # Check if failed or has DLL errors
                            dll_error = False
                            if result.returncode != 0:
                                dll_error = True
                            if result.stderr and ("dll" in result.stderr.lower() or "not found" in result.stderr.lower() or "error" in result.stderr.lower()):
                                dll_error = True
                                
                            if dll_error:
                                raise Exception(f"whisper.cpp retornó error. Código: {result.returncode}. Stderr: {result.stderr}")
                        except Exception as exc:
                            logger.warning("La ejecución GPU/CUDA falló o el binario no está: %s. Aplicando fallback de CPU...", exc)
                            # Alertar al usuario
                            def alert_user():
                                import tkinter.messagebox
                                tkinter.messagebox.showwarning(
                                    "WhisperKey - Fallback de CPU",
                                    "La ejecución en GPU (CUDA) falló o faltan dependencias (DLLs).\nSe descargará y utilizará la versión de CPU (AVX2) de forma automática."
                                )
                            import threading
                            threading.Thread(target=alert_user, daemon=True).start()
                            
                            cpu_bin_dir = project_root / "assets" / "bin" / "cpu"
                            cpu_bin_dir.mkdir(parents=True, exist_ok=True)
                            main_exe_path_cpu = cpu_bin_dir / "main.exe"
                            
                            if not main_exe_path_cpu.exists():
                                url_cpu = "https://github.com/ggerganov/whisper.cpp/releases/download/v1.5.4/whisper-1.5.4-bin-x64.zip"
                                import zipfile
                                temp_zip = pathlib.Path(tempfile.gettempdir()) / "whisper_cpu_bin.zip"
                                try:
                                    logger.info("Descargando binario CPU de fallback...")
                                    resp = requests.get(url_cpu)
                                    resp.raise_for_status()
                                    with open(temp_zip, 'wb') as f_zip:
                                        f_zip.write(resp.content)
                                    logger.info("Extrayendo binario CPU...")
                                    with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                                        zip_ref.extractall(cpu_bin_dir)
                                finally:
                                    if temp_zip.exists():
                                        try:
                                            temp_zip.unlink()
                                        except Exception:
                                            pass
                            
                            cmd[0] = str(main_exe_path_cpu)
                            logger.info("Reintentando con binario CPU: %s", " ".join(cmd))
                            result = subprocess.run(
                                cmd,
                                capture_output=True,
                                text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                            if result.returncode != 0:
                                raise Exception(f"La transcripción con CPU también falló: {result.stderr}")
                        
                        # Parse stdout for transcribed text
                        stdout = result.stdout
                        parsed_lines = []
                        for line in stdout.splitlines():
                            line_str = line.strip()
                            if not line_str:
                                continue
                            if "-->" in line_str and "]" in line_str:
                                idx = line_str.rfind("]")
                                text_part = line_str[idx + 1:].strip()
                                if text_part:
                                    parsed_lines.append(text_part)
                        
                        text = " ".join(parsed_lines).strip()
                        
                        if text:
                            logger.info("Transcripción exitosa: %s", text)
                            injection_fn(text)
                            add_entry(text)
                            trim()
                        else:
                            logger.warning("Transcripción final vacía (no se reconoció voz).")
                            
                    except Exception as exc:
                        logger.exception("Error en transcripción")
                        sounds.play_error()
                    finally:
                        try:
                            os.unlink(temp_path)
                        except Exception as e:
                            logger.warning("No se pudo eliminar archivo temporal %s: %s", temp_path, e)
            buffer = []
        elif isinstance(chunk, str) and chunk == "RESET":
            logger.info("Recibida señal de RESET: vaciando buffer de transcripción sin procesar.")
            buffer = []
        else:
            buffer.append(chunk)

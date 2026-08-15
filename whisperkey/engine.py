"""Resident whisper.cpp engine backed by whisper-server.

Keeps the Whisper model loaded in memory and transcribes over a local HTTP
endpoint (POST /inference), instead of spawning a fresh process and reloading
the model from disk on every dictation. This is the core latency fix: after the
first warm-up, each transcription only pays for inference, not model loading.
"""

from __future__ import annotations

import logging
import os
import pathlib
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# In whisper.cpp >= 1.7 the server binary is named whisper-server(.exe);
# older releases shipped it as server(.exe).
SERVER_EXE_NAME = "whisper-server.exe" if sys.platform == "win32" else "whisper-server"
LEGACY_SERVER_EXE_NAME = "server.exe" if sys.platform == "win32" else "server"

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _find_free_port() -> int:
    """Reserve an ephemeral loopback port and return it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def resolve_server_exe(bin_dir: Path) -> Path | None:
    """Return the whisper-server executable inside *bin_dir*, or None."""
    for name in (SERVER_EXE_NAME, LEGACY_SERVER_EXE_NAME):
        candidate = bin_dir / name
        if candidate.exists():
            return candidate
    return None


def _assign_to_job_object(proc: subprocess.Popen) -> object | None:
    """Assigns *proc* to a Win32 Job Object configured with KILL_ON_JOB_CLOSE."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        JobObjectExtendedLimitInformation = 9
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryLimit", ctypes.c_size_t),
                ("PeakJobMemoryLimit", ctypes.c_size_t),
            ]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        res = kernel32.SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not res:
            kernel32.CloseHandle(job)
            return None

        proc_handle = getattr(proc, "_handle", None)
        if proc_handle is not None:
            kernel32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc_handle)))
        return job
    except Exception as exc:
        log.debug("No se pudo asociar JobObject al proceso C++: %s", exc)
        return None


class WhisperServer:
    """Lifecycle manager for a resident whisper-server process."""

    def __init__(
        self,
        exe_path: Path,
        model_path: Path,
        *,
        language: str = "auto",
        threads: int | None = None,
    ) -> None:
        self.exe_path = Path(exe_path)
        self.model_path = Path(model_path)
        self.language = language or "auto"
        self.threads = threads or (os.cpu_count() or 4)
        self.host = "127.0.0.1"
        self.port: int | None = None
        self._proc: subprocess.Popen | None = None
        self._job: object | None = None
        self._log_fh = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, ready_timeout: float = 90.0) -> None:
        """Launch the server and block until it accepts HTTP connections."""
        if self.is_alive():
            return
        if not self.exe_path.exists():
            raise FileNotFoundError(f"whisper-server no encontrado: {self.exe_path}")
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {self.model_path}")

        self.port = _find_free_port()
        exe_dir = self.exe_path.parent

        # Load whisper.dll / cublas*.dll from the binary directory on Windows.
        if sys.platform == "win32":
            try:
                os.add_dll_directory(str(exe_dir))
            except Exception as exc:  # pragma: no cover - platform specific
                log.debug("No se pudo registrar DLL dir %s: %s", exe_dir, exc)

        cmd = [
            str(self.exe_path),
            "-m", str(self.model_path),
            "--host", self.host,
            "--port", str(self.port),
            "-t", str(self.threads),
            "-l", self.language,
        ]

        # Redirect server output to a log file so the OS pipe buffer never fills
        # (which would otherwise stall the server after enough requests).
        log_path = pathlib.Path.home() / ".whisperkey" / "whisper-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fh = open(log_path, "wb")

        log.info("Iniciando whisper-server residente: %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(exe_dir),
            stdout=self._log_fh,
            stderr=subprocess.STDOUT,
            creationflags=_CREATE_NO_WINDOW,
        )
        self._job = _assign_to_job_object(self._proc)

        self._wait_until_ready(ready_timeout, log_path)

    def _wait_until_ready(self, timeout: float, log_path: pathlib.Path) -> None:
        deadline = time.time() + timeout
        last_err: Exception | None = None
        while time.time() < deadline:
            if not self.is_alive():
                raise RuntimeError(
                    "whisper-server terminó al arrancar. Últimas líneas:\n"
                    + _tail(log_path)
                )
            try:
                # Any HTTP response means the server is listening and the model
                # has finished loading (it binds the port only after loading).
                requests.get(self.base_url + "/", timeout=2)
                log.info("whisper-server listo en %s", self.base_url)
                return
            except Exception as exc:
                last_err = exc
            time.sleep(0.3)

        self.stop()
        raise TimeoutError(
            f"whisper-server no respondió en {timeout}s ({last_err})"
        )

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            except Exception as exc:
                log.warning("Error al detener whisper-server: %s", exc)
            else:
                log.info("whisper-server detenido (memoria liberada).")

        if self._job is not None:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self._job)
            except Exception:
                pass
            self._job = None

        if self._log_fh is not None:
            try:
                self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None


    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def transcribe(
        self,
        wav_path: Path,
        *,
        prompt: str = "",
        language: str | None = None,
    ) -> str:
        """POST a WAV file to /inference and return the transcribed text."""
        if not self.is_alive():
            raise RuntimeError("whisper-server no está corriendo")

        data: dict[str, str] = {
            "response_format": "json",
            "temperature": "0.0",
        }
        lang = language or self.language
        if lang and lang != "auto":
            data["language"] = lang
        if prompt:
            data["prompt"] = prompt

        with open(wav_path, "rb") as fh:
            files = {"file": ("audio.wav", fh, "audio/wav")}
            resp = requests.post(
                self.base_url + "/inference",
                files=files,
                data=data,
                timeout=300,
            )
        resp.raise_for_status()

        try:
            payload = resp.json()
        except ValueError:
            return resp.text.strip()
        return (payload.get("text") or "").strip()


def _tail(path: pathlib.Path, max_chars: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "(sin salida)"
    return text[-max_chars:]

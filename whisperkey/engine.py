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
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# In whisper.cpp >= 1.7 the server binary is named whisper-server(.exe);
# older releases shipped it as server(.exe).
SERVER_EXE_NAME = "whisper-server.exe" if sys.platform == "win32" else "whisper-server"
LEGACY_SERVER_EXE_NAME = "server.exe" if sys.platform == "win32" else "server"

# Release zips are not laid out consistently: the CUDA build extracts into a
# Release/ subdirectory while the CPU build is flat. Search both, plus bin/.
_NESTED_BIN_SUBDIRS = ("", "Release", "bin", "build/bin")

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Presence of this string in the binary means the server has a request-parameter
# table (whisper.cpp >= ~1.6). Builds without it silently discard every form
# field and transcribe using the startup flags only.
_PARAM_TABLE_SENTINEL = b"response_format"

# Form fields the /inference endpoint may accept, depending on build.
_KNOWN_REQUEST_FIELDS = (
    "response_format",
    "temperature",
    "temperature_inc",
    "prompt",
    "carry_initial_prompt",
    "language",
    "beam_size",
    "best_of",
    "max_len",
    "entropy_thold",
    "logprob_thold",
    "no_speech_thold",
    "suppress_nst",
    "translate",
    "no_timestamps",
    "vad",
    "vad_threshold",
    "vad_min_speech_duration_ms",
    "vad_min_silence_duration_ms",
    "vad_speech_pad_ms",
)


def _find_free_port() -> int:
    """Reserve an ephemeral loopback port and return it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def default_engine_threads() -> int:
    """Threads for the engine, leaving headroom for the audio callback.

    Handing every core to whisper.cpp starves the PortAudio capture thread,
    which drops frames and cuts words out of the recording.
    """
    cpus = os.cpu_count() or 4
    return max(1, cpus - 2)


def resolve_server_exe(bin_dir: Path) -> Path | None:
    """Return the whisper-server executable under *bin_dir*, or None.

    Searches the flat directory and the nested layouts used by the official
    release zips (the CUDA build extracts into Release/).
    """
    for subdir in _NESTED_BIN_SUBDIRS:
        base = bin_dir / subdir if subdir else bin_dir
        for name in (SERVER_EXE_NAME, LEGACY_SERVER_EXE_NAME):
            candidate = base / name
            if candidate.exists():
                return candidate
    return None


@dataclass(frozen=True)
class EngineCapabilities:
    """What the whisper-server binary on disk actually supports.

    Sending a parameter the build does not parse is not an error: the server
    answers 200 OK and quietly ignores it. Probing up front is the only way to
    know whether the configured prompt, language and decoding options reach the
    decoder at all.
    """

    flags: frozenset[str]
    request_fields: frozenset[str]

    @property
    def accepts_request_params(self) -> bool:
        return bool(self.request_fields)

    def supports_flag(self, flag: str) -> bool:
        return flag in self.flags

    def supports_field(self, field: str) -> bool:
        return field in self.request_fields

    @classmethod
    def unknown(cls) -> EngineCapabilities:
        return cls(flags=frozenset(), request_fields=frozenset())

    @classmethod
    def probe(cls, exe_path: Path) -> EngineCapabilities:
        """Inspect *exe_path* for its CLI flags and request-parameter table."""
        return cls(
            flags=frozenset(_probe_flags(exe_path)),
            request_fields=frozenset(_probe_request_fields(exe_path)),
        )


def _probe_flags(exe_path: Path) -> set[str]:
    """Return the long CLI flags advertised by ``<exe> --help``."""
    try:
        proc = subprocess.run(
            [str(exe_path), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(exe_path.parent),
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception as exc:
        log.warning("No se pudo consultar --help de %s: %s", exe_path.name, exc)
        return set()

    output = (proc.stdout or "") + (proc.stderr or "")
    return set(re.findall(r"--([a-z0-9][a-z0-9-]*)", output))


def _probe_request_fields(exe_path: Path) -> set[str]:
    """Return the /inference form fields *exe_path* is able to parse.

    Returns an empty set for builds with no request-parameter table at all —
    those honour only the flags given at startup.
    """
    try:
        blob = exe_path.read_bytes()
    except Exception as exc:
        log.warning("No se pudo inspeccionar %s: %s", exe_path.name, exc)
        return set()

    if _PARAM_TABLE_SENTINEL not in blob:
        return set()

    return {
        field
        for field in _KNOWN_REQUEST_FIELDS
        if b"\x00" + field.encode() + b"\x00" in blob
    }


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
        prompt: str = "",
        beam_size: int = 5,
        suppress_nst: bool = True,
        vad_model_path: Path | None = None,
    ) -> None:
        self.exe_path = Path(exe_path)
        self.model_path = Path(model_path)
        self.language = language or "auto"
        self.threads = threads or default_engine_threads()
        self.prompt = prompt
        self.beam_size = beam_size
        self.suppress_nst = suppress_nst
        self.vad_model_path = Path(vad_model_path) if vad_model_path else None
        self.host = "127.0.0.1"
        self.port: int | None = None
        self.capabilities = EngineCapabilities.unknown()
        self._proc: subprocess.Popen | None = None
        self._job: object | None = None
        self._log_fh = None
        self._lock = threading.RLock()

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

        self.capabilities = EngineCapabilities.probe(self.exe_path)
        if not self.capabilities.accepts_request_params:
            log.warning(
                "El motor %s no expone parámetros por request (build antiguo). "
                "Prompt e idioma se aplican como flags de arranque.",
                self.exe_path.name,
            )

        cmd = [
            str(self.exe_path),
            "-m", str(self.model_path),
            "--host", self.host,
            "--port", str(self.port),
            "-t", str(self.threads),
            "-l", self.language,
        ]
        cmd += self._startup_decoding_flags()

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

    def _startup_decoding_flags(self) -> list[str]:
        """Decoding flags applied at startup.

        The prompt is passed here as well as per request: on builds without a
        request-parameter table this is the only way it reaches the decoder, and
        on modern builds the per-request value simply takes precedence.
        """
        caps = self.capabilities
        flags: list[str] = []

        if self.prompt and caps.supports_flag("prompt"):
            flags += ["--prompt", self.prompt]
        if self.beam_size > 1 and caps.supports_flag("beam-size"):
            flags += ["-bs", str(self.beam_size)]
        if self.suppress_nst and caps.supports_flag("suppress-nst"):
            flags.append("-sns")
        if (
            self.vad_model_path is not None
            and self.vad_model_path.exists()
            and caps.supports_flag("vad")
            and caps.supports_flag("vad-model")
        ):
            flags += ["--vad", "-vm", str(self.vad_model_path)]
            log.info("VAD activo (%s)", self.vad_model_path.name)
        elif self.vad_model_path is not None:
            log.info("VAD solicitado pero no soportado por este motor; continuando sin VAD.")

        return flags

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

    def ensure_alive(self) -> None:
        """Restart the server if the process died (crash, OOM, killed)."""
        with self._lock:
            if self.is_alive():
                return
            log.warning("whisper-server no está corriendo. Reiniciando el motor...")
            self.stop()
            self.start()
            log.info("whisper-server reiniciado en %s", self.base_url)

    def _build_request_data(self, prompt: str, language: str | None) -> dict[str, str]:
        """Assemble the form fields this build is actually able to parse."""
        caps = self.capabilities
        data: dict[str, str] = {}

        def put(field: str, value: str) -> None:
            if caps.supports_field(field):
                data[field] = value

        put("response_format", "json")
        put("temperature", "0.0")
        if self.beam_size > 1:
            put("beam_size", str(self.beam_size))
        if self.suppress_nst:
            put("suppress_nst", "true")

        lang = language or self.language
        if lang and lang != "auto":
            put("language", lang)
        if prompt:
            put("prompt", prompt)

        return data

    def transcribe(
        self,
        wav_path: Path,
        *,
        prompt: str = "",
        language: str | None = None,
    ) -> str:
        """POST a WAV file to /inference and return the transcribed text.

        Restarts the engine and retries once if the server died between
        dictations, so a crashed process does not disable transcription for the
        rest of the session.
        """
        self.ensure_alive()
        data = self._build_request_data(prompt, language)

        try:
            resp = self._post_inference(wav_path, data)
        except (requests.ConnectionError, requests.Timeout) as exc:
            log.warning("Fallo al contactar whisper-server (%s). Reintentando...", exc)
            self.ensure_alive()
            resp = self._post_inference(wav_path, data)

        resp.raise_for_status()

        try:
            payload = resp.json()
        except ValueError:
            return resp.text.strip()
        return (payload.get("text") or "").strip()

    def _post_inference(self, wav_path: Path, data: dict[str, str]):
        with open(wav_path, "rb") as fh:
            files = {"file": ("audio.wav", fh, "audio/wav")}
            return requests.post(
                self.base_url + "/inference",
                files=files,
                data=data,
                timeout=300,
            )


def _tail(path: pathlib.Path, max_chars: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return "(sin salida)"
    return text[-max_chars:]

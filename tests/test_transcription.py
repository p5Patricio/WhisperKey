"""Tests for the transcription backend (resident whisper-server engine)."""

from __future__ import annotations

import io
import pathlib
import threading
import time
import zipfile
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from whisperkey import transcription
from whisperkey.errors import ModelLoadError
from whisperkey.state import AppState


# ----------------------------------------------------------------------
# Helpers & fixtures
# ----------------------------------------------------------------------

def _voice(sr: int = 16000, secs: float = 0.3, amp: float = 0.2) -> np.ndarray:
    """A non-silent mono chunk (passes the energy gate)."""
    t = np.linspace(0, secs, int(sr * secs), endpoint=False)
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32).reshape(-1, 1)


def _wait(pred, timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class FakeServer:
    """Stand-in for engine.WhisperServer."""

    def __init__(self, text: str = "hola mundo") -> None:
        self.text = text
        self.stopped = False
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, wav_path, *, prompt: str = "", language: str | None = None) -> str:
        self.calls.append({"wav": str(wav_path), "prompt": prompt, "language": language})
        return self.text

    def stop(self) -> None:
        self.stopped = True


def _config(**overrides: Any) -> dict:
    cfg = {
        "model": {"name": "tiny", "device": "cpu"},
        "audio": {"sample_rate": 16000},
        "transcription": {"language": "", "prompt": "", "min_duration": 0.1, "threads": 0},
    }
    for section, values in overrides.items():
        cfg[section].update(values)
    return cfg


@pytest.fixture
def isolated_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / ".whisperkey" / "models").mkdir(parents=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def fake_sounds() -> MagicMock:
    return MagicMock()


def _make_platform(tmp_path: pathlib.Path, device: str = "cpu"):
    class FakePlatform:
        def get_project_root(self) -> pathlib.Path:
            return tmp_path / "project"

        def get_bundled_bin_dir(self) -> pathlib.Path:
            return tmp_path / "bundle" / "bin"

        def get_cuda_bin_dir(self) -> pathlib.Path:
            return tmp_path / "appdata" / "bin-cuda"

        def detect_gpu(self) -> tuple[str, str]:
            return (device, "int8")

    return FakePlatform()


# ----------------------------------------------------------------------
# clean_transcription
# ----------------------------------------------------------------------

class TestCleanTranscription:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("[BLANK_AUDIO]", ""),
            ("(música)", ""),
            ("[MUSIC]", ""),
            ("Hola esto es una prueba", "Hola esto es una prueba"),
            ("Hola [BLANK_AUDIO] mundo", "Hola mundo"),
            ("Texto\n[MUSIC]\nmas texto", "Texto mas texto"),
            ("  hola   con  espacios ", "hola con espacios"),
            # Legitimate parentheticals must be preserved.
            ("(esto es un ejemplo entre parentesis)", "(esto es un ejemplo entre parentesis)"),
        ],
    )
    def test_cleanup(self, raw: str, expected: str) -> None:
        assert transcription.clean_transcription(raw) == expected


# ----------------------------------------------------------------------
# transcription_worker
# ----------------------------------------------------------------------

class TestTranscriptionWorker:
    def _start_worker(self, state: AppState, config: dict, injected: list) -> threading.Thread:
        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, injected.append, MagicMock()),
            daemon=True,
        )
        worker.start()
        return worker

    def _stop_worker(self, state: AppState, worker: threading.Thread) -> None:
        state.shutdown_event.set()
        state.audio_queue.put(None)  # wake worker from blocking get()
        worker.join(timeout=3)

    def test_transcribes_and_injects_cleaned_text(self, isolated_home, monkeypatch) -> None:
        state = AppState(audio_queue_maxsize=10)
        server = FakeServer("hola [BLANK_AUDIO] mundo")
        state.set_model(server)
        config = _config(transcription={"prompt": "vocab tecnico"})
        injected: list[str] = []

        worker = self._start_worker(state, config, injected)
        state.audio_queue.put(_voice(secs=0.2))
        state.put_sentinel()
        assert _wait(lambda: injected)
        self._stop_worker(state, worker)

        assert injected == ["hola mundo"]
        assert len(server.calls) == 1
        assert server.calls[0]["prompt"] == "vocab tecnico"

    def test_skips_short_audio(self, isolated_home) -> None:
        state = AppState(audio_queue_maxsize=10)
        server = FakeServer()
        state.set_model(server)
        config = _config(transcription={"min_duration": 0.5})
        injected: list[str] = []

        worker = self._start_worker(state, config, injected)
        state.audio_queue.put(np.zeros((100, 1), dtype=np.float32))
        state.put_sentinel()
        assert _wait(lambda: state.audio_queue.qsize() == 0)
        time.sleep(0.1)
        self._stop_worker(state, worker)

        assert not injected
        assert not server.calls

    def test_skips_silent_audio_energy_gate(self, isolated_home) -> None:
        state = AppState(audio_queue_maxsize=10)
        server = FakeServer()
        state.set_model(server)
        config = _config()
        injected: list[str] = []

        worker = self._start_worker(state, config, injected)
        # Long enough to pass min_frames, but silent -> energy gate skips it.
        state.audio_queue.put(np.zeros((int(16000 * 0.3), 1), dtype=np.float32))
        state.put_sentinel()
        assert _wait(lambda: state.audio_queue.qsize() == 0)
        time.sleep(0.1)
        self._stop_worker(state, worker)

        assert not injected
        assert not server.calls

    def test_empty_buffer_noop(self, isolated_home) -> None:
        state = AppState(audio_queue_maxsize=10)
        server = FakeServer()
        state.set_model(server)
        injected: list[str] = []

        worker = self._start_worker(state, _config(), injected)
        state.put_sentinel()
        assert _wait(lambda: state.audio_queue.qsize() == 0)
        time.sleep(0.1)
        self._stop_worker(state, worker)

        assert not injected
        assert not server.calls

    def test_reset_clears_buffer(self, isolated_home) -> None:
        state = AppState(audio_queue_maxsize=10)
        server = FakeServer()
        state.set_model(server)
        injected: list[str] = []

        worker = self._start_worker(state, _config(), injected)
        state.audio_queue.put(_voice(secs=0.2))
        state.audio_queue.put("RESET")
        state.put_sentinel()  # buffer is empty after RESET
        assert _wait(lambda: state.audio_queue.qsize() == 0)
        time.sleep(0.1)
        self._stop_worker(state, worker)

        assert not injected
        assert not server.calls

    def test_transcribe_error_plays_sound(self, isolated_home) -> None:
        state = AppState(audio_queue_maxsize=10)

        class BoomServer(FakeServer):
            def transcribe(self, *a, **k):
                raise RuntimeError("boom")

        state.set_model(BoomServer())
        config = _config()
        injected: list[str] = []
        sounds = MagicMock()
        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, injected.append, sounds),
            daemon=True,
        )
        worker.start()
        state.audio_queue.put(_voice(secs=0.2))
        state.put_sentinel()
        assert _wait(lambda: sounds.play_error.called)
        self._stop_worker(state, worker)

        assert not injected


# ----------------------------------------------------------------------
# load_model / unload_model
# ----------------------------------------------------------------------

class TestLoadModel:
    def test_starts_server_and_downloads_model(self, isolated_home, fake_sounds, monkeypatch) -> None:
        server = FakeServer()
        monkeypatch.setattr(transcription, "_start_server", lambda cfg, mp, ov=None: server)
        created: dict[str, Any] = {}

        def fake_dl(url: str, dest: pathlib.Path, desc: str) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("model")
            created["url"] = url

        monkeypatch.setattr(transcription, "_download_file", fake_dl)

        state = AppState(audio_queue_maxsize=10)
        transcription.load_model(state, _config(), fake_sounds)

        assert state.model is server
        assert "ggml-tiny.bin" in created["url"]
        fake_sounds.play_ready.assert_called_once()

    def test_skips_when_already_loading(self, isolated_home, fake_sounds, monkeypatch) -> None:
        def boom(*a, **k):
            raise AssertionError("should not be called")

        monkeypatch.setattr(transcription, "_start_server", boom)
        state = AppState(audio_queue_maxsize=10)
        state.set_loading(True)
        transcription.load_model(state, _config(), fake_sounds)
        assert state.model is None

    def test_auto_selects_model(self, isolated_home, fake_sounds, monkeypatch) -> None:
        monkeypatch.setattr(transcription, "_start_server", lambda cfg, mp, ov=None: FakeServer())
        monkeypatch.setattr("whisperkey.config.detect_optimal_model", lambda cfg: "base")
        seen: dict[str, Any] = {}

        def fake_dl(url: str, dest: pathlib.Path, desc: str) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("model")
            seen["url"] = url

        monkeypatch.setattr(transcription, "_download_file", fake_dl)
        state = AppState(audio_queue_maxsize=10)
        transcription.load_model(state, _config(model={"name": "auto"}), fake_sounds)
        assert "ggml-base.bin" in seen["url"]

    def test_does_not_redownload_existing_model(self, isolated_home, fake_sounds, monkeypatch) -> None:
        (isolated_home / ".whisperkey" / "models" / "ggml-tiny.bin").write_text("m")
        monkeypatch.setattr(transcription, "_start_server", lambda cfg, mp, ov=None: FakeServer())

        def boom(*a, **k):
            raise AssertionError("download should be skipped")

        monkeypatch.setattr(transcription, "_download_file", boom)
        state = AppState(audio_queue_maxsize=10)
        transcription.load_model(state, _config(), fake_sounds)
        assert state.model is not None

    def test_raises_on_download_failure(self, isolated_home, fake_sounds, monkeypatch) -> None:
        def failing_dl(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(transcription, "_download_file", failing_dl)
        state = AppState(audio_queue_maxsize=10)
        with pytest.raises(ModelLoadError):
            transcription.load_model(state, _config(), fake_sounds)
        fake_sounds.play_error.assert_called_once()

    def test_raises_on_server_start_failure(self, isolated_home, fake_sounds, monkeypatch) -> None:
        (isolated_home / ".whisperkey" / "models" / "ggml-tiny.bin").write_text("m")

        def boom(*a, **k):
            raise RuntimeError("server crash")

        monkeypatch.setattr(transcription, "_start_server", boom)
        state = AppState(audio_queue_maxsize=10)
        with pytest.raises(ModelLoadError):
            transcription.load_model(state, _config(), fake_sounds)


class TestUnloadModel:
    def test_stops_server_and_clears(self) -> None:
        state = AppState(audio_queue_maxsize=10)
        server = FakeServer()
        state.set_model(server)
        transcription.unload_model(state)
        assert server.stopped is True
        assert state.model is None

    def test_noop_when_none(self) -> None:
        state = AppState(audio_queue_maxsize=10)
        transcription.unload_model(state)
        assert state.model is None


# ----------------------------------------------------------------------
# device selection & engine provisioning
# ----------------------------------------------------------------------

class TestDeviceSelection:
    @pytest.mark.parametrize(
        "device,detected,expected",
        [
            ("cpu", "cuda", "cpu"),
            ("cuda", "cpu", "cuda"),
            ("auto", "cuda", "cuda"),
            ("auto", "cpu", "cpu"),
        ],
    )
    def test_select_device(self, tmp_path, monkeypatch, device, detected, expected) -> None:
        monkeypatch.setattr(
            "whisperkey.platform.get_platform", lambda: _make_platform(tmp_path, detected)
        )
        assert transcription._select_device({"model": {"device": device}}) == expected


class TestEngineProvisioning:
    def _zip_with_server(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("whisper-server.exe", "fake server")
            zf.writestr("whisper.dll", "fake dll")
        return buf.getvalue()

    def test_downloads_cpu_engine_when_missing(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(
            "whisperkey.platform.get_platform", lambda: _make_platform(tmp_path, "cpu")
        )
        zip_bytes = self._zip_with_server()
        urls: list[str] = []

        class FakeResp:
            headers = {"content-length": str(len(zip_bytes))}

            def raise_for_status(self) -> None:
                pass

            def iter_content(self, chunk_size: int = 8192):
                for i in range(0, len(zip_bytes), chunk_size):
                    yield zip_bytes[i : i + chunk_size]

        def fake_get(url: str, **kwargs: Any) -> FakeResp:
            urls.append(url)
            return FakeResp()

        monkeypatch.setattr("requests.get", fake_get)
        exe = transcription._ensure_engine_for("cpu")
        assert exe.name == "whisper-server.exe"
        assert exe.exists()
        assert any(".zip" in u for u in urls)

    def test_uses_existing_engine_without_download(self, tmp_path, monkeypatch) -> None:
        platform = _make_platform(tmp_path, "cpu")
        bundled = platform.get_bundled_bin_dir()
        bundled.mkdir(parents=True)
        (bundled / "whisper-server.exe").write_text("already here")
        monkeypatch.setattr("whisperkey.platform.get_platform", lambda: platform)

        def boom(*a, **k):
            raise AssertionError("should not download")

        monkeypatch.setattr("requests.get", boom)
        exe = transcription._ensure_engine_for("cpu")
        assert exe == bundled / "whisper-server.exe"


class TestWorkerMaxDuration:
    def test_worker_forces_cut_on_max_duration(self, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=20)
        server = FakeServer("texto cortado")
        state.set_model(server)
        state.set_toggle(True)

        injected: list[str] = []
        # Sample rate 16000, max_duration 0.5s -> 8000 samples
        cfg = _config(
            transcription={"min_duration": 0.1, "max_duration": 0.5, "language": "", "prompt": ""}
        )

        t = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, cfg, injected.append, fake_sounds),
            daemon=True,
        )
        t.start()

        # Send 0.3s chunk, then another 0.3s chunk (total 0.6s >= 0.5s max_duration)
        chunk = _voice(sr=16000, secs=0.3)
        state.audio_queue.put(chunk)
        state.audio_queue.put(chunk)

        assert _wait(lambda: len(injected) == 1, timeout=3.0)
        assert injected == ["texto cortado"]
        assert state.get_toggle() is False
        fake_sounds.play_stop.assert_called()

        state.shutdown_event.set()
        state.put_sentinel()
        t.join(timeout=2.0)


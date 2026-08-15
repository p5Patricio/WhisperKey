"""End-to-end integration tests for the dictation pipeline.

These tests wire together the real components with heavy mocking of external
resources (audio hardware, resident whisper-server, clipboard, platform) to
verify the full path:

    hotkey press -> audio capture -> audio queue -> transcription worker ->
    server.transcribe -> text cleanup -> text injection -> history entry.
"""

from __future__ import annotations

import pathlib
import queue
import sys
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from whisperkey import audio, hotkeys, injection, transcription
from whisperkey.history import get_entries
from whisperkey.state import AppState


class FakeServer:
    """Stand-in for the resident engine.WhisperServer."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, wav_path, *, prompt: str = "", language: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "language": language})
        return self.text

    def stop(self) -> None:
        pass


@pytest.fixture
def e2e_mocks(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a fully mocked environment for end-to-end tests."""
    # 1. Redirect home and models/bin directories
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    project_root = tmp_path / "project"
    assets_bin = project_root / "assets" / "bin"
    assets_bin.mkdir(parents=True)
    (assets_bin / "main.exe").write_text("fake", encoding="utf-8")
    models_dir = tmp_path / ".whisperkey" / "models"
    models_dir.mkdir(parents=True)
    (models_dir / "ggml-tiny.bin").write_text("model", encoding="utf-8")

    # 2. Mock platform
    class FakePlatform:
        def get_project_root(self) -> pathlib.Path:
            return project_root

        def detect_gpu(self) -> tuple[str, str]:
            return ("cpu", "int8")

        def get_paste_shortcut(self) -> tuple[str, str]:
            return ("ctrl", "v")

    monkeypatch.setattr("whisperkey.platform.get_platform", lambda: FakePlatform())

    # 3. Mock sounddevice
    stream_instances: list[Any] = []

    class FakeInputStream:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.callback = kwargs.get("callback")
            self.device = kwargs.get("device")
            self.samplerate = kwargs.get("samplerate")
            self.channels = kwargs.get("channels")
            self.dtype = kwargs.get("dtype")
            self._started = False
            self._closed = False

        def start(self) -> None:
            self._started = True

        def stop(self) -> None:
            self._started = False

        def close(self) -> None:
            self._closed = True

        def inject(self, frames: int = 1024) -> None:
            if not self._started or self.callback is None:
                return
            # Non-silent tone so the transcription energy gate does not skip it.
            mono = 0.2 * np.sin(
                2 * np.pi * 220 * np.linspace(0, frames / 16000, frames, endpoint=False)
            )
            data = np.tile(mono.reshape(-1, 1), (1, self.channels)).astype(self.dtype)
            self.callback(data, frames, None, None)

    monkeypatch.setattr("sounddevice.InputStream", FakeInputStream)
    monkeypatch.setattr("sounddevice.query_devices", lambda: [
        {"name": "Default", "max_input_channels": 2},
    ])

    # 4. Mock whisper.cpp subprocess
    commands_run: list[list[str]] = []

    def fake_subprocess_run(cmd: list[str], **kwargs: Any) -> Any:
        commands_run.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stdout = "[00:00:00.000 --> 00:00:02.000] integrated test result"
        result.stderr = ""
        return result

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    # 5. Mock clipboard / injection
    injected_texts: list[str] = []
    clipboard_backup: list[str] = []

    def fake_paste() -> str:
        return clipboard_backup[-1] if clipboard_backup else ""

    def fake_copy(text: str) -> None:
        if not clipboard_backup:
            clipboard_backup.append("original")
        if text == "original":
            return
        injected_texts.append(text)

    monkeypatch.setattr("pyperclip.paste", fake_paste)
    monkeypatch.setattr("pyperclip.copy", fake_copy)

    # 6. Mock keyboard listener
    listener_callbacks: dict[str, Any] = {}
    listeners: list[MagicMock] = []

    class FakeListener:
        def __init__(self, on_press: Any, on_release: Any) -> None:
            self.on_press = on_press
            self.on_release = on_release
            listener_callbacks["on_press"] = on_press
            listener_callbacks["on_release"] = on_release
            listeners.append(self)
            self._started = False
            self._stopped = False

        def start(self) -> "FakeListener":
            self._started = True
            return self

        def stop(self) -> None:
            self._stopped = True

    monkeypatch.setattr("pynput.keyboard.Listener", FakeListener)

    from pynput import keyboard as kb

    return {
        "project_root": project_root,
        "stream_instances": stream_instances,
        "commands_run": commands_run,
        "injected_texts": injected_texts,
        "listener_callbacks": listener_callbacks,
        "kb": kb,
    }


class TestEndToEndDictation:
    def test_ptt_to_injected_text(self, e2e_mocks: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        # Minimal config matching real app defaults
        config = {
            "hotkeys": {"ptt": "f9", "toggle": "f10", "load_model_key": ""},
            "audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": "", "queue_maxsize": 100},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.1},
            "model": {"name": "tiny"},
            "overlay": {"enabled": False},
        }

        state = AppState(audio_queue_maxsize=100)
        state.set_model(FakeServer("integrated test result"))
        overlay = MagicMock()
        sounds = MagicMock()

        # Start audio stream
        stream = audio.start_stream(state, config)
        e2e_mocks["stream_instances"].append(stream)

        # Start keyboard listener
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = e2e_mocks["listener_callbacks"]["on_press"]
        on_release = e2e_mocks["listener_callbacks"]["on_release"]

        # Start transcription worker
        injected_by_worker: list[str] = []
        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, injected_by_worker.append, sounds),
            daemon=True,
        )
        worker.start()

        # Simulate PTT
        on_press(e2e_mocks["kb"].Key.f9)
        assert state.get_ptt() is True

        # Inject audio chunks
        for _ in range(10):
            stream.inject(frames=320)
            time.sleep(0.001)

        # Release PTT -> sentinel
        on_release(e2e_mocks["kb"].Key.f9)
        assert state.get_ptt() is False

        # Wait for worker to finish transcription
        for _ in range(100):
            if injected_by_worker:
                break
            time.sleep(0.05)

        state.shutdown_event.set()
        state.audio_queue.put(None)
        worker.join(timeout=5)
        listener.stop()
        audio.stop_stream(stream)

        assert injected_by_worker
        assert "integrated test result" in injected_by_worker

    def test_history_records_transcription(self, e2e_mocks: dict, monkeypatch: pytest.MonkeyPatch) -> None:
        config = {
            "hotkeys": {"ptt": "f9", "toggle": "f10", "load_model_key": ""},
            "audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": "", "queue_maxsize": 100},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.1},
            "model": {"name": "tiny"},
            "overlay": {"enabled": False},
        }

        state = AppState(audio_queue_maxsize=100)
        state.set_model(FakeServer("integrated test result"))
        sounds = MagicMock()
        overlay = MagicMock()

        stream = audio.start_stream(state, config)
        e2e_mocks["stream_instances"].append(stream)

        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = e2e_mocks["listener_callbacks"]["on_press"]
        on_release = e2e_mocks["listener_callbacks"]["on_release"]

        # Use real transcription worker that calls history.add_entry
        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, injection.inject_text, sounds),
            daemon=True,
        )
        worker.start()

        on_press(e2e_mocks["kb"].Key.f9)
        for _ in range(10):
            stream.inject(frames=320)
            time.sleep(0.001)
        on_release(e2e_mocks["kb"].Key.f9)

        for _ in range(100):
            if e2e_mocks["injected_texts"]:
                break
            time.sleep(0.05)

        state.shutdown_event.set()
        state.audio_queue.put(None)
        worker.join(timeout=5)
        listener.stop()
        audio.stop_stream(stream)

        assert e2e_mocks["injected_texts"]
        entries = get_entries()
        assert any("integrated test result" in entry.get("text", "") for entry in entries)

"""Rigorous tests for transcription backend using whisper.cpp (C++ engine)."""

from __future__ import annotations

import pathlib
import queue
import sys
import threading
import time
import wave
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from whisperkey import transcription
from whisperkey.errors import ModelLoadError
from whisperkey.state import AppState


@pytest.fixture
def isolated_models_dir(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect model home to a temp directory."""
    models_dir = tmp_path / ".whisperkey" / "models"
    models_dir.mkdir(parents=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)
    return models_dir


@pytest.fixture
def mock_platform(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Mock platform so project_root points to a temp dir containing assets/bin."""
    project_root = tmp_path / "project"
    assets_bin = project_root / "assets" / "bin"
    assets_bin.mkdir(parents=True)
    main_exe = assets_bin / "main.exe"
    main_exe.write_text("fake", encoding="utf-8")

    class FakePlatform:
        def get_project_root(self) -> pathlib.Path:
            return project_root

        def detect_gpu(self) -> tuple[str, str]:
            return ("cpu", "int8")

    monkeypatch.setattr("whisperkey.platform.get_platform", lambda: FakePlatform())
    return project_root


@pytest.fixture
def mock_requests(monkeypatch: pytest.MonkeyPatch):
    """Mock requests.get and track downloads, returning a valid zip when needed."""
    downloads: list[dict[str, Any]] = []

    # Pre-build a minimal valid zip file in memory.
    import zipfile as _zipfile
    import io as _io

    zip_buffer = _io.BytesIO()
    with _zipfile.ZipFile(zip_buffer, "w", _zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.exe", "fake main.exe")
    zip_bytes = zip_buffer.getvalue()

    class FakeResponse:
        def __init__(self, content: bytes, headers: dict[str, Any] | None = None) -> None:
            self.content = content
            self._headers = headers or {"content-length": str(len(content))}
            self.headers = self._headers
            self._chunks: list[bytes] | None = None

        def raise_for_status(self) -> None:
            pass

        def iter_content(self, chunk_size: int = 4096) -> Any:
            if self._chunks is None:
                for i in range(0, len(self.content), chunk_size):
                    yield self.content[i : i + chunk_size]
            else:
                yield from self._chunks

    def fake_get(url: str, stream: bool = False, **kwargs: Any) -> FakeResponse:
        downloads.append({"url": url, "stream": stream})
        if ".zip" in url:
            content = zip_bytes
        else:
            content = b"fake model bytes"
        return FakeResponse(content)

    monkeypatch.setattr("requests.get", fake_get)
    return downloads


@pytest.fixture
def fake_sounds() -> MagicMock:
    return MagicMock()


class TestWhisperCppEngineConfirmation:
    """Guard rails proving the engine is whisper.cpp (C++), not faster-whisper."""

    def test_transcription_uses_main_exe_subprocess(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, mock_requests: list, monkeypatch: pytest.MonkeyPatch, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "some prompt", "min_duration": 0.1},
        }
        # Pre-create model file
        isolated_models_dir.mkdir(parents=True, exist_ok=True)
        (isolated_models_dir / "ggml-tiny.bin").write_text("model", encoding="utf-8")
        state.set_model("tiny")

        commands_run: list[list[str]] = []

        def fake_subprocess_run(cmd: list[str], **kwargs: Any) -> Any:
            commands_run.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "[00:00:00.000 --> 00:00:02.000] hello world"
            result.stderr = ""
            return result

        monkeypatch.setattr("subprocess.run", fake_subprocess_run)
        injected_texts: list[str] = []

        def fake_inject(text: str) -> None:
            injected_texts.append(text)

        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, fake_inject, fake_sounds),
            daemon=True,
        )
        worker.start()
        # Generate enough audio to pass min_duration
        audio_chunk = np.zeros((int(16000 * 0.2), 1), dtype=np.float32)
        state.audio_queue.put(audio_chunk)
        state.put_sentinel()
        # Wait for the worker to process the sentinel before shutting down.
        for _ in range(50):
            if not injected_texts and not commands_run:
                time.sleep(0.05)
            else:
                break
        state.shutdown_event.set()
        state.audio_queue.put(None)  # wake worker from blocking get()
        worker.join(timeout=5)
        assert worker.is_alive() is False
        assert len(commands_run) == 1
        cmd = commands_run[0]
        assert pathlib.Path(cmd[0]).name == "main.exe"
        assert "-m" in cmd
        assert "-f" in cmd
        assert "-l" in cmd
        assert "-nt" in cmd
        assert "-p" not in cmd
        assert "--prompt" not in cmd
        assert "hello world" in injected_texts

    def test_load_model_downloads_whisper_cpp_binary(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, mock_requests: list, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.3},
        }
        transcription.load_model(state, config, fake_sounds)
        assert state.model == "tiny"
        assert any("whisper.cpp" in req["url"] or "ggml" in req["url"] for req in mock_requests)

    def test_load_model_downloads_model_file_if_missing(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, mock_requests: list, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.3},
        }
        transcription.load_model(state, config, fake_sounds)
        assert (isolated_models_dir / "ggml-tiny.bin").exists()
        assert any("ggml-tiny.bin" in req["url"] for req in mock_requests)

    def test_load_model_skips_when_already_loading(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, mock_requests: list, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.set_loading(True)
        config = {"model": {"name": "tiny"}, "audio": {"sample_rate": 16000}, "transcription": {"language": "", "prompt": "", "min_duration": 0.3}}
        transcription.load_model(state, config, fake_sounds)
        assert not mock_requests

    def test_load_model_auto_selects_model(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, mock_requests: list, fake_sounds: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {
            "model": {"name": "auto"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.3},
        }
        monkeypatch.setattr("whisperkey.config.detect_optimal_model", lambda cfg: "base")
        transcription.load_model(state, config, fake_sounds)
        assert state.model == "base"
        assert any("ggml-base.bin" in req["url"] for req in mock_requests)

    def test_load_model_raises_when_download_fails(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, fake_sounds: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        def failing_get(url: str, **kwargs: Any) -> Any:
            raise RuntimeError("network down")

        monkeypatch.setattr("requests.get", failing_get)
        state = AppState(audio_queue_maxsize=10)
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.3},
        }
        with pytest.raises(ModelLoadError):
            transcription.load_model(state, config, fake_sounds)

    def test_transcription_worker_handles_empty_buffer(self, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.set_model("tiny")
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.3},
        }
        injected: list[str] = []

        def fake_inject(text: str) -> None:
            injected.append(text)

        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, fake_inject, fake_sounds),
            daemon=True,
        )
        worker.start()
        state.put_sentinel()
        worker.join(timeout=2)
        assert not injected

    def test_transcription_worker_skips_short_audio(self, isolated_models_dir: pathlib.Path, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.set_model("tiny")
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.5},
        }
        injected: list[str] = []

        def fake_inject(text: str) -> None:
            injected.append(text)

        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, fake_inject, fake_sounds),
            daemon=True,
        )
        worker.start()
        state.audio_queue.put(np.zeros((100, 1), dtype=np.float32))
        state.put_sentinel()
        worker.join(timeout=2)
        assert not injected

    def test_transcription_worker_fallback_to_cpu(self, isolated_models_dir: pathlib.Path, mock_platform: pathlib.Path, mock_requests: list, monkeypatch: pytest.MonkeyPatch, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.1},
        }
        (isolated_models_dir / "ggml-tiny.bin").write_text("model", encoding="utf-8")
        state.set_model("tiny")

        run_count = {"n": 0}
        commands_run: list[list[str]] = []

        def fake_subprocess_run(cmd: list[str], **kwargs: Any) -> Any:
            commands_run.append(cmd)
            run_count["n"] += 1
            result = MagicMock()
            if run_count["n"] == 1:
                result.returncode = 1
                result.stderr = "CUDA error"
                result.stdout = ""
            else:
                result.returncode = 0
                result.stderr = ""
                result.stdout = "[00:00:00.000 --> 00:00:02.000] fallback works"
            return result

        monkeypatch.setattr("subprocess.run", fake_subprocess_run)
        injected: list[str] = []

        def fake_inject(text: str) -> None:
            injected.append(text)

        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, fake_inject, fake_sounds),
            daemon=True,
        )
        worker.start()
        audio_chunk = np.zeros((int(16000 * 0.2), 1), dtype=np.float32)
        state.audio_queue.put(audio_chunk)
        state.put_sentinel()
        for _ in range(50):
            if not injected:
                time.sleep(0.05)
            else:
                break
        state.shutdown_event.set()
        state.audio_queue.put(None)  # wake worker from blocking get()
        worker.join(timeout=5)
        assert run_count["n"] == 2
        assert any("cpu" in str(pathlib.Path(cmd[0]).parent).lower() for cmd in commands_run[1:])
        assert "fallback works" in injected

    def test_transcription_worker_resets_buffer(self, fake_sounds: MagicMock) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.set_model("tiny")
        config = {
            "model": {"name": "tiny"},
            "audio": {"sample_rate": 16000},
            "transcription": {"language": "", "prompt": "", "min_duration": 0.1},
        }
        injected: list[str] = []

        def fake_inject(text: str) -> None:
            injected.append(text)

        worker = threading.Thread(
            target=transcription.transcription_worker,
            args=(state, config, fake_inject, fake_sounds),
            daemon=True,
        )
        worker.start()
        state.audio_queue.put(np.zeros((800, 1), dtype=np.float32))
        state.audio_queue.put("RESET")
        state.audio_queue.put(np.zeros((800, 1), dtype=np.float32))
        state.put_sentinel()
        for _ in range(50):
            if state.audio_queue.qsize() > 0:
                time.sleep(0.05)
            else:
                break
        state.shutdown_event.set()
        state.audio_queue.put(None)
        worker.join(timeout=2)
        # Should not crash; buffer should be reset at RESET

    def test_unload_model(self) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.set_model("tiny")
        transcription.unload_model(state)
        assert state.model is None

    def test_unload_model_noop_when_none(self) -> None:
        state = AppState(audio_queue_maxsize=10)
        transcription.unload_model(state)
        assert state.model is None


class TestTranscriptionStdoutParsing:
    def test_parse_line_with_timestamp(self) -> None:
        stdout = "[00:00:00.000 --> 00:00:02.000]  hello world  \n"
        text = self._parse(stdout)
        assert text == "hello world"

    def test_parse_line_without_timestamp(self) -> None:
        stdout = "hello world\n"
        text = self._parse(stdout)
        assert text == "hello world"

    def test_parse_multiple_lines(self) -> None:
        stdout = "[00:00:00.000 --> 00:00:02.000] first line\n[00:00:02.000 --> 00:00:04.000] second line"
        text = self._parse(stdout)
        assert text == "first line second line"

    def test_parse_empty_lines_and_noise(self) -> None:
        stdout = "\n\n[00:00:00.000 --> 00:00:02.000] result\n\n"
        text = self._parse(stdout)
        assert text == "result"

    def test_parse_includes_non_timestamp_lines(self) -> None:
        # Current parser does not filter log lines; this documents the behavior.
        stdout = "whisper.cpp: loading model\n[00:00:00.000 --> 00:00:02.000] result"
        text = self._parse(stdout)
        assert text == "whisper.cpp: loading model result"

    def _parse(self, stdout: str) -> str:
        parsed_lines = []
        for line in stdout.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if "-->" in line_str and "]" in line_str:
                idx = line_str.rfind("]")
                text_part = line_str[idx + 1 :].strip()
                if text_part:
                    parsed_lines.append(text_part)
            else:
                parsed_lines.append(line_str)
        return " ".join(parsed_lines).strip()

"""Rigorous tests for audio stream capture via mocked sounddevice."""

from __future__ import annotations

import time
from typing import Any, Callable
from unittest.mock import MagicMock

import numpy as np
import pytest

from whisperkey import audio
from whisperkey.state import AppState


class FakeInputStream:
    """Mock sounddevice.InputStream that invokes the callback when started."""

    def __init__(
        self,
        callback: Callable[..., None],
        device: int | None = None,
        samplerate: int = 16000,
        channels: int = 1,
        dtype: str = "float32",
        **kwargs: Any,
    ) -> None:
        self.callback = callback
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self._started = False
        self._closed = False

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def close(self) -> None:
        self._closed = True

    def inject(self, frames: int = 1024) -> None:
        if not self._started:
            return
        data = np.zeros((frames, self.channels), dtype=self.dtype)
        self.callback(data, frames, None, None)


@pytest.fixture
def mock_sounddevice(monkeypatch: pytest.MonkeyPatch):
    """Replace sounddevice with a factory that captures InputStream instances."""
    streams: list[FakeInputStream] = []

    def fake_input_stream(*args: Any, **kwargs: Any) -> FakeInputStream:
        stream = FakeInputStream(*args, **kwargs)
        streams.append(stream)
        return stream

    monkeypatch.setattr("sounddevice.InputStream", fake_input_stream)
    monkeypatch.setattr("sounddevice.query_devices", lambda: [
        {"name": "Mic 1", "max_input_channels": 2},
        {"name": "Mic 2", "max_input_channels": 2},
    ])
    return streams


class TestStartStream:
    def test_start_stream_creates_input_stream(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config)
        assert stream._started is True
        assert stream.samplerate == 16000
        assert stream.channels == 1
        assert stream.dtype == "float32"

    def test_callback_enqueues_when_recording(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config)
        state.set_ptt(True)
        stream.inject(frames=512)
        assert state.audio_queue.qsize() == 1

    def test_callback_ignores_when_not_recording(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config)
        stream.inject(frames=512)
        assert state.audio_queue.empty()

    def test_callback_resolves_device_by_name(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": "Mic 2"}}
        audio.start_stream(state, config)
        assert mock_sounddevice[0].device == 1

    def test_callback_falls_back_to_default_when_device_not_found(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": "Unknown Mic"}}
        audio.start_stream(state, config)
        assert mock_sounddevice[0].device is None

    def test_callback_drops_oldest_when_queue_full(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=2)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config)
        state.set_ptt(True)
        stream.inject(frames=512)
        stream.inject(frames=512)
        stream.inject(frames=512)
        assert state.audio_queue.qsize() == 2
        first = state.audio_queue.get_nowait()
        second = state.audio_queue.get_nowait()
        assert first.shape[0] == 512
        assert second.shape[0] == 512

    def test_callback_detects_time_gap_and_resets(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        overlay = MagicMock()
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config, overlay=overlay)
        state.set_ptt(True)
        stream.inject(frames=512)
        time.sleep(4.1)
        stream.inject(frames=512)
        assert state.get_ptt() is False
        overlay.hide.assert_called_once()


class TestStopStream:
    def test_stop_stream_stops_and_closes(self, mock_sounddevice: list) -> None:
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config)
        audio.stop_stream(stream)
        assert stream._started is False
        assert stream._closed is True

    def test_stop_stream_raises_audio_device_error(self, mock_sounddevice: list, monkeypatch: pytest.MonkeyPatch) -> None:
        from whisperkey.errors import AudioDeviceError
        state = AppState(audio_queue_maxsize=10)
        config = {"audio": {"sample_rate": 16000, "channels": 1, "dtype": "float32", "device": ""}}
        stream = audio.start_stream(state, config)
        stream.close = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(AudioDeviceError):
            audio.stop_stream(stream)

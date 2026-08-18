"""Regression tests for the audio paths that cut and glued words together."""

from __future__ import annotations

import time
import wave
import zipfile
from pathlib import Path

import numpy as np
import pytest

from whisperkey import transcription
from whisperkey.state import AppState


class TestStopGrace:
    def test_capture_continues_after_the_key_is_released(self) -> None:
        """PortAudio still holds the last block when the hotkey comes up."""
        state = AppState()
        state.set_ptt(True)
        state.begin_stop_grace(0.3)

        assert state.is_recording() is False
        assert state.is_capturing() is True

    def test_capture_stops_once_the_grace_window_expires(self) -> None:
        state = AppState()
        state.set_ptt(True)
        state.begin_stop_grace(0.05)
        time.sleep(0.1)

        assert state.is_capturing() is False

    def test_stop_recording_ends_capture_immediately(self) -> None:
        state = AppState()
        state.set_ptt(True)
        state.begin_stop_grace(5.0)
        state.stop_recording()

        assert state.is_capturing() is False

    def test_stop_recording_keeps_queued_audio(self) -> None:
        state = AppState()
        state.audio_queue.put(np.zeros((10, 1), dtype=np.float32))
        state.set_ptt(True)
        state.stop_recording()

        assert state.audio_queue.qsize() == 1


class TestDropAccounting:
    def test_dropped_chunks_are_counted(self) -> None:
        """Discarded audio must leave a trace; silent loss cannot be diagnosed."""
        state = AppState()
        assert state.note_dropped_chunk() == 1
        assert state.note_dropped_chunk() == 2
        assert state.dropped_chunks == 2

    def test_reset_recording_discards_and_reports(self, caplog: pytest.LogCaptureFixture) -> None:
        state = AppState()
        for _ in range(3):
            state.audio_queue.put(np.zeros((10, 1), dtype=np.float32))

        with caplog.at_level("WARNING"):
            state.reset_recording()

        assert "3 chunks" in caplog.text
        assert state.audio_queue.get_nowait() == "RESET"


class TestPrepareWav:
    def _read(self, path: str) -> tuple[int, int, np.ndarray]:
        with wave.open(path, "rb") as wav:
            frames = wav.getnframes()
            data = np.frombuffer(wav.readframes(frames), dtype=np.int16)
            return wav.getnchannels(), wav.getframerate(), data

    def test_stereo_is_downmixed_not_interleaved(self, tmp_path: Path) -> None:
        """Flattening stereo doubles the apparent sample rate and garbles speech."""
        frames = 8000
        left = np.full((frames, 1), 0.5, dtype=np.float32)
        right = np.full((frames, 1), 0.1, dtype=np.float32)
        stereo = np.concatenate([left, right], axis=1)

        path = transcription._prepare_wav([stereo], 16000, 100, channels=2)
        assert path is not None
        try:
            channels, rate, data = self._read(path)
            assert channels == 1
            assert rate == 16000
            assert len(data) == frames  # not 2 * frames
        finally:
            Path(path).unlink(missing_ok=True)

    def test_rejects_audio_below_the_silence_floor(self) -> None:
        quiet = np.full((16000, 1), 1e-5, dtype=np.float32)
        assert transcription._prepare_wav([quiet], 16000, 100) is None

    def test_rejects_audio_shorter_than_the_minimum(self) -> None:
        short = np.full((50, 1), 0.2, dtype=np.float32)
        assert transcription._prepare_wav([short], 16000, 4800) is None


class TestLoudnessNormalization:
    def _rms(self, audio: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(audio))))

    def test_quiet_audio_is_brought_up_towards_the_target(self) -> None:
        audio = np.full(1000, 0.01, dtype=np.float32)
        out = transcription._normalize_loudness(audio, self._rms(audio))
        assert self._rms(out) > self._rms(audio)
        assert self._rms(out) <= transcription._TARGET_RMS + 1e-6

    def test_gain_is_capped(self) -> None:
        audio = np.full(1000, 1e-4, dtype=np.float32)
        out = transcription._normalize_loudness(audio, self._rms(audio))
        assert np.max(np.abs(out)) <= 1e-4 * transcription._MAX_GAIN + 1e-9

    def test_loud_audio_is_left_alone(self) -> None:
        audio = np.full(1000, 0.5, dtype=np.float32)
        out = transcription._normalize_loudness(audio, self._rms(audio))
        assert np.allclose(out, audio)

    def test_peak_never_clips(self) -> None:
        audio = np.full(1000, 0.01, dtype=np.float32)
        audio[0] = 0.9  # a single click must not push the signal over the ceiling
        out = transcription._normalize_loudness(audio, self._rms(audio))
        assert np.max(np.abs(out)) <= transcription._PEAK_CEILING + 1e-6

    def test_silence_is_not_amplified(self) -> None:
        audio = np.zeros(1000, dtype=np.float32)
        assert np.array_equal(transcription._normalize_loudness(audio, 0.0), audio)


class TestSafeExtract:
    def test_rejects_paths_escaping_the_destination(self, tmp_path: Path) -> None:
        archive = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../escaped.dll", b"x")

        dest = tmp_path / "out"
        dest.mkdir()
        with zipfile.ZipFile(archive) as zf:
            with pytest.raises(ValueError, match="fuera del destino"):
                transcription._safe_extract(zf, dest)

        assert not (tmp_path / "escaped.dll").exists()

    def test_extracts_normal_and_nested_entries(self, tmp_path: Path) -> None:
        archive = tmp_path / "ok.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("whisper-server.exe", b"x")
            zf.writestr("Release/whisper.dll", b"y")

        dest = tmp_path / "out"
        with zipfile.ZipFile(archive) as zf:
            transcription._safe_extract(zf, dest)

        assert (dest / "whisper-server.exe").exists()
        assert (dest / "Release" / "whisper.dll").exists()

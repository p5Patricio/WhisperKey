"""Rigorous tests for the sounds feedback module."""

from __future__ import annotations

import importlib
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

import whisperkey.platform
import whisperkey.sounds as sounds


@pytest.fixture
def mock_platform(monkeypatch: pytest.MonkeyPatch):
    """Provide a mocked platform and reload sounds module with it."""
    mock = MagicMock()
    mock.play_beep = MagicMock()
    monkeypatch.setattr(whisperkey.platform, "get_platform", lambda: mock)
    importlib.reload(sounds)
    return mock


class TestSoundsEnabled:
    def test_sounds_enabled_by_default(self, mock_platform: MagicMock) -> None:
        assert sounds._enabled is True

    def test_set_enabled_disables_sounds(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(False)
        assert sounds._enabled is False
        sounds.play_start()
        sounds.play_stop()
        sounds.play_ready()
        sounds.play_error()
        mock_platform.play_beep.assert_not_called()

    def test_set_enabled_reenables_sounds(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(False)
        sounds.set_enabled(True)
        sounds.play_start()
        time.sleep(0.15)
        assert mock_platform.play_beep.called


class TestSoundsPlayStart:
    def test_play_start_triggers_beep(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(True)
        sounds.play_start()
        time.sleep(0.15)
        mock_platform.play_beep.assert_called_once_with(1200, 0.1)


class TestSoundsPlayStop:
    def test_play_stop_triggers_beep(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(True)
        sounds.play_stop()
        time.sleep(0.15)
        mock_platform.play_beep.assert_called_once_with(800, 0.1)


class TestSoundsPlayReady:
    def test_play_ready_triggers_double_beep(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(True)
        sounds.play_ready()
        time.sleep(0.25)
        assert mock_platform.play_beep.call_count == 2
        mock_platform.play_beep.assert_any_call(1000, 0.080)
        mock_platform.play_beep.assert_any_call(1200, 0.080)


class TestSoundsPlayError:
    def test_play_error_triggers_beep(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(True)
        sounds.play_error()
        time.sleep(0.35)
        mock_platform.play_beep.assert_called_once_with(400, 0.3)


class TestSoundsThreading:
    def test_sounds_run_in_background_threads(self, mock_platform: MagicMock) -> None:
        sounds.set_enabled(True)
        sounds.play_start()
        sounds.play_stop()
        sounds.play_ready()
        sounds.play_error()
        time.sleep(0.5)
        assert mock_platform.play_beep.call_count >= 4

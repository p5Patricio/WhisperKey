"""Rigorous tests for the splash screen."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from whisperkey import splash


class FakeCTk:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._title = ""
        self._geometry = ""
        self._overrideredirect = False
        self._withdrawn = False
        self._destroyed = False
        self._scheduled: list[tuple[int, Any]] = []

    def title(self, text: str) -> None:
        self._title = text

    def geometry(self, value: str) -> None:
        self._geometry = value

    def overrideredirect(self, value: bool) -> None:
        self._overrideredirect = value

    def withdraw(self) -> None:
        self._withdrawn = True

    def update_idletasks(self) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def after(self, ms: int, fn: Any) -> None:
        self._scheduled.append((ms, fn))

    def destroy(self) -> None:
        self._destroyed = True

    def winfo_exists(self) -> bool:
        return not self._destroyed

    def cget(self, key: str) -> Any:
        if key == "mode":
            return "indeterminate"
        return None


class FakeCTkToplevel:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._title = ""
        self._geometry = ""
        self._overrideredirect = False
        self._withdrawn = False
        self._destroyed = False
        self._scheduled: list[tuple[int, Any]] = []

    def title(self, text: str) -> None:
        self._title = text

    def geometry(self, value: str) -> None:
        self._geometry = value

    def overrideredirect(self, value: bool) -> None:
        self._overrideredirect = value

    def resizable(self, *args: Any) -> None:
        pass

    def transient(self, master: Any) -> None:
        pass

    def withdraw(self) -> None:
        self._withdrawn = True

    def update_idletasks(self) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return 1920

    def winfo_screenheight(self) -> int:
        return 1080

    def after(self, ms: int, fn: Any) -> None:
        self._scheduled.append((ms, fn))
        fn()

    def destroy(self) -> None:
        self._destroyed = True

    def winfo_exists(self) -> bool:
        return not self._destroyed


class FakeCTkLabel:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.text = kwargs.get("text", "")
        self.config_calls: list[dict[str, Any]] = []

    def configure(self, **kwargs: Any) -> None:
        self.config_calls.append(kwargs)

    def pack(self, **kwargs: Any) -> None:
        pass


class FakeCTkProgressBar:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._mode = kwargs.get("mode", "determinate")
        self._value = 0.0
        self._started = False

    def set(self, value: float) -> None:
        self._value = value

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def cget(self, key: str) -> Any:
        if key == "mode":
            return self._mode
        return None

    def configure(self, **kwargs: Any) -> None:
        if "mode" in kwargs:
            self._mode = kwargs["mode"]

    def pack(self, **kwargs: Any) -> None:
        pass


@pytest.fixture
def mock_ctk(monkeypatch: pytest.MonkeyPatch):
    """Provide mocked customtkinter widgets."""
    import customtkinter as ctk
    monkeypatch.setattr(ctk, "CTk", FakeCTk)
    monkeypatch.setattr(ctk, "CTkToplevel", FakeCTkToplevel)
    monkeypatch.setattr(ctk, "CTkLabel", FakeCTkLabel)
    monkeypatch.setattr(ctk, "CTkProgressBar", FakeCTkProgressBar)
    monkeypatch.setattr(ctk, "CTkImage", MagicMock)
    monkeypatch.setattr(ctk, "CTkFont", lambda *args, **kwargs: None)
    monkeypatch.setattr(splash, "ctk", ctk)
    return ctk


class TestSplashScreen:
    def test_splash_creates_window(self, mock_ctk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("os.path.exists", lambda p: False)
        s = splash.SplashScreen()
        assert s._window is not None
        assert s._window._overrideredirect is True
        assert s._window._title == "WhisperKey — Cargando..."

    def test_splash_noop_when_ctk_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(splash, "ctk", None)
        s = splash.SplashScreen()
        assert s._window is None

    def test_set_status_updates_label(self, mock_ctk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("os.path.exists", lambda p: False)
        s = splash.SplashScreen()
        s.set_status("Loading model...")
        assert any("Loading model..." in str(call) for call in s._label.config_calls)

    def test_close_destroys_window(self, mock_ctk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("os.path.exists", lambda p: False)
        s = splash.SplashScreen()
        s.close()
        assert s._window._destroyed

    def test_on_download_progress_switches_to_determinate(self, mock_ctk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("os.path.exists", lambda p: False)
        s = splash.SplashScreen()
        s._on_download_progress(100, 200, 50.0)
        assert s._progress._mode == "determinate"
        assert s._progress._value == 0.5

    def test_update_progress_ui_sets_label(self, mock_ctk: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("os.path.exists", lambda p: False)
        s = splash.SplashScreen()
        s._update_progress_ui(100, 200, 50.0)
        assert any("50.0%" in str(call) for call in s._label.config_calls)

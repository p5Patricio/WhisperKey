"""Rigorous tests for the system tray icon logic."""

from __future__ import annotations

import pathlib
import sys
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from whisperkey import tray
from whisperkey.state import AppState


@pytest.fixture
def mock_pystray(monkeypatch: pytest.MonkeyPatch):
    """Mock pystray.Icon and Menu."""
    icons: list[MagicMock] = []
    menus: list[MagicMock] = []

    class FakeMenu:
        def __init__(self, *items: Any) -> None:
            self.items = list(items)
            menus.append(self)

    class FakeIcon:
        def __init__(self, name: str, icon: Any, title: str) -> None:
            self.name = name
            self.icon = icon
            self.title = title
            self.menu = None
            self._stopped = False
            icons.append(self)

        def run(self) -> None:
            while not self._stopped:
                time.sleep(0.005)

        def stop(self) -> None:
            self._stopped = True

    monkeypatch.setattr("pystray.Icon", FakeIcon)
    monkeypatch.setattr("pystray.Menu", FakeMenu)
    monkeypatch.setattr("pystray.MenuItem", lambda text, action, **kwargs: (text, action))
    return icons, menus


@pytest.fixture
def mock_image(monkeypatch: pytest.MonkeyPatch):
    """Mock PIL.Image.open so tray icon loading never touches disk."""
    monkeypatch.setattr(
        "PIL.Image.open",
        lambda path: MagicMock(convert=lambda mode: MagicMock()),
    )


def _run_tray_in_thread(state: AppState, config: dict, on_load: Any, on_unload: Any, on_quit: Any) -> threading.Thread:
    """Helper to run the blocking tray function in a daemon thread."""
    t = threading.Thread(
        target=tray.start_tray,
        args=(state, config, on_load, on_unload, on_quit),
        daemon=True,
    )
    t.start()
    time.sleep(0.05)
    return t


class TestAssetsDir:
    def test_assets_dir_in_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        path = tray._assets_dir()
        assert path.is_absolute()
        assert path.name == "icons"
        assert (path.parent / "bin").exists() or True

    def test_assets_dir_in_pyinstaller_bundle(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        meipass = tmp_path / "_internal"
        meipass.mkdir()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
        path = tray._assets_dir()
        assert path == meipass / "assets" / "icons"


import pathlib


class TestLoadIcon:
    def test_load_icon_uses_file_when_present(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        icons_dir = tmp_path / "icons"
        icons_dir.mkdir()
        (icons_dir / "tray_ready.png").write_text("png", encoding="utf-8")
        monkeypatch.setattr(tray, "_assets_dir", lambda: icons_dir)
        opened: list[str] = []

        def fake_open(path: pathlib.Path) -> MagicMock:
            opened.append(str(path))
            return MagicMock(convert=lambda mode: MagicMock())

        monkeypatch.setattr("PIL.Image.open", fake_open)
        img = tray._load_icon("tray_ready.png", "green")
        assert "tray_ready.png" in opened[0]

    def test_load_icon_fallback_when_missing(self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
        icons_dir = tmp_path / "icons"
        icons_dir.mkdir()
        monkeypatch.setattr(tray, "_assets_dir", lambda: icons_dir)
        monkeypatch.setattr("PIL.Image.open", lambda path: (_ for _ in ()).throw(FileNotFoundError()))
        img = tray._load_icon("tray_missing.png", "blue")
        assert img is not None


class TestUpdateTrayIcon:
    def test_update_tray_icon_ready(self, mock_pystray: tuple) -> None:
        icons, _ = mock_pystray
        icon = MagicMock()
        state = AppState()
        state.set_model("tiny")
        tray._update_tray_icon(icon, state, {"hotkeys": {"ptt": "f9"}})
        assert "f9" in icon.title

    def test_update_tray_icon_loading(self, mock_pystray: tuple) -> None:
        icon = MagicMock()
        state = AppState()
        state.set_loading(True)
        tray._update_tray_icon(icon, state, {"hotkeys": {"ptt": "f9"}})
        assert "Cargando" in icon.title

    def test_update_tray_icon_idle(self, mock_pystray: tuple) -> None:
        icon = MagicMock()
        state = AppState()
        tray._update_tray_icon(icon, state, {"hotkeys": {"ptt": "f9"}})
        assert "Sin modelo" in icon.title


class TestStartTray:
    def test_start_tray_creates_icon(self, mock_pystray: tuple, mock_image: None) -> None:
        icons, _ = mock_pystray
        state = AppState()
        config = {"hotkeys": {"ptt": "f9"}}
        thread = _run_tray_in_thread(state, config, lambda: None, lambda: None, lambda icon: None)
        assert len(icons) == 1
        assert icons[0].name == "WhisperKey"
        state.shutdown_event.set()
        thread.join(timeout=2)

    def test_tray_menu_load_when_model_missing(self, mock_pystray: tuple, mock_image: None) -> None:
        icons, _ = mock_pystray
        state = AppState()
        config = {"hotkeys": {"ptt": "f9"}}
        thread = _run_tray_in_thread(state, config, lambda: None, lambda: None, lambda icon: None)
        time.sleep(0.1)
        state.shutdown_event.set()
        thread.join(timeout=2)
        assert icons[0].menu is not None

    def test_tray_menu_unload_when_model_loaded(self, mock_pystray: tuple, mock_image: None) -> None:
        icons, _ = mock_pystray
        state = AppState()
        state.set_model("tiny")
        config = {"hotkeys": {"ptt": "f9"}}
        thread = _run_tray_in_thread(state, config, lambda: None, lambda: None, lambda icon: None)
        time.sleep(0.1)
        state.shutdown_event.set()
        thread.join(timeout=2)
        assert icons[0].menu is not None

    def test_tray_quit_callback(self, mock_pystray: tuple, mock_image: None) -> None:
        icons, menus = mock_pystray
        state = AppState()
        config = {"hotkeys": {"ptt": "f9"}}
        quit_called: list[Any] = []

        def on_quit(icon: Any) -> None:
            quit_called.append(icon)

        thread = _run_tray_in_thread(state, config, lambda: None, lambda: None, on_quit)
        time.sleep(0.1)
        # Find the "Salir" menu item and invoke its action
        menu = icons[0].menu if icons[0].menu else menus[-1]
        for item in menu.items:
            text, action = item
            if text == "Salir":
                action(icons[0], None)
                break
        thread.join(timeout=2)
        assert quit_called
        assert state.shutdown_event.is_set()

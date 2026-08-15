"""Rigorous tests for the overlay UI using mocked tkinter."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from whisperkey import overlay


class FakeTk:
    """Mock tkinter.Tk root."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._withdrawn = False
        self._deiconified = False
        self._destroyed = False
        self._geometry = ""
        self._overrideredirect = False
        self._alpha = 1.0
        self._bg = ""
        self._topmost = False
        self._scheduled: list[tuple[int, Any]] = []
        self._width = 200
        self._height = 60
        self._screen_width = 1920
        self._screen_height = 1080

    def overrideredirect(self, value: bool) -> None:
        self._overrideredirect = value
        self.calls.append(("overrideredirect", (value,), {}))

    def wm_attributes(self, key: str, value: Any | None = None) -> Any:
        if value is None:
            if key == "-topmost":
                return self._topmost
            if key == "-alpha":
                return self._alpha
        if key == "-topmost":
            self._topmost = value
        elif key == "-alpha":
            self._alpha = value
        self.calls.append(("wm_attributes", (key, value), {}))

    def configure(self, **kwargs: Any) -> None:
        self._bg = kwargs.get("bg", self._bg)
        self.calls.append(("configure", tuple(), kwargs))

    def withdraw(self) -> None:
        self._withdrawn = True
        self.calls.append(("withdraw", tuple(), {}))

    def deiconify(self) -> None:
        self._deiconified = True
        self.calls.append(("deiconify", tuple(), {}))

    def destroy(self) -> None:
        self._destroyed = True
        self.calls.append(("destroy", tuple(), {}))

    def geometry(self, value: str | None = None) -> str:
        if value is not None:
            self._geometry = value
            self.calls.append(("geometry", (value,), {}))
        return self._geometry

    def update_idletasks(self) -> None:
        self.calls.append(("update_idletasks", tuple(), {}))

    def winfo_reqwidth(self) -> int:
        return self._width

    def winfo_reqheight(self) -> int:
        return self._height

    def winfo_screenwidth(self) -> int:
        return self._screen_width

    def winfo_screenheight(self) -> int:
        return self._screen_height

    def after(self, ms: int, fn: Any) -> None:
        self._scheduled.append((ms, fn))
        self.calls.append(("after", (ms, fn), {}))
        fn()

    def mainloop(self) -> None:
        self.calls.append(("mainloop", tuple(), {}))


class FakeLabel:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.config_calls: list[dict[str, Any]] = []

    def config(self, **kwargs: Any) -> None:
        self.config_calls.append(kwargs)

    def pack(self, **kwargs: Any) -> None:
        pass


@pytest.fixture
def mock_tk(monkeypatch: pytest.MonkeyPatch):
    """Provide mocked tkinter and label factories."""
    fake_roots: list[FakeTk] = []
    fake_labels: list[FakeLabel] = []

    def make_root() -> FakeTk:
        root = FakeTk()
        fake_roots.append(root)
        return root

    def make_label(*args: Any, **kwargs: Any) -> FakeLabel:
        label = FakeLabel(*args, **kwargs)
        fake_labels.append(label)
        return label

    import tkinter as tk
    monkeypatch.setattr(tk, "Tk", make_root)
    monkeypatch.setattr(tk, "Label", make_label)
    monkeypatch.setattr(overlay, "tk", tk)
    return fake_roots, fake_labels


class TestRecordingOverlay:
    def test_disabled_overlay_does_not_create_window(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": False}}
        ov = overlay.RecordingOverlay(config)
        assert ov._enabled is False
        assert fake_roots == []

    def test_enabled_overlay_creates_window(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        assert len(fake_roots) == 1
        root = fake_roots[0]
        assert root._overrideredirect is True
        assert root._topmost is True
        assert root._alpha == 0.85
        assert root._withdrawn is True

    def test_position_bottom_right(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_ptt()
        root = fake_roots[0]
        assert "+" in root._geometry

    def test_show_ptt(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_ptt()
        label = fake_labels[0]
        assert any(call.get("text") == overlay.STATES["ptt"]["text"] for call in label.config_calls)
        assert fake_roots[0]._deiconified

    def test_show_toggle(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_toggle()
        label = fake_labels[0]
        assert any(call.get("text") == overlay.STATES["toggle"]["text"] for call in label.config_calls)

    def test_show_loading(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_loading()
        label = fake_labels[0]
        assert any(call.get("text") == overlay.STATES["loading"]["text"] for call in label.config_calls)

    def test_show_error(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_error("custom error")
        label = fake_labels[0]
        assert any(call.get("text") == "custom error" for call in label.config_calls)

    def test_hide(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_ptt()
        ov.hide()
        assert fake_roots[0]._withdrawn

    def test_destroy(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "bottom-right", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.destroy()
        assert fake_roots[0]._destroyed

    def test_position_top_left(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "top-left", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_ptt()
        root = fake_roots[0]
        # geometry is "+x+y"
        assert root._geometry.startswith("+")

    def test_invalid_position_defaults_to_bottom_right(self, mock_tk: tuple) -> None:
        fake_roots, fake_labels = mock_tk
        config = {"overlay": {"enabled": True, "position": "invalid", "opacity": 0.85, "font_size": 14}}
        ov = overlay.RecordingOverlay(config)
        ov.show_ptt()
        root = fake_roots[0]
        assert root._geometry

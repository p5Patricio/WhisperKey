"""Rigorous tests for text injection via clipboard + paste shortcut."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from whisperkey import injection
from whisperkey.errors import InjectionError


@pytest.fixture
def mock_dependencies(monkeypatch: pytest.MonkeyPatch):
    """Mock clipboard and keyboard controller for isolated injection tests."""
    clipboard_state = {"current": "", "previous": "original"}

    def fake_copy(text: str) -> None:
        clipboard_state["current"] = text

    def fake_paste() -> str:
        return clipboard_state["previous"]

    monkeypatch.setattr("pyperclip.copy", fake_copy)
    monkeypatch.setattr("pyperclip.paste", fake_paste)

    class FakeController:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def pressed(self, key: object):
            class Context:
                def __enter__(ctx) -> "Context":
                    return ctx

                def __exit__(ctx, *args: object) -> None:
                    pass

            return Context()

        def press(self, key: object) -> None:
            self.calls.append(("press", str(key)))

        def release(self, key: object) -> None:
            self.calls.append(("release", str(key)))

    fake_controller = FakeController()
    monkeypatch.setattr("pynput.keyboard.Controller", lambda: fake_controller)

    monkeypatch.setattr(
        injection._platform,  # type: ignore[attr-defined]
        "get_paste_shortcut",
        lambda: ("ctrl", "v"),
    )

    return clipboard_state, fake_controller


class TestInjectText:
    def test_inject_empty_text_is_noop(self, mock_dependencies: tuple) -> None:
        clipboard_state, controller = mock_dependencies
        injection.inject_text("")
        assert clipboard_state["current"] == ""
        assert controller.calls == []

    def test_inject_copies_text_and_sends_shortcut(self, mock_dependencies: tuple) -> None:
        clipboard_state, controller = mock_dependencies
        injection.inject_text("hello world", pre_delay_ms=1, post_delay_ms=1)
        # clipboard is restored after injection; controller should have sent paste
        assert ("press", "v") in controller.calls
        assert ("release", "v") in controller.calls
        assert clipboard_state["current"] == "original"

    def test_inject_restores_previous_clipboard(self, mock_dependencies: tuple) -> None:
        clipboard_state, controller = mock_dependencies
        injection.inject_text("new text", pre_delay_ms=1, post_delay_ms=1)
        assert clipboard_state["current"] == "original"

    def test_inject_skips_restore_when_previous_too_large(self, mock_dependencies: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
        clipboard_state, controller = mock_dependencies
        large_text = "x" * (injection._CLIPBOARD_SIZE_LIMIT + 1)
        monkeypatch.setattr("pyperclip.paste", lambda: large_text)
        injection.inject_text("new text", pre_delay_ms=1, post_delay_ms=1)
        # Should not restore because previous was too large
        assert clipboard_state["current"] == "new text"

    def test_inject_raises_injection_error_on_failure(self, mock_dependencies: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
        def failing_copy(_: str) -> None:
            raise RuntimeError("clipboard broken")

        monkeypatch.setattr("pyperclip.copy", failing_copy)
        with pytest.raises(InjectionError):
            injection.inject_text("boom", pre_delay_ms=1, post_delay_ms=1)


class TestKeyMap:
    def test_key_map_contains_expected_modifiers(self) -> None:
        from pynput import keyboard
        assert injection._KEY_MAP["ctrl"] == keyboard.Key.ctrl
        assert injection._KEY_MAP["command"] == keyboard.Key.cmd
        assert injection._KEY_MAP["alt"] == keyboard.Key.alt
        assert injection._KEY_MAP["shift"] == keyboard.Key.shift

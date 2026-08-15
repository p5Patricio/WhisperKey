"""Rigorous tests for the keyboard listener / hotkey handling."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from pynput import keyboard as kb

from whisperkey import hotkeys
from whisperkey.state import AppState


class TestResolveKey:
    def test_resolve_special_key(self) -> None:
        key = hotkeys.resolve_key("f9")
        assert key == kb.Key.f9

    def test_resolve_caps_lock(self) -> None:
        key = hotkeys.resolve_key("caps_lock")
        assert key == kb.Key.caps_lock

    def test_resolve_single_char(self) -> None:
        key = hotkeys.resolve_key("a")
        assert isinstance(key, kb.KeyCode)
        assert key.char == "a"

    def test_resolve_strips_whitespace(self) -> None:
        key = hotkeys.resolve_key("  F10  ")
        assert key == kb.Key.f10

    def test_resolve_unknown_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            hotkeys.resolve_key("not_a_key")

    def test_resolve_multi_char_unknown_raises(self) -> None:
        with pytest.raises(ValueError):
            hotkeys.resolve_key("ab")


@pytest.fixture
def listener_deps(monkeypatch: pytest.MonkeyPatch):
    """Provide mocked deps and capture listener callbacks."""
    state = AppState(audio_queue_maxsize=10)
    sounds = MagicMock()
    overlay = MagicMock()
    config = {
        "hotkeys": {
            "ptt": "f9",
            "toggle": "f10",
            "load_model_key": "f11",
        },
        "model": {"name": "tiny"},
    }
    state.set_model("tiny")  # model must be loaded for hotkeys to react

    captured_callbacks: dict[str, Any] = {}
    listener_instances: list[MagicMock] = []

    class FakeListener:
        def __init__(self, on_press: Any, on_release: Any) -> None:
            self.on_press = on_press
            self.on_release = on_release
            self._started = False
            self._stopped = False
            captured_callbacks["on_press"] = on_press
            captured_callbacks["on_release"] = on_release
            listener_instances.append(self)

        def start(self) -> "FakeListener":
            self._started = True
            return self

        def stop(self) -> None:
            self._stopped = True

    monkeypatch.setattr("pynput.keyboard.Listener", FakeListener)
    return state, sounds, overlay, config, captured_callbacks, listener_instances


class TestStartListener:
    def test_start_listener_resolves_keys_from_config(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, listener_instances = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        assert listener._started is True
        assert listener_instances[0] is listener

    def test_ptt_press_starts_recording(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f9)
        assert state.get_ptt() is True
        assert state.is_recording() is True
        sounds.play_start.assert_called_once()
        overlay.show_ptt.assert_called_once()

    def test_ptt_release_stops_recording(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_release = captured_callbacks["on_release"]
        on_press(kb.Key.f9)
        on_release(kb.Key.f9)
        assert state.get_ptt() is False
        assert state.is_recording() is False
        sounds.play_stop.assert_called_once()
        overlay.hide.assert_called_once()
        assert state.audio_queue.get_nowait() is None  # sentinel

    def test_toggle_press_toggles_recording(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f10)
        assert state.get_toggle() is True
        assert state.is_recording() is True
        sounds.play_start.assert_called_once()
        overlay.show_toggle.assert_called_once()

    def test_toggle_press_again_stops_recording(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_release = captured_callbacks["on_release"]
        on_press(kb.Key.f10)
        on_release(kb.Key.f10)  # resets toggle lock
        on_press(kb.Key.f10)
        assert state.get_toggle() is False
        assert state.is_recording() is False
        assert sounds.play_stop.called
        assert overlay.hide.called

    def test_load_model_key_unloads_when_model_loaded(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f11)
        assert state.get_unload_requested() is True

    def test_load_model_key_loads_when_model_missing(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        state.clear_model()
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f11)
        assert state.get_load_requested() is True

    def test_unknown_key_is_ignored(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f12)
        assert state.get_ptt() is False
        assert state.get_toggle() is False

    def test_key_when_model_missing_plays_error(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        state.clear_model()
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f9)
        sounds.play_error.assert_called_once()

    def test_shutdown_event_ignores_keys(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        state.shutdown_event.set()
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f9)
        assert state.get_ptt() is False

    def test_listener_stop_flag(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, listener_instances = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        listener.stop()
        assert listener._stopped is True

    def test_toggle_lock_prevents_double_trigger(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_release = captured_callbacks["on_release"]
        on_press(kb.Key.f10)
        on_press(kb.Key.f10)
        on_press(kb.Key.f10)
        # Only one toggle ON happened
        assert state.get_toggle() is True
        on_release(kb.Key.f10)
        on_press(kb.Key.f10)
        assert state.get_toggle() is False
        assert sounds.play_stop.call_count == 1

    def test_toggle_release_resets_lock(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_release = captured_callbacks["on_release"]
        on_press(kb.Key.f10)
        assert state.get_toggle() is True
        on_release(kb.Key.f10)  # resets lock
        on_press(kb.Key.f10)
        # After release, next press can toggle off again
        assert state.get_toggle() is False

    def test_config_with_list_toggle(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        config["hotkeys"]["toggle"] = ["f10"]
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f10)
        assert state.get_toggle() is True

    def test_config_with_empty_load_model_key(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        config["hotkeys"]["load_model_key"] = ""
        listener = hotkeys.start_listener(state, config, overlay, sounds)
        on_press = captured_callbacks["on_press"]
        on_press(kb.Key.f11)
        assert state.get_load_requested() is False
        assert state.get_unload_requested() is False

    def test_load_unload_model_callbacks_invoked(self, listener_deps: tuple) -> None:
        state, sounds, overlay, config, captured_callbacks, _ = listener_deps
        on_load_mock = MagicMock()
        on_unload_mock = MagicMock()
        listener = hotkeys.start_listener(
            state, config, overlay, sounds,
            on_load=on_load_mock,
            on_unload=on_unload_mock,
        )
        on_press = captured_callbacks["on_press"]

        # When model is loaded, pressing load_model_key triggers unload
        on_press(kb.Key.f11)
        assert state.get_unload_requested() is True
        on_unload_mock.assert_called_once()
        on_load_mock.assert_not_called()

        # When model is None, pressing load_model_key triggers load
        state.clear_model()
        on_press(kb.Key.f11)
        assert state.get_load_requested() is True
        on_load_mock.assert_called_once()


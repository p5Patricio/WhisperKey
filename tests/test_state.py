"""Rigorous tests for AppState shared state dataclass."""

from __future__ import annotations

import queue
import threading
import time

import pytest

from whisperkey.state import AppState


class TestAppStateInitialization:
    def test_default_initial_state(self) -> None:
        state = AppState()
        assert state.ptt_active is False
        assert state.toggle_active is False
        assert state.model is None
        assert state.is_loading is False
        assert state.load_model_requested is False
        assert state.unload_model_requested is False
        assert state.audio_queue_maxsize == 0
        assert state.shutdown_event.is_set() is False

    def test_audio_queue_created_with_maxsize(self) -> None:
        state = AppState(audio_queue_maxsize=5)
        assert state.audio_queue.maxsize == 5
        assert isinstance(state.audio_queue, queue.Queue)

    def test_audio_queue_zero_maxsize_means_unbounded(self) -> None:
        state = AppState(audio_queue_maxsize=0)
        assert state.audio_queue.maxsize == 0

    def test_lock_and_event_are_initialized(self) -> None:
        state = AppState()
        # threading.Lock is a factory function, not a class
        assert state.lock is not None
        assert hasattr(state.lock, "acquire")
        assert hasattr(state.lock, "release")
        assert isinstance(state.shutdown_event, threading.Event)


class TestAppStateRecordingFlags:
    def test_set_and_get_ptt(self) -> None:
        state = AppState()
        state.set_ptt(True)
        assert state.get_ptt() is True
        state.set_ptt(False)
        assert state.get_ptt() is False

    def test_set_and_get_toggle(self) -> None:
        state = AppState()
        state.set_toggle(True)
        assert state.get_toggle() is True
        state.set_toggle(False)
        assert state.get_toggle() is False

    def test_is_recording_ptt_only(self) -> None:
        state = AppState()
        state.set_ptt(True)
        assert state.is_recording() is True
        state.set_ptt(False)
        assert state.is_recording() is False

    def test_is_recording_toggle_only(self) -> None:
        state = AppState()
        state.set_toggle(True)
        assert state.is_recording() is True
        state.set_toggle(False)
        assert state.is_recording() is False

    def test_is_recording_both_active(self) -> None:
        state = AppState()
        state.set_ptt(True)
        state.set_toggle(True)
        assert state.is_recording() is True


class TestAppStateLoadingFlags:
    def test_set_and_get_loading(self) -> None:
        state = AppState()
        state.set_loading(True)
        assert state.get_loading() is True
        state.set_loading(False)
        assert state.get_loading() is False

    def test_load_and_unload_request_flags(self) -> None:
        state = AppState()
        state.set_load_requested(True)
        assert state.get_load_requested() is True
        state.set_load_requested(False)
        assert state.get_load_requested() is False

        state.set_unload_requested(True)
        assert state.get_unload_requested() is True
        state.set_unload_requested(False)
        assert state.get_unload_requested() is False


class TestAppStateModel:
    def test_set_and_clear_model(self) -> None:
        state = AppState()
        state.set_model("tiny")
        assert state.model == "tiny"
        state.clear_model()
        assert state.model is None

    def test_clear_model_runs_gc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        state = AppState()
        state.set_model("base")
        collected = []

        def fake_collect() -> list:
            collected.append(1)
            return []

        monkeypatch.setattr("gc.collect", fake_collect)
        state.clear_model()
        assert collected


class TestAppStateQueueOperations:
    def test_put_sentinel_adds_none(self) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.put_sentinel()
        assert state.audio_queue.get_nowait() is None
        assert state.audio_queue.empty()

    def test_put_sentinel_replaces_oldest_when_full(self) -> None:
        state = AppState(audio_queue_maxsize=2)
        state.audio_queue.put("old")
        state.audio_queue.put("recent")
        state.put_sentinel()
        items = []
        while not state.audio_queue.empty():
            items.append(state.audio_queue.get_nowait())
        assert items == ["recent", None]

    def test_reset_recording_clears_queue_and_sets_reset_sentinel(self) -> None:
        state = AppState(audio_queue_maxsize=10)
        state.audio_queue.put("chunk1")
        state.audio_queue.put("chunk2")
        state.set_ptt(True)
        state.set_toggle(True)
        state.reset_recording()
        assert state.get_ptt() is False
        assert state.get_toggle() is False
        assert state.audio_queue.get_nowait() == "RESET"
        assert state.audio_queue.empty()

    def test_reset_recording_when_full(self) -> None:
        state = AppState(audio_queue_maxsize=2)
        state.audio_queue.put("chunk1")
        state.audio_queue.put("chunk2")
        state.reset_recording()
        # Should clear all audio chunks and place a single RESET sentinel
        assert state.audio_queue.get_nowait() == "RESET"
        assert state.audio_queue.empty()


class TestAppStateThreadSafety:
    def test_concurrent_ptt_toggles(self) -> None:
        state = AppState()
        errors = []

        def toggle_loop() -> None:
            try:
                for _ in range(1000):
                    state.set_ptt(True)
                    assert state.get_ptt() is True
                    state.set_ptt(False)
                    assert state.get_ptt() is False
            except AssertionError:
                errors.append("assertion")

        threads = [threading.Thread(target=toggle_loop) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_concurrent_queue_puts_and_reset(self) -> None:
        state = AppState(audio_queue_maxsize=100)
        stop = threading.Event()

        def producer() -> None:
            while not stop.is_set():
                try:
                    state.audio_queue.put_nowait("chunk")
                except queue.Full:
                    pass
                time.sleep(0.0001)

        threads = [threading.Thread(target=producer) for _ in range(4)]
        for t in threads:
            t.start()
        time.sleep(0.05)
        state.reset_recording()
        stop.set()
        for t in threads:
            t.join()
        # After reset, the only item that should be guaranteed is RESET or nothing
        remaining = []
        while not state.audio_queue.empty():
            remaining.append(state.audio_queue.get_nowait())
        assert all(item in ("chunk", "RESET") for item in remaining)
        assert "RESET" in remaining or not remaining

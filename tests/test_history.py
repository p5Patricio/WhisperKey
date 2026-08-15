"""Rigorous tests for the JSONL transcription history persistence."""

from __future__ import annotations

import json
import pathlib

import pytest

from whisperkey import history


@pytest.fixture(autouse=True)
def isolated_history_file(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect history file to a temp path so tests never touch ~/.whisperkey/history.jsonl."""
    hist_dir = tmp_path / "whisperkey"
    hist_dir.mkdir(parents=True)
    hist_file = hist_dir / "history.jsonl"
    monkeypatch.setattr(history, "_HISTORY_DIR", hist_dir)
    monkeypatch.setattr(history, "_HISTORY_FILE", hist_file)
    return hist_file


class TestHistoryAddEntry:
    def test_add_entry_creates_file(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("hello world")
        assert isolated_history_file.exists()

    def test_add_entry_persists_text_and_timestamp(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("transcribed text")
        lines = isolated_history_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["text"] == "transcribed text"
        assert "timestamp" in data
        assert data["timestamp"].endswith("+00:00")

    def test_add_entry_skips_empty_text(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("")
        history.add_entry("   ")
        assert not isolated_history_file.exists()

    def test_add_entry_strips_whitespace(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("  spaced text  ")
        data = json.loads(isolated_history_file.read_text(encoding="utf-8").strip())
        assert data["text"] == "spaced text"

    def test_add_entry_appends_multiple_lines(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("first")
        history.add_entry("second")
        lines = isolated_history_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["text"] == "first"
        assert json.loads(lines[1])["text"] == "second"


class TestHistoryGetEntries:
    def test_get_entries_empty(self) -> None:
        entries = history.get_entries()
        assert entries == []

    def test_get_entries_default_limit(self, isolated_history_file: pathlib.Path) -> None:
        for i in range(150):
            history.add_entry(f"entry {i}")
        entries = history.get_entries()
        assert len(entries) == 100
        assert entries[0]["text"] == "entry 149"
        assert entries[-1]["text"] == "entry 50"

    def test_get_entries_custom_limit(self, isolated_history_file: pathlib.Path) -> None:
        for i in range(10):
            history.add_entry(f"entry {i}")
        entries = history.get_entries(limit=3)
        assert len(entries) == 3
        assert entries[0]["text"] == "entry 9"

    def test_get_entries_ignores_corrupted_lines(self, isolated_history_file: pathlib.Path) -> None:
        isolated_history_file.write_text(
            '{"text": "good"}\nnot json\n{"text": "also good"}\n',
            encoding="utf-8",
        )
        entries = history.get_entries()
        assert len(entries) == 2
        assert entries[0]["text"] == "also good"
        assert entries[1]["text"] == "good"

    def test_get_entries_returns_recent_first(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("alpha")
        history.add_entry("beta")
        entries = history.get_entries()
        assert entries[0]["text"] == "beta"
        assert entries[1]["text"] == "alpha"


class TestHistoryClear:
    def test_clear_removes_file(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("test")
        history.clear()
        assert not isolated_history_file.exists()

    def test_clear_is_noop_when_file_missing(self) -> None:
        history.clear()
        assert history.get_entries() == []


class TestHistoryTrim:
    def test_trim_keeps_latest_max_entries(self, isolated_history_file: pathlib.Path) -> None:
        for i in range(history._MAX_ENTRIES + 50):
            history.add_entry(f"entry {i}")
        history.trim()
        lines = isolated_history_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == history._MAX_ENTRIES
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
        assert first["text"] == "entry 50"
        assert last["text"] == f"entry {history._MAX_ENTRIES + 49}"

    def test_trim_noop_when_under_limit(self, isolated_history_file: pathlib.Path) -> None:
        history.add_entry("one")
        history.add_entry("two")
        history.trim()
        entries = history.get_entries()
        assert len(entries) == 2

    def test_trim_noop_when_file_missing(self) -> None:
        history.trim()
        assert history.get_entries() == []

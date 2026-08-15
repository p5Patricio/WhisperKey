"""Tests for whisperkey.config canonical path and migration logic."""

from __future__ import annotations

import pathlib
import shutil
import sys
import tomllib

import pytest

from whisperkey import config as config_module


@pytest.fixture
def isolated_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect Path.home() to a temp directory so tests never touch ~/.whisperkey."""
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(pathlib.Path, "home", lambda: home)
    return home


@pytest.fixture(autouse=True)
def isolated_project_root(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect project root to a temp directory so tests never touch the real config."""
    from whisperkey.platform import get_platform
    
    # Create a fake project root
    fake_root = tmp_path / "project"
    fake_root.mkdir(parents=True)
    
    # Mock get_project_root to return our fake root
    original_get_project_root = get_platform().get_project_root
    
    def fake_get_project_root():
        return fake_root
    
    monkeypatch.setattr(get_platform(), "get_project_root", fake_get_project_root)
    
    # Also mock _legacy_repo_config_path to use our fake root
    def fake_legacy_path():
        return fake_root / "config.toml"
    
    monkeypatch.setattr(config_module, "_legacy_repo_config_path", fake_legacy_path)
    
    return fake_root


@pytest.fixture(autouse=True)
def isolated_repo_root(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the legacy repo-root config path to a temp directory.

    This is autouse because every config call runs migration first, so we must
    ensure the real repo-root config.toml never leaks into the isolated home.
    """
    legacy = tmp_path / "repo" / "config.toml"
    legacy.parent.mkdir(parents=True)
    monkeypatch.setattr(
        config_module, "_legacy_repo_config_path", lambda: legacy
    )
    return legacy


class TestConfigPath:
    def test_get_config_path_is_absolute_and_under_project_root(
        self, isolated_home: pathlib.Path
    ) -> None:
        # In dev mode (not frozen), config should be in project root
        path = pathlib.Path(config_module.get_config_path())
        assert path.is_absolute()
        assert path.name == "config.toml"
        assert path.parent.exists()

    def test_get_config_path_idempotent(
        self, isolated_home: pathlib.Path
    ) -> None:
        first = config_module.get_config_path()
        second = config_module.get_config_path()
        assert first == second


class TestFirstRun:
    def test_is_first_run_true_when_missing(
        self, isolated_home: pathlib.Path
    ) -> None:
        assert config_module.is_first_run() is True

    def test_is_first_run_true_when_flag_true(
        self, isolated_home: pathlib.Path
    ) -> None:
        config_module.write_config(None, {"app": {"first_run": True}})
        assert config_module.is_first_run() is True

    def test_is_first_run_false_when_flag_false(
        self, isolated_home: pathlib.Path
    ) -> None:
        config_module.write_config(None, {"app": {"first_run": False}})
        assert config_module.is_first_run() is False


class TestLoadConfig:
    def test_load_config_creates_defaults_when_missing(
        self, isolated_home: pathlib.Path
    ) -> None:
        cfg = config_module.load_config()
        assert cfg["app"]["first_run"] is True
        assert cfg["hotkeys"]["ptt"] == "f9"
        assert cfg["audio"]["sample_rate"] == 16000
        canonical = pathlib.Path(config_module.get_config_path())
        assert canonical.exists()

    def test_load_config_merges_user_values(
        self, isolated_home: pathlib.Path
    ) -> None:
        config_module.write_config(None, {"model": {"name": "small"}})
        cfg = config_module.load_config()
        assert cfg["model"]["name"] == "small"
        assert cfg["hotkeys"]["ptt"] == "f9"

    def test_load_config_validates_invalid_position(
        self, isolated_home: pathlib.Path
    ) -> None:
        config_module.write_config(
            None, {"overlay": {"position": "invalid"}}
        )
        with pytest.raises(ValueError):
            config_module.load_config()


class TestWriteConfig:
    def test_write_config_preserves_comments_and_structure(
        self, isolated_home: pathlib.Path
    ) -> None:
        config_module.write_config(None, {"app": {"first_run": False}})
        text = pathlib.Path(config_module.get_config_path()).read_text(
            encoding="utf-8"
        )
        assert "# WhisperKey" in text
        assert "[model]" in text
        assert "[hotkeys]" in text
        assert 'first_run = false' in text

    def test_write_config_explicit_path(
        self, isolated_home: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        explicit = tmp_path / "custom.toml"
        config_module.write_config(str(explicit), {"app": {"first_run": False}})
        assert explicit.exists()
        with open(explicit, "rb") as f:
            cfg = tomllib.load(f)
        assert cfg["app"]["first_run"] is False


class TestMigration:
    def test_legacy_config_is_migrated_to_canonical_path(
        self,
        isolated_home: pathlib.Path,
        isolated_repo_root: pathlib.Path,
    ) -> None:
        isolated_repo_root.write_text(
            '[app]\nfirst_run = false\n\n[model]\nname = "small"\n',
            encoding="utf-8",
        )
        cfg = config_module.load_config()
        canonical = pathlib.Path(config_module.get_config_path())
        assert canonical.exists()
        assert cfg["app"]["first_run"] is False
        assert cfg["model"]["name"] == "small"

    def test_migration_is_skipped_when_canonical_already_exists(
        self,
        isolated_home: pathlib.Path,
        isolated_repo_root: pathlib.Path,
    ) -> None:
        config_module.write_config(
            None, {"app": {"first_run": False}, "model": {"name": "base"}}
        )
        isolated_repo_root.write_text(
            'first_run = true\n[model]\nname = "small"\n',
            encoding="utf-8",
        )
        cfg = config_module.load_config()
        assert cfg["model"]["name"] == "base"

    def test_migration_no_legacy_file_creates_defaults(
        self, isolated_home: pathlib.Path
    ) -> None:
        cfg = config_module.load_config()
        assert cfg["app"]["first_run"] is True


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-specific path assertions"
)
class TestWindowsPath:
    def test_config_path_uses_drive_letter_on_windows(
        self, isolated_home: pathlib.Path
    ) -> None:
        path = pathlib.Path(config_module.get_config_path())
        assert path.drive
        assert len(path.parts) >= 3


def test_defaults_ptt_is_f9() -> None:
    assert config_module.DEFAULTS["hotkeys"]["ptt"] == "f9"
    assert 'ptt = "f9"' in config_module.DEFAULT_TOML_CONTENT


def test_deep_merge_preserves_unmodified_sections() -> None:
    base = {
        "model": {"name": "tiny", "device": "cpu"},
        "transcription": {"prompt": "Custom prompt", "language": "es", "threads": 4},
        "app": {"first_run": False},
    }
    updates = {
        "model": {"name": "base"},
        "audio": {"sample_rate": 16000},
    }
    merged = config_module._deep_merge(base, updates)
    assert merged["transcription"]["prompt"] == "Custom prompt"
    assert merged["transcription"]["language"] == "es"
    assert merged["model"]["name"] == "base"
    assert merged["model"]["device"] == "cpu"
    assert merged["app"]["first_run"] is False


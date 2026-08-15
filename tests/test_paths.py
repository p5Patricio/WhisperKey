"""Tests for frozen-app path resolution."""

from __future__ import annotations

import importlib
import os
import pathlib
import sys

import pytest

from whisperkey import platform as platform_pkg
from whisperkey.platform import get_platform


@pytest.fixture(autouse=True)
def reset_platform_singleton(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(platform_pkg, "_platform_instance", None)
    yield


@pytest.fixture
def win_platform(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "platform", "win32")
    importlib.reload(platform_pkg)
    return get_platform()


class TestGetInstallDir:
    def test_dev_mode_returns_project_root(self, win_platform) -> None:
        assert win_platform.get_install_dir() == win_platform.get_project_root()

    def test_frozen_mode_returns_executable_parent(
        self, win_platform, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(
            sys, "executable", r"C:\Program Files\WhisperKey\WhisperKey.exe"
        )
        install_dir = win_platform.get_install_dir()
        assert install_dir == pathlib.Path(r"C:\Program Files\WhisperKey")

    def test_frozen_mode_different_path(
        self, win_platform, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"D:\Apps\WhisperKey\WhisperKey.exe")
        install_dir = win_platform.get_install_dir()
        assert install_dir == pathlib.Path(r"D:\Apps\WhisperKey")


class TestGetAppdataDir:
    def test_dev_mode_returns_project_root(self, win_platform) -> None:
        assert win_platform.get_appdata_dir() == win_platform.get_project_root()

    def test_frozen_mode_returns_appdata_whisperkey(
        self, win_platform, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("APPDATA", str(tmp_path))
        appdata_dir = win_platform.get_appdata_dir()
        assert appdata_dir == tmp_path / "WhisperKey"
        assert appdata_dir.name == "WhisperKey"

    def test_frozen_mode_uses_appdata_env_var(
        self, win_platform, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        custom_appdata = tmp_path / "custom_appdata"
        custom_appdata.mkdir()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("APPDATA", str(custom_appdata))
        appdata_dir = win_platform.get_appdata_dir()
        assert appdata_dir.parent == custom_appdata


class TestGetProjectRoot:
    def test_returns_absolute_path(self, win_platform) -> None:
        root = win_platform.get_project_root()
        assert root.is_absolute()

    def test_returns_whisperkey_directory(self, win_platform) -> None:
        root = win_platform.get_project_root()
        assert root.name == "WhisperKey"

    def test_contains_whisperkey_package(self, win_platform) -> None:
        root = win_platform.get_project_root()
        assert (root / "whisperkey").is_dir()

    def test_unchanged_by_frozen_flag(
        self, win_platform, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root_before = win_platform.get_project_root()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        root_after = win_platform.get_project_root()
        assert root_before == root_after

"""Rigorous tests for whisperkey.platform abstraction."""

from __future__ import annotations

import importlib
import os
import pathlib
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from whisperkey import platform as platform_pkg
from whisperkey.platform import get_platform
from whisperkey.platform.base import BasePlatform


@pytest.fixture(autouse=True)
def reset_platform_singleton(monkeypatch: pytest.MonkeyPatch):
    """Reset the platform singleton before each test."""
    monkeypatch.setattr(platform_pkg, "_platform_instance", None)
    yield


class TestPlatformFactory:
    def test_get_platform_returns_windows_on_win32(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.__class__.__name__ == "WindowsPlatform"

    def test_get_platform_returns_mac_on_darwin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.__class__.__name__ == "MacPlatform"

    def test_get_platform_returns_linux_on_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.__class__.__name__ == "LinuxPlatform"

    def test_get_platform_raises_on_unsupported_os(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "unknown_os")
        importlib.reload(platform_pkg)
        with pytest.raises(Exception):
            get_platform()

    def test_get_platform_is_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        first = get_platform()
        second = get_platform()
        assert first is second


class TestBasePlatform:
    def test_base_platform_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BasePlatform()  # type: ignore[misc]


class TestWindowsPlatform:
    def test_get_paste_shortcut(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.get_paste_shortcut() == ("ctrl", "v")

    def test_get_project_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        root = platform.get_project_root()
        assert root.is_absolute()
        assert root.name == "WhisperKey"
        assert (root / "whisperkey" / "platform" / "windows.py").exists()

    def test_get_venv_python(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.get_venv_python().name == "python.exe"

    def test_detect_gpu_when_nvidia_smi_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        monkeypatch.setattr("shutil.which", lambda name: None)
        device, compute = platform.detect_gpu()
        assert device == "cpu"
        assert compute == "int8"

    def test_detect_gpu_when_nvidia_smi_returns_gpu(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()

        def fake_which(name: str) -> str | None:
            return "nvidia-smi" if name == "nvidia-smi" else None

        monkeypatch.setattr("shutil.which", fake_which)

        class FakeResult:
            returncode = 0
            stdout = "NVIDIA GeForce RTX 4060\n"

        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kwargs: FakeResult(),
        )
        device, compute = platform.detect_gpu()
        assert device == "cuda"
        assert compute == "int8_float16"

    def test_detect_gpu_when_nvidia_smi_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()

        def fake_which(name: str) -> str | None:
            return "nvidia-smi" if name == "nvidia-smi" else None

        monkeypatch.setattr("shutil.which", fake_which)
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
        )
        device, compute = platform.detect_gpu()
        assert device == "cpu"
        assert compute == "int8"

    def test_generate_launcher(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        monkeypatch.setattr(platform, "get_project_root", lambda: tmp_path)
        platform.generate_launcher()
        launcher = tmp_path / "lanzador.vbs"
        assert launcher.exists()
        text = launcher.read_text(encoding="utf-8")
        assert "WhisperKey" in text
        assert "pythonw.exe" in text
        assert "-m whisperkey" in text

    def test_setup_autostart(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        monkeypatch.setattr(platform, "get_project_root", lambda: tmp_path)
        startup_dir = tmp_path / "startup"
        monkeypatch.setenv("APPDATA", str(tmp_path))
        platform.generate_launcher()
        platform.setup_autostart()
        assert (tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "WhisperKey.vbs").exists()

    def test_remove_autostart(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        startup_dir = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_dir.mkdir(parents=True)
        startup_file = startup_dir / "WhisperKey.vbs"
        startup_file.write_text("test", encoding="utf-8")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        platform.remove_autostart()
        assert not startup_file.exists()

    def test_is_autostart_enabled(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()
        startup_dir = tmp_path / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_dir.mkdir(parents=True)
        startup_file = startup_dir / "WhisperKey.vbs"
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert platform.is_autostart_enabled() is False
        startup_file.write_text("test", encoding="utf-8")
        assert platform.is_autostart_enabled() is True


class TestMacAndLinuxCommon:
    def test_linux_paste_shortcut(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.get_paste_shortcut() == ("ctrl", "v")

    def test_mac_paste_shortcut(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        importlib.reload(platform_pkg)
        platform = get_platform()
        assert platform.get_paste_shortcut() == ("command", "v")

    def test_mac_detect_gpu_arm_mps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        importlib.reload(platform_pkg)
        platform = get_platform()
        monkeypatch.setattr("platform.machine", lambda: "arm64")
        device, compute = platform.detect_gpu()
        assert device == "mps"
        assert compute == "float16"

    def test_linux_detect_gpu_no_nvidia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        importlib.reload(platform_pkg)
        platform = get_platform()
        monkeypatch.setattr("shutil.which", lambda name: None)
        device, compute = platform.detect_gpu()
        assert device == "cpu"
        assert compute == "int8"


class TestSingleInstanceLock:
    def test_windows_single_instance_lock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        importlib.reload(platform_pkg)
        platform = get_platform()

        # First acquisition should succeed
        success1, handle1 = platform.acquire_single_instance_lock("Test_Unique_Mutex_1")
        assert success1 is True

        # Second acquisition with same name should report already exists (False)
        success2, handle2 = platform.acquire_single_instance_lock("Test_Unique_Mutex_1")
        assert success2 is False
        assert handle2 is None

        # Clean up
        platform.release_single_instance_lock(handle1)

    def test_base_platform_single_instance_lock_fallback(self) -> None:
        class DummyPlatform(BasePlatform):
            def play_beep(self, freq: int, duration: float) -> None: pass
            def get_paste_shortcut(self) -> tuple[str, str]: return ("ctrl", "v")
            def detect_gpu(self) -> tuple[str, str]: return ("cpu", "int8")
            def setup_autostart(self) -> None: pass
            def remove_autostart(self) -> None: pass
            def is_autostart_enabled(self) -> bool: return False
            def get_venv_python(self) -> pathlib.Path: return pathlib.Path("python")
            def get_project_root(self) -> pathlib.Path: return pathlib.Path(".")

        dummy = DummyPlatform()
        success, handle = dummy.acquire_single_instance_lock()
        assert success is True
        assert handle is None
        dummy.release_single_instance_lock(handle)


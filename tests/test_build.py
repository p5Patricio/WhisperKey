"""Integration tests for PyInstaller build pipeline."""

from __future__ import annotations

import pathlib
import sys
from unittest.mock import patch

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
SPEC_FILE = PROJECT_ROOT / "WhisperKey.spec"
BUILD_SCRIPT = PROJECT_ROOT / "tools" / "build.py"
ASSETS_DIR = PROJECT_ROOT / "assets"
BIN_DIR = ASSETS_DIR / "bin"
ICONS_DIR = ASSETS_DIR / "icons"


class TestBuildPipeline:
    """Integration tests for build pipeline (requires PyInstaller)."""

    def test_build_script_exists(self) -> None:
        """Verify build script exists."""
        assert BUILD_SCRIPT.exists(), "tools/build.py not found"

    def test_spec_file_exists(self) -> None:
        """Verify WhisperKey.spec exists."""
        assert SPEC_FILE.exists(), "WhisperKey.spec not found"

    def test_whisper_cpp_binaries_in_spec(self) -> None:
        """Verify whisper.cpp binaries are included in spec."""
        spec_content = SPEC_FILE.read_text(encoding="utf-8")
        assert "assets/bin" in spec_content

    def test_assets_in_spec(self) -> None:
        """Verify assets are included in spec."""
        spec_content = SPEC_FILE.read_text(encoding="utf-8")
        assert "assets/icons" in spec_content

    def test_version_in_spec(self) -> None:
        """Verify version is imported in spec."""
        spec_content = SPEC_FILE.read_text(encoding="utf-8")
        assert "whisperkey.version" in spec_content

    def test_spec_includes_hidden_imports(self) -> None:
        """Verify critical hidden imports are in spec."""
        spec_content = SPEC_FILE.read_text(encoding="utf-8")
        expected = [
            "whisperkey.platform.windows",
            "whisperkey.splash",
            "whisperkey.settings_gui",
            "whisperkey.updater",
        ]
        for module in expected:
            assert module in spec_content, f"{module} missing from spec hiddenimports"

    def test_spec_icon_path(self) -> None:
        """Verify spec references app.ico icon."""
        spec_content = SPEC_FILE.read_text(encoding="utf-8")
        assert "app.ico" in spec_content


class TestWhisperCppBinaries:
    """Tests for whisper.cpp binary inclusion."""

    @pytest.mark.skipif(
        not BIN_DIR.exists(),
        reason="assets/bin/ not found — run whisper.cpp build first",
    )
    def test_main_exe_exists_in_assets(self) -> None:
        """Verify main.exe exists in assets/bin/."""
        main_exe = BIN_DIR / "main.exe"
        assert main_exe.exists(), "whisper.cpp main.exe not found in assets/bin/"

    @pytest.mark.skipif(
        not BIN_DIR.exists(),
        reason="assets/bin/ not found — run whisper.cpp build first",
    )
    def test_whisper_dll_exists_in_assets(self) -> None:
        """Verify whisper.dll exists in assets/bin/."""
        whisper_dll = BIN_DIR / "whisper.dll"
        assert whisper_dll.exists(), "whisper.dll not found in assets/bin/"

    @pytest.mark.skipif(
        not BIN_DIR.exists(),
        reason="assets/bin/ not found — run whisper.cpp build first",
    )
    def test_cuda_dll_optional(self) -> None:
        """Verify CUDA DLL exists in assets/bin/ (optional)."""
        cublas_dll = BIN_DIR / "cublas64_12.dll"
        if cublas_dll.exists():
            assert cublas_dll.stat().st_size > 0


class TestAssets:
    """Tests for asset inclusion."""

    def test_logo_exists(self) -> None:
        """Verify logo.png exists."""
        logo = ASSETS_DIR / "logo.png"
        assert logo.exists(), "logo.png not found in assets/"
        assert logo.stat().st_size > 0

    def test_tray_icons_exist(self) -> None:
        """Verify tray icons exist."""
        assert ICONS_DIR.exists(), "assets/icons/ directory not found"

        required_icons = [
            "tray_idle.png",
            "tray_ready.png",
            "tray_loading.png",
            "tray_error.png",
        ]

        for icon in required_icons:
            icon_path = ICONS_DIR / icon
            assert icon_path.exists(), f"{icon} not found in assets/icons/"
            assert icon_path.stat().st_size > 0, f"{icon} is empty"

    def test_app_icon_exists(self) -> None:
        """Verify app.ico exists."""
        app_ico = ICONS_DIR / "app.ico"
        assert app_ico.exists(), "app.ico not found in assets/icons/"
        assert app_ico.stat().st_size > 0


class TestE2EWhisperCpp:
    """E2E tests for whisper.cpp execution (requires manual testing)."""

    @pytest.mark.skip(reason="Requires manual E2E testing with installed app")
    def test_installed_app_can_execute_whisper_cpp(self) -> None:
        """Verify installed app can execute whisper.cpp.

        Manual test steps:
        1. Build installer with `installer/build.bat`
        2. Install WhisperKey-Setup.exe
        3. Launch installed app
        4. Verify transcription works
        """

    @pytest.mark.skip(reason="Requires manual E2E testing")
    def test_installed_app_preserves_config(self) -> None:
        """Verify installed app preserves config after reinstall.

        Manual test steps:
        1. Install WhisperKey
        2. Configure custom settings
        3. Uninstall (preserve config)
        4. Reinstall
        5. Verify settings preserved
        """

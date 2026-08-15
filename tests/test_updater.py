"""Rigorous tests for the update checker."""

from __future__ import annotations

import hashlib
import pathlib
from unittest.mock import MagicMock

import pytest

from whisperkey import updater


@pytest.fixture
def mock_requests(monkeypatch: pytest.MonkeyPatch):
    """Mock requests.get and return a configurable response."""
    call_log: list[dict[str, object]] = []

    def fake_get(url: str, timeout: float = 15, **kwargs: object) -> MagicMock:
        call_log.append({"url": url, "timeout": timeout})
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/example/release",
            "body": "New features!",
        }
        return response

    monkeypatch.setattr("requests.get", fake_get)
    return call_log


class TestCheckUpdate:
    def test_update_available_when_newer(self, mock_requests: list) -> None:
        monkeypatch = pytest.MonkeyPatch()
        with monkeypatch.context() as m:
            m.setattr(updater, "VERSION", "1.0.0")
            is_newer, version, url, changelog = updater.check_update()
            assert is_newer is True
            assert version == "1.2.0"
            assert url == "https://github.com/example/release"
            assert changelog == "New features!"

    def test_no_update_when_current_is_newer(self, mock_requests: list) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.setattr(updater, "VERSION", "2.0.0")
            is_newer, version, _, _ = updater.check_update()
            assert is_newer is False
            assert version == "1.2.0"

    def test_no_update_when_same_version(self, mock_requests: list) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.setattr(updater, "VERSION", "1.2.0")
            is_newer, version, _, _ = updater.check_update()
            assert is_newer is False
            assert version == "1.2.0"

    def test_update_when_major_behind(self, mock_requests: list) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.setattr(updater, "VERSION", "0.9.5")
            is_newer, version, _, _ = updater.check_update()
            assert is_newer is True
            assert version == "1.2.0"

    def test_api_url_is_correct(self, mock_requests: list) -> None:
        updater.check_update()
        assert mock_requests[0]["url"] == updater._API_URL
        assert mock_requests[0]["timeout"] == 15

    def test_check_update_raises_when_requests_missing(self, mock_requests: list) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.delattr("requests.get", raising=False)

            def fake_import(name: str, *args: object, **kwargs: object) -> object:
                if name == "requests":
                    raise ImportError("No module named requests")
                return __builtins__["__import__"](name, *args, **kwargs)

            m.setattr("builtins.__import__", fake_import)
            with pytest.raises(RuntimeError):
                updater.check_update()

    def test_parse_ignores_non_numeric_version_parts(self, mock_requests: list) -> None:
        with pytest.MonkeyPatch().context() as m:
            response = MagicMock()
            response.raise_for_status = MagicMock()
            response.json.return_value = {
                "tag_name": "v1.2.0-beta.1",
                "html_url": "",
                "body": "",
            }
            m.setattr("requests.get", lambda *args, **kwargs: response)
            m.setattr(updater, "VERSION", "1.0.0")
            is_newer, version, _, _ = updater.check_update()
            assert is_newer is True
            assert version == "1.2.0-beta.1"

    def test_check_update_propagates_http_error(self, mock_requests: list) -> None:
        def failing_get(url: str, **kwargs: object) -> MagicMock:
            response = MagicMock()
            response.raise_for_status.side_effect = Exception("HTTP 500")
            return response

        with pytest.MonkeyPatch().context() as m:
            m.setattr("requests.get", failing_get)
            with pytest.raises(Exception):
                updater.check_update()


class TestSHA256Verification:
    def test_valid_hash_passes(self, tmp_path: pathlib.Path) -> None:
        test_file = tmp_path / "test.exe"
        test_file.write_bytes(b"test content")
        expected = hashlib.sha256(b"test content").hexdigest()
        assert updater.verify_sha256(test_file, expected) is True

    def test_invalid_hash_fails(self, tmp_path: pathlib.Path) -> None:
        test_file = tmp_path / "test.exe"
        test_file.write_bytes(b"test content")
        assert updater.verify_sha256(test_file, "wrong_hash") is False

    def test_missing_file_returns_false(self, tmp_path: pathlib.Path) -> None:
        missing = tmp_path / "nonexistent.exe"
        assert updater.verify_sha256(missing, "any_hash") is False

    def test_empty_file_hashes_correctly(self, tmp_path: pathlib.Path) -> None:
        test_file = tmp_path / "empty.exe"
        test_file.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert updater.verify_sha256(test_file, expected) is True


class TestDownloadInstaller:
    def test_download_failure_returns_false(self, tmp_path: pathlib.Path) -> None:
        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "requests.get",
                lambda *a, **kw: (_ for _ in ()).throw(Exception("Network error")),
            )
            dest = tmp_path / "installer.exe"
            assert updater.download_installer("http://example.com/installer.exe", dest) is False

    def test_download_success_returns_true(self, tmp_path: pathlib.Path) -> None:
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "12"}
        mock_response.iter_content.return_value = [b"fake_content!!"]
        mock_response.raise_for_status = MagicMock()

        with pytest.MonkeyPatch().context() as m:
            m.setattr("requests.get", lambda *a, **kw: mock_response)
            dest = tmp_path / "installer.exe"
            assert updater.download_installer("http://example.com/installer.exe", dest) is True
            assert dest.exists()
            assert dest.read_bytes() == b"fake_content!!"

    def test_download_http_error_returns_false(self, tmp_path: pathlib.Path) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 404")

        with pytest.MonkeyPatch().context() as m:
            m.setattr("requests.get", lambda *a, **kw: mock_response)
            dest = tmp_path / "installer.exe"
            assert updater.download_installer("http://example.com/installer.exe", dest) is False


class TestLaunchSilentInstall:
    def test_launch_with_correct_args(self, tmp_path: pathlib.Path) -> None:
        installer = tmp_path / "installer.exe"
        installer.write_bytes(b"fake")

        mock_popen = MagicMock()

        with pytest.MonkeyPatch().context() as m:
            m.setattr("subprocess.Popen", mock_popen)
            m.setattr("sys.exit", lambda code: None)
            result = updater.launch_silent_install(installer)

            assert result is True
            call_args = mock_popen.call_args[0][0]
            assert str(installer) in call_args
            assert "/SILENT" in call_args
            assert "/CLOSEAPPLICATIONS" in call_args

    def test_launch_calls_sys_exit(self, tmp_path: pathlib.Path) -> None:
        installer = tmp_path / "installer.exe"
        installer.write_bytes(b"fake")

        exit_called = []

        def fake_exit(code: int) -> None:
            exit_called.append(code)

        with pytest.MonkeyPatch().context() as m:
            m.setattr("subprocess.Popen", MagicMock())
            m.setattr("sys.exit", fake_exit)
            updater.launch_silent_install(installer)
            assert exit_called == [0]

    def test_launch_failure_returns_false(self, tmp_path: pathlib.Path) -> None:
        installer = tmp_path / "installer.exe"
        installer.write_bytes(b"fake")

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "subprocess.Popen",
                lambda *a, **kw: (_ for _ in ()).throw(OSError("Cannot launch")),
            )
            result = updater.launch_silent_install(installer)
            assert result is False

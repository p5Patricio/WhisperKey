"""Rigorous tests for the update checker."""

from __future__ import annotations

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

"""Regression tests for the whisper.cpp engine contract.

These cover the failure modes that made v1.2.0 lose transcription accuracy:
a binary that could not be found inside the release zip's nested layout, and a
stale binary that silently discarded every request parameter.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from whisperkey.engine import (
    EngineCapabilities,
    WhisperServer,
    default_engine_threads,
    resolve_server_exe,
)

SERVER_NAME = "whisper-server.exe" if sys.platform == "win32" else "whisper-server"
LEGACY_NAME = "server.exe" if sys.platform == "win32" else "server"


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


class TestResolveServerExe:
    def test_finds_flat_layout(self, tmp_path: Path) -> None:
        expected = _touch(tmp_path / SERVER_NAME)
        assert resolve_server_exe(tmp_path) == expected

    def test_finds_nested_release_layout(self, tmp_path: Path) -> None:
        """The CUDA release zip extracts into a Release/ subdirectory.

        Missing this is what made the app re-download 670 MB on every launch.
        """
        expected = _touch(tmp_path / "Release" / SERVER_NAME)
        assert resolve_server_exe(tmp_path) == expected

    def test_finds_nested_bin_layout(self, tmp_path: Path) -> None:
        expected = _touch(tmp_path / "bin" / SERVER_NAME)
        assert resolve_server_exe(tmp_path) == expected

    def test_falls_back_to_legacy_name(self, tmp_path: Path) -> None:
        expected = _touch(tmp_path / LEGACY_NAME)
        assert resolve_server_exe(tmp_path) == expected

    def test_prefers_modern_name_over_legacy(self, tmp_path: Path) -> None:
        modern = _touch(tmp_path / SERVER_NAME)
        _touch(tmp_path / LEGACY_NAME)
        assert resolve_server_exe(tmp_path) == modern

    def test_returns_none_when_absent(self, tmp_path: Path) -> None:
        assert resolve_server_exe(tmp_path) is None


class TestEngineCapabilities:
    def test_unknown_accepts_nothing(self) -> None:
        caps = EngineCapabilities.unknown()
        assert caps.accepts_request_params is False
        assert caps.supports_field("prompt") is False
        assert caps.supports_flag("vad") is False

    def test_binary_without_param_table_reports_no_request_fields(
        self, tmp_path: Path
    ) -> None:
        """Old builds parse no form fields at all, even ones they name."""
        exe = tmp_path / "old-server.bin"
        exe.write_bytes(b"\x00prompt\x00\x00language\x00")
        assert EngineCapabilities.probe(exe).request_fields == frozenset()

    def test_binary_with_param_table_reports_its_fields(self, tmp_path: Path) -> None:
        exe = tmp_path / "new-server.bin"
        exe.write_bytes(
            b"\x00response_format\x00\x00prompt\x00\x00beam_size\x00\x00vad\x00"
        )
        caps = EngineCapabilities.probe(exe)
        assert caps.accepts_request_params is True
        assert caps.supports_field("prompt")
        assert caps.supports_field("beam_size")
        assert not caps.supports_field("temperature_inc")

    def test_probe_of_missing_file_is_not_fatal(self, tmp_path: Path) -> None:
        caps = EngineCapabilities.probe(tmp_path / "nope.exe")
        assert caps.accepts_request_params is False


class TestRequestPayload:
    def _server(self, caps: EngineCapabilities, **kwargs) -> WhisperServer:
        server = WhisperServer(Path("engine.exe"), Path("model.bin"), **kwargs)
        server.capabilities = caps
        return server

    def test_sends_nothing_the_engine_cannot_parse(self) -> None:
        """A field the build ignores must not be sent: it looks like it worked."""
        server = self._server(EngineCapabilities.unknown(), prompt="spanglish")
        assert server._build_request_data("spanglish", "es") == {}

    def test_sends_supported_fields(self) -> None:
        caps = EngineCapabilities(
            flags=frozenset(),
            request_fields=frozenset(
                {"response_format", "temperature", "prompt", "language", "beam_size"}
            ),
        )
        server = self._server(caps, beam_size=5)
        data = server._build_request_data("spanglish", "es")
        assert data["prompt"] == "spanglish"
        assert data["language"] == "es"
        assert data["beam_size"] == "5"
        assert data["response_format"] == "json"
        assert "suppress_nst" not in data

    def test_auto_language_is_not_forced(self) -> None:
        caps = EngineCapabilities(flags=frozenset(), request_fields=frozenset({"language"}))
        server = self._server(caps, language="auto")
        assert "language" not in server._build_request_data("", None)


class TestStartupFlags:
    def test_prompt_passed_as_flag_for_old_engines(self) -> None:
        """The startup flag is the only path left when requests are ignored."""
        caps = EngineCapabilities(flags=frozenset({"prompt", "beam-size"}), request_fields=frozenset())
        server = WhisperServer(Path("e.exe"), Path("m.bin"), prompt="spanglish", beam_size=5)
        server.capabilities = caps
        flags = server._startup_decoding_flags()
        assert flags[:2] == ["--prompt", "spanglish"]
        assert "-bs" in flags

    def test_unsupported_flags_are_omitted(self) -> None:
        server = WhisperServer(Path("e.exe"), Path("m.bin"), prompt="x", beam_size=5)
        server.capabilities = EngineCapabilities.unknown()
        assert server._startup_decoding_flags() == []

    def test_vad_requires_flag_and_model_file(self, tmp_path: Path) -> None:
        vad_model = _touch(tmp_path / "silero.bin")
        caps = EngineCapabilities(
            flags=frozenset({"vad", "vad-model"}), request_fields=frozenset()
        )
        server = WhisperServer(
            Path("e.exe"), Path("m.bin"), beam_size=1, suppress_nst=False,
            vad_model_path=vad_model,
        )
        server.capabilities = caps
        assert server._startup_decoding_flags() == ["--vad", "-vm", str(vad_model)]

    def test_vad_skipped_when_model_missing(self, tmp_path: Path) -> None:
        caps = EngineCapabilities(
            flags=frozenset({"vad", "vad-model"}), request_fields=frozenset()
        )
        server = WhisperServer(
            Path("e.exe"), Path("m.bin"), beam_size=1, suppress_nst=False,
            vad_model_path=tmp_path / "absent.bin",
        )
        server.capabilities = caps
        assert server._startup_decoding_flags() == []


class TestEngineThreads:
    def test_leaves_headroom_for_the_audio_callback(self) -> None:
        import os

        cpus = os.cpu_count() or 4
        threads = default_engine_threads()
        assert threads >= 1
        assert threads <= max(1, cpus - 2)

    def test_never_returns_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("os.cpu_count", lambda: 1)
        assert default_engine_threads() == 1

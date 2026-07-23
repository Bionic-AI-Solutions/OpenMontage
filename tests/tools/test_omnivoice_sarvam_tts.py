"""Unit tests for OmniVoice and Sarvam TTS tools (mocked HTTP)."""

from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest

from tools.audio.omnivoice_tts import OmniVoiceTTS
from tools.audio.sarvam_tts import SarvamTTS, _resolve_target_language
from tools.base_tool import ToolStatus


class _BytesResp:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status
        self.headers = {"Content-Type": "audio/wav"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _minimal_wav(payload_len: int = 2000) -> bytes:
    # RIFF header + PCM payload large enough to pass the empty-audio guard.
    data_size = payload_len
    riff_size = 36 + data_size
    header = (
        b"RIFF"
        + riff_size.to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + (1).to_bytes(2, "little")
        + (1).to_bytes(2, "little")
        + (24000).to_bytes(4, "little")
        + (48000).to_bytes(4, "little")
        + (2).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + b"data"
        + data_size.to_bytes(4, "little")
    )
    return header + (b"\x00" * data_size)


def test_omnivoice_available_when_healthz_ok(monkeypatch):
    tool = OmniVoiceTTS()
    monkeypatch.setenv("OMNIVOICE_BASE_URL", "http://omnivoice.test:7861")

    def fake_urlopen(req, timeout=5):
        assert req.full_url.endswith("/healthz")
        return _BytesResp(b'{"status":"ok"}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert tool.get_status() == ToolStatus.AVAILABLE


def test_omnivoice_generate_writes_wav(monkeypatch, tmp_path):
    tool = OmniVoiceTTS()
    monkeypatch.setenv("OMNIVOICE_BASE_URL", "http://omnivoice.test:7861")
    wav = _minimal_wav()

    def fake_urlopen(req, timeout=180):
        assert "/v1/audio/speech" in req.full_url
        return _BytesResp(wav)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "tools.analysis.audio_probe.probe_duration", lambda p: 1.25
    )

    out = tmp_path / "n.wav"
    result = tool.execute({"text": "Hello weights.", "output_path": str(out)})
    assert result.success is True
    assert out.exists()
    assert out.stat().st_size > 1000
    assert result.data["provider"] == "omnivoice"
    assert result.cost_usd == 0.0


def test_sarvam_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert SarvamTTS().get_status() == ToolStatus.UNAVAILABLE


def test_sarvam_language_resolution():
    assert _resolve_target_language("hi") == "hi-IN"
    assert _resolve_target_language("en-IN") == "en-IN"
    assert _resolve_target_language(None) == "en-IN"


def test_sarvam_generate_decodes_base64(monkeypatch, tmp_path):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    tool = SarvamTTS()
    wav = _minimal_wav()
    payload = json.dumps(
        {"audios": [base64.b64encode(wav).decode("ascii")], "request_id": "r1"}
    ).encode()

    def fake_urlopen(req, timeout=90):
        assert req.full_url.endswith("/text-to-speech")
        headers = {k.lower(): v for k, v in req.header_items()}
        assert headers.get("api-subscription-key") == "test-key"
        return _BytesResp(payload)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(
        "tools.analysis.audio_probe.probe_duration", lambda p: 2.0
    )

    out = tmp_path / "s.wav"
    result = tool.execute(
        {
            "text": "Weights that wake up.",
            "voice": "abhilash",
            "language": "en",
            "output_path": str(out),
        }
    )
    assert result.success is True
    assert out.read_bytes()[:4] == b"RIFF"
    assert result.data["voice"] == "abhilash"
    assert result.data["language"] == "en-IN"

"""Unit tests for gpu-ai client helpers and tools (mocked HTTP)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from lib import gpu_ai_client as client
from tools.base_tool import ToolStatus
from tools.gpu_ai.genimage import GenImage
from tools.gpu_ai.media_services import MediaServices
from tools.gpu_ai.tts import GpuAiTTS


class _Resp:
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
        self.body = body
        self.status = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}

    def json(self):
        return json.loads(self.body.decode())


def test_gpu_ai_tts_writes_audio(monkeypatch, tmp_path):
    wav = b"RIFF" + b"\x00" * 1200

    def fake_post_json(url, payload, timeout=180):
        assert url.endswith("/v1/audio/speech")
        assert payload["voice"] == "aditya"
        return _Resp(wav)

    monkeypatch.setenv("GPU_AI_BASE_URL", "http://gpu-ai.test")
    monkeypatch.setattr(client, "post_json", fake_post_json)
    monkeypatch.setattr(
        "tools.analysis.audio_probe.probe_duration", lambda p: 1.5
    )
    monkeypatch.setattr(GpuAiTTS, "get_status", lambda self: ToolStatus.AVAILABLE)

    out = tmp_path / "n.wav"
    result = GpuAiTTS().execute(
        {"text": "Hello", "voice": "aditya", "output_path": str(out)}
    )
    assert result.success is True
    assert out.read_bytes() == wav


def test_gpu_ai_tts_accepts_voice_id(monkeypatch, tmp_path):
    wav = b"RIFF" + b"\x00" * 1200

    def fake_post_json(url, payload, timeout=180):
        assert payload["voice"] == "aditya"
        return _Resp(wav)

    monkeypatch.setenv("GPU_AI_BASE_URL", "http://gpu-ai.test")
    monkeypatch.setattr(client, "post_json", fake_post_json)
    monkeypatch.setattr(
        "tools.analysis.audio_probe.probe_duration", lambda p: 1.0
    )

    out = tmp_path / "n2.wav"
    result = GpuAiTTS().execute(
        {"text": "Hi", "voice_id": "aditya", "output_path": str(out)}
    )
    assert result.success is True


def test_genimage_surfaces_runware_credit_hint(monkeypatch, tmp_path):
    class FakeSession:
        def initialize(self):
            return None

        def call_tool(self, name, args, timeout=300):
            return {
                "success": False,
                "backend": "runware",
                "error": 'HTTP error: 400 - {"errors":[{"code":"insufficientCredits"}]}',
            }

    monkeypatch.setattr(client, "GenImageSession", FakeSession)
    result = GenImage().execute(
        {
            "operation": "generate",
            "prompt": "x",
            "output_path": str(tmp_path / "x.png"),
        }
    )
    assert result.success is False
    assert "openai_image" in (result.error or "")
    assert result.data.get("backend") == "runware"


def test_genimage_generate_decodes_png(monkeypatch, tmp_path):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    b64 = base64.b64encode(png).decode()

    class FakeSession:
        def initialize(self):
            return None

        def call_tool(self, name, args, timeout=300):
            assert name == "gi_generate_image"
            assert args["tenant_id"] == "base"
            return {"success": True, "image_data": b64, "backend": "comfyui"}

    monkeypatch.setattr(client, "GenImageSession", FakeSession)
    monkeypatch.setattr(GenImage, "get_status", lambda self: ToolStatus.AVAILABLE)

    out = tmp_path / "g.png"
    result = GenImage().execute(
        {
            "operation": "generate",
            "prompt": "a lighthouse",
            "output_path": str(out),
        }
    )
    assert result.success is True
    assert out.read_bytes().startswith(b"\x89PNG")
    assert result.data["backend"] == "comfyui"


def test_media_services_polls(monkeypatch, tmp_path):
    monkeypatch.setattr(
        client,
        "submit_media_job",
        lambda service, **kw: {"job_id": "j1", "status": "queued"},
    )
    monkeypatch.setattr(
        client,
        "poll_media_job",
        lambda service, job_id, **kw: {
            "job_id": job_id,
            "status": "done",
            "result": {"cuts": 3},
        },
    )
    monkeypatch.setattr(
        MediaServices, "get_status", lambda self: ToolStatus.AVAILABLE
    )

    out = tmp_path / "job.json"
    result = MediaServices().execute(
        {
            "service": "scenes",
            "url": "https://example.com/a.mp4",
            "output_path": str(out),
        }
    )
    assert result.success is True
    assert result.data["job_id"] == "j1"
    assert out.exists()


def test_parse_sse_json():
    body = (
        b"event: message\r\n"
        b'data: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\r\n\r\n'
    )
    assert client._parse_sse_json(body)["result"]["ok"] is True

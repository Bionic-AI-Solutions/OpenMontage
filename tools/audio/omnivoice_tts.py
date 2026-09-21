"""OmniVoice in-cluster / gateway text-to-speech provider tool.

Talks to the OmniVoice HTTP API (default: in-cluster ai-services).
Uses a registered voice_id, or voice design via ``instruct``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

DEFAULT_BASE_URL = "http://omnivoice-api.ai-services.svc.cluster.local:7861"
# Stable registered clone on the cluster OmniVoice service (from /v1/info).
DEFAULT_VOICE_ID = "c32af141013d"


class OmniVoiceTTS(BaseTool):
    name = "omnivoice_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "omnivoice"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "OmniVoice runs in-cluster by default.\n"
        "  export OMNIVOICE_BASE_URL=http://omnivoice-api.ai-services.svc.cluster.local:7861\n"
        "Or via the gpu-ai gateway:\n"
        "  export OMNIVOICE_BASE_URL=https://mcp.baisoln.com/gpu-ai\n"
        "  export OMNIVOICE_API_KEY=<X-API-Key>\n"
        "List voices: GET $OMNIVOICE_BASE_URL/v1/info"
    )
    fallback = "sarvam_tts"
    fallback_tools = ["sarvam_tts", "openai_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "voice_design",
        "multilingual",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "instruct": True,
    }
    best_for = [
        "in-cluster narration with no per-character cost",
        "English explainer voiceover",
        "multilingual zero-shot TTS",
    ]
    not_good_for = [
        "offline air-gapped hosts without cluster/gateway access",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice": {
                "type": "string",
                "default": DEFAULT_VOICE_ID,
                "description": "Registered OmniVoice voice_id (from /v1/info).",
            },
            "instruct": {
                "type": "string",
                "description": (
                    "Voice-design instruction (gender/age/pitch/accent). "
                    "Used with /v1/audio/speech when no usable voice is set."
                ),
            },
            "language": {
                "type": "string",
                "default": "en",
                "description": "Language hint (ASCII English → en; omit for auto).",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.5,
                "maximum": 1.5,
            },
            "format": {
                "type": "string",
                "default": "wav",
                "enum": ["wav", "mp3", "pcm", "opus"],
            },
            "response_format": {
                "type": "string",
                "default": "wav",
                "enum": ["wav", "mp3", "pcm", "opus"],
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "503", "429"])
    idempotency_key_fields = ["text", "voice", "instruct", "language", "speed", "format"]
    side_effects = ["writes audio file to output_path", "calls OmniVoice API"]
    user_visible_verification = ["Listen to generated audio for intelligibility and tone"]

    @staticmethod
    def _base_url() -> str:
        return (
            os.environ.get("OMNIVOICE_BASE_URL")
            or os.environ.get("OMNIVOICE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")

    def get_status(self) -> ToolStatus:
        base = self._base_url()
        # In-cluster URL is available without a key; gateway needs API key.
        if "mcp.baisoln.com" in base and not os.environ.get("OMNIVOICE_API_KEY"):
            return ToolStatus.UNAVAILABLE
        try:
            req = urllib.request.Request(
                f"{base}/healthz",
                headers=self._headers(),
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return ToolStatus.AVAILABLE
        except Exception:
            # Gateway may not expose /healthz — fall back to /v1/info
            try:
                req = urllib.request.Request(
                    f"{base}/v1/info",
                    headers=self._headers(),
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        return ToolStatus.AVAILABLE
            except Exception:
                return ToolStatus.UNAVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # In-cluster OmniVoice has no per-character billing.
        return 0.0

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "audio/wav, application/json, */*"}
        api_key = os.environ.get("OMNIVOICE_API_KEY") or os.environ.get("MCP_API_KEY")
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            result = self._generate(inputs)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            return ToolResult(
                success=False,
                error=f"OmniVoice TTS HTTP {exc.code}: {body}",
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"OmniVoice TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = 0.0
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        from tools.analysis.audio_probe import probe_duration

        text = inputs["text"]
        voice = inputs.get("voice") or os.environ.get("OMNIVOICE_DEFAULT_VOICE_ID") or DEFAULT_VOICE_ID
        instruct = inputs.get("instruct")
        language = inputs.get("language", "en")
        speed = float(inputs.get("speed", 1.0))
        fmt = inputs.get("response_format") or inputs.get("format", "wav")
        base = self._base_url()

        output_path = Path(inputs.get("output_path", f"omnivoice_tts.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Prefer OpenAI-compatible /v1/audio/speech with a registered voice.
        payload: dict[str, Any] = {
            "model": "omnivoice",
            "input": text,
            "response_format": fmt,
            "speed": speed,
        }
        if language:
            payload["language"] = language
        if voice:
            payload["voice"] = voice
        if instruct:
            payload["instruct"] = instruct

        audio = self._post_json(f"{base}/v1/audio/speech", payload)
        if len(audio) < 1000:
            # Empty/near-empty WAV — retry via by-voice form endpoint.
            if not voice:
                return ToolResult(
                    success=False,
                    error=(
                        "OmniVoice returned empty audio. Provide a registered "
                        f"voice_id (default {DEFAULT_VOICE_ID}) or a usable instruct."
                    ),
                )
            audio = self._post_form(
                f"{base}/v1/tts/by-voice/{urllib.parse.quote(voice)}",
                {
                    "text": text,
                    "language": language or "",
                    "speed": str(speed),
                    **({"instruct": instruct} if instruct else {}),
                },
            )

        if len(audio) < 1000:
            return ToolResult(
                success=False,
                error=f"OmniVoice returned too little audio ({len(audio)} bytes)",
            )

        output_path.write_bytes(audio)
        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "omnivoice",
                "voice": voice,
                "instruct": instruct,
                "language": language,
                "format": fmt,
                "speed": speed,
                "text_length": len(text),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "base_url": base,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model="omnivoice",
        )

    def _post_json(self, url: str, payload: dict[str, Any]) -> bytes:
        body = json.dumps(payload).encode("utf-8")
        headers = {**self._headers(), "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.read()

    def _post_form(self, url: str, fields: dict[str, str]) -> bytes:
        body = urllib.parse.urlencode({k: v for k, v in fields.items() if v != ""}).encode("utf-8")
        headers = {
            **self._headers(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.read()

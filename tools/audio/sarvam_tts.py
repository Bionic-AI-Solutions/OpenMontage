"""Sarvam AI text-to-speech provider tool (Indic-focused Bulbul models).

API: https://api.sarvam.ai/text-to-speech
Auth: api-subscription-key: $SARVAM_API_KEY
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

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

_DEFAULT_MODEL = "bulbul:v2"
_DEFAULT_LANG = "en-IN"
_DEFAULT_SPEAKER = "anushka"

_LANGUAGE_CODE_MAP = {
    "hi": "hi-IN",
    "mr": "mr-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "bn": "bn-IN",
    "kn": "kn-IN",
    "gu": "gu-IN",
    "od": "od-IN",
    "or": "od-IN",
    "pa": "pa-IN",
    "ml": "ml-IN",
    "en": "en-IN",
}

SARVAM_SPEAKERS = (
    "anushka",
    "abhilash",
    "manisha",
    "vidya",
    "arya",
    "karun",
    "hitesh",
    "diya",
    "maitreyi",
)


def _resolve_target_language(language: Optional[str]) -> str:
    if not language:
        return _DEFAULT_LANG
    mapped = _LANGUAGE_CODE_MAP.get(language.lower())
    if mapped:
        return mapped
    if "-" in language:
        return language
    return _DEFAULT_LANG


class SarvamTTS(BaseTool):
    name = "sarvam_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "sarvam"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set the SARVAM_API_KEY environment variable:\n"
        "  export SARVAM_API_KEY=your_key_here\n"
        "Get a key at https://www.sarvam.ai/"
    )
    fallback = "omnivoice_tts"
    fallback_tools = ["omnivoice_tts", "openai_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "indic_languages",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "Indic-language narration",
        "en-IN explainer voiceover",
        "Bulbul v2 preset speakers",
    ]
    not_good_for = [
        "voice clone matching",
        "fully offline production",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice": {
                "type": "string",
                "default": _DEFAULT_SPEAKER,
                "enum": list(SARVAM_SPEAKERS),
                "description": "Sarvam Bulbul v2 speaker name",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": "Sarvam TTS model (bulbul:v2 or bulbul:v1)",
            },
            "language": {
                "type": "string",
                "default": "en-IN",
                "description": "BCP-47 target language (e.g. en-IN, hi-IN) or ISO 639-1 (en, hi).",
            },
            "format": {
                "type": "string",
                "default": "wav",
                "enum": ["wav"],
                "description": "Sarvam returns WAV (base64).",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "model", "language"]
    side_effects = ["writes audio file to output_path", "calls Sarvam API"]
    user_visible_verification = ["Listen to generated audio for intelligibility and tone"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("SARVAM_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Approximate; Sarvam billing is credit-based.
        return round(len(inputs.get("text", "")) * 0.00001, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("SARVAM_API_KEY"):
            return ToolResult(success=False, error="No Sarvam API key. " + self.install_instructions)

        start = time.time()
        try:
            result = self._generate(inputs)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            return ToolResult(success=False, error=f"Sarvam TTS HTTP {exc.code}: {body}")
        except Exception as exc:
            return ToolResult(success=False, error=f"Sarvam TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        from tools.analysis.audio_probe import probe_duration

        text = inputs["text"]
        speaker = inputs.get("voice", _DEFAULT_SPEAKER)
        model = inputs.get("model", _DEFAULT_MODEL)
        language = _resolve_target_language(inputs.get("language"))
        fmt = "wav"

        output_path = Path(inputs.get("output_path", f"sarvam_tts.{fmt}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "inputs": [text],
            "target_language_code": language,
            "speaker": speaker,
            "model": model,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.sarvam.ai/text-to-speech",
            data=body,
            headers={
                "api-subscription-key": os.environ["SARVAM_API_KEY"],
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        audios = data.get("audios") or []
        if not audios:
            return ToolResult(success=False, error=f"Sarvam returned empty audios: {data}")

        audio_bytes = b"".join(base64.b64decode(a) for a in audios)
        output_path.write_bytes(audio_bytes)
        audio_duration = probe_duration(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": speaker,
                "language": language,
                "format": fmt,
                "text_length": len(text),
                "request_id": data.get("request_id"),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=model,
        )

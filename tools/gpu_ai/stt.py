"""gpu-ai speech-to-text via ``/v1/audio/transcriptions`` (faster-whisper chain)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lib import gpu_ai_client as client
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


class GpuAiSTT(BaseTool):
    name = "gpu_ai_stt"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "speech_to_text"
    provider = "gpu_ai"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Requires GPU_AI_BASE_URL reaching mcp-api-server (openmontage NetworkPolicy).\n"
        "POST multipart file to /v1/audio/transcriptions"
    )
    fallback_tools = ["azure_speech_to_text"]
    agent_skills = ["gpu-ai", "speech-to-text", "azure-speech-to-text"]

    capabilities = ["speech_to_text", "transcription"]
    supports = {"timestamps": True, "offline": False}
    best_for = ["narration transcript for captions", "reference clip transcription"]

    input_schema = {
        "type": "object",
        "required": ["audio_path"],
        "properties": {
            "audio_path": {"type": "string"},
            "model": {"type": "string", "default": "whisper-1"},
            "language": {"type": "string"},
            "response_format": {
                "type": "string",
                "default": "json",
                "enum": ["json", "text", "verbose_json", "srt", "vtt"],
            },
            "output_path": {
                "type": "string",
                "description": "Optional path to write transcript text/JSON.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "503"])
    idempotency_key_fields = ["audio_path", "model", "language", "response_format"]
    side_effects = ["reads audio file", "calls gpu-ai STT"]
    user_visible_verification = ["Read transcript for accuracy"]

    def get_status(self) -> ToolStatus:
        if client.health_ok(f"{client.gpu_ai_base()}/health") or client.health_ok(
            f"{client.gpu_ai_base()}/healthz"
        ):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            audio_path = Path(inputs["audio_path"])
            if not audio_path.exists():
                return ToolResult(success=False, error=f"Audio not found: {audio_path}")

            fields = {"model": inputs.get("model") or "whisper-1"}
            if inputs.get("language"):
                fields["language"] = inputs["language"]
            if inputs.get("response_format"):
                fields["response_format"] = inputs["response_format"]

            mime = "audio/wav"
            suffix = audio_path.suffix.lower()
            if suffix == ".mp3":
                mime = "audio/mpeg"
            elif suffix == ".m4a":
                mime = "audio/mp4"

            result = client.post_multipart(
                f"{client.gpu_ai_base()}/v1/audio/transcriptions",
                fields=fields,
                files={"file": (audio_path.name, audio_path.read_bytes(), mime)},
                timeout=300,
            )

            ctype = result.headers.get("content-type", "")
            if "application/json" in ctype or result.body[:1] == b"{":
                data = result.json()
                text = data.get("text") if isinstance(data, dict) else str(data)
            else:
                text = result.text()
                data = {"text": text}

            out_path = inputs.get("output_path")
            artifacts = []
            if out_path:
                p = Path(out_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(data, dict):
                    import json

                    p.write_text(
                        json.dumps(data, indent=2)
                        if p.suffix.lower() == ".json"
                        else (text or ""),
                        encoding="utf-8",
                    )
                else:
                    p.write_text(str(data), encoding="utf-8")
                artifacts.append(str(p))

            return ToolResult(
                success=True,
                data={
                    "provider": "gpu_ai",
                    "text": text,
                    "raw": data if isinstance(data, dict) else {"text": text},
                    "audio_path": str(audio_path),
                },
                artifacts=artifacts,
                model=fields["model"],
                duration_seconds=round(time.time() - start, 2),
                cost_usd=0.0,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"gpu_ai_stt failed: {exc}")

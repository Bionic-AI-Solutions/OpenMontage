"""gpu-ai multi-engine TTS via mcp-api-server ``/v1/audio/speech``.

Routes by voice name through the gateway registry. The gateway names its
engines generically (localclone, indian, eleven, local, openai, legacy1,
legacy2); `model` may be one of those to pin an engine, or `tts-1` to let the
voice decide. Prefer this over calling an engine directly when the
NetworkPolicy allows openmontage → mcp-api-server.
"""

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


class GpuAiTTS(BaseTool):
    name = "gpu_ai_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "gpu_ai"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "In-cluster: ensure NetworkPolicy allows openmontage → mcp-api-server.\n"
        "  export GPU_AI_BASE_URL=http://mcp-api-server.ai-services.svc.cluster.local:8000\n"
        "Optional: MCP_API_KEY for Kong / public URL.\n"
        "List voices: GET $GPU_AI_BASE_URL/v1/audio/voices"
    )
    fallback = "omnivoice_tts"
    fallback_tools = ["omnivoice_tts", "sarvam_tts", "openai_tts"]
    agent_skills = ["gpu-ai", "text-to-speech"]

    capabilities = ["text_to_speech", "voice_selection", "multilingual"]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "multi_engine": True,
    }
    best_for = [
        "cluster narration via the gateway's localclone/indian/eleven engines",
        "voice selection across engines with one tool",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "voice": {
                "type": "string",
                "default": "aditya",
                "description": "Gateway voice name (e.g. aditya, anushka, Roger).",
            },
            "voice_id": {
                "type": "string",
                "description": "Alias for voice (accepted from tts_selector).",
            },
            "language": {"type": "string", "default": "en"},
            "model": {
                "type": "string",
                "default": "tts-1",
                "description": "tts-1 (voice picks the engine) or a gateway engine "
                "name: localclone, indian, eleven, local, openai.",
            },
            "response_format": {
                "type": "string",
                "default": "wav",
                "enum": ["wav", "mp3", "pcm", "opus"],
            },
            "speed": {"type": "number", "default": 1.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["timeout", "503"])
    idempotency_key_fields = ["text", "voice", "language", "response_format", "speed"]
    side_effects = ["writes audio file", "calls gpu-ai TTS gateway"]
    user_visible_verification = ["Listen to generated audio"]

    def get_status(self) -> ToolStatus:
        if client.health_ok(f"{client.gpu_ai_base()}/healthz") or client.health_ok(
            f"{client.gpu_ai_base()}/health"
        ):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            text = inputs["text"]
            voice = inputs.get("voice") or inputs.get("voice_id") or "aditya"
            fmt = inputs.get("response_format") or "wav"
            payload = {
                "input": text,
                "voice": voice,
                "model": inputs.get("model") or "tts-1",
                "response_format": fmt,
                "language": inputs.get("language") or "en",
            }
            if inputs.get("speed") and inputs["speed"] != 1.0:
                payload["speed"] = inputs["speed"]

            result = client.post_json(
                f"{client.gpu_ai_base()}/v1/audio/speech",
                payload,
                timeout=180,
            )
            audio = result.body
            if len(audio) < 500:
                return ToolResult(
                    success=False,
                    error=f"gpu_ai_tts returned too little audio ({len(audio)} bytes)",
                )

            out = Path(inputs.get("output_path") or f"gpu_ai_tts.{fmt}")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(audio)

            duration = None
            try:
                from tools.analysis.audio_probe import probe_duration

                duration = probe_duration(out)
            except Exception:
                pass

            return ToolResult(
                success=True,
                data={
                    "provider": "gpu_ai",
                    "voice": voice,
                    # The gateway's public name for the engine that answered
                    # (absent on a streamed reply).
                    "engine": result.headers.get("x-tts-engine-used"),
                    "format": fmt,
                    "text_length": len(text),
                    "audio_duration_seconds": round(duration, 2) if duration else None,
                    "base_url": client.gpu_ai_base(),
                    "output": str(out),
                },
                artifacts=[str(out)],
                model="gpu-ai-tts",
                duration_seconds=round(time.time() - start, 2),
                cost_usd=0.0,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"gpu_ai_tts failed: {exc}")

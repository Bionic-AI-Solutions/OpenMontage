"""gpu-ai ACE-Step music generation via ``/v1/audio/music`` (async job)."""

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


class GpuAiMusic(BaseTool):
    name = "gpu_ai_music"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "music_generation"
    provider = "gpu_ai"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Requires GPU_AI_BASE_URL → mcp-api-server with ACE-Step/Comfy music enabled.\n"
        "POST /v1/audio/music then poll /v1/audio/music/jobs/{id}"
    )
    fallback_tools = ["pixabay_music", "music_gen"]
    agent_skills = ["gpu-ai", "music", "acestep"]

    capabilities = ["music_generation", "instrumental_bed"]
    supports = {"loop": True, "lyrics": True, "offline": False}
    best_for = ["custom instrumental beds for explainers", "loopable background music"]

    input_schema = {
        "type": "object",
        "required": ["tags"],
        "properties": {
            "tags": {
                "type": "string",
                "description": "Comma-separated style tags (genre/mood/instruments).",
            },
            "seconds": {"type": "number", "default": 30},
            "loop": {"type": "boolean", "default": False},
            "lyrics": {"type": "string", "default": "[inst]"},
            "response_format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "wav"],
            },
            "output_path": {"type": "string"},
            "poll_timeout_s": {"type": "number", "default": 600},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "503"])
    idempotency_key_fields = ["tags", "seconds", "loop", "lyrics", "response_format"]
    side_effects = ["calls gpu-ai music job API", "writes audio file"]
    user_visible_verification = ["Listen to bed under narration"]

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
            fmt = inputs.get("response_format") or "mp3"
            payload = {
                "tags": inputs["tags"],
                "seconds": float(inputs.get("seconds") or 30),
                "loop": bool(inputs.get("loop") or False),
                "lyrics": inputs.get("lyrics") or "[inst]",
                "response_format": fmt,
            }
            # Prefer async jobs (won't hold the connection during Comfy render).
            # Fall back to sync /v1/audio/music when jobs endpoint is unavailable.
            job_id = "sync"
            audio: bytes
            try:
                submit = client.post_json(
                    f"{client.gpu_ai_base()}/v1/audio/music/jobs",
                    payload,
                    timeout=60,
                ).json()
                job_id = str(submit.get("job_id") or submit.get("id") or "")
                if not job_id:
                    raise RuntimeError(f"no job_id: {submit}")
                deadline = time.time() + float(inputs.get("poll_timeout_s") or 600)
                status: dict[str, Any] = {}
                while time.time() < deadline:
                    status = client.get_json(
                        f"{client.gpu_ai_base()}/v1/audio/music/jobs/{job_id}",
                        timeout=30,
                    )
                    st = (status.get("status") or "").lower()
                    if st in {"done", "completed", "failed", "error"}:
                        break
                    time.sleep(2)
                if (status.get("status") or "").lower() not in {"done", "completed"}:
                    return ToolResult(
                        success=False,
                        error=f"music job {job_id} not done: {status}",
                    )
                audio = client.request(
                    "GET",
                    f"{client.gpu_ai_base()}/v1/audio/music/jobs/{job_id}/audio",
                    timeout=120,
                ).body
            except Exception:
                # Sync path returns raw audio bytes.
                sync = client.post_json(
                    f"{client.gpu_ai_base()}/v1/audio/music",
                    payload,
                    timeout=float(inputs.get("poll_timeout_s") or 600),
                )
                audio = sync.body
                job_id = "sync"

            out = Path(inputs.get("output_path") or f"gpu_ai_music.{fmt}")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(audio)

            return ToolResult(
                success=True,
                data={
                    "provider": "gpu_ai",
                    "tags": payload["tags"],
                    "seconds": payload["seconds"],
                    "job_id": job_id,
                    "output": str(out),
                    "format": fmt,
                },
                artifacts=[str(out)],
                model="ace-step",
                duration_seconds=round(time.time() - start, 2),
                cost_usd=0.0,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"gpu_ai_music failed: {exc}")

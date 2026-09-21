"""Voice Studio media-services: scenes / diarize / separate / animate.

In-cluster ClusterIP APIs (no Kong). Jobs take ``input.url`` or ``input.object_key``.
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

_SERVICES = ("scenes", "diarize", "separate", "animate")


class MediaServices(BaseTool):
    name = "media_services"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "media_pipeline"
    provider = "media_services"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "In-cluster media-services namespace APIs:\n"
        "  scenes / diarize / separate / animate\n"
        "Provide a reachable media URL (http/https) in `url`."
    )
    agent_skills = ["ffmpeg", "video_toolkit", "avatar-video"]

    capabilities = [
        "scene_detect",
        "speaker_diarization",
        "source_separation",
        "portrait_animation",
    ]
    supports = {"async_jobs": True, "offline": False}
    best_for = [
        "shot detection on source footage",
        "speaker diarization for interviews",
        "vocal/stem separation",
        "talking-head / lip-sync style animation jobs",
    ]

    input_schema = {
        "type": "object",
        "required": ["service"],
        "properties": {
            "service": {
                "type": "string",
                "enum": list(_SERVICES),
            },
            "url": {
                "type": "string",
                "description": "HTTP(S) URL of the media file for the worker to fetch.",
            },
            "object_key": {
                "type": "string",
                "description": "Object storage key if the worker shares a bucket.",
            },
            "options": {
                "type": "object",
                "description": "Service-specific options passed through.",
            },
            "wait": {
                "type": "boolean",
                "default": True,
                "description": "Poll until done (default true).",
            },
            "poll_timeout_s": {"type": "number", "default": 600},
            "output_path": {
                "type": "string",
                "description": "Optional path to write the job JSON result.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "503"])
    idempotency_key_fields = ["service", "url", "object_key"]
    side_effects = ["submits media-services job", "may write result JSON"]
    user_visible_verification = ["Inspect job result / output artifacts"]

    def get_status(self) -> ToolStatus:
        ok = any(
            client.health_ok(f"{client.media_base(s)}/healthz") for s in _SERVICES
        )
        return ToolStatus.AVAILABLE if ok else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            service = inputs["service"]
            if service not in _SERVICES:
                return ToolResult(success=False, error=f"Unknown service: {service}")
            if not inputs.get("url") and not inputs.get("object_key"):
                return ToolResult(success=False, error="url or object_key required")

            submitted = client.submit_media_job(
                service,
                url=inputs.get("url"),
                object_key=inputs.get("object_key"),
                options=inputs.get("options"),
            )
            job_id = (
                submitted.get("job_id")
                or submitted.get("id")
                or (submitted.get("job") or {}).get("id")
            )
            if not job_id:
                return ToolResult(
                    success=False,
                    error=f"No job_id in submit response: {submitted}",
                )

            result = submitted
            if inputs.get("wait", True):
                result = client.poll_media_job(
                    service,
                    str(job_id),
                    timeout_s=float(inputs.get("poll_timeout_s") or 600),
                )
                status = (result.get("status") or "").lower()
                if status in {"failed", "error"}:
                    return ToolResult(
                        success=False,
                        error=f"{service} job failed: {result}",
                        data=result,
                    )

            artifacts = []
            if inputs.get("output_path"):
                import json

                out = Path(inputs["output_path"])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(result, indent=2), encoding="utf-8")
                artifacts.append(str(out))

            return ToolResult(
                success=True,
                data={
                    "provider": "media_services",
                    "service": service,
                    "job_id": str(job_id),
                    "result": result,
                },
                artifacts=artifacts,
                model=service,
                duration_seconds=round(time.time() - start, 2),
                cost_usd=0.0,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"media_services failed: {exc}")

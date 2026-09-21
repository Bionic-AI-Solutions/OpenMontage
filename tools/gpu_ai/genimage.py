"""GenImage MCP tools — FLUX via ComfyUI (Runware fallback).

Operations: generate | edit | upscale | remove_bg
In-cluster MCP: http://mcp-genimage-server.mcp.svc.cluster.local:8008/mcp
Tenant default: ``base``
"""

from __future__ import annotations

import base64
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


class GenImage(BaseTool):
    name = "genimage"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "genimage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "In-cluster GenImage MCP (no Kong key needed inside the cluster):\n"
        "  export GENIMAGE_MCP_URL=http://mcp-genimage-server.mcp.svc.cluster.local:8008/mcp\n"
        "  export GENIMAGE_TENANT_ID=base\n"
        "Tools: gi_generate_image, gi_edit_image, gi_upscale_image, gi_remove_background"
    )
    fallback_tools = ["openai_image", "google_imagen"]
    agent_skills = ["gpu-ai", "flux-best-practices", "bfl-api", "comfyui"]

    capabilities = [
        "generate_image",
        "edit_image",
        "upscale_image",
        "remove_background",
        "img2img",
    ]
    supports = {
        "local_comfyui": True,
        "flux": True,
        "instruction_edit": True,
        "offline": False,
    }
    best_for = [
        "FLUX stills for explainers (cluster ComfyUI)",
        "instruction edits with Kontext",
        "upscale / background removal",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["generate", "edit", "upscale", "remove_bg"],
                "default": "generate",
            },
            "prompt": {
                "type": "string",
                "description": "Required for generate/edit.",
            },
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "steps": {"type": "integer", "default": 28},
            "cfg_scale": {"type": "number", "default": 1.0},
            "guidance": {"type": "number", "default": 2.5},
            "model": {"type": "string"},
            "image_path": {
                "type": "string",
                "description": "Source image for edit/upscale/remove_bg (and optional img2img).",
            },
            "strength": {"type": "number"},
            "tenant_id": {"type": "string"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "503"])
    idempotency_key_fields = [
        "operation",
        "prompt",
        "width",
        "height",
        "steps",
        "image_path",
        "model",
    ]
    side_effects = ["calls GenImage MCP", "writes image file"]
    user_visible_verification = ["Inspect image quality and prompt adherence"]

    def get_status(self) -> ToolStatus:
        # Health is on /health, not /mcp
        base = client.genimage_mcp_url().rsplit("/mcp", 1)[0]
        if client.health_ok(f"{base}/health"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Local ComfyUI path is free; Runware fallback has cost but unknown here.
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            op = inputs.get("operation") or "generate"
            tenant = inputs.get("tenant_id") or client.genimage_tenant()
            session = client.GenImageSession()
            session.initialize()

            if op == "generate":
                if not inputs.get("prompt"):
                    return ToolResult(success=False, error="prompt required for generate")
                args: dict[str, Any] = {
                    "tenant_id": tenant,
                    "prompt": inputs["prompt"],
                    "width": int(inputs.get("width") or 1024),
                    "height": int(inputs.get("height") or 1024),
                    "steps": int(inputs.get("steps") or 28),
                    "cfg_scale": float(inputs.get("cfg_scale") or 1.0),
                }
                if inputs.get("model"):
                    args["model"] = inputs["model"]
                if inputs.get("image_path"):
                    args["reference_image"] = self._image_arg(inputs["image_path"])
                    if inputs.get("strength") is not None:
                        args["strength"] = float(inputs["strength"])
                result = session.call_tool("gi_generate_image", args, timeout=300)
                tool_name = "gi_generate_image"

            elif op == "edit":
                if not inputs.get("prompt") or not inputs.get("image_path"):
                    return ToolResult(
                        success=False,
                        error="prompt and image_path required for edit",
                    )
                args = {
                    "tenant_id": tenant,
                    "prompt": inputs["prompt"],
                    "image_data": self._image_arg(inputs["image_path"]),
                }
                if inputs.get("model"):
                    args["model"] = inputs["model"]
                if inputs.get("steps") is not None:
                    args["steps"] = int(inputs["steps"])
                if inputs.get("guidance") is not None:
                    args["guidance"] = float(inputs["guidance"])
                result = session.call_tool("gi_edit_image", args, timeout=300)
                tool_name = "gi_edit_image"

            elif op == "upscale":
                if not inputs.get("image_path"):
                    return ToolResult(success=False, error="image_path required for upscale")
                args = {
                    "tenant_id": tenant,
                    "image_data": self._image_arg(inputs["image_path"]),
                }
                result = session.call_tool("gi_upscale_image", args, timeout=300)
                tool_name = "gi_upscale_image"

            elif op == "remove_bg":
                if not inputs.get("image_path"):
                    return ToolResult(
                        success=False, error="image_path required for remove_bg"
                    )
                args = {
                    "tenant_id": tenant,
                    "image_data": self._image_arg(inputs["image_path"]),
                }
                result = session.call_tool("gi_remove_background", args, timeout=300)
                tool_name = "gi_remove_background"

            else:
                return ToolResult(success=False, error=f"Unknown operation: {op}")

            if isinstance(result, dict) and result.get("success") is False:
                err = result.get("error") or f"{tool_name} failed"
                backend = result.get("backend")
                hint = ""
                err_l = str(err).lower()
                if "insufficientcredits" in err_l or "insufficient credits" in err_l:
                    hint = (
                        " (ComfyUI likely OOM'd and Runware fallback has no credits; "
                        "use openai_image / google_imagen, or free GPU VRAM and retry)"
                    )
                elif "out of memory" in err_l or "oom" in err_l:
                    hint = " (ComfyUI GPU OOM — free VRAM or fall back to openai_image)"
                return ToolResult(
                    success=False,
                    error=f"{err}{hint}",
                    data={"backend": backend, "tool": tool_name, "tenant_id": tenant},
                )

            image_bytes = client.decode_image_payload(result)
            out = Path(inputs.get("output_path") or f"genimage_{op}.png")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(image_bytes)

            return ToolResult(
                success=True,
                data={
                    "provider": "genimage",
                    "operation": op,
                    "tool": tool_name,
                    "tenant_id": tenant,
                    "backend": result.get("backend") if isinstance(result, dict) else None,
                    "width": result.get("width") if isinstance(result, dict) else None,
                    "height": result.get("height") if isinstance(result, dict) else None,
                    "output": str(out),
                    "bytes": len(image_bytes),
                },
                artifacts=[str(out)],
                model=inputs.get("model") or "flux1-dev-fp8",
                duration_seconds=round(time.time() - start, 2),
                cost_usd=0.0,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"genimage failed: {exc}")

    @staticmethod
    def _image_arg(path_or_b64: str) -> str:
        p = Path(path_or_b64)
        if p.exists():
            return base64.b64encode(p.read_bytes()).decode("ascii")
        return path_or_b64

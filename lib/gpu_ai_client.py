"""Shared HTTP client for in-cluster gpu-ai / GenImage / media-services APIs.

Prefer ClusterIP URLs from the openmontage namespace (after NetworkPolicy allows
``openmontage`` → ``mcp-api-server``). Public Kong URLs are a fallback when
``GPU_AI_BASE_URL`` is overridden, but Cloudflare bot rules may block pod
User-Agents — keep in-cluster defaults for production.

Env knobs:
  MCP_API_KEY / GPU_AI_API_KEY   – optional for in-cluster; required for Kong
  GPU_AI_BASE_URL               – default mcp-api-server.ai-services:8000
  GENIMAGE_MCP_URL              – default mcp-genimage-server.mcp:8008/mcp
  GENIMAGE_TENANT_ID            – default ``base``
  MEDIA_<NAME>_URL              – override per media-services API
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

DEFAULT_GPU_AI_BASE = "http://mcp-api-server.ai-services.svc.cluster.local:8000"
DEFAULT_GENIMAGE_MCP = "http://mcp-genimage-server.mcp.svc.cluster.local:8008/mcp"
DEFAULT_TENANT = "base"

MEDIA_DEFAULTS = {
    "scenes": "http://scenes-api.media-services.svc.cluster.local:8000",
    "diarize": "http://diarize-api.media-services.svc.cluster.local:8000",
    "separate": "http://separate-api.media-services.svc.cluster.local:8000",
    "animate": "http://animate-api.media-services.svc.cluster.local:8000",
}


def api_key() -> str:
    return (
        os.environ.get("MCP_API_KEY")
        or os.environ.get("GPU_AI_API_KEY")
        or os.environ.get("OMNIVOICE_API_KEY")
        or ""
    ).strip()


def gpu_ai_base() -> str:
    return (
        os.environ.get("GPU_AI_BASE_URL")
        or os.environ.get("GPU_AI_URL")
        or DEFAULT_GPU_AI_BASE
    ).rstrip("/")


def genimage_mcp_url() -> str:
    return (os.environ.get("GENIMAGE_MCP_URL") or DEFAULT_GENIMAGE_MCP).rstrip("/")


def genimage_tenant() -> str:
    return (os.environ.get("GENIMAGE_TENANT_ID") or DEFAULT_TENANT).strip() or DEFAULT_TENANT


def media_base(service: str) -> str:
    env_key = f"MEDIA_{service.upper()}_URL"
    return (os.environ.get(env_key) or MEDIA_DEFAULTS[service]).rstrip("/")


def _auth_headers(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream, */*",
        "User-Agent": "OpenMontage/gpu-ai-client",
    }
    key = api_key()
    if key:
        headers["X-API-Key"] = key
    if extra:
        headers.update(extra)
    return headers


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def request(
    method: str,
    url: str,
    *,
    data: Optional[bytes] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 120,
    allow_http_error: bool = False,
) -> HttpResult:
    req = urllib.request.Request(
        url,
        data=data,
        headers=_auth_headers(headers),
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return HttpResult(
                status=resp.status,
                headers={k.lower(): v for k, v in resp.headers.items()},
                body=resp.read(),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if allow_http_error:
            return HttpResult(
                status=exc.code,
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                body=body,
            )
        raise RuntimeError(f"HTTP {exc.code} {url}: {body[:500]!r}") from exc


def get_json(url: str, *, timeout: float = 30) -> Any:
    return request("GET", url, timeout=timeout).json()


def post_json(url: str, payload: dict[str, Any], *, timeout: float = 180) -> HttpResult:
    body = json.dumps(payload).encode("utf-8")
    return request(
        "POST",
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )


def post_multipart(
    url: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
    *,
    timeout: float = 180,
) -> HttpResult:
    """Minimal multipart/form-data POST (no external deps)."""
    boundary = f"----OpenMontage{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        chunks.append(value.encode("utf-8") + b"\r\n")
    for name, (filename, content, content_type) in files.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
        )
        chunks.append(content + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    return request(
        "POST",
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=timeout,
    )


def health_ok(url: str, *, timeout: float = 5) -> bool:
    try:
        request("GET", url, timeout=timeout)
        return True
    except Exception:
        return False


# ── GenImage MCP (streamable HTTP) ──────────────────────────────────────────


def _parse_sse_json(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace")
    # Prefer the last JSON object in SSE data lines.
    payloads: list[dict[str, Any]] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                payloads.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    if payloads:
        return payloads[-1]
    # Non-SSE JSON body
    return json.loads(text)


class GenImageSession:
    """Stateful MCP session against the GenImage server."""

    def __init__(self, url: Optional[str] = None):
        self.url = (url or genimage_mcp_url()).rstrip("/")
        self.session_id: Optional[str] = None

    def initialize(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "openmontage", "version": "1.0"},
            },
        }
        result = post_json(self.url, payload, timeout=30)
        self.session_id = (
            result.headers.get("mcp-session-id")
            or result.headers.get("Mcp-Session-Id")
        )
        # Some servers put session in body; keep going even if header missing
        # (in-cluster FastMCP usually sets the header).
        _parse_sse_json(result.body)
        # notifications/initialized (best-effort)
        if self.session_id:
            try:
                post_json(
                    self.url,
                    {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {},
                    },
                    timeout=10,
                )
            except Exception:
                pass

    def call_tool(self, name: str, arguments: dict[str, Any], *, timeout: float = 300) -> Any:
        if not self.session_id:
            self.initialize()
        headers = {}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 1_000_000,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        body = json.dumps(payload).encode("utf-8")
        result = request(
            "POST",
            self.url,
            data=body,
            headers={**headers, "Content-Type": "application/json"},
            timeout=timeout,
            # FastMCP may return HTTP 400 when the tool reports success=false
            # (e.g. ComfyUI OOM → Runware insufficient credits).
            allow_http_error=True,
        )
        # Refresh session id if rotated
        sid = result.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid
        try:
            message = _parse_sse_json(result.body)
        except Exception as exc:
            snippet = result.body[:500].decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GenImage MCP HTTP {result.status}: {snippet}"
            ) from exc
        if "error" in message:
            raise RuntimeError(f"GenImage MCP error: {message['error']}")
        tool_result = message.get("result") or {}
        # FastMCP often wraps JSON in content[0].text
        content = tool_result.get("content") or []
        if content and isinstance(content, list):
            text = content[0].get("text") if isinstance(content[0], dict) else None
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return {"raw_text": text, **tool_result}
                if isinstance(parsed, dict) and parsed.get("success") is False:
                    return parsed
                return parsed
        if isinstance(tool_result, dict) and "success" in tool_result:
            return tool_result
        if result.status >= 400:
            return {
                "success": False,
                "error": f"HTTP {result.status}: {result.body[:400]!r}",
            }
        return tool_result


def decode_image_payload(result: dict[str, Any]) -> bytes:
    """Extract image bytes from a gi_* tool result."""
    import base64

    b64 = (
        result.get("image_data")
        or result.get("image_base64")
        or result.get("data")
    )
    if not b64 and isinstance(result.get("raw_text"), str):
        try:
            nested = json.loads(result["raw_text"])
            b64 = nested.get("image_data") or nested.get("image_base64")
        except json.JSONDecodeError:
            pass
    if not b64:
        raise RuntimeError(f"No image_data in GenImage result keys={list(result)[:20]}")
    if isinstance(b64, str) and b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]
    return base64.b64decode(b64)


# ── Media-services async jobs ───────────────────────────────────────────────


def submit_media_job(
    service: str,
    *,
    url: Optional[str] = None,
    object_key: Optional[str] = None,
    options: Optional[dict[str, Any]] = None,
    timeout: float = 60,
) -> dict[str, Any]:
    if service not in MEDIA_DEFAULTS:
        raise ValueError(f"Unknown media service: {service}")
    if not url and not object_key:
        raise ValueError("Provide url or object_key")
    payload: dict[str, Any] = {
        "input": {"url": url, "object_key": object_key},
    }
    if options:
        payload["options"] = options
    endpoint = f"{media_base(service)}/v1/{service}"
    result = post_json(endpoint, payload, timeout=timeout)
    return result.json()


def poll_media_job(
    service: str,
    job_id: str,
    *,
    timeout_s: float = 600,
    interval_s: float = 2.0,
) -> dict[str, Any]:
    endpoint = f"{media_base(service)}/v1/{service}/jobs/{job_id}"
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = get_json(endpoint, timeout=30)
        status = (last.get("status") or last.get("state") or "").lower()
        if status in {"done", "completed", "succeeded", "failed", "error"}:
            return last
        time.sleep(interval_s)
    raise TimeoutError(f"{service} job {job_id} timed out; last={last}")


def file_to_data_url(path: Path, mime: str = "application/octet-stream") -> str:
    import base64

    data = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.DOTALL)

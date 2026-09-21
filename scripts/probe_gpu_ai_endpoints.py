#!/usr/bin/env python3
"""Live probe of cluster gpu-ai / GenImage / media-services endpoints."""

from __future__ import annotations

import os
import time
from pathlib import Path

from lib import gpu_ai_client as c
from lib.vault_config import ensure_vault_config_loaded


def main() -> int:
    ensure_vault_config_loaded()
    results: list[tuple[str, bool, str]] = []

    def report(name: str, passed: bool, detail: str = "") -> None:
        results.append((name, passed, detail))
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    base = c.gpu_ai_base()
    report("mcp-api /health", c.health_ok(f"{base}/health"), base)
    report("mcp-api /healthz", c.health_ok(f"{base}/healthz"), base)

    gen_base = c.genimage_mcp_url().rsplit("/mcp", 1)[0]
    report("genimage /health", c.health_ok(f"{gen_base}/health"), gen_base)

    for svc in ("scenes", "diarize", "separate", "animate"):
        u = c.media_base(svc)
        report(f"media {svc} /healthz", c.health_ok(f"{u}/healthz"), u)

    omni = os.environ.get(
        "OMNIVOICE_BASE_URL",
        "http://omnivoice-api.ai-services.svc.cluster.local:7861",
    )
    report(
        "omnivoice reachability",
        c.health_ok(f"{omni}/health") or c.health_ok(omni),
        omni,
    )

    # Voices
    try:
        voices = c.get_json(f"{base}/v1/audio/voices", timeout=30)
        n = 0
        if isinstance(voices, list):
            n = len(voices)
        elif isinstance(voices, dict):
            for key in ("voices", "data", "items"):
                if isinstance(voices.get(key), list):
                    n = len(voices[key])
                    break
            if not n:
                n = sum(1 for v in voices.values() if isinstance(v, list))
        report(
            "GET /v1/audio/voices",
            n > 0,
            f"{n} voices; type={type(voices).__name__}",
        )
    except Exception as exc:
        report("GET /v1/audio/voices", False, str(exc)[:220])

    # TTS
    speech_path: Path | None = None
    try:
        r = c.post_json(
            f"{base}/v1/audio/speech",
            {
                "model": "tts-1",
                "voice": "aditya",
                "input": "Endpoint check.",
                "response_format": "wav",
            },
            timeout=120,
        )
        speech_path = Path("/tmp/endpoint_check.wav")
        speech_path.write_bytes(r.body)
        report("POST /v1/audio/speech", len(r.body) > 1000, f"{len(r.body)} bytes")
    except Exception as exc:
        report("POST /v1/audio/speech", False, str(exc)[:220])

    # STT
    try:
        if speech_path and speech_path.exists():
            r = c.post_multipart(
                f"{base}/v1/audio/transcriptions",
                {"model": "whisper-1"},
                {"file": ("check.wav", speech_path.read_bytes(), "audio/wav")},
                timeout=120,
            )
            data = r.json()
            text = data.get("text") if isinstance(data, dict) else str(data)[:80]
            report("POST /v1/audio/transcriptions", bool(text), f"text={text!r}"[:180])
        else:
            report("POST /v1/audio/transcriptions", False, "no speech sample")
    except Exception as exc:
        report("POST /v1/audio/transcriptions", False, str(exc)[:220])

    # Music
    try:
        r = c.post_json(
            f"{base}/v1/audio/music",
            {
                "tags": "ambient, soft, instrumental",
                "seconds": 8,
                "lyrics": "[inst]",
                "response_format": "mp3",
            },
            timeout=60,
        )
        body = r.json()
        job_id = (
            body.get("id")
            or body.get("job_id")
            or (body.get("job") or {}).get("id")
        )
        report(
            "POST /v1/audio/music",
            bool(job_id) or str(body.get("status", "")).lower()
            in {"queued", "running", "completed", "pending"},
            str(body)[:200],
        )
        if job_id:
            deadline = time.time() + 120
            last: dict = {}
            while time.time() < deadline:
                last = c.get_json(f"{base}/v1/audio/music/jobs/{job_id}", timeout=30)
                st = (last.get("status") or last.get("state") or "").lower()
                if st in {"done", "completed", "succeeded", "failed", "error"}:
                    break
                time.sleep(3)
            st = last.get("status") or last.get("state") or "?"
            ok_status = str(st).lower() in {"done", "completed", "succeeded"}
            report(
                "GET /v1/audio/music/jobs/{id}",
                ok_status,
                f"status={st} keys={list(last)[:12]}",
            )
    except Exception as exc:
        report("POST /v1/audio/music", False, str(exc)[:220])

    # GenImage
    try:
        from tools.gpu_ai.genimage import GenImage

        result = GenImage().execute(
            {
                "operation": "generate",
                "prompt": "simple blue square icon, flat design, no text",
                "width": 512,
                "height": 512,
                "steps": 8,
                "output_path": "/tmp/endpoint_genimage.png",
            }
        )
        detail = result.error or (
            f"backend={result.data.get('backend')} bytes={result.data.get('bytes')}"
        )
        report("genimage gi_generate_image", result.success, str(detail)[:220])
    except Exception as exc:
        report("genimage gi_generate_image", False, str(exc)[:220])

    # media-services scenes
    try:
        from tools.gpu_ai.media_services import MediaServices

        result = MediaServices().execute(
            {
                "service": "scenes",
                "url": "https://samplelib.com/lib/preview/mp4/sample-5s.mp4",
                "wait": True,
                "poll_timeout_s": 120,
            }
        )
        detail = result.error or str(result.data)[:180]
        report("media_services scenes", result.success, str(detail)[:220])
    except Exception as exc:
        report("media_services scenes", False, str(exc)[:220])

    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    print()
    print(f"SUMMARY: {passed} passed, {failed} failed of {len(results)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

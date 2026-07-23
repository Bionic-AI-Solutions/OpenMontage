# gpu-ai Cluster Media Stack

Use this skill when producing stories/videos on the Solution cluster and choosing
among in-cluster audio / image / footage APIs.

## When to use

- Preflight or asset stage inside Kubernetes (`openmontage` namespace)
- User asks to prefer local/cluster media over paid cloud
- Selectors should route to `gpu_ai` / `genimage` / `media_services`

## Tools (OpenMontage wrappers)

| Tool | Capability | Endpoint |
|------|------------|----------|
| `gpu_ai_tts` | Multi-engine TTS (OmniVoice/Sarvam/ElevenLabs by voice) | `GPU_AI_BASE_URL/v1/audio/speech` |
| `gpu_ai_stt` | faster-whisper transcription | `/v1/audio/transcriptions` |
| `gpu_ai_music` | ACE-Step instrumental beds | `/v1/audio/music` |
| `genimage` | FLUX generate/edit/upscale/remove_bg | GenImage MCP |
| `media_services` | scenes / diarize / separate / animate | media-services ClusterIPs |
| `omnivoice_tts` | Direct OmniVoice (bypass gateway) | `OMNIVOICE_BASE_URL` |

Selectors auto-discover these when `capability` matches (`tts`, `image_generation`, …).

## Cluster defaults

```bash
GPU_AI_BASE_URL=http://mcp-api-server.ai-services.svc.cluster.local:8000
GENIMAGE_MCP_URL=http://mcp-genimage-server.mcp.svc.cluster.local:8008/mcp
GENIMAGE_TENANT_ID=base
COMFYUI_SERVER_URL=http://comfyui.comfyui.svc.cluster.local:8188
OMNIVOICE_BASE_URL=http://omnivoice-api.ai-services.svc.cluster.local:7861
```

Prefer **ClusterIP** URLs. Public `mcp.baisoln.com` may be blocked by Cloudflare from pods.

## Recommended production routing

1. **Narration:** `tts_selector` → `preferred_provider: "gpu_ai"`, voice `aditya`
2. **Stills:** `image_selector` → `preferred_provider: "genimage"`; on ComfyUI OOM / Runware credit failure → `openai_image`
3. **Music:** `gpu_ai_music` → else `pixabay_music` / `music_library/`
4. **Captions:** `gpu_ai_stt` on the mixed narration track
5. **Footage jobs:** `media_services` with a URL the worker can fetch (not a pod-local path)

## Known limits

- GenImage tries ComfyUI first; GPU OOM falls back to Runware (needs wallet credits).
- Wan2 / video_generation worker pools on mcp-api-server may be inactive — do not promise cluster video gen until healthy.
- `comfyui_image` (bundled FLUX2 workflow) is separate from GenImage's FLUX.1-dev path and may be DEGRADED if models are missing.

## Examples

```python
# Narration via gateway
{"text": "...", "voice": "aditya", "preferred_provider": "gpu_ai"}  # via tts_selector

# Still via GenImage
{"prompt": "...", "preferred_provider": "genimage", "width": 1536, "height": 1024}

# Music bed
{"tags": "ambient, soft piano, documentary, instrumental", "seconds": 45}
```

Full usage notes: `docs/feature/gpu-ai-integration/usage-document.md`

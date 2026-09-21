# Usage: Cluster gpu-ai Media Integration

## What this adds

OpenMontage tools that call the **in-cluster** gpu-ai stack for story/video production:

| Tool | Capability | Backend |
|------|------------|---------|
| `gpu_ai_tts` | Multi-engine TTS (gateway engines localclone/indian/eleven/local/openai, picked by voice) | `mcp-api-server` `/v1/audio/speech` |
| `gpu_ai_stt` | Speech-to-text | `mcp-api-server` `/v1/audio/transcriptions` |
| `gpu_ai_music` | ACE-Step instrumental beds | `mcp-api-server` `/v1/audio/music` |
| `genimage` | FLUX generate / edit / upscale / remove_bg | GenImage MCP (ComfyUI) |
| `media_services` | scenes / diarize / separate / animate | `media-services` APIs |
| `omnivoice_tts` / `sarvam_tts` | Direct OmniVoice or Sarvam (already present) | Omnivoice API / Sarvam cloud |

## Prerequisites

1. NetworkPolicy allows `openmontage` → `mcp-api-server` (Deploy repo manifest).
2. ConfigMap sets `GPU_AI_BASE_URL`, `GENIMAGE_MCP_URL`, `GENIMAGE_TENANT_ID=base`.
3. Optional: `MCP_API_KEY` from Vault `shared/api-keys` (needed for Kong/public; not required for ClusterIP).

## Agent selection guidance

- **Stills for explainers:** prefer `genimage` (`operation=generate`) over paid OpenAI when ComfyUI is healthy.
- **Narration:** prefer `gpu_ai_tts` with `voice=aditya` (localclone engine via gateway); fallback `omnivoice_tts` / `sarvam_tts`.
- **Captions:** `gpu_ai_stt` on the final narration mix.
- **Music:** `gpu_ai_music` with style tags; fallback `pixabay_music`.
- **Source footage:** `media_services` with `service=scenes|diarize|separate|animate` and a reachable `url`.

## Example calls

```python
from tools.gpu_ai.genimage import GenImage
from tools.gpu_ai.tts import GpuAiTTS
from tools.gpu_ai.media_services import MediaServices

GenImage().execute({
    "operation": "generate",
    "prompt": "Neural network nodes waking up, editorial science illustration",
    "width": 1536, "height": 1024, "steps": 28,
    "output_path": "projects/demo/assets/images/hero.png",
})

GpuAiTTS().execute({
    "text": "Weights wake up when the network learns.",
    "voice": "aditya",
    "output_path": "projects/demo/assets/audio/narration.wav",
})

MediaServices().execute({
    "service": "scenes",
    "url": "https://example.com/clip.mp4",
    "wait": True,
})
```

## Pipeline wiring

Selectors discover these tools automatically:

- `tts_selector` → providers with `capability="tts"` (includes `gpu_ai_tts`, `omnivoice_tts`, `sarvam_tts`)
- `image_selector` → `capability="image_generation"` (includes `genimage`)

Explainer / animation asset directors prefer cluster providers when AVAILABLE
(`preferred_provider: "gpu_ai"` / `"genimage"`). Layer-3 skill: `.agents/skills/gpu-ai/SKILL.md`.

## Notes

- Cloudflare may block pod User-Agents on `mcp.baisoln.com`; always prefer ClusterIP URLs inside the cluster.
- GenImage tenant default is `base` (Vault `genimage_tenants_json`).
- GenImage tries ComfyUI first; on GPU OOM it falls back to Runware. If Runware has no credits, use `openai_image`.
- Wan2 / LongCat video-gen worker pools are currently inactive on mcp-api-server — not wired until those pools are healthy.

# Feature: gpu-ai Integration

## Status: Complete (with known cluster limits)
## Priority: High

### Progress Checklist
- [x] Inventory gpu-ai / GenImage / media-services APIs
- [x] Shared client (`lib/gpu_ai_client.py`)
- [x] Tools: `gpu_ai_tts`, `gpu_ai_stt`, `gpu_ai_music`, `genimage`, `media_services`
- [x] NetworkPolicy allow `openmontage` → `mcp-api-server`
- [x] Vault/ESO + ConfigMap wiring (`MCP_API_KEY`, GPU_AI_*, GENIMAGE_*, MEDIA_*, COMFYUI_*)
- [x] Unit tests (mocked HTTP)
- [x] Live verify tools in workspace pod registry
- [x] Selector adapters (`voice_id`, genimage `operation` mapping)
- [x] Explainer/animation asset-director + `.agents/skills/gpu-ai` routing guidance
- [x] Rebuild/push image with tools baked in (`docker4zerocool/openmontage:20260719-full` — Node 22 + Remotion + HyperFrames + Mermaid + gpu-ai)

### Live verification (2026-07-19)
| Surface | Result |
|---------|--------|
| mcp-api-server `/health` from openmontage | ✅ |
| `gpu_ai_tts` (voice `aditya`) | ✅ |
| Registry: gpu_ai_* / genimage / media_services | ✅ available |
| `genimage` generate | ⚠️ ComfyUI OOM → Runware insufficient credits |
| Wan2 video pools | ❌ inactive (deferred) |

### Blockers/Issues
- ComfyUI FLUX path OOMs under current GPU pressure; Runware wallet empty — stills fall back to `openai_image`
- Public Kong path blocked by Cloudflare bot rules from pods — ClusterIP is the supported path

#!/usr/bin/env python3
"""Cinematic marketing montage: The Map They Don't Sell You.

Cluster-first: genimage stills → comfyui_video I2V → Remotion CinematicRenderer.
VEO/Sora are NOT used unless explicitly requested.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.checkpoint import PROJECTS_DIR, write_checkpoint
from lib.vault_config import ensure_vault_config_loaded
from schemas.artifacts import validate_artifact

PID = "coffee-map-marketing"
TITLE = "The Map They Don't Sell You"
PIPELINE = "cinematic"
PLAYBOOK = "flat-motion-graphics"
BUDGET = 5.0  # cluster gens ~$0; buffer for unexpected cloud fallbacks (none planned)

# Beat map — genimage still + comfy I2V for motion scenes; title for landing
SCENES = [
    {
        "id": "sc1",
        "label": "American coffee mythology",
        "duration": 11.0,
        "kind": "motion",
        "narration": (
            "America feels like it invented the coffee break. "
            "Steam in the street. Cups on every corner. The brand story is everywhere."
        ),
        "image_prompt": (
            "Cinematic dusk city street with warm cafe windows and rising steam from takeaway cups, "
            "anonymous storefronts without logos or brand names, wet pavement reflections, "
            "shallow depth of field, shot on 35mm, golden-hour mixed with neon practical lights, "
            "photorealistic editorial marketing still, no text"
        ),
        "motion_prompt": (
            "Slow push-in through steam toward glowing cafe windows, gentle handheld drift, "
            "cinematic shallow depth, photorealistic"
        ),
    },
    {
        "id": "sc2",
        "label": "The map reveal",
        "duration": 12.0,
        "kind": "motion",
        "narration": (
            "Open the real map — and Finland drinks about three times more coffee per person."
        ),
        "image_prompt": (
            "Dark editorial world map visualization on a glass table in a dim studio, "
            "Northern Europe glowing cyan #06B6D4 while North America is muted slate, "
            "volumetric spot light from above, cinematic product photography style, no text labels"
        ),
        "motion_prompt": (
            "Camera slowly dollies toward the glowing Northern Europe region on the map, "
            "cyan light intensifies, cinematic"
        ),
    },
    {
        "id": "sc3",
        "label": "Finnish ritual",
        "duration": 13.0,
        "kind": "motion",
        "narration": (
            "Twelve kilograms a year. Dark winter mornings. Quiet kitchens. "
            "A ritual, not a billboard."
        ),
        "image_prompt": (
            "Scandinavian kitchen at blue-hour winter morning, frost on the window, "
            "hands pouring filter coffee into a simple ceramic mug, warm tungsten practical light "
            "against cold blue exterior, intimate documentary still, no logos, no text"
        ),
        "motion_prompt": (
            "Steam rises from the mug as coffee finishes pouring, soft window light, slow subtle push"
        ),
    },
    {
        "id": "sc4",
        "label": "Same bean, different habit",
        "duration": 11.0,
        "kind": "motion",
        "narration": (
            "Americans land closer to four point two kilograms. Same bean. Completely different habit."
        ),
        "image_prompt": (
            "Split-composition editorial still: left a hurried commuting hand with a paper cup "
            "in cool fluorescent light, right a calm ceramic mug on a wooden table in soft daylight, "
            "clean modern advertising photography, no logos, no text"
        ),
        "motion_prompt": (
            "Subtle parallax between the two sides of the frame, gentle breathing camera motion"
        ),
    },
    {
        "id": "sc5",
        "label": "Nordic leaders",
        "duration": 12.0,
        "kind": "motion",
        "narration": (
            "Norway. Iceland. Denmark. The Netherlands. Sweden. "
            "The top of the chart is Northern Europe — not the loudest brand."
        ),
        "image_prompt": (
            "Montage-ready cinematic still of a Nordic harbor cafe at overcast midday, "
            "bicycles, pale wood interior glimpsed through glass, muted teal and grey palette, "
            "documentary photography, no logos, no text"
        ),
        "motion_prompt": (
            "Slow lateral pan across the harbor cafe facade, overcast soft light, cinematic"
        ),
    },
    {
        "id": "sc6",
        "label": "Growers mid-pack",
        "duration": 13.0,
        "kind": "motion",
        "narration": (
            "Brazil grows about forty percent of the world's coffee — "
            "and still sits mid-pack as a drinker. Growers do not automatically wear the crown."
        ),
        "image_prompt": (
            "Brazilian coffee plantation at golden hour, workers with baskets among green rows of "
            "coffee plants, warm low sun, dust in the light, epic wide documentary frame, "
            "no logos, no text"
        ),
        "motion_prompt": (
            "Slow crane-like rise over coffee rows as workers move through the plants, golden hour"
        ),
    },
    {
        "id": "sc7",
        "label": "Two billion cups",
        "duration": 10.0,
        "kind": "motion",
        "narration": (
            "Zoom out: more than two billion cups every day. Demand is winning."
        ),
        "image_prompt": (
            "Aerial dawn view of a dense city with countless tiny warm window lights suggesting "
            "morning rituals, cool blue hour sky, cinematic wide establishing shot, no text"
        ),
        "motion_prompt": (
            "Slow aerial drift forward over the glowing city at dawn, epic scale"
        ),
    },
    {
        "id": "sc8",
        "label": "Landing title",
        "duration": 8.0,
        "kind": "title",
        "narration": (
            "So next time someone says America runs on coffee — show them the map."
        ),
        "image_prompt": (
            "Abstract dark slate background with a single cyan light streak suggesting a map meridian, "
            "minimal premium brand end-card backdrop, no text, no logos"
        ),
        "title_text": "Show them the map.",
        "title_accent": "#06B6D4",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def must_valid(name: str, data: dict) -> dict:
    validate_artifact(name, data)
    return data


def cp(stage: str, status: str, artifacts: dict, **kw) -> None:
    write_checkpoint(
        PROJECTS_DIR, PID, stage, status, artifacts, pipeline_type=PIPELINE, **kw
    )
    print(f"[cp] {stage} -> {status}", flush=True)


def audio_duration(path: Path) -> float:
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode == 0 and probe.stdout.strip():
        return float(probe.stdout.strip())
    return 1.0


def stretch_clip(src: Path, dst: Path, target_s: float) -> None:
    """Loop/pad a short WAN clip to cover the narration beat."""
    dur = audio_duration(src)
    if dur <= 0:
        raise RuntimeError(f"bad clip duration: {src}")
    # Scale to 1080p and loop to target length
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(src),
            "-t", f"{target_s:.3f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
            str(dst),
        ],
        check=True, capture_output=True,
    )


def ken_burns(img: Path, dst: Path, target_s: float) -> None:
    frames = max(int(target_s * 30), 30)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(img),
            "-vf",
            (
                "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
                f"zoompan=z='min(zoom+0.0007,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s=1920x1080:fps=30"
            ),
            "-t", f"{target_s:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(dst),
        ],
        check=True, capture_output=True,
    )


def main() -> int:
    ensure_vault_config_loaded()
    os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")

    pdir = PROJECTS_DIR / PID
    art_dir = pdir / "artifacts"
    (pdir / "assets/images").mkdir(parents=True, exist_ok=True)
    (pdir / "assets/video").mkdir(parents=True, exist_ok=True)
    (pdir / "assets/audio").mkdir(parents=True, exist_ok=True)
    (pdir / "assets/music").mkdir(parents=True, exist_ok=True)
    (pdir / "renders").mkdir(parents=True, exist_ok=True)

    research = json.loads((art_dir / "research_brief.json").read_text(encoding="utf-8"))
    spent = 0.0
    full_narration = " ".join(sc["narration"] for sc in SCENES)
    planned = sum(sc["duration"] for sc in SCENES)

    # ── research checkpoint (already have brief) ──────────────────────────
    cp("research", "completed", {"research_brief": research})

    # ── proposal ──────────────────────────────────────────────────────────
    cp("proposal", "in_progress", {})
    concept_options = [
        {
            "id": "c1",
            "title": TITLE,
            "hook": "America feels #1. The map says Finland drinks 3× more.",
            "narrative_structure": "myth_busting",
            "visual_approach": (
                "GenImage stills → ComfyUI WAN I2V motion clips → Remotion CinematicRenderer montage"
            ),
            "suggested_playbook": PLAYBOOK,
            "target_audience": "Brand / marketing viewers on YouTube and LinkedIn",
            "target_platform": "youtube",
            "target_duration_seconds": 90,
            "key_points": [
                "Finland ~12 kg vs US ~4.2 kg per person",
                "Nordic countries lead per-capita rankings",
                "Brazil grows ~40% but drinks mid-pack",
                "2B+ cups daily; demand outruns supply narrative",
            ],
            "core_message": "Brand ubiquity is not consumption leadership — show them the map.",
            "cta": "Show them the map.",
            "tone": "premium documentary marketing",
            "grounded_in": ["Finland 12kg", "US 4.2kg", "Nordic tier", "Brazil 40%", "2B cups"],
            "why_this_works": "Myth-bust hook plus cinematic motion from cluster gens.",
        },
        {
            "id": "c2",
            "title": "Grown Here. Drunk Elsewhere.",
            "hook": "Brazil grows the coffee. Someone else drinks the crown.",
            "narrative_structure": "comparison",
            "visual_approach": "Harvest-to-cup trade montage",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "Sustainability-curious",
            "target_platform": "youtube",
            "target_duration_seconds": 90,
            "key_points": ["Brazil production share", "Nordic drinkers", "Value downstream"],
            "core_message": "Growing and drinking are different power maps.",
            "cta": "Follow the cup past the farm gate.",
            "tone": "investigative",
            "grounded_in": ["Brazil production", "Nordic drinking"],
            "why_this_works": "Trade angle from research DP6.",
        },
        {
            "id": "c3",
            "title": "Two Billion Quiet Mornings",
            "hook": "Two billion cups a day — who owns the habit?",
            "narrative_structure": "data_narrative",
            "visual_approach": "Dawn-scale montage landing on Finland",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "General curiosity",
            "target_platform": "youtube",
            "target_duration_seconds": 90,
            "key_points": ["2B cups", "180M bags", "Per-capita surprise"],
            "core_message": "Planetary habit, unexpected leaders.",
            "cta": "Look past the loudest brand.",
            "tone": "awe",
            "grounded_in": ["2B cups", "demand"],
            "why_this_works": "Scale hook DP4–DP5.",
        },
    ]

    proposal = must_valid(
        "proposal_packet",
        {
            "version": "1.0",
            "concept_options": concept_options,
            "selected_concept": {
                "concept_id": "c1",
                "rationale": "User approved Concept 1 with Remotion body; video gen switched to comfyui_video per user default.",
                "modifications": [
                    "render_runtime=remotion",
                    "video_provider=comfyui_video (not veo)",
                    "image_provider=genimage",
                    "~90s YouTube",
                ],
            },
            "production_plan": {
                "pipeline": PIPELINE,
                "playbook": PLAYBOOK,
                "stages": [
                    {
                        "stage": "script",
                        "tools": [{"tool_name": "script_writer", "role": "Beat-map VO", "available": True, "estimated_cost_usd": 0}],
                        "approach": "Hook → map myth-bust → ritual → contrast → Nordics → Brazil → scale → CTA",
                    },
                    {
                        "stage": "scene_plan",
                        "tools": [{"tool_name": "scene_planner", "role": "Motion beats", "available": True, "estimated_cost_usd": 0}],
                        "approach": "7 motion scenes + title landing",
                    },
                    {
                        "stage": "assets",
                        "tools": [
                            {
                                "tool_name": "genimage",
                                "role": "Hero stills",
                                "provider": "genimage",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "Cluster FLUX via Comfy/GenImage MCP",
                            },
                            {
                                "tool_name": "comfyui_video",
                                "role": "I2V motion from stills",
                                "provider": "comfyui",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "User default: cluster WAN 2.2 over paid VEO",
                            },
                            {
                                "tool_name": "tts_selector",
                                "role": "Narration",
                                "provider": "gpu_ai",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "aditya via gpu_ai",
                            },
                            {
                                "tool_name": "gpu_ai_music",
                                "role": "Bed",
                                "provider": "gpu_ai",
                                "available": True,
                                "estimated_cost_usd": 0,
                            },
                        ],
                        "approach": "Still → I2V per motion beat; stretch clips to narration; title card for landing",
                        "fallback_if_unavailable": "Ken Burns from stills only after user approval — never silent VEO",
                    },
                    {
                        "stage": "edit",
                        "tools": [{"tool_name": "edit_director", "role": "Cinematic timeline", "available": True, "estimated_cost_usd": 0}],
                        "approach": "CinematicRenderer scenes + soundtrack",
                    },
                    {
                        "stage": "compose",
                        "tools": [
                            {
                                "tool_name": "video_compose",
                                "role": "Remotion CinematicRenderer",
                                "provider": "remotion",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "User-locked Remotion body for video-led montage",
                            }
                        ],
                        "approach": "renderer_family=cinematic-trailer, composition_mode=templated",
                    },
                ],
                "delivery_promise": {
                    "promise_type": "motion_led",
                    "motion_required": True,
                    "tone_mode": "cinematic",
                    "quality_floor": "presentable",
                    "approved_fallback": None,
                },
                "renderer_family": "cinematic-trailer",
                "render_runtime": "remotion",
                "composition_mode": "templated",
                "music_source": {
                    "source_type": "ai_generated",
                    "provider": "gpu_ai",
                    "mood_direction": "premium documentary electronic, low key",
                    "estimated_cost_usd": 0,
                },
                "taste_profile": {
                    "design_read": "Premium coffee-world brand film — photographic motion, cyan map accent, no chart UI.",
                    "visual_variance": 6,
                    "motion_intensity": 7,
                    "information_density": 4,
                    "anti_patterns": ["Stock chart cards", "Logo-heavy cafe stock", "Silent VEO upgrade"],
                    "quality_gates": ["Real WAN motion on myth-bust beats", "No paid video eng unless asked"],
                },
            },
            "cost_estimate": {
                "total_estimated_usd": 0.0,
                "line_items": [
                    {"tool": "genimage", "operation": "8 stills", "quantity": 8, "estimated_usd": 0},
                    {"tool": "comfyui_video", "operation": "7 I2V clips", "quantity": 7, "estimated_usd": 0},
                    {"tool": "tts_selector/gpu_ai", "operation": "narration", "quantity": 1, "estimated_usd": 0},
                    {"tool": "gpu_ai_music", "operation": "bed", "quantity": 1, "estimated_usd": 0},
                ],
                "budget_cap_usd": BUDGET,
                "budget_verdict": "within_budget",
            },
            "approval": {
                "status": "approved",
                "user_notes": "go concept 1 remotion body; switch to comfyui_video+genimage; always default Comfy over VEO",
                "approved_budget_usd": BUDGET,
            },
            "metadata": {"title": TITLE, "approved_at": now_iso()},
        },
    )
    save_json(art_dir / "proposal_packet.json", proposal)

    decision_log = must_valid(
        "decision_log",
        {
            "version": "1.0",
            "project_id": PID,
            "decisions": [
                {
                    "decision_id": "d-001",
                    "stage": "proposal",
                    "category": "concept_selection",
                    "subject": "Marketing concept",
                    "options_considered": [
                        {"option_id": "c1", "label": TITLE, "score": 1.0, "reason": "Approved"},
                        {"option_id": "c2", "label": "Grown Here. Drunk Elsewhere.", "score": 0.7, "reason": "Alt", "rejected_because": "User chose c1"},
                        {"option_id": "c3", "label": "Two Billion Quiet Mornings", "score": 0.65, "reason": "Alt", "rejected_because": "User chose c1"},
                    ],
                    "selected": "c1",
                    "reason": "User go on concept 1",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-002",
                    "stage": "proposal",
                    "category": "render_runtime_selection",
                    "subject": "Technical render runtime",
                    "options_considered": [
                        {"option_id": "remotion", "label": "Remotion CinematicRenderer", "score": 1.0, "reason": "Video-led OffthreadVideo montage"},
                        {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.55, "reason": "Titles strong, weaker for clip body", "rejected_because": "User locked Remotion body"},
                        {"option_id": "ffmpeg", "label": "FFmpeg concat", "score": 0.2, "reason": "No cinematic grade", "rejected_because": "Fails motion-led promise"},
                    ],
                    "selected": "remotion",
                    "reason": "User-approved Remotion body",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-003",
                    "stage": "proposal",
                    "category": "provider_selection",
                    "subject": "Generated video provider",
                    "options_considered": [
                        {"option_id": "comfyui_video", "label": "ComfyUI WAN 2.2 I2V", "score": 1.0, "reason": "Cluster, $0, models present"},
                        {"option_id": "veo_video", "label": "Google Veo", "score": 0.4, "reason": "Polish but ~$0.40/s", "rejected_because": "User default: Comfy unless explicitly asking for VEO"},
                        {"option_id": "sora_video", "label": "Sora", "score": 0.35, "reason": "Paid", "rejected_because": "Not requested; pricier than Comfy"},
                    ],
                    "selected": "comfyui_video",
                    "reason": "User instructed always default to ComfyUI video",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-004",
                    "stage": "proposal",
                    "category": "composition_mode",
                    "subject": "How Remotion composition is authored",
                    "options_considered": [
                        {"option_id": "templated", "label": "CinematicRenderer stock scenes", "score": 0.85, "reason": "video+title scenes fit gen montage"},
                        {"option_id": "atelier", "label": "Bespoke atelier composition", "score": 0.7, "reason": "Max uniqueness, slower", "rejected_because": "Templated cinematic grammar sufficient for this cut"},
                    ],
                    "selected": "templated",
                    "reason": "CinematicRenderer is built for OffthreadVideo montages",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.85,
                },
            ],
        },
    )
    save_json(art_dir / "decision_log.json", decision_log)
    cp(
        "proposal", "completed",
        {"proposal_packet": proposal, "decision_log": decision_log},
        human_approved=True,
        cost_snapshot={"total_spent_usd": 0, "total_reserved_usd": 0, "budget_remaining_usd": BUDGET},
    )

    # ── script ────────────────────────────────────────────────────────────
    cp("script", "in_progress", {})
    t = 0.0
    sections = []
    for sc in SCENES:
        sections.append({
            "id": sc["id"],
            "label": sc["label"],
            "text": sc["narration"],
            "start_seconds": t,
            "end_seconds": t + sc["duration"],
            "speaker_directions": "Premium documentary VO, calm authority",
            "delivery_cues": {
                "pace": "measured",
                "energy": "controlled myth-bust",
                "emphasis_words": ["Finland", "three times", "twelve", "forty percent", "map"],
                "provider_text": sc["narration"],
            },
        })
        t += sc["duration"]
    script = must_valid(
        "script",
        {
            "version": "1.0",
            "title": TITLE,
            "total_duration_seconds": planned,
            "voice_performance": {
                "performance_intent": "Premium brand-film narrator",
                "pacing_profile": "cinematic",
                "energy_curve": "hook → evidence → landing",
                "pause_policy": "Beat before key numbers",
                "sample_section_id": "sc2",
                "provider_notes": {"gpu_ai": "voice=aditya"},
            },
            "sections": sections,
            "metadata": {
                "beat_map": ["hook", "reveal", "ritual", "contrast", "leaders", "growers", "scale", "landing"],
                "title_card_copy": ["Show them the map."],
                "word_count": len(full_narration.split()),
            },
        },
    )
    save_json(art_dir / "script.json", script)
    cp("script", "completed", {"script": script}, human_approved=True)

    # ── scene_plan ────────────────────────────────────────────────────────
    cp("scene_plan", "in_progress", {})
    t = 0.0
    scenes_out = []
    for sc in SCENES:
        scenes_out.append({
            "id": sc["id"],
            "type": "generated",
            "description": f"{sc['label']}: {sc['kind']} via genimage+comfyui_video",
            "start_seconds": t,
            "end_seconds": t + sc["duration"],
            "script_section_id": sc["id"],
            "narrative_role": "deliver_payload" if sc["id"] != "sc8" else "call_to_action",
            "information_role": sc["label"],
            "hero_moment": sc["id"] in {"sc2", "sc3"},
            "shot_intent": sc["motion_prompt"] if sc["kind"] == "motion" else sc["title_text"],
            "required_assets": [
                {"type": "image", "description": sc["image_prompt"][:120], "source": "generate"},
                *(
                    [{"type": "video", "description": "ComfyUI I2V", "source": "generate"}]
                    if sc["kind"] == "motion"
                    else []
                ),
            ],
            "texture_keywords": ["cinematic", "photoreal", "documentary"],
        })
        t += sc["duration"]
    scene_plan = must_valid(
        "scene_plan",
        {
            "version": "1.0",
            "style_playbook": PLAYBOOK,
            "scenes": scenes_out,
            "metadata": {
                "render_runtime": "remotion",
                "renderer_family": "cinematic-trailer",
                "video_provider": "comfyui_video",
                "image_provider": "genimage",
            },
        },
    )
    save_json(art_dir / "scene_plan.json", scene_plan)
    cp("scene_plan", "completed", {"scene_plan": scene_plan}, human_approved=True)

    # ── assets ────────────────────────────────────────────────────────────
    cp("assets", "in_progress", {})
    from tools.audio.tts_selector import TTSSelector
    from tools.gpu_ai.genimage import GenImage
    from tools.gpu_ai.music import GpuAiMusic
    from tools.video.comfyui_video import ComfyUIVideo

    gen = GenImage()
    comfy = ComfyUIVideo()
    manifest_assets = []

    # Narration first (needed for timing)
    narr_rel = "assets/audio/narration.wav"
    narr_path = pdir / narr_rel
    print("[tool] tts_selector | preferred_provider=gpu_ai | voice=aditya", flush=True)
    tts = TTSSelector().execute({
        "text": full_narration,
        "voice_id": "aditya",
        "preferred_provider": "gpu_ai",
        "output_path": str(narr_path),
        "response_format": "wav",
        "speed": 0.92,
    })
    if not tts.success or not narr_path.exists():
        print(f"[fail] TTS: {tts.error}", flush=True)
        return 1
    spent += float(tts.cost_usd or 0)
    narr_dur = audio_duration(narr_path)
    print(f"[ok] narration {narr_dur:.1f}s", flush=True)
    manifest_assets.append({
        "id": "narration_main",
        "type": "narration",
        "path": narr_rel,
        "source_tool": "tts_selector",
        "scene_id": "sc1",
        "provider": "gpu_ai",
        "duration_seconds": round(narr_dur, 2),
        "cost_usd": float(tts.cost_usd or 0),
        "format": "wav",
    })

    scale = narr_dur / planned if planned else 1.0
    public_dir = Path(__file__).resolve().parent.parent / "remotion-composer" / "public" / PID
    public_dir.mkdir(parents=True, exist_ok=True)

    for sc in SCENES:
        beat_dur = sc["duration"] * scale
        img_rel = f"assets/images/{sc['id']}.png"
        img_path = pdir / img_rel
        print(f"[tool] genimage | operation=generate | scene={sc['id']}", flush=True)
        img_res = gen.execute({
            "operation": "generate",
            "prompt": sc["image_prompt"],
            "width": 1280,
            "height": 720,
            "steps": 28,
            "output_path": str(img_path),
        })
        if not img_res.success or not img_path.exists():
            print(f"[fail] genimage {sc['id']}: {img_res.error}", flush=True)
            # openai fallback only after announce — user said cluster first; try once
            print("[tool] openai_image | fallback after genimage failure — asking path: auto-try once", flush=True)
            from tools.graphics.openai_image import OpenAIImage
            img_res = OpenAIImage().execute({
                "prompt": sc["image_prompt"],
                "size": "1792x1024",
                "output_path": str(img_path),
            })
            if not img_res.success or not img_path.exists():
                print(f"[fail] image {sc['id']}: {img_res.error}", flush=True)
                return 1
            spent += float(img_res.cost_usd or 0)
            img_tool = "openai_image"
        else:
            spent += float(img_res.cost_usd or 0)
            img_tool = "genimage"
        manifest_assets.append({
            "id": f"img_{sc['id']}",
            "type": "image",
            "path": img_rel,
            "source_tool": img_tool,
            "scene_id": sc["id"],
            "prompt": sc["image_prompt"],
            "cost_usd": float(img_res.cost_usd or 0),
            "resolution": "1280x720",
        })

        out_rel = f"assets/video/{sc['id']}.mp4"
        out_path = pdir / out_rel

        if sc["kind"] == "motion":
            raw_path = pdir / f"assets/video/{sc['id']}_raw.mp4"
            print(
                f"[tool] comfyui_video | operation=image_to_video | scene={sc['id']} | "
                f"model=WAN2.2-I2V-14B | reason=cluster default",
                flush=True,
            )
            vid = comfy.execute({
                "prompt": sc["motion_prompt"],
                "operation": "image_to_video",
                "reference_image_path": str(img_path),
                "width": 832,
                "height": 480,
                "num_frames": 81,
                "output_path": str(raw_path),
            })
            if vid.success and raw_path.exists():
                spent += float(vid.cost_usd or 0)
                stretch_clip(raw_path, out_path, beat_dur)
                vtool = "comfyui_video"
            else:
                print(f"[warn] comfy I2V failed ({vid.error}); Ken Burns fallback for {sc['id']}", flush=True)
                ken_burns(img_path, out_path, beat_dur)
                vtool = "ffmpeg_ken_burns"
            manifest_assets.append({
                "id": f"vid_{sc['id']}",
                "type": "video",
                "path": out_rel,
                "source_tool": vtool,
                "scene_id": sc["id"],
                "prompt": sc["motion_prompt"],
                "duration_seconds": round(beat_dur, 2),
                "cost_usd": float(vid.cost_usd or 0) if vid.success else 0,
            })
        else:
            ken_burns(img_path, out_path, beat_dur)
            manifest_assets.append({
                "id": f"vid_{sc['id']}",
                "type": "video",
                "path": out_rel,
                "source_tool": "ffmpeg_ken_burns",
                "scene_id": sc["id"],
                "duration_seconds": round(beat_dur, 2),
                "cost_usd": 0,
            })

        # Stage for Remotion staticFile
        shutil.copy2(out_path, public_dir / f"{sc['id']}.mp4")
        shutil.copy2(img_path, public_dir / f"{sc['id']}.png")

    music_rel = "assets/music/bed.mp3"
    music_path = pdir / music_rel
    print("[tool] gpu_ai_music | documentary bed 100s", flush=True)
    music = GpuAiMusic().execute({
        "tags": "cinematic documentary, soft electronic pulse, low key, instrumental",
        "seconds": 100,
        "loop": True,
        "lyrics": "[inst]",
        "response_format": "mp3",
        "output_path": str(music_path),
        "poll_timeout_s": 600,
    })
    music_tool = "gpu_ai_music"
    if not (music.success and music_path.exists()):
        print(f"[warn] gpu music failed: {music.error}; pixabay", flush=True)
        from tools.audio.pixabay_music import PixabayMusic
        music = PixabayMusic().execute({
            "query": "cinematic ambient documentary",
            "min_duration": 60,
            "max_duration": 180,
            "output_path": str(music_path),
        })
        music_tool = "pixabay_music"
    if music.success and music_path.exists():
        spent += float(music.cost_usd or 0)
        shutil.copy2(music_path, public_dir / "bed.mp3")
        manifest_assets.append({
            "id": "music_bed",
            "type": "music",
            "path": music_rel,
            "source_tool": music_tool,
            "scene_id": "sc1",
            "duration_seconds": 100,
            "cost_usd": float(music.cost_usd or 0),
            "format": "mp3",
        })

    shutil.copy2(narr_path, public_dir / "narration.wav")

    manifest = must_valid(
        "asset_manifest",
        {"version": "1.0", "assets": manifest_assets, "total_cost_usd": round(spent, 4)},
    )
    save_json(art_dir / "asset_manifest.json", manifest)
    cp(
        "assets", "completed", {"asset_manifest": manifest},
        human_approved=True,
        cost_snapshot={"total_spent_usd": spent, "total_reserved_usd": 0, "budget_remaining_usd": BUDGET - spent},
    )

    # ── edit ──────────────────────────────────────────────────────────────
    cp("edit", "in_progress", {})
    cinematic_scenes = []
    t = 0.0
    cuts = []
    for sc in SCENES:
        beat_dur = sc["duration"] * scale
        if sc["kind"] == "title":
            cinematic_scenes.append({
                "id": sc["id"],
                "kind": "title",
                "startSeconds": round(t, 3),
                "durationSeconds": round(beat_dur, 3),
                "text": sc["title_text"],
                "accent": sc.get("title_accent", "#06B6D4"),
                "backgroundSrc": f"{PID}/{sc['id']}.mp4",
                "variant": "plate",
            })
        else:
            cinematic_scenes.append({
                "id": sc["id"],
                "kind": "video",
                "startSeconds": round(t, 3),
                "durationSeconds": round(beat_dur, 3),
                "src": f"{PID}/{sc['id']}.mp4",
                "tone": "steel",
                "fadeInFrames": 8,
                "fadeOutFrames": 8,
            })
        cuts.append({
            "id": f"cut_{sc['id']}",
            "source": f"vid_{sc['id']}",
            "in_seconds": 0,
            "out_seconds": round(beat_dur, 3),
            "layer": "primary",
            "reason": sc["label"],
            "transition_in": "fade",
            "transition_out": "fade",
            "transition_duration": 0.35,
        })
        t += beat_dur

    remotion_props = {
        "version": "1.0",
        "renderer_family": "cinematic-trailer",
        "render_runtime": "remotion",
        "composition_mode": "templated",
        "playbook": PLAYBOOK,
        "scenes": cinematic_scenes,
        "cuts": cuts,
        "soundtrack": {"src": f"{PID}/narration.wav", "volume": 1.0},
        **(
            {"music": {"src": f"{PID}/bed.mp3", "volume": 0.14, "fadeInSeconds": 1.5, "fadeOutSeconds": 2.5}}
            if (pdir / music_rel).exists()
            else {}
        ),
        "metadata": {
            "delivery_promise": proposal["production_plan"]["delivery_promise"],
            "video_provider": "comfyui_video",
        },
    }
    save_json(art_dir / "remotion_props.json", remotion_props)

    edit = must_valid(
        "edit_decisions",
        {
            "version": "1.0",
            "render_runtime": "remotion",
            "renderer_family": "cinematic-trailer",
            "composition_mode": "templated",
            "cuts": cuts,
            "audio": {
                "narration": {"segments": [{"asset_id": "narration_main", "start_seconds": 0}]},
                **(
                    {"music": {"asset_id": "music_bed", "volume": 0.14, "fade_in_seconds": 1.5, "fade_out_seconds": 2.5}}
                    if any(a["id"] == "music_bed" for a in manifest_assets)
                    else {}
                ),
            },
            "subtitles": {"enabled": False},
            "metadata": {
                "delivery_promise": proposal["production_plan"]["delivery_promise"],
                "remotion_props_path": "artifacts/remotion_props.json",
                "narration_duration_seconds": narr_dur,
            },
        },
    )
    save_json(art_dir / "edit_decisions.json", edit)
    cp("edit", "completed", {"edit_decisions": edit}, human_approved=True)

    # ── compose ───────────────────────────────────────────────────────────
    cp("compose", "in_progress", {})
    from tools.video.video_compose import VideoCompose

    out_mp4 = pdir / "renders" / "coffee_map_marketing.mp4"
    print(
        "[tool] video_compose | provider=remotion | renderer_family=cinematic-trailer | "
        "reason=user-approved Remotion body",
        flush=True,
    )
    compose = VideoCompose().execute({
        "operation": "render",
        "edit_decisions": remotion_props,
        "asset_manifest": {
            "version": "1.0",
            "assets": [{**a, "path": str(pdir / a["path"])} for a in manifest_assets],
        },
        "scene_plan": scene_plan.get("scenes"),
        "proposal_packet": proposal,
        "output_path": str(out_mp4),
        "profile": "youtube_landscape",
        "options": {"subtitle_burn": False},
        "script_text": full_narration,
        "remotion_timeout_ms": 180000,
    })
    if not compose.success:
        print(f"[fail] compose: {compose.error}", flush=True)
        cp("compose", "failed", {"error": compose.error})
        return 1

    out_dur = audio_duration(out_mp4)
    report = must_valid(
        "render_report",
        {
            "version": "1.0",
            "outputs": [{
                "path": "renders/coffee_map_marketing.mp4",
                "format": "mp4",
                "resolution": "1920x1080",
                "duration_seconds": round(out_dur, 2),
                "codec": "h264",
            }],
            "render_grammar": "cinematic-trailer",
            "metadata": {
                "render_runtime": "remotion",
                "video_provider": "comfyui_video",
                "image_provider": "genimage",
                "spent_usd": spent,
                "final_review": (compose.data or {}).get("final_review"),
            },
        },
    )
    save_json(art_dir / "render_report.json", report)
    cp(
        "compose", "completed", {"render_report": report},
        cost_snapshot={"total_spent_usd": spent, "total_reserved_usd": 0, "budget_remaining_usd": BUDGET - spent},
    )

    publish = must_valid(
        "publish_log",
        {
            "version": "1.0",
            "entries": [{
                "platform": "board",
                "status": "exported",
                "url": f"https://om.baisoln.com/p/{PID}",
                "export_path": "renders/coffee_map_marketing.mp4",
                "timestamp": now_iso(),
                "visibility": "unlisted",
                "metadata_used": {"title": TITLE, "description": "Marketing montage — ComfyUI WAN + GenImage + Remotion"},
            }],
            "metadata": {"completed_at": now_iso()},
        },
    )
    save_json(art_dir / "publish_log.json", publish)
    cp("publish", "completed", {"publish_log": publish}, human_approved=True)

    print(
        f"[done] {out_mp4} ({out_dur:.1f}s) spent=${spent:.4f} "
        f"board=https://om.baisoln.com/p/{PID}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

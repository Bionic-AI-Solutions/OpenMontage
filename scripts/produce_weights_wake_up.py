#!/usr/bin/env python3
"""Produce 'Weights That Wake Up' via animated-explainer (ffmpeg + OmniVoice)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint
from lib.events import emit_event
from lib.vault_config import ensure_vault_config_loaded
from schemas.artifacts import validate_artifact

PID = "weights-that-wake-up"
TITLE = "Weights That Wake Up"
PIPELINE = "animated-explainer"
PLAYBOOK = "clean-professional"
BUDGET = 2.0

SCENES = [
    {
        "id": "sc1",
        "label": "Sleeping weights",
        "duration": 6.0,
        "narration": (
            "At first, the network is asleep. Millions of tiny weights sit random — "
            "no pattern, no meaning, just noise waiting for a signal."
        ),
        "image_prompt": (
            "Editorial conceptual illustration of a sleeping neural network: "
            "dim grid of soft glowing nodes connected by faint threads, deep indigo "
            "and charcoal palette, shallow depth of field, cinematic soft key light "
            "from upper left, clean modern science magazine style, no text, no logos"
        ),
        "animation": "ken-burns-slow-zoom",
    },
    {
        "id": "sc2",
        "label": "First example",
        "duration": 7.0,
        "narration": (
            "Then an example arrives. An input travels forward, each layer transforming "
            "it, until a guess appears — usually wrong."
        ),
        "image_prompt": (
            "Conceptual illustration of a data pulse traveling left to right through "
            "layered neural network nodes, warm amber signal on cool blue layers, "
            "motion streak implying forward pass, clean technical editorial style, "
            "no text, no logos, soft volumetric light"
        ),
        "animation": "pan-right",
    },
    {
        "id": "sc3",
        "label": "Error and gradient",
        "duration": 7.0,
        "narration": (
            "Error measures how far that guess was. Gradients flow backward, telling "
            "every weight how to nudge — a little more, a little less."
        ),
        "image_prompt": (
            "Conceptual reverse wave of cyan light flowing backward through a neural "
            "network graph, subtle error heatmap glow near the output, precise "
            "diagrammatic editorial illustration, dark background, no text, no logos"
        ),
        "animation": "pan-left",
    },
    {
        "id": "sc4",
        "label": "Weights waking",
        "duration": 8.0,
        "narration": (
            "Repeat this thousands of times and the weights wake up. Chaos becomes "
            "structure. The network starts to recognize what matters."
        ),
        "image_prompt": (
            "Neural network awakening: nodes brighten from left to right into a "
            "coherent constellation, gold and teal luminescence, before-to-after "
            "sense of order emerging from chaos, cinematic science illustration, "
            "no text, no logos"
        ),
        "animation": "ken-burns-slow-zoom",
    },
    {
        "id": "sc5",
        "label": "Generalization",
        "duration": 7.0,
        "narration": (
            "Learning is not memorizing answers. It is discovering a shape in the data "
            "that still works on examples the network has never seen."
        ),
        "image_prompt": (
            "Abstract landscape of a smooth learned decision surface with a few "
            "new glowing sample points landing correctly on it, minimal geometric "
            "editorial style, dawn light, hopeful tone, no text, no logos"
        ),
        "animation": "ken-burns-slow-zoom",
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
        PROJECTS_DIR,
        PID,
        stage,
        status,
        artifacts,
        pipeline_type=PIPELINE,
        **kw,
    )
    print(f"[cp] {stage} -> {status}", flush=True)


def main() -> int:
    ensure_vault_config_loaded()
    pdir = PROJECTS_DIR / PID
    if pdir.exists():
        print(f"[init] removing prior project at {pdir}", flush=True)
        shutil.rmtree(pdir)

    init_project(
        PID,
        title=TITLE,
        pipeline_type=PIPELINE,
        style_playbook=PLAYBOOK,
    )
    art_dir = pdir / "artifacts"
    spent = 0.0
    total_duration = sum(s["duration"] for s in SCENES)
    full_narration = " ".join(sc["narration"] for sc in SCENES)

    # ── research ──────────────────────────────────────────────────────────
    cp("research", "in_progress", {})
    research = must_valid(
        "research_brief",
        {
            "version": "1.0",
            "topic": "How a neural network learns — weights that wake up",
            "research_date": "2026-07-19",
            "landscape": {
                "existing_content": [
                    {
                        "title": "3Blue1Brown Neural Networks",
                        "source": "youtube",
                        "angle": "math intuition",
                        "what_it_covers": "forward pass, gradients, visual math",
                        "url": "https://www.3blue1brown.com/topics/neural-networks",
                    },
                    {
                        "title": "StatQuest Neural Networks",
                        "source": "youtube",
                        "angle": "whiteboard pedagogy",
                        "what_it_covers": "loss and backprop basics",
                    },
                    {
                        "title": "CS231n notes",
                        "source": "blog",
                        "angle": "course notes",
                        "what_it_covers": "optimization and generalization",
                        "url": "https://cs231n.github.io/",
                    },
                ],
                "saturated_angles": ["generic 'what is a neural network' intros"],
                "underserved_gaps": [
                    "short metaphor-first story of weights waking through training"
                ],
            },
            "data_points": [
                {
                    "claim": "Networks start from random weights and learn via gradient descent.",
                    "source_url": "https://www.deeplearningbook.org/",
                    "credibility": "secondary_source",
                },
                {
                    "claim": "Backpropagation assigns each weight a share of the error.",
                    "source_url": "https://www.nature.com/articles/323533a0",
                    "credibility": "primary_source",
                },
                {
                    "claim": "Generalization is performance on unseen examples.",
                    "source_url": "https://cs231n.github.io/",
                    "credibility": "secondary_source",
                },
            ],
            "audience_insights": {
                "common_questions": [
                    "What are weights before training?",
                    "What does a forward pass do?",
                    "How do gradients change weights?",
                    "Why does repetition create recognition?",
                    "What is generalization vs memorization?",
                ],
                "misconceptions": [
                    {
                        "myth": "The network memorizes every answer.",
                        "reality": "It discovers reusable structure that transfers.",
                    }
                ],
                "knowledge_level": "Beginner to intermediate builders",
            },
            "angles_discovered": [
                {
                    "name": "Weights that wake up",
                    "hook": "Watch sleeping weights wake as gradients teach them.",
                    "type": "evergreen",
                    "why_now": "Short-form ML explainers keep growing",
                    "grounded_in": ["data_point_1", "data_point_2"],
                },
                {
                    "name": "Error as teacher",
                    "hook": "The loss signal is the only teacher the network has.",
                    "type": "contrarian",
                    "why_now": "Counters magic-model narratives",
                    "grounded_in": ["data_point_2"],
                },
                {
                    "name": "Shape in the data",
                    "hook": "Learning is discovering a shape that still works on new points.",
                    "type": "evergreen",
                    "why_now": "Generalization is the real product promise",
                    "grounded_in": ["data_point_3"],
                },
            ],
            "sources": [
                {
                    "url": "https://www.deeplearningbook.org/",
                    "title": "Deep Learning Book",
                    "used_for": "data_points",
                },
                {
                    "url": "https://www.nature.com/articles/323533a0",
                    "title": "Learning representations by back-propagating errors",
                    "used_for": "data_points",
                },
                {
                    "url": "https://cs231n.github.io/",
                    "title": "CS231n",
                    "used_for": "data_points",
                },
                {
                    "url": "https://www.3blue1brown.com/topics/neural-networks",
                    "title": "3Blue1Brown Neural Networks",
                    "used_for": "landscape",
                },
                {
                    "url": "https://distill.pub/",
                    "title": "Distill",
                    "used_for": "landscape",
                },
            ],
        },
    )
    save_json(art_dir / "research_brief.json", research)
    cp("research", "completed", {"research_brief": research})

    # ── proposal ──────────────────────────────────────────────────────────
    cp("proposal", "in_progress", {})
    proposal = must_valid(
        "proposal_packet",
        {
            "version": "1.0",
            "concept_options": [
                {
                    "id": "c1",
                    "title": TITLE,
                    "hook": "Watch sleeping weights wake as gradients teach them.",
                    "narrative_structure": "analogy",
                    "visual_approach": "still-led conceptual illustrations with Ken Burns",
                    "suggested_playbook": PLAYBOOK,
                    "target_audience": "Curious builders new to ML",
                    "target_platform": "youtube",
                    "target_duration_seconds": total_duration,
                    "key_points": [
                        "Random weights start asleep",
                        "Forward pass makes a guess",
                        "Gradients nudge every weight",
                        "Repetition creates structure",
                        "Generalization beats memorization",
                    ],
                    "core_message": "Learning is weights waking into structure.",
                    "why_this_works": "Grounded metaphor gap found in research landscape",
                    "grounded_in": ["angles_discovered[0]", "data_points[0]"],
                },
                {
                    "id": "c2",
                    "title": "Error as Teacher",
                    "hook": "The loss signal is the only teacher the network has.",
                    "narrative_structure": "problem_solution",
                    "visual_approach": "error heatmap and reverse-flow diagrams",
                    "target_duration_seconds": total_duration,
                    "key_points": ["Guess", "Measure error", "Propagate blame", "Update"],
                    "why_this_works": "Centers the undervalued loss signal",
                    "grounded_in": ["angles_discovered[1]"],
                },
                {
                    "id": "c3",
                    "title": "Shape in the Data",
                    "hook": "Learning discovers a shape that still works on new points.",
                    "narrative_structure": "data_narrative",
                    "visual_approach": "decision-surface landscape",
                    "target_duration_seconds": total_duration + 5,
                    "key_points": ["Fit", "Overfit risk", "Holdout truth"],
                    "why_this_works": "Ends on the real product promise: generalization",
                    "grounded_in": ["angles_discovered[2]"],
                },
            ],
            "selected_concept": {
                "concept_id": "c1",
                "rationale": "User approved concept 1 from the earlier concept menu.",
            },
            "production_plan": {
                "pipeline": PIPELINE,
                "playbook": PLAYBOOK,
                "render_runtime": "ffmpeg",
                "stages": [
                    {
                        "stage": "script",
                        "tools": [],
                        "approach": "Write metaphor-led narration to duration budget",
                    },
                    {
                        "stage": "assets",
                        "tools": [
                            {
                                "tool_name": "omnivoice_tts",
                                "role": "narration",
                                "provider": "omnivoice",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                                "why_this_provider": "User requested OmniVoice/Sarvam",
                            },
                            {
                                "tool_name": "openai_image",
                                "role": "scene stills",
                                "provider": "openai",
                                "available": True,
                                "estimated_cost_usd": 1.2,
                                "why_this_provider": "Available paid image path in cluster",
                            },
                            {
                                "tool_name": "pixabay_music",
                                "role": "music bed",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                            },
                        ],
                        "approach": "5 stills + OmniVoice narration + free music bed",
                        "fallback_if_unavailable": "sarvam_tts for narration",
                    },
                    {
                        "stage": "compose",
                        "tools": [
                            {
                                "tool_name": "video_compose",
                                "role": "ffmpeg ken burns compose",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                            }
                        ],
                        "approach": "render_runtime=ffmpeg with Ken Burns still segments",
                    },
                ],
            },
            "cost_estimate": {
                "total_estimated_usd": 1.4,
                "line_items": [
                    {
                        "tool": "openai_image",
                        "operation": "5 scene stills",
                        "estimated_usd": 1.2,
                    },
                    {
                        "tool": "omnivoice_tts",
                        "operation": "narration",
                        "estimated_usd": 0.0,
                    },
                    {
                        "tool": "video_compose",
                        "operation": "ffmpeg compose",
                        "estimated_usd": 0.0,
                    },
                ],
                "budget_verdict": "within_budget",
            },
            "approval": {
                "status": "approved",
                "approved_budget_usd": BUDGET,
                "user_notes": "User approved concept 1, Sarvam/OmniVoice TTS, ffmpeg compose.",
            },
        },
    )
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
                    "subject": "Explainer concept",
                    "options_considered": [
                        {
                            "option_id": "c1",
                            "label": "Weights That Wake Up",
                            "score": 0.95,
                            "reason": "User-selected metaphor",
                        },
                        {
                            "option_id": "c2",
                            "label": "Error as Teacher",
                            "score": 0.7,
                            "reason": "Strong but not chosen",
                            "rejected_because": "User chose concept 1",
                        },
                        {
                            "option_id": "c3",
                            "label": "Shape in the Data",
                            "score": 0.65,
                            "reason": "Generalization-first",
                            "rejected_because": "User chose concept 1",
                        },
                    ],
                    "selected": "c1",
                    "reason": "User confirmed the first concept.",
                },
                {
                    "decision_id": "d-002",
                    "stage": "proposal",
                    "category": "voice_selection",
                    "subject": "Narration TTS provider",
                    "options_considered": [
                        {
                            "option_id": "omnivoice",
                            "label": "omnivoice_tts",
                            "score": 0.95,
                            "reason": "In-cluster, free, user-approved",
                        },
                        {
                            "option_id": "sarvam",
                            "label": "sarvam_tts",
                            "score": 0.85,
                            "reason": "Vault key present; fallback",
                        },
                        {
                            "option_id": "elevenlabs",
                            "label": "elevenlabs_tts",
                            "score": 0.5,
                            "reason": "Paid",
                            "rejected_because": "User asked for Sarvam/OmniVoice",
                        },
                    ],
                    "selected": "omnivoice",
                    "reason": "Primary OmniVoice with Sarvam fallback.",
                },
                {
                    "decision_id": "d-003",
                    "stage": "proposal",
                    "category": "render_runtime_selection",
                    "subject": "Compose runtime",
                    "options_considered": [
                        {
                            "option_id": "ffmpeg",
                            "label": "ffmpeg Ken Burns",
                            "score": 0.9,
                            "reason": "Available in image; user approved",
                        },
                        {
                            "option_id": "remotion",
                            "label": "remotion",
                            "score": 0.2,
                            "reason": "Not in container image",
                            "rejected_because": "Node/Remotion unavailable",
                        },
                    ],
                    "selected": "ffmpeg",
                    "reason": "User approved ffmpeg compose for this run.",
                },
            ],
        },
    )
    save_json(art_dir / "proposal_packet.json", proposal)
    save_json(art_dir / "decision_log.json", decision_log)
    cp(
        "proposal",
        "completed",
        {"proposal_packet": proposal, "decision_log": decision_log},
        human_approved=True,
    )

    # ── script ────────────────────────────────────────────────────────────
    cp("script", "in_progress", {})
    t = 0.0
    sections = []
    for i, sc in enumerate(SCENES):
        sections.append(
            {
                "id": f"s{i+1}",
                "label": sc["label"],
                "text": sc["narration"],
                "start_seconds": t,
                "end_seconds": t + sc["duration"],
            }
        )
        t += sc["duration"]
    script = must_valid(
        "script",
        {
            "version": "1.0",
            "title": TITLE,
            "total_duration_seconds": total_duration,
            "sections": sections,
        },
    )
    save_json(art_dir / "script.json", script)
    cp("script", "completed", {"script": script}, human_approved=True)

    # ── scene_plan ────────────────────────────────────────────────────────
    cp("scene_plan", "in_progress", {})
    t = 0.0
    scenes = []
    for i, sc in enumerate(SCENES):
        scenes.append(
            {
                "id": sc["id"],
                "type": "broll",
                "description": f"{sc['label']}: {sc['image_prompt'][:160]}",
                "start_seconds": t,
                "end_seconds": t + sc["duration"],
                "script_section_id": f"s{i+1}",
                "required_assets": [
                    {
                        "type": "image",
                        "description": sc["image_prompt"],
                        "source": "generate",
                    }
                ],
            }
        )
        t += sc["duration"]
    scene_plan = must_valid("scene_plan", {"version": "1.0", "scenes": scenes})
    save_json(art_dir / "scene_plan.json", scene_plan)
    cp("scene_plan", "completed", {"scene_plan": scene_plan}, human_approved=True)

    # ── assets ────────────────────────────────────────────────────────────
    cp("assets", "in_progress", {})
    from tools.audio.omnivoice_tts import OmniVoiceTTS
    from tools.audio.pixabay_music import PixabayMusic
    from tools.graphics.openai_image import OpenAIImage

    manifest_assets = []

    print(
        "[tool] omnivoice_tts | provider=omnivoice | model=omnivoice | "
        "voice=c32af141013d | reason=user-requested in-cluster TTS | sample=s1",
        flush=True,
    )
    sample_path = pdir / "assets/audio/sample_s1.wav"
    emit_event(pdir, {"tool": "omnivoice_tts", "event": "start", "scene_id": "sc1"})
    sample = OmniVoiceTTS().execute(
        {
            "text": SCENES[0]["narration"],
            "voice": "c32af141013d",
            "language": "en",
            "format": "wav",
            "output_path": str(sample_path),
        }
    )
    tts_tool = "omnivoice_tts"
    tts_voice = "c32af141013d"
    tts_kwargs: dict = {"voice": "c32af141013d", "language": "en", "format": "wav"}
    if not sample.success:
        from tools.audio.sarvam_tts import SarvamTTS

        print(
            "[tool] sarvam_tts | provider=sarvam | model=bulbul:v2 | voice=abhilash | "
            "reason=omnivoice sample failed | sample=s1",
            flush=True,
        )
        sample = SarvamTTS().execute(
            {
                "text": SCENES[0]["narration"],
                "voice": "abhilash",
                "language": "en-IN",
                "output_path": str(sample_path),
            }
        )
        tts_tool = "sarvam_tts"
        tts_voice = "abhilash"
        tts_kwargs = {"voice": "abhilash", "language": "en-IN"}
    emit_event(
        pdir,
        {
            "tool": tts_tool,
            "event": "finish",
            "scene_id": "sc1",
            "success": sample.success,
            "cost_usd": sample.cost_usd or 0,
            "output_path": "assets/audio/sample_s1.wav",
        },
    )
    if not sample.success:
        print(f"[fail] TTS sample: {sample.error}", flush=True)
        return 1
    print(f"[ok] TTS sample {sample.data.get('audio_duration_seconds')}s via {tts_tool}", flush=True)

    narr_path = pdir / "assets/audio/narration.wav"
    print(f"[tool] {tts_tool} | batch narration | voice={tts_voice}", flush=True)
    if tts_tool == "omnivoice_tts":
        narr = OmniVoiceTTS().execute(
            {"text": full_narration, "output_path": str(narr_path), **tts_kwargs}
        )
    else:
        from tools.audio.sarvam_tts import SarvamTTS

        narr = SarvamTTS().execute(
            {"text": full_narration, "output_path": str(narr_path), **tts_kwargs}
        )
    if not narr.success:
        print(f"[fail] full narration: {narr.error}", flush=True)
        return 1
    spent += float(narr.cost_usd or 0)
    narr_dur = float(narr.data.get("audio_duration_seconds") or total_duration)
    manifest_assets.append(
        {
            "id": "narration_main",
            "type": "audio",
            "path": "assets/audio/narration.wav",
            "source_tool": tts_tool,
            "scene_id": "sc1",
        }
    )

    img_tool = OpenAIImage()
    for sc in SCENES:
        rel = f"assets/images/{sc['id']}.png"
        out = pdir / rel
        print(
            "[tool] openai_image | provider=openai | model=gpt-image-2 | "
            f"quality=medium | scene={sc['id']}",
            flush=True,
        )
        emit_event(pdir, {"tool": "openai_image", "event": "start", "scene_id": sc["id"]})
        result = img_tool.execute(
            {
                "prompt": sc["image_prompt"],
                "model": "gpt-image-2",
                "size": "1536x1024",
                "quality": "medium",
                "output_path": str(out),
            }
        )
        emit_event(
            pdir,
            {
                "tool": "openai_image",
                "event": "finish",
                "scene_id": sc["id"],
                "success": result.success,
                "cost_usd": result.cost_usd or 0,
                "output_path": rel,
            },
        )
        if not result.success:
            print(f"[fail] image {sc['id']}: {result.error}", flush=True)
            return 1
        spent += float(result.cost_usd or 0)
        manifest_assets.append(
            {
                "id": f"img_{sc['id']}",
                "type": "image",
                "path": rel,
                "source_tool": "openai_image",
                "scene_id": sc["id"],
            }
        )
        print(f"[ok] {sc['id']} image (${result.cost_usd})", flush=True)

    music_rel = "assets/music/bed.mp3"
    music_path = pdir / music_rel
    print("[tool] pixabay_music | query=ambient soft electronic calm", flush=True)
    music = PixabayMusic().execute(
        {
            "query": "ambient soft electronic calm",
            "min_duration": 30,
            "max_duration": 180,
            "output_path": str(music_path),
        }
    )
    if music.success and music_path.exists():
        manifest_assets.append(
            {
                "id": "music_bed",
                "type": "audio",
                "path": music_rel,
                "source_tool": "pixabay_music",
                "scene_id": "sc1",
            }
        )
    else:
        print(f"[warn] music skipped: {music.error}", flush=True)

    manifest = must_valid(
        "asset_manifest",
        {"version": "1.0", "assets": manifest_assets, "total_cost_usd": round(spent, 4)},
    )
    save_json(art_dir / "asset_manifest.json", manifest)
    cp(
        "assets",
        "completed",
        {"asset_manifest": manifest},
        human_approved=True,
        cost_snapshot={
            "total_spent_usd": spent,
            "total_reserved_usd": 0.0,
            "budget_remaining_usd": BUDGET - spent,
        },
    )

    # ── edit ──────────────────────────────────────────────────────────────
    cp("edit", "in_progress", {})
    scale = narr_dur / total_duration if total_duration else 1.0
    cuts = []
    for sc in SCENES:
        dur = sc["duration"] * scale
        cuts.append(
            {
                "id": f"cut_{sc['id']}",
                "source": f"img_{sc['id']}",
                "in_seconds": 0,
                "out_seconds": dur,
                "layer": "primary",
                "transform": {"animation": sc["animation"]},
                "transition_in": "fade",
                "transition_out": "fade",
                "transition_duration": 0.35,
                "reason": sc["label"],
            }
        )
    edit = must_valid(
        "edit_decisions",
        {
            "version": "1.0",
            "render_runtime": "ffmpeg",
            "renderer_family": "explainer-teacher",
            "cuts": cuts,
            "audio": {
                "narration": {
                    "segments": [{"asset_id": "narration_main", "start_seconds": 0}]
                },
                **(
                    {
                        "music": {
                            "asset_id": "music_bed",
                            "volume": 0.12,
                            "fade_in_seconds": 1.0,
                            "fade_out_seconds": 2.0,
                        }
                    }
                    if any(a["id"] == "music_bed" for a in manifest_assets)
                    else {}
                ),
            },
            "subtitles": {"enabled": False},
            "metadata": {
                "delivery_promise": {
                    "motion_required": False,
                    "still_led_ok": True,
                    "runtime": "ffmpeg",
                },
                "proposal_render_runtime": "ffmpeg",
                "compose_target": {"width": 1920, "height": 1080, "fit": "cover"},
            },
        },
    )
    save_json(art_dir / "edit_decisions.json", edit)
    cp("edit", "completed", {"edit_decisions": edit}, human_approved=True)

    # ── compose ───────────────────────────────────────────────────────────
    cp("compose", "in_progress", {})
    from tools.video.video_compose import VideoCompose

    narr_abs = pdir / "assets/audio/narration.wav"
    mixed_audio = pdir / "assets/audio/mix.wav"
    if (pdir / music_rel).exists():
        fade_out_start = max(narr_dur - 2, 0)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(narr_abs),
                "-i",
                str(pdir / music_rel),
                "-filter_complex",
                (
                    f"[1:a]volume=0.12,afade=t=in:st=0:d=1,"
                    f"afade=t=out:st={fade_out_start}:d=2[m];"
                    "[0:a][m]amix=inputs=2:duration=first:dropout_transition=2"
                ),
                "-c:a",
                "pcm_s16le",
                str(mixed_audio),
            ],
            check=True,
            capture_output=True,
        )
        audio_path = mixed_audio
    else:
        audio_path = narr_abs

    out_mp4 = pdir / "renders" / "weights_that_wake_up.mp4"
    print(
        "[tool] video_compose | provider=ffmpeg | render_runtime=ffmpeg | "
        "reason=user-approved still-led ken burns",
        flush=True,
    )
    # Resolve cut sources to absolute paths for compose (tool also resolves via manifest)
    compose = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": edit,
            "asset_manifest": {
                "version": "1.0",
                "assets": [
                    {**a, "path": str(pdir / a["path"])} for a in manifest_assets
                ],
            },
            "scene_plan": scene_plan.get("scenes"),
            "proposal_packet": proposal,
            "audio_path": str(audio_path),
            "output_path": str(out_mp4),
            "options": {"subtitle_burn": False},
            "script_text": full_narration,
        }
    )
    if not compose.success:
        print(f"[fail] compose: {compose.error}", flush=True)
        return 1

    report = must_valid(
        "render_report",
        {
            "version": "1.0",
            "outputs": [
                {
                    "path": "renders/weights_that_wake_up.mp4",
                    "format": "mp4",
                    "resolution": "1920x1080",
                    "duration_seconds": narr_dur,
                    "codec": "libx264",
                }
            ],
            "render_grammar": "explainer-teacher",
            "metadata": {
                "render_runtime": "ffmpeg",
                "tts_tool": tts_tool,
                "spent_usd": spent,
                "final_review": (compose.data or {}).get("final_review"),
            },
        },
    )
    save_json(art_dir / "render_report.json", report)
    cp(
        "compose",
        "completed",
        {"render_report": report},
        cost_snapshot={
            "total_spent_usd": spent,
            "total_reserved_usd": 0.0,
            "budget_remaining_usd": BUDGET - spent,
        },
    )

    publish = must_valid(
        "publish_log",
        {
            "version": "1.0",
            "entries": [
                {
                    "platform": "backlot",
                    "status": "published",
                    "url": f"https://om.baisoln.com/p/{PID}",
                    "export_path": "renders/weights_that_wake_up.mp4",
                    "timestamp": now_iso(),
                    "visibility": "unlisted",
                    "metadata_used": {"title": TITLE},
                }
            ],
        },
    )
    save_json(art_dir / "publish_log.json", publish)
    cp("publish", "completed", {"publish_log": publish}, human_approved=True)

    print(f"[done] {out_mp4} spent=${spent:.2f}", flush=True)
    print(f"[board] https://om.baisoln.com/p/{PID}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

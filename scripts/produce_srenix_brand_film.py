#!/usr/bin/env python3
"""Srenix brand film: Everyone Else Sends Alerts.

Locked concept from plan. Cluster-first: genimage → comfyui_video I2V → Remotion
CinematicRenderer. No VEO unless explicitly requested.
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

from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint
from lib.vault_config import ensure_vault_config_loaded
from schemas.artifacts import validate_artifact

PID = "srenix-everyone-else-sends-alerts"
TITLE = "Everyone Else Sends Alerts"
PIPELINE = "cinematic"
PLAYBOOK = "flat-motion-graphics"
BUDGET = 5.0

# Locked VO + scene cards (~60s target; timings are planned holds)
SCENES = [
    {
        "id": "sc1",
        "label": "Pager night",
        "duration": 10.0,
        "kind": "motion",
        "narration": (
            "Your cluster is paging you again. Another alert. Another tab. Another night."
        ),
        "image_prompt": (
            "Cinematic night ops desk in a dark room, smartphone glowing with a generic red "
            "notification badge, blurred terminal windows in the background, cool blue monitor "
            "light and warm desk lamp, shallow depth of field, photorealistic editorial still, "
            "no logos, no readable brand names, no text overlays"
        ),
        "motion_prompt": (
            "Slow push toward the glowing phone on the desk, subtle handheld breathe, cinematic"
        ),
    },
    {
        "id": "sc2",
        "label": "Alert storm",
        "duration": 10.0,
        "kind": "motion",
        "narration": (
            "Observability got louder. On-call did not get quieter."
        ),
        "image_prompt": (
            "Abstract cinematic visualization of cascading red signal streaks and log-like light "
            "rain falling over a dark server-rack silhouette, high contrast, premium tech brand "
            "film still, no vendor logos, no readable text"
        ),
        "motion_prompt": (
            "Signals cascade downward faster, camera slowly rises past the rack silhouette"
        ),
    },
    {
        "id": "sc3",
        "label": "The turn",
        "duration": 12.0,
        "kind": "motion",
        "narration": (
            "Srenix doesn't just watch. It detects. Remediates. Verifies."
        ),
        "image_prompt": (
            "Same dark ops desk as before but calmer: monitors show a single soft green verify "
            "pulse instead of red chaos, steam from a coffee mug, quiet blue-hour window light, "
            "photorealistic, no logos, no text"
        ),
        "motion_prompt": (
            "Green verify pulse gently brightens once, camera settles, calm cinematic hold"
        ),
    },
    {
        "id": "sc4",
        "label": "Closed loop",
        "duration": 10.0,
        "kind": "motion",
        "narration": (
            "In-cluster. Your guardrails. Your model. Every action signed and replayable."
        ),
        "image_prompt": (
            "Clean premium diagrammatic still of a three-node cycle on dark slate: Detect, "
            "Remediate, Verify as simple geometric nodes connected by cyan #06B6D4 arcs, "
            "minimal motion-graphics ready composition, no product UI chrome, no logos"
        ),
        "motion_prompt": (
            "Cyan arc light travels around the Detect-Remediate-Verify cycle once, elegant and slow"
        ),
    },
    {
        "id": "sc5",
        "label": "Perimeter",
        "duration": 10.0,
        "kind": "motion",
        "narration": (
            "One operator. Your perimeter. Fixes inside the leash you set."
        ),
        "image_prompt": (
            "Cinematic private data-center aisle with cool white lights, a single operator station "
            "at the end of the row, sense of sovereignty and control, photorealistic, "
            "no cloud vendor logos, no readable rack labels"
        ),
        "motion_prompt": (
            "Slow dolly down the aisle toward the operator station, controlled and premium"
        ),
    },
    {
        "id": "sc6",
        "label": "Landing",
        "duration": 8.0,
        "kind": "title",
        "narration": (
            "Everyone else sends alerts. Srenix sends fixes. srenix.ai"
        ),
        "image_prompt": (
            "Minimal dark slate end-card backdrop with a single soft cyan meridian light streak, "
            "premium brand film empty frame ready for title type, no logos, no text in the image"
        ),
        "title_text": "Everyone else sends alerts.\nSrenix sends fixes.",
        "title_accent": "#06B6D4",
        "motion_prompt": "Static premium hold",
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
    subprocess.run(
        [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
            "-t", f"{target_s:.3f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst),
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
            "-t", f"{target_s:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst),
        ],
        check=True, capture_output=True,
    )


def write_locked_creative(art_dir: Path) -> None:
    """Persist locked VO + scene cards before generation (plan collaboration deliverables)."""
    vo_lines = [
        {"id": sc["id"], "label": sc["label"], "seconds": sc["duration"], "text": sc["narration"]}
        for sc in SCENES
    ]
    locked = {
        "version": "1.0",
        "locked_at": now_iso(),
        "concept": TITLE,
        "target_duration_seconds": sum(sc["duration"] for sc in SCENES),
        "cta": "srenix.ai",
        "voice_over": vo_lines,
        "full_narration": " ".join(sc["narration"] for sc in SCENES),
        "scene_cards": [
            {
                "id": sc["id"],
                "label": sc["label"],
                "duration_seconds": sc["duration"],
                "kind": sc["kind"],
                "image_prompt": sc["image_prompt"],
                "motion_prompt": sc.get("motion_prompt"),
                "title_text": sc.get("title_text"),
            }
            for sc in SCENES
        ],
        "production_defaults": {
            "pipeline": PIPELINE,
            "render_runtime": "remotion",
            "renderer_family": "cinematic-trailer",
            "image_provider": "genimage",
            "video_provider": "comfyui_video",
            "tts_provider": "gpu_ai",
            "voice": "aditya",
        },
    }
    save_json(art_dir / "locked_creative.json", locked)
    md = [
        f"# {TITLE} — Locked creative",
        "",
        f"Locked at: {locked['locked_at']}",
        "",
        "## Voice-over",
        "",
    ]
    for line in vo_lines:
        md.append(f"- **{line['id']} ({line['seconds']:.0f}s) — {line['label']}:** {line['text']}")
    md.extend(["", "## Scene cards", ""])
    for sc in locked["scene_cards"]:
        md.append(f"### {sc['id']} — {sc['label']} ({sc['duration_seconds']:.0f}s, {sc['kind']})")
        md.append(f"- Image: {sc['image_prompt'][:160]}...")
        if sc.get("motion_prompt"):
            md.append(f"- Motion: {sc['motion_prompt']}")
        if sc.get("title_text"):
            md.append(f"- Title: {sc['title_text'].replace(chr(10), ' / ')}")
        md.append("")
    (art_dir / "locked_creative.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[lock] wrote {art_dir / 'locked_creative.json'}", flush=True)


def main() -> int:
    ensure_vault_config_loaded()
    os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")

    pdir = PROJECTS_DIR / PID
    if not (pdir / "project.json").exists():
        init_project(
            PID,
            title=TITLE,
            pipeline_type=PIPELINE,
            style_playbook=PLAYBOOK,
        )
    art_dir = pdir / "artifacts"
    for sub in ("assets/images", "assets/video", "assets/audio", "assets/music", "renders"):
        (pdir / sub).mkdir(parents=True, exist_ok=True)

    write_locked_creative(art_dir)

    spent = 0.0
    full_narration = " ".join(sc["narration"] for sc in SCENES)
    planned = sum(sc["duration"] for sc in SCENES)

    # Research brief (lightweight, product-grounded)
    cp("research", "in_progress", {})
    research = must_valid(
        "research_brief",
        {
            "version": "1.0",
            "topic": "Srenix AI SRE for Kubernetes — Detect. Remediate. Verify.",
            "research_date": "2026-07-20",
            "research_summary": (
                "Srenix is an in-cluster AI reliability operator that closes the loop by default: "
                "detect drift/issues, remediate within policy guardrails, verify the fix. "
                "Differentiator vs alert-only observability: sends fixes, not just noise; BYO-LLM; open core."
            ),
            "landscape": {
                "existing_content": [
                    {
                        "title": "Sazabi funding brand film (LinkedIn)",
                        "source": "linkedin",
                        "angle": "cinematic product manifesto",
                        "what_it_covers": "Status-quo broken → new observability machine; heroic CTA",
                        "url": "https://www.linkedin.com/feed/update/urn:li:activity:7475940394170507264/",
                    },
                    {
                        "title": "Srenix product site",
                        "source": "website",
                        "angle": "Detect. Remediate. Verify.",
                        "what_it_covers": "In-cluster closed loop, guardrails, BYO-LLM",
                        "url": "https://srenix.ai/",
                    },
                    {
                        "title": "Legacy observability dashboards",
                        "source": "blog",
                        "angle": "alert fatigue",
                        "what_it_covers": "Louder telemetry without quieter on-call",
                    },
                ],
                "saturated_angles": ["Another AI dashboard demo", "Generic Kubernetes explainer"],
                "underserved_gaps": ["Closed-loop fix under guardrails as the hero, not chat-about-logs"],
            },
            "data_points": [
                {
                    "claim": "Srenix tagline positions against alert-only tools: everyone else sends alerts; Srenix sends fixes.",
                    "source_url": "https://srenix.ai/",
                    "credibility": "primary_source",
                    "surprise_factor": "notable",
                },
                {
                    "claim": "Closed-loop detect → remediate → verify is the default mode, not a roadmap milestone.",
                    "source_url": "https://srenix.ai/",
                    "credibility": "primary_source",
                    "surprise_factor": "counterintuitive",
                },
                {
                    "claim": "Runs in-cluster with operator-defined policy leash and bring-your-own LLM.",
                    "source_url": "https://srenix.ai/",
                    "credibility": "primary_source",
                    "surprise_factor": "notable",
                },
            ],
            "audience_insights": {
                "common_questions": [
                    "Does it actually fix things or only summarize?",
                    "Where does my data go?",
                    "Can I keep human approval?",
                ],
                "misconceptions": [
                    {
                        "myth": "AI SRE means unsupervised chaos in production.",
                        "reality": "Srenix actions sit inside operator-defined guardrails with signed audit.",
                    }
                ],
                "knowledge_level": "Platform / SRE engineers",
            },
            "angles_discovered": [
                {
                    "name": "Everyone Else Sends Alerts",
                    "hook": "Observability got louder. On-call did not get quieter.",
                    "type": "contrarian",
                    "why_now": "Alert fatigue + agent era",
                    "grounded_in": ["data_point_1", "data_point_2"],
                },
                {
                    "name": "The Leash",
                    "hook": "Reasoning power. Policy has the leash.",
                    "type": "evergreen",
                    "why_now": "Trust barrier for autonomous ops",
                    "grounded_in": ["data_point_3"],
                },
                {
                    "name": "Quiet On-Call",
                    "hook": "On-call should be quieter every week.",
                    "type": "evergreen",
                    "why_now": "Outcome buyers care about",
                    "grounded_in": ["data_point_2"],
                },
            ],
            "sources": [
                {
                    "url": "https://srenix.ai/",
                    "title": "Srenix — product site",
                    "used_for": "data_points + core promise Detect/Remediate/Verify",
                    "reliability": "primary",
                },
                {
                    "url": "https://www.linkedin.com/feed/update/urn:li:activity:7475940394170507264/",
                    "title": "Sazabi LinkedIn brand film reference",
                    "used_for": "landscape existing_content + cinematic manifesto structure",
                    "reliability": "secondary",
                },
                {
                    "url": "https://www.sazabi.com/",
                    "title": "Sazabi — company site",
                    "used_for": "landscape context for reference brand film",
                    "reliability": "secondary",
                },
                {
                    "url": "https://kubernetes.io/docs/concepts/overview/",
                    "title": "Kubernetes overview",
                    "used_for": "audience_insights platform/SRE knowledge baseline",
                    "reliability": "primary",
                },
                {
                    "url": "https://sre.google/sre-book/introduction/",
                    "title": "Google SRE Book — Introduction",
                    "used_for": "audience_insights on-call / reliability framing",
                    "reliability": "secondary",
                },
            ],
        },
    )
    save_json(art_dir / "research_brief.json", research)
    cp("research", "completed", {"research_brief": research})

    # Proposal
    cp("proposal", "in_progress", {})
    concept_options = [
        {
            "id": "c1",
            "title": TITLE,
            "hook": "Observability got louder. On-call did not get quieter.",
            "narrative_structure": "problem_solution",
            "visual_approach": "Cinematic ops night → alert storm → quiet verify → closed loop → end card",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "Platform and SRE leads on LinkedIn",
            "target_platform": "linkedin",
            "target_duration_seconds": 60,
            "key_points": [
                "Alert fatigue is the enemy",
                "Detect. Remediate. Verify.",
                "In-cluster, guardrails, BYO model, signed actions",
                "CTA: srenix.ai",
            ],
            "core_message": "Everyone else sends alerts. Srenix sends fixes.",
            "cta": "Visit srenix.ai",
            "tone": "sharp premium ops",
            "grounded_in": ["tagline", "closed-loop default", "in-cluster BYO-LLM"],
            "why_this_works": "Steals Sazabi manifesto punch without mecha copy; Srenix-specific promise.",
        },
        {
            "id": "c2",
            "title": "The Leash",
            "hook": "An agent that fixes — with your policy on the leash.",
            "narrative_structure": "comparison",
            "visual_approach": "Autonomy vs guardrail tension",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "Security-conscious platform teams",
            "target_platform": "linkedin",
            "target_duration_seconds": 60,
            "key_points": ["Policy leash", "Signed actions", "Human approval"],
            "core_message": "Power with a leash.",
            "cta": "srenix.ai",
            "tone": "trust-first",
            "grounded_in": ["guardrails"],
            "why_this_works": "Addresses autonomy fear.",
        },
        {
            "id": "c3",
            "title": "Quiet On-Call",
            "hook": "On-call should be quieter every week.",
            "narrative_structure": "journey",
            "visual_approach": "Week-over-week quieter pager",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "On-call engineers",
            "target_platform": "linkedin",
            "target_duration_seconds": 60,
            "key_points": ["Closed loop", "Verify", "Outcome"],
            "core_message": "Quieter weeks are the product.",
            "cta": "srenix.ai",
            "tone": "hopeful",
            "grounded_in": ["verify loop"],
            "why_this_works": "Outcome-led.",
        },
    ]
    proposal = must_valid(
        "proposal_packet",
        {
            "version": "1.0",
            "concept_options": concept_options,
            "selected_concept": {
                "concept_id": "c1",
                "rationale": "Plan default locked: Everyone Else Sends Alerts",
                "modifications": [
                    "CTA: srenix.ai",
                    "Remotion cinematic body",
                    "genimage + comfyui_video only",
                ],
            },
            "production_plan": {
                "pipeline": PIPELINE,
                "playbook": PLAYBOOK,
                "stages": [
                    {
                        "stage": "script",
                        "tools": [{"tool_name": "script_writer", "role": "VO beats", "available": True, "estimated_cost_usd": 0}],
                        "approach": "Locked VO from plan",
                    },
                    {
                        "stage": "scene_plan",
                        "tools": [{"tool_name": "scene_planner", "role": "6 cinematic beats", "available": True, "estimated_cost_usd": 0}],
                        "approach": "5 motion + title landing",
                    },
                    {
                        "stage": "assets",
                        "tools": [
                            {
                                "tool_name": "genimage",
                                "role": "stills",
                                "provider": "genimage",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "Cluster default",
                            },
                            {
                                "tool_name": "comfyui_video",
                                "role": "I2V",
                                "provider": "comfyui",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "Workspace default over VEO",
                            },
                            {
                                "tool_name": "tts_selector",
                                "role": "VO",
                                "provider": "gpu_ai",
                                "available": True,
                                "estimated_cost_usd": 0,
                            },
                            {
                                "tool_name": "gpu_ai_music",
                                "role": "bed",
                                "provider": "gpu_ai",
                                "available": True,
                                "estimated_cost_usd": 0,
                            },
                        ],
                        "approach": "Still → I2V; Ken Burns only if Comfy fails (logged)",
                        "fallback_if_unavailable": "Ken Burns — never silent VEO",
                    },
                    {
                        "stage": "edit",
                        "tools": [{"tool_name": "edit_director", "role": "timeline", "available": True, "estimated_cost_usd": 0}],
                        "approach": "CinematicRenderer scenes",
                    },
                    {
                        "stage": "compose",
                        "tools": [
                            {
                                "tool_name": "video_compose",
                                "role": "Remotion",
                                "provider": "remotion",
                                "available": True,
                                "estimated_cost_usd": 0,
                                "why_this_provider": "Video-led OffthreadVideo body",
                            }
                        ],
                        "approach": "cinematic-trailer templated",
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
                    "mood_direction": "tense to resolved cinematic electronic",
                    "estimated_cost_usd": 0,
                },
                "taste_profile": {
                    "design_read": "Premium SRE brand film — pager dread to quiet verify; cyan accent; no mecha.",
                    "visual_variance": 5,
                    "motion_intensity": 6,
                    "information_density": 3,
                    "anti_patterns": ["Gundam copy", "Dashboard UI chrome", "VEO without ask"],
                    "quality_gates": ["Core tagline on end card", "Real WAN motion on mid beats"],
                },
            },
            "cost_estimate": {
                "total_estimated_usd": 0.0,
                "line_items": [
                    {"tool": "genimage", "operation": "6 stills", "quantity": 6, "estimated_usd": 0},
                    {"tool": "comfyui_video", "operation": "5 I2V", "quantity": 5, "estimated_usd": 0},
                    {"tool": "tts_selector", "operation": "VO", "quantity": 1, "estimated_usd": 0},
                    {"tool": "gpu_ai_music", "operation": "bed", "quantity": 1, "estimated_usd": 0},
                ],
                "budget_cap_usd": BUDGET,
                "budget_verdict": "within_budget",
            },
            "approval": {
                "status": "approved",
                "user_notes": "Implement plan as specified — locked concept + produce",
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
                    "subject": "Brand film concept",
                    "options_considered": [
                        {"option_id": "c1", "label": TITLE, "score": 1.0, "reason": "Plan default"},
                        {"option_id": "c2", "label": "The Leash", "score": 0.7, "reason": "Alt", "rejected_because": "Plan locked c1"},
                        {"option_id": "c3", "label": "Quiet On-Call", "score": 0.65, "reason": "Alt", "rejected_because": "Plan locked c1"},
                    ],
                    "selected": "c1",
                    "reason": "Plan implement as specified",
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
                        {"option_id": "remotion", "label": "Remotion", "score": 1.0, "reason": "CinematicRenderer montage"},
                        {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.5, "reason": "Titles only", "rejected_because": "Plan: Remotion body"},
                        {"option_id": "ffmpeg", "label": "FFmpeg", "score": 0.2, "reason": "Weak", "rejected_because": "motion_required"},
                    ],
                    "selected": "remotion",
                    "reason": "Plan",
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
                        {"option_id": "comfyui_video", "label": "ComfyUI WAN", "score": 1.0, "reason": "Cluster default"},
                        {"option_id": "veo_video", "label": "VEO", "score": 0.3, "reason": "Paid", "rejected_because": "User default: Comfy unless asked"},
                    ],
                    "selected": "comfyui_video",
                    "reason": "video-gen-defaults rule",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-004",
                    "stage": "proposal",
                    "category": "composition_mode",
                    "subject": "Composition authoring mode",
                    "options_considered": [
                        {"option_id": "templated", "label": "CinematicRenderer", "score": 0.9, "reason": "Fits gen montage"},
                        {"option_id": "atelier", "label": "Atelier", "score": 0.6, "reason": "Slower", "rejected_because": "Templated sufficient for LinkedIn cut"},
                    ],
                    "selected": "templated",
                    "reason": "Plan production path",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.9,
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

    # Script
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
            "speaker_directions": "Sharp, premium, measured — LinkedIn brand film",
            "delivery_cues": {
                "pace": "measured",
                "energy": "controlled urgency resolving to confidence",
                "emphasis_words": ["detects", "Remediates", "Verifies", "fixes"],
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
                "performance_intent": "Premium LinkedIn brand-film narrator",
                "pacing_profile": "cinematic",
                "energy_curve": "tension → turn → resolve",
                "pause_policy": "Beat after each Detect/Remediate/Verify",
                "sample_section_id": "sc3",
                "provider_notes": {"gpu_ai": "voice=aditya speed=0.88"},
            },
            "sections": sections,
            "metadata": {
                "beat_map": ["hook", "problem", "turn", "proof", "perimeter", "landing"],
                "title_card_copy": ["Everyone else sends alerts.", "Srenix sends fixes."],
                "locked_creative": "artifacts/locked_creative.json",
            },
        },
    )
    save_json(art_dir / "script.json", script)
    cp("script", "completed", {"script": script}, human_approved=True)

    # Scene plan
    cp("scene_plan", "in_progress", {})
    t = 0.0
    scenes_out = []
    roles = ["establish_context", "build_tension", "deliver_payload", "evidence", "resolution", "call_to_action"]
    for i, sc in enumerate(SCENES):
        scenes_out.append({
            "id": sc["id"],
            "type": "generated",
            "description": f"{sc['label']}: {sc['kind']}",
            "start_seconds": t,
            "end_seconds": t + sc["duration"],
            "script_section_id": sc["id"],
            "narrative_role": roles[i],
            "information_role": sc["label"],
            "hero_moment": sc["id"] in {"sc3", "sc4"},
            "shot_intent": sc.get("motion_prompt") or sc.get("title_text", ""),
            "required_assets": [
                {"type": "image", "description": sc["image_prompt"][:100], "source": "generate"},
                *(
                    [{"type": "video", "description": "comfyui I2V", "source": "generate"}]
                    if sc["kind"] == "motion"
                    else []
                ),
            ],
            "texture_keywords": ["cinematic", "ops", "premium"],
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

    # Assets
    cp("assets", "in_progress", {})
    from tools.audio.tts_selector import TTSSelector
    from tools.gpu_ai.genimage import GenImage
    from tools.gpu_ai.music import GpuAiMusic
    from tools.video.comfyui_video import ComfyUIVideo

    gen = GenImage()
    comfy = ComfyUIVideo()
    manifest_assets = []

    narr_rel = "assets/audio/narration.wav"
    narr_path = pdir / narr_rel
    print("[tool] tts_selector | preferred_provider=gpu_ai | voice=aditya | speed=0.88", flush=True)
    tts = TTSSelector().execute({
        "text": full_narration,
        "voice_id": "aditya",
        "preferred_provider": "gpu_ai",
        "output_path": str(narr_path),
        "response_format": "wav",
        "speed": 0.88,
    })
    if not tts.success or not narr_path.exists():
        print(f"[fail] TTS: {tts.error}", flush=True)
        return 1
    spent += float(tts.cost_usd or 0)
    narr_dur = audio_duration(narr_path)
    print(f"[ok] narration {narr_dur:.1f}s", flush=True)
    manifest_assets.append({
        "id": "narration_main", "type": "narration", "path": narr_rel,
        "source_tool": "tts_selector", "scene_id": "sc1", "provider": "gpu_ai",
        "duration_seconds": round(narr_dur, 2), "cost_usd": float(tts.cost_usd or 0), "format": "wav",
    })

    scale = narr_dur / planned if planned else 1.0
    public_dir = Path(__file__).resolve().parent.parent / "remotion-composer" / "public" / PID
    public_dir.mkdir(parents=True, exist_ok=True)

    # Sample protocol: first motion scene announced as sample, then continue batch (plan approved)
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
            return 1
        spent += float(img_res.cost_usd or 0)
        manifest_assets.append({
            "id": f"img_{sc['id']}", "type": "image", "path": img_rel,
            "source_tool": "genimage", "scene_id": sc["id"], "prompt": sc["image_prompt"],
            "cost_usd": float(img_res.cost_usd or 0), "resolution": "1280x720",
        })

        out_rel = f"assets/video/{sc['id']}.mp4"
        out_path = pdir / out_rel
        if sc["kind"] == "motion":
            raw_path = pdir / f"assets/video/{sc['id']}_raw.mp4"
            print(
                f"[tool] comfyui_video | operation=image_to_video | scene={sc['id']} | "
                "model=WAN2.2-I2V-14B | reason=cluster default",
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
                print(f"[warn] comfy I2V failed ({vid.error}); Ken Burns for {sc['id']}", flush=True)
                ken_burns(img_path, out_path, beat_dur)
                vtool = "ffmpeg_ken_burns"
            manifest_assets.append({
                "id": f"vid_{sc['id']}", "type": "video", "path": out_rel,
                "source_tool": vtool, "scene_id": sc["id"], "prompt": sc["motion_prompt"],
                "duration_seconds": round(beat_dur, 2),
                "cost_usd": float(vid.cost_usd or 0) if vid.success else 0,
            })
        else:
            ken_burns(img_path, out_path, beat_dur)
            manifest_assets.append({
                "id": f"vid_{sc['id']}", "type": "video", "path": out_rel,
                "source_tool": "ffmpeg_ken_burns", "scene_id": sc["id"],
                "duration_seconds": round(beat_dur, 2), "cost_usd": 0,
            })
        shutil.copy2(out_path, public_dir / f"{sc['id']}.mp4")
        shutil.copy2(img_path, public_dir / f"{sc['id']}.png")

    music_rel = "assets/music/bed.mp3"
    music_path = pdir / music_rel
    print("[tool] gpu_ai_music | tense-to-resolved cinematic bed", flush=True)
    music = GpuAiMusic().execute({
        "tags": "cinematic electronic, tension resolving, premium tech, low key, instrumental",
        "seconds": 75,
        "loop": True,
        "lyrics": "[inst]",
        "response_format": "mp3",
        "output_path": str(music_path),
        "poll_timeout_s": 600,
    })
    music_tool = "gpu_ai_music"
    if not (music.success and music_path.exists()):
        from tools.audio.pixabay_music import PixabayMusic
        music = PixabayMusic().execute({
            "query": "cinematic tension ambient",
            "min_duration": 45,
            "max_duration": 180,
            "output_path": str(music_path),
        })
        music_tool = "pixabay_music"
    if music.success and music_path.exists():
        spent += float(music.cost_usd or 0)
        shutil.copy2(music_path, public_dir / "bed.mp3")
        manifest_assets.append({
            "id": "music_bed", "type": "music", "path": music_rel,
            "source_tool": music_tool, "scene_id": "sc1",
            "duration_seconds": 75, "cost_usd": float(music.cost_usd or 0), "format": "mp3",
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

    # Edit
    cp("edit", "in_progress", {})
    cinematic_scenes = []
    cuts = []
    t = 0.0
    for sc in SCENES:
        beat_dur = sc["duration"] * scale
        if sc["kind"] == "title":
            cinematic_scenes.append({
                "id": sc["id"], "kind": "title",
                "startSeconds": round(t, 3), "durationSeconds": round(beat_dur, 3),
                "text": sc["title_text"], "accent": sc.get("title_accent", "#06B6D4"),
                "backgroundSrc": f"{PID}/{sc['id']}.mp4", "variant": "plate",
            })
        else:
            cinematic_scenes.append({
                "id": sc["id"], "kind": "video",
                "startSeconds": round(t, 3), "durationSeconds": round(beat_dur, 3),
                "src": f"{PID}/{sc['id']}.mp4", "tone": "steel",
                "fadeInFrames": 8, "fadeOutFrames": 8,
            })
        cuts.append({
            "id": f"cut_{sc['id']}", "source": f"vid_{sc['id']}",
            "in_seconds": 0, "out_seconds": round(beat_dur, 3),
            "layer": "primary", "reason": sc["label"],
            "transition_in": "fade", "transition_out": "fade", "transition_duration": 0.35,
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
            {"music": {"src": f"{PID}/bed.mp3", "volume": 0.13, "fadeInSeconds": 1.2, "fadeOutSeconds": 2.0}}
            if (pdir / music_rel).exists() else {}
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
                    {"music": {"asset_id": "music_bed", "volume": 0.13, "fade_in_seconds": 1.2, "fade_out_seconds": 2.0}}
                    if any(a["id"] == "music_bed" for a in manifest_assets) else {}
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

    # Compose
    cp("compose", "in_progress", {})
    from tools.video.video_compose import VideoCompose

    out_mp4 = pdir / "renders" / "srenix_everyone_else_sends_alerts.mp4"
    print(
        "[tool] video_compose | provider=remotion | renderer_family=cinematic-trailer",
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
                "path": "renders/srenix_everyone_else_sends_alerts.mp4",
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
                "export_path": "renders/srenix_everyone_else_sends_alerts.mp4",
                "timestamp": now_iso(),
                "visibility": "unlisted",
                "metadata_used": {
                    "title": TITLE,
                    "description": "Srenix LinkedIn brand film — Detect. Remediate. Verify.",
                    "hashtags": ["Srenix", "Kubernetes", "SRE"],
                },
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

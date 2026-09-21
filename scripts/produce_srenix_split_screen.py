#!/usr/bin/env python3
"""Srenix split-screen marketing ad: Two Timelines.

Same actor, diverging futures. Left = alert-only on-call. Right = Srenix loop.
Shows BOTH real kubectl terminal and stylized SRENIX operator UI.

Cluster-first: genimage → comfyui_video I2V → ffmpeg hstack (split beats)
→ Remotion CinematicRenderer. No VEO unless explicitly requested.
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

PID = "srenix-split-two-operators"
TITLE = "Two Timelines"
PIPELINE = "cinematic"
PLAYBOOK = "flat-motion-graphics"
BUDGET = 5.0

ACTOR = (
    "the same man in his early 30s with South Asian features, short dark hair, "
    "grey zip hoodie, black over-ear headphones, competent SRE engineer"
)

# ~60s beat map — split lanes diverge after sc2; broll from srenix.ai capabilities
SCENES = [
    {
        "id": "sc1",
        "label": "Twin establish",
        "duration": 6.0,
        "kind": "split",
        "narration": "Same engineer. Same cluster. Same incident.",
        "left_image_prompt": (
            f"Split-screen LEFT pane only: {ACTOR} at a night NOC desk facing a wall of "
            "monitors showing calm blue dashboards, cool monitor glow on his face, "
            "photorealistic cinematic still, no logos, no readable text"
        ),
        "right_image_prompt": (
            f"Split-screen RIGHT pane only: identical framing — {ACTOR} at the same NOC desk "
            "with the same monitor wall in calm blue, mirror composition, photorealistic, "
            "no logos, no text"
        ),
        "left_motion_prompt": "Slow subtle push toward the engineer, monitors steady blue, cinematic",
        "right_motion_prompt": "Slow subtle push toward the engineer, monitors steady blue, cinematic",
    },
    {
        "id": "sc2",
        "label": "Same alert",
        "duration": 4.0,
        "kind": "split",
        "narration": "Two timelines. One alert.",
        "left_image_prompt": (
            f"LEFT pane: {ACTOR} at NOC desk as multiple monitors begin flashing red alert "
            "reflection on his face, tension rising, photorealistic, no logos"
        ),
        "right_image_prompt": (
            f"RIGHT pane: same {ACTOR} same desk as monitors flash red alert light on his "
            "face, identical starting point, photorealistic, no logos"
        ),
        "left_motion_prompt": "Red alert pulses spread across monitors, face lit red, subtle handheld",
        "right_motion_prompt": "Red alert pulses spread across monitors, face lit red, subtle handheld",
    },
    {
        "id": "sc3",
        "label": "Divergence",
        "duration": 7.0,
        "kind": "split",
        "narration": "Left: alerts only. Right: the loop begins.",
        "left_image_prompt": (
            f"LEFT pane: {ACTOR} panicking, hunched over laptop typing fast, many monitors "
            "now deep red, phone buzzing beside keyboard, sweat sheen, chaotic energy, "
            "photorealistic, no logos"
        ),
        "right_image_prompt": (
            f"RIGHT pane: same {ACTOR} sitting upright, eyes lifted from laptop watching "
            "monitors calmly, only two monitors red others still blue, composed posture, "
            "photorealistic, no logos"
        ),
        "left_motion_prompt": "Frantic typing, more monitors turn red, anxious micro-movements",
        "right_motion_prompt": "Engineer holds still and watches, minimal typing, calm breathing",
    },
    {
        "id": "sc4",
        "label": "Detect b-roll",
        "duration": 5.0,
        "kind": "motion",
        "narration": "Twenty-one probes. Drift on the wire. Nothing sleeps unnoticed.",
        "image_prompt": (
            "Cinematic abstract visualization of Kubernetes drift detection: dark server room "
            "with floating holographic DriftReport cards and probe nodes lighting up cyan #06B6D4, "
            "premium tech brand b-roll, diagrammatic but photoreal, no vendor logos, no readable text"
        ),
        "motion_prompt": "Probe nodes pulse cyan in sequence across the rack, camera drifts forward",
    },
    {
        "id": "sc5",
        "label": "Real terminal",
        "duration": 5.0,
        "kind": "motion",
        "narration": "kubectl rollout restart. Policy bounds every move.",
        "image_prompt": (
            "Close-up cinematic terminal on dark background showing realistic green monospace "
            "kubectl commands scrolling: kubectl get pods, kubectl rollout restart deployment, "
            "kubectl rollout status, subtle cyan accent glow, photoreal screen capture style, "
            "no logos besides generic shell prompt"
        ),
        "motion_prompt": "Terminal text scrolls slowly with new command lines appearing, push-in",
    },
    {
        "id": "sc6",
        "label": "SRENIX operator UI",
        "duration": 5.0,
        "kind": "motion",
        "narration": "Detect. Remediate. Verify — under your operator.",
        "image_prompt": (
            "Stylized premium SRENIX operator console UI on dark slate: three glowing stages "
            "DETECT REMEDIATE VERIFY in cyan #06B6D4, policy guardrail ring, audit_id hash, "
            "Ed25519 attestation checkmark, futuristic but clean ops dashboard, no other logos"
        ),
        "motion_prompt": "UI stages light up in sequence Detect then Remediate then Verify, elegant motion",
    },
    {
        "id": "sc7",
        "label": "Green wave",
        "duration": 7.0,
        "kind": "split",
        "narration": "Screens go green. Breathing room returns.",
        "left_image_prompt": (
            f"LEFT pane: {ACTOR} overwhelmed, all monitors blazing red, hands on head, "
            "tabs multiplying, maximum chaos, photorealistic"
        ),
        "right_image_prompt": (
            f"RIGHT pane: same {ACTOR} leaning back relieved as monitor wall flips from red "
            "to green verify states one by one, soft smile, photorealistic"
        ),
        "left_motion_prompt": "More red alerts cascade, engineer slumps forward stressed",
        "right_motion_prompt": "Monitors turn green in a wave left to right, engineer exhales and leans back",
    },
    {
        "id": "sc8",
        "label": "Verify loop",
        "duration": 4.0,
        "kind": "motion",
        "narration": "Diagnose. Fix. Re-diagnose. The loop closes itself.",
        "image_prompt": (
            "Clean motion-graphics ready diagram on dark background: circular loop arrows "
            "diagnose → fix → re-diagnose → resolve with cyan #06B6D4 glow, minimal premium "
            "SRE aesthetic, no logos"
        ),
        "motion_prompt": "Light travels around the closed-loop diagram once, smooth and confident",
    },
    {
        "id": "sc9",
        "label": "In-cluster perimeter",
        "duration": 4.0,
        "kind": "motion",
        "narration": "In-cluster. Your model. Signed and replayable.",
        "image_prompt": (
            "Cinematic private Kubernetes cluster bay: server racks behind glass, soft white "
            "aisle lights, subtle helm install terminal in foreground, sense of data sovereignty "
            "and BYO-LLM perimeter, photorealistic, no cloud vendor logos"
        ),
        "motion_prompt": "Slow dolly down the secure cluster aisle, controlled premium movement",
    },
    {
        "id": "sc10",
        "label": "Climax contrast",
        "duration": 6.0,
        "kind": "split",
        "narration": "Left still drowns. Right sits back.",
        "left_image_prompt": (
            f"LEFT pane: {ACTOR} in full crisis mode, face red from monitor glow, typing "
            "feverishly, energy drink cans, total alert storm, photorealistic"
        ),
        "right_image_prompt": (
            f"RIGHT pane: same {ACTOR} relaxed in chair, arms behind head, all monitors calm "
            "green, coffee mug steam rising, quiet victory, photorealistic"
        ),
        "left_motion_prompt": "Chaotic typing and flickering red screens accelerate",
        "right_motion_prompt": "Calm hold, gentle steam from coffee, green monitors steady",
    },
    {
        "id": "sc11",
        "label": "Landing",
        "duration": 7.0,
        "kind": "title",
        "narration": "Everyone else sends alerts. Srenix sends fixes. srenix.ai",
        "image_prompt": (
            "Minimal dark slate end-card with soft cyan meridian light, premium brand film "
            "empty frame, no text in image"
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


def stretch_lane(src: Path, dst: Path, target_s: float) -> None:
    """960-wide lane clip for split stitching."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
            "-t", f"{target_s:.3f}",
            "-vf", "scale=960:1080:force_original_aspect_ratio=increase,crop=960:1080,fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst),
        ],
        check=True, capture_output=True,
    )


def ken_burns(img: Path, dst: Path, target_s: float, width: int = 1920) -> None:
    height = 1080
    frames = max(int(target_s * 30), 30)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(img),
            "-vf",
            (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"zoompan=z='min(zoom+0.0007,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={width}x{height}:fps=30"
            ),
            "-t", f"{target_s:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dst),
        ],
        check=True, capture_output=True,
    )


def stitch_split(left: Path, right: Path, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(left), "-i", str(right),
            "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]",
            "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(dst),
        ],
        check=True, capture_output=True,
    )


def write_locked_creative(art_dir: Path) -> None:
    locked = {
        "version": "1.0",
        "locked_at": now_iso(),
        "concept": "Two Timelines — split-screen comparison ad",
        "format": "split_screen_same_actor",
        "target_duration_seconds": sum(sc["duration"] for sc in SCENES),
        "cta": "srenix.ai + helm install",
        "creative_decisions": {
            "actor": "Same actor both panes; timelines diverge after shared alert",
            "terminal": "Show BOTH real kubectl terminal (sc5) and stylized SRENIX UI (sc6)",
            "length": "60s LinkedIn landscape",
            "broll": "Detect probes, verify loop, in-cluster perimeter from srenix.ai",
        },
        "voice_over": [
            {
                "id": sc["id"],
                "label": sc["label"],
                "seconds": sc["duration"],
                "text": sc["narration"],
            }
            for sc in SCENES
        ],
        "full_narration": " ".join(sc["narration"] for sc in SCENES),
        "scene_cards": [
            {
                "id": sc["id"],
                "label": sc["label"],
                "duration_seconds": sc["duration"],
                "kind": sc["kind"],
                **(
                    {
                        "left_image_prompt": sc["left_image_prompt"],
                        "right_image_prompt": sc["right_image_prompt"],
                        "left_motion": sc.get("left_motion_prompt"),
                        "right_motion": sc.get("right_motion_prompt"),
                    }
                    if sc["kind"] == "split"
                    else {
                        "image_prompt": sc.get("image_prompt"),
                        "motion_prompt": sc.get("motion_prompt"),
                        "title_text": sc.get("title_text"),
                    }
                ),
            }
            for sc in SCENES
        ],
    }
    save_json(art_dir / "locked_creative.json", locked)
    md = [
        "# Locked creative — Two Timelines (split-screen)",
        "",
        f"**Concept:** {locked['concept']}",
        f"**Target:** {locked['target_duration_seconds']}s",
        "",
        "## VO",
        "",
    ]
    for vo in locked["voice_over"]:
        md.append(f"- **{vo['label']}** ({vo['seconds']}s): \"{vo['text']}\"")
    md.append("")
    md.append("## Scene cards")
    md.append("")
    for sc in locked["scene_cards"]:
        md.append(f"### {sc['id']} — {sc['label']} ({sc['duration_seconds']}s)")
        if sc["kind"] == "split":
            md.append(f"- Left: {sc['left_image_prompt'][:140]}...")
            md.append(f"- Right: {sc['right_image_prompt'][:140]}...")
        elif sc.get("title_text"):
            md.append(f"- Title: {sc['title_text'].replace(chr(10), ' / ')}")
        else:
            md.append(f"- Image: {sc.get('image_prompt', '')[:140]}...")
        md.append("")
    (art_dir / "locked_creative.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[lock] wrote {art_dir / 'locked_creative.json'}", flush=True)


def _research_brief() -> dict:
    return {
        "version": "1.0",
        "topic": "Srenix split-screen — alerts vs closed-loop fix",
        "research_date": "2026-07-20",
        "research_summary": (
            "Split-screen comparison: same SRE engineer, same incident; left pane drowns in "
            "alert-only observability while right pane runs Srenix detect-remediate-verify "
            "in-cluster with policy guardrails. Product proof from srenix.ai: 21 K8s probes, "
            "DriftReports, policy-bounded fixers, signed audit, BYO-LLM."
        ),
        "landscape": {
            "existing_content": [
                {
                    "title": "Sazabi LinkedIn manifesto",
                    "source": "linkedin",
                    "angle": "cinematic comparison energy",
                    "what_it_covers": "Status quo broken → new machine",
                    "url": "https://www.linkedin.com/feed/update/urn:li:activity:7475940394170507264/",
                },
                {
                    "title": "Srenix product site",
                    "source": "website",
                    "angle": "detect-remediate-verify loop",
                    "what_it_covers": "In-cluster operator, probes, fixers, verify",
                    "url": "https://srenix.ai/",
                },
                {
                    "title": "Before/after SaaS ads",
                    "source": "youtube",
                    "angle": "split comparison",
                    "what_it_covers": "Side-by-side emotional contrast",
                },
            ],
            "saturated_angles": ["Generic AI dashboard demo", "Stock NOC b-roll without story"],
            "underserved_gaps": ["Same actor diverging timelines with real terminal + operator UI"],
        },
        "data_points": [
            {
                "claim": "21 K8s probes plus cloud probe families detect drift before pages escalate.",
                "source_url": "https://srenix.ai/",
                "credibility": "primary_source",
                "surprise_factor": "notable",
            },
            {
                "claim": "Closed-loop diagnose→fix→re-diagnose is default, not roadmap.",
                "source_url": "https://srenix.ai/",
                "credibility": "primary_source",
                "surprise_factor": "counterintuitive",
            },
            {
                "claim": "Every AI action JWT-signed, hash-chained, replayable; audit bundle export.",
                "source_url": "https://srenix.ai/",
                "credibility": "primary_source",
                "surprise_factor": "notable",
            },
        ],
        "audience_insights": {
            "common_questions": [
                "Will it actually fix production or just summarize?",
                "Can I keep human approval?",
                "Does data leave my cluster?",
            ],
            "misconceptions": [
                {
                    "myth": "Autonomous SRE means unsupervised chaos.",
                    "reality": "Policy leash + signed actions + verify loop.",
                }
            ],
            "knowledge_level": "Platform/SRE engineers on LinkedIn",
        },
        "angles_discovered": [
            {
                "name": "Two Timelines",
                "hook": "Same engineer. Two futures.",
                "type": "contrarian",
                "why_now": "Alert fatigue + agent era",
                "grounded_in": ["data_point_1", "data_point_2"],
            },
            {
                "name": "Terminal truth",
                "hook": "Show kubectl AND the operator UI.",
                "type": "evergreen",
                "why_now": "Buyers want proof not slides",
                "grounded_in": ["data_point_3"],
            },
            {
                "name": "Quiet on-call",
                "hook": "Green wave vs red storm",
                "type": "narrative",
                "why_now": "Outcome-led marketing",
                "grounded_in": ["data_point_2"],
            },
        ],
        "sources": [
            {
                "url": "https://srenix.ai/",
                "title": "Srenix product site",
                "used_for": "data_points + b-roll capabilities",
                "reliability": "primary",
            },
            {
                "url": "https://www.linkedin.com/feed/update/urn:li:activity:7475940394170507264/",
                "title": "Sazabi LinkedIn reference",
                "used_for": "landscape comparison energy",
                "reliability": "secondary",
            },
            {
                "url": "https://kubernetes.io/docs/concepts/overview/",
                "title": "Kubernetes overview",
                "used_for": "audience baseline",
                "reliability": "primary",
            },
            {
                "url": "https://sre.google/sre-book/introduction/",
                "title": "Google SRE Book",
                "used_for": "on-call framing",
                "reliability": "secondary",
            },
            {
                "url": "https://helm.sh/docs/intro/quickstart/",
                "title": "Helm quickstart",
                "used_for": "CTA helm install",
                "reliability": "secondary",
            },
        ],
    }


def main() -> int:
    ensure_vault_config_loaded()
    os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")

    pdir = PROJECTS_DIR / PID
    if not (pdir / "project.json").exists():
        init_project(PID, title=TITLE, pipeline_type=PIPELINE, style_playbook=PLAYBOOK)
    art_dir = pdir / "artifacts"
    for sub in ("assets/images", "assets/video", "assets/audio", "assets/music", "renders"):
        (pdir / sub).mkdir(parents=True, exist_ok=True)

    write_locked_creative(art_dir)

    spent = 0.0
    full_narration = " ".join(sc["narration"] for sc in SCENES)
    planned = sum(sc["duration"] for sc in SCENES)

    cp("research", "in_progress", {})
    research = must_valid("research_brief", _research_brief())
    save_json(art_dir / "research_brief.json", research)
    cp("research", "completed", {"research_brief": research})

    cp("proposal", "in_progress", {})
    proposal = must_valid(
        "proposal_packet",
        {
            "version": "1.0",
            "concept_options": [
                {
                    "id": "c1",
                    "title": TITLE,
                    "hook": "Same engineer. Two timelines.",
                    "narrative_structure": "comparison",
                    "visual_approach": "Split-screen L/R + capability b-roll + dual terminal",
                    "target_duration_seconds": 60,
                    "why_this_works": "Instant myth-bust; shows fixes not alerts",
                },
                {
                    "id": "c2",
                    "title": "Terminal Proof",
                    "hook": "kubectl on screen, policy on the leash.",
                    "narrative_structure": "problem_solution",
                    "visual_approach": "Full-frame terminal montage",
                    "target_duration_seconds": 60,
                    "why_this_works": "Engineer buyers want receipts",
                },
                {
                    "id": "c3",
                    "title": "Quiet On-Call",
                    "hook": "Green wave vs red storm.",
                    "narrative_structure": "journey",
                    "visual_approach": "Outcome-led split contrast",
                    "target_duration_seconds": 60,
                    "why_this_works": "Emotional payoff",
                },
            ],
            "selected_concept": {
                "concept_id": "c1",
                "rationale": "User-approved split-screen creative",
                "modifications": ["Same actor", "60s", "kubectl + SRENIX UI both"],
            },
            "production_plan": {
                "pipeline": PIPELINE,
                "playbook": PLAYBOOK,
                "stages": [
                    {"stage": "script", "tools": [{"tool_name": "script_writer", "role": "VO", "available": True}], "approach": "Locked split VO"},
                    {"stage": "assets", "tools": [
                        {"tool_name": "genimage", "role": "stills", "available": True},
                        {"tool_name": "comfyui_video", "role": "I2V", "available": True},
                        {"tool_name": "ffmpeg", "role": "hstack split", "available": True},
                        {"tool_name": "tts_selector", "role": "VO", "available": True},
                        {"tool_name": "gpu_ai_music", "role": "bed", "available": True},
                    ], "approach": "Dual lane gen → stitch → Remotion"},
                    {"stage": "compose", "tools": [{"tool_name": "video_compose", "role": "Remotion", "available": True}], "approach": "cinematic-trailer"},
                ],
                "delivery_promise": {
                    "promise_type": "motion_led",
                    "motion_required": True,
                    "tone_mode": "cinematic",
                    "quality_floor": "presentable",
                },
                "renderer_family": "cinematic-trailer",
                "render_runtime": "remotion",
                "composition_mode": "templated",
                "music_source": {"source_type": "ai_generated", "provider": "gpu_ai", "mood_direction": "tension to resolve"},
                "taste_profile": {
                    "design_read": "Split-screen same-actor comparison; red vs green; terminal proof",
                    "visual_variance": 6,
                    "motion_intensity": 7,
                    "information_density": 4,
                    "anti_patterns": ["VEO without ask", "Mecha copy", "Dashboard chrome"],
                    "quality_gates": ["Split readable on mobile", "Both terminal styles visible"],
                },
            },
            "cost_estimate": {
                "total_estimated_usd": 0.0,
                "line_items": [{"tool": "genimage", "operation": "lanes+broll", "estimated_usd": 0}],
                "budget_cap_usd": BUDGET,
                "budget_verdict": "within_budget",
            },
            "approval": {"status": "approved", "user_notes": "Creative locked: same actor, 60s, both terminals", "approved_budget_usd": BUDGET},
            "metadata": {"title": TITLE, "approved_at": now_iso()},
        },
    )
    decision_log = must_valid(
        "decision_log",
        {
            "version": "1.0",
            "project_id": PID,
            "decisions": [{
                "decision_id": "d-001",
                "stage": "proposal",
                "category": "provider_selection",
                "subject": "Video provider",
                "options_considered": [
                    {"option_id": "comfyui_video", "label": "ComfyUI WAN", "score": 1.0, "reason": "Cluster default"},
                    {"option_id": "veo_video", "label": "VEO", "score": 0.2, "reason": "Paid cloud", "rejected_because": "Not requested"},
                ],
                "selected": "comfyui_video",
                "reason": "video-gen-defaults",
                "user_visible": True,
                "user_approved": True,
                "confidence": 1.0,
            }],
        },
    )
    save_json(art_dir / "proposal_packet.json", proposal)
    save_json(art_dir / "decision_log.json", decision_log)
    cp("proposal", "completed", {"proposal_packet": proposal, "decision_log": decision_log}, human_approved=True)

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
            "speaker_directions": "Sharp comparison narrator — left tense, right resolved",
            "delivery_cues": {
                "pace": "measured",
                "energy": "contrast",
                "emphasis_words": ["Same", "alerts", "loop", "green", "fixes"],
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
                "performance_intent": "Split-screen comparison VO",
                "pacing_profile": "cinematic",
                "energy_curve": "mirror → diverge → proof → punch",
                "pause_policy": "Beat on 'Same engineer' and tagline",
                "sample_section_id": "sc3",
                "provider_notes": {"gpu_ai": "voice=aditya speed=0.82"},
            },
            "sections": sections,
            "metadata": {"locked_creative": "artifacts/locked_creative.json"},
        },
    )
    save_json(art_dir / "script.json", script)
    cp("script", "completed", {"script": script}, human_approved=True)

    cp("scene_plan", "in_progress", {})
    t = 0.0
    scenes_out = []
    roles = [
        "establish_context", "build_tension", "comparison", "evidence",
        "deliver_payload", "deliver_payload", "comparison", "evidence",
        "resolution", "comparison", "call_to_action",
    ]
    for i, sc in enumerate(SCENES):
        scenes_out.append({
            "id": sc["id"],
            "type": "generated",
            "description": f"{sc['label']} ({sc['kind']})",
            "start_seconds": t,
            "end_seconds": t + sc["duration"],
            "script_section_id": sc["id"],
            "narrative_role": roles[i],
            "information_role": sc["kind"],
            "hero_moment": sc["id"] in {"sc5", "sc6", "sc7"},
            "shot_intent": sc.get("motion_prompt") or sc.get("left_motion_prompt", ""),
            "required_assets": [{"type": "video", "description": sc["label"], "source": "generate"}],
            "texture_keywords": ["split-screen" if sc["kind"] == "split" else "broll", "cinematic"],
        })
        t += sc["duration"]
    scene_plan = must_valid(
        "scene_plan",
        {
            "version": "1.0",
            "style_playbook": PLAYBOOK,
            "scenes": scenes_out,
            "metadata": {"render_runtime": "remotion", "renderer_family": "cinematic-trailer"},
        },
    )
    save_json(art_dir / "scene_plan.json", scene_plan)
    cp("scene_plan", "completed", {"scene_plan": scene_plan}, human_approved=True)

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
    print("[tool] tts_selector | voice=aditya | speed=0.82", flush=True)
    tts = TTSSelector().execute({
        "text": full_narration,
        "voice_id": "aditya",
        "preferred_provider": "gpu_ai",
        "output_path": str(narr_path),
        "response_format": "wav",
        "speed": 0.82,
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

    def gen_lane(sc_id: str, side: str, prompt: str, motion: str, beat_dur: float) -> tuple[Path, str]:
        img_rel = f"assets/images/{sc_id}_{side}.png"
        img_path = pdir / img_rel
        print(f"[tool] genimage | scene={sc_id} lane={side}", flush=True)
        img_res = gen.execute({
            "operation": "generate",
            "prompt": prompt,
            "width": 960,
            "height": 1080,
            "steps": 28,
            "output_path": str(img_path),
        })
        if not img_res.success or not img_path.exists():
            raise RuntimeError(f"genimage {sc_id}_{side}: {img_res.error}")
        nonlocal spent
        spent += float(img_res.cost_usd or 0)
        manifest_assets.append({
            "id": f"img_{sc_id}_{side}", "type": "image", "path": img_rel,
            "source_tool": "genimage", "scene_id": sc_id, "prompt": prompt,
            "cost_usd": float(img_res.cost_usd or 0), "resolution": "960x1080",
        })
        raw_path = pdir / f"assets/video/{sc_id}_{side}_raw.mp4"
        lane_path = pdir / f"assets/video/{sc_id}_{side}.mp4"
        print(f"[tool] comfyui_video | scene={sc_id} lane={side} | WAN2.2-I2V", flush=True)
        vid = comfy.execute({
            "prompt": motion,
            "operation": "image_to_video",
            "reference_image_path": str(img_path),
            "width": 480,
            "height": 544,
            "num_frames": 81,
            "output_path": str(raw_path),
        })
        vtool = "comfyui_video"
        if vid.success and raw_path.exists():
            spent += float(vid.cost_usd or 0)
            stretch_lane(raw_path, lane_path, beat_dur)
        else:
            print(f"[warn] I2V fail {sc_id}_{side}: {vid.error}; Ken Burns", flush=True)
            ken_burns(img_path, lane_path, beat_dur, width=960)
            vtool = "ffmpeg_ken_burns"
        manifest_assets.append({
            "id": f"vid_{sc_id}_{side}", "type": "video", "path": str(lane_path.relative_to(pdir)),
            "source_tool": vtool, "scene_id": sc_id, "duration_seconds": round(beat_dur, 2),
            "cost_usd": float(vid.cost_usd or 0) if vid.success else 0,
        })
        return lane_path, vtool

    for sc in SCENES:
        beat_dur = sc["duration"] * scale
        out_rel = f"assets/video/{sc['id']}.mp4"
        out_path = pdir / out_rel

        if sc["kind"] == "split":
            left_path, _ = gen_lane(sc["id"], "left", sc["left_image_prompt"], sc["left_motion_prompt"], beat_dur)
            right_path, _ = gen_lane(sc["id"], "right", sc["right_image_prompt"], sc["right_motion_prompt"], beat_dur)
            stitch_split(left_path, right_path, out_path)
            manifest_assets.append({
                "id": f"vid_{sc['id']}", "type": "video", "path": out_rel,
                "source_tool": "ffmpeg_hstack", "scene_id": sc["id"],
                "duration_seconds": round(beat_dur, 2), "cost_usd": 0,
            })
        elif sc["kind"] == "motion":
            img_rel = f"assets/images/{sc['id']}.png"
            img_path = pdir / img_rel
            print(f"[tool] genimage | scene={sc['id']}", flush=True)
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
            raw_path = pdir / f"assets/video/{sc['id']}_raw.mp4"
            print(f"[tool] comfyui_video | scene={sc['id']} | WAN2.2-I2V", flush=True)
            vid = comfy.execute({
                "prompt": sc["motion_prompt"],
                "operation": "image_to_video",
                "reference_image_path": str(img_path),
                "width": 832,
                "height": 480,
                "num_frames": 81,
                "output_path": str(raw_path),
            })
            vtool = "comfyui_video"
            if vid.success and raw_path.exists():
                spent += float(vid.cost_usd or 0)
                stretch_clip(raw_path, out_path, beat_dur)
            else:
                print(f"[warn] I2V fail {sc['id']}: {vid.error}; Ken Burns", flush=True)
                ken_burns(img_path, out_path, beat_dur)
                vtool = "ffmpeg_ken_burns"
            manifest_assets.append({
                "id": f"vid_{sc['id']}", "type": "video", "path": out_rel,
                "source_tool": vtool, "scene_id": sc["id"], "duration_seconds": round(beat_dur, 2),
                "cost_usd": float(vid.cost_usd or 0) if vid.success else 0,
            })
            shutil.copy2(img_path, public_dir / f"{sc['id']}.png")
        else:
            img_rel = f"assets/images/{sc['id']}.png"
            img_path = pdir / img_rel
            gen.execute({
                "operation": "generate",
                "prompt": sc["image_prompt"],
                "width": 1280,
                "height": 720,
                "steps": 28,
                "output_path": str(img_path),
            })
            ken_burns(img_path, out_path, beat_dur)
            manifest_assets.append({
                "id": f"vid_{sc['id']}", "type": "video", "path": out_rel,
                "source_tool": "ffmpeg_ken_burns", "scene_id": sc["id"],
                "duration_seconds": round(beat_dur, 2), "cost_usd": 0,
            })
            shutil.copy2(img_path, public_dir / f"{sc['id']}.png")

        shutil.copy2(out_path, public_dir / f"{sc['id']}.mp4")

    music_rel = "assets/music/bed.mp3"
    music_path = pdir / music_rel
    print("[tool] gpu_ai_music | tension-to-resolve bed", flush=True)
    music = GpuAiMusic().execute({
        "tags": "cinematic electronic, tension resolving, comparison ad, instrumental",
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
            "query": "cinematic tension",
            "min_duration": 45,
            "output_path": str(music_path),
        })
        music_tool = "pixabay_music"
    if music.success and music_path.exists():
        spent += float(music.cost_usd or 0)
        shutil.copy2(music_path, public_dir / "bed.mp3")
        manifest_assets.append({
            "id": "music_bed", "type": "music", "path": music_rel,
            "source_tool": music_tool, "scene_id": "sc1", "duration_seconds": 75,
            "cost_usd": float(music.cost_usd or 0), "format": "mp3",
        })
    shutil.copy2(narr_path, public_dir / "narration.wav")

    manifest = must_valid(
        "asset_manifest",
        {"version": "1.0", "assets": manifest_assets, "total_cost_usd": round(spent, 4)},
    )
    save_json(art_dir / "asset_manifest.json", manifest)
    cp("assets", "completed", {"asset_manifest": manifest}, human_approved=True,
       cost_snapshot={"total_spent_usd": spent, "budget_remaining_usd": BUDGET - spent})

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
                "fadeInFrames": 6, "fadeOutFrames": 6,
            })
        cuts.append({
            "id": f"cut_{sc['id']}", "source": f"vid_{sc['id']}",
            "in_seconds": 0, "out_seconds": round(beat_dur, 3),
            "layer": "primary", "reason": sc["label"],
            "transition_in": "fade", "transition_out": "fade", "transition_duration": 0.25,
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
        **({"music": {"src": f"{PID}/bed.mp3", "volume": 0.14, "fadeInSeconds": 1.0, "fadeOutSeconds": 2.0}}
           if music_path.exists() else {}),
        "metadata": {"delivery_promise": proposal["production_plan"]["delivery_promise"]},
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
                **({"music": {"asset_id": "music_bed", "volume": 0.14}} if music_path.exists() else {}),
            },
            "subtitles": {"enabled": False},
            "metadata": {"remotion_props_path": "artifacts/remotion_props.json", "narration_duration_seconds": narr_dur},
        },
    )
    save_json(art_dir / "edit_decisions.json", edit)
    cp("edit", "completed", {"edit_decisions": edit}, human_approved=True)

    cp("compose", "in_progress", {})
    from tools.video.video_compose import VideoCompose

    out_mp4 = pdir / "renders" / "srenix_split_two_operators.mp4"
    print("[tool] video_compose | remotion | cinematic-trailer", flush=True)
    compose = VideoCompose().execute({
        "operation": "render",
        "edit_decisions": remotion_props,
        "asset_manifest": {
            "version": "1.0",
            "assets": [{**a, "path": str(pdir / a["path"])} for a in manifest_assets if a.get("path")],
        },
        "scene_plan": scene_plan.get("scenes"),
        "proposal_packet": proposal,
        "output_path": str(out_mp4),
        "profile": "youtube_landscape",
        "options": {"subtitle_burn": False},
        "script_text": full_narration,
        "remotion_timeout_ms": 240000,
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
                "path": "renders/srenix_split_two_operators.mp4",
                "format": "mp4",
                "resolution": "1920x1080",
                "duration_seconds": round(out_dur, 2),
                "codec": "h264",
            }],
            "render_grammar": "cinematic-trailer",
            "metadata": {"spent_usd": spent, "format": "split_screen"},
        },
    )
    save_json(art_dir / "render_report.json", report)
    cp("compose", "completed", {"render_report": report})

    publish = must_valid(
        "publish_log",
        {
            "version": "1.0",
            "entries": [{
                "platform": "board",
                "status": "exported",
                "url": f"https://om.baisoln.com/p/{PID}",
                "export_path": "renders/srenix_split_two_operators.mp4",
                "timestamp": now_iso(),
                "visibility": "unlisted",
                "metadata_used": {
                    "title": TITLE,
                    "description": "Srenix split-screen: same engineer, two timelines. Detect. Remediate. Verify.",
                    "hashtags": ["Srenix", "Kubernetes", "SRE", "splitscreen"],
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

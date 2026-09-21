#!/usr/bin/env python3
"""Produce 'The Map That Humiliates Starbucks' via animated-explainer + Remotion.

Continues the existing coffee-world-consumption project (research already done).
Approved: Concept 1, Remotion, flat-motion-graphics, ~90s YouTube, voice aditya/gpu_ai.
"""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.checkpoint import PROJECTS_DIR, write_checkpoint
from lib.vault_config import ensure_vault_config_loaded
from schemas.artifacts import validate_artifact

PID = "coffee-world-consumption"
TITLE = "The Map That Humiliates Starbucks"
PIPELINE = "animated-explainer"
PLAYBOOK = "flat-motion-graphics"
BUDGET = 3.0
TARGET_DURATION = 90.0

# Timed scene beats — Remotion component grammar (explainer-data)
SCENES = [
    {
        "id": "sc1",
        "label": "Hook — America vs Finland",
        "duration": 12.0,
        "narration": (
            "America feels like the coffee capital of the world. "
            "Starbucks on every corner. Open the per-capita map — "
            "and Finland drinks about three times more."
        ),
        "cut": {
            "type": "hero_title",
            "text": "America feels #1",
            "subtitle": "Finland drinks ~3× more coffee per person",
            "backgroundColor": "#0F172A",
        },
        "scene_type": "text_card",
        "narrative_role": "establish_context",
        "hero_moment": True,
    },
    {
        "id": "sc2",
        "label": "US vs Finland compare",
        "duration": 14.0,
        "narration": (
            "Finns drink roughly twelve kilograms of coffee per person each year. "
            "Americans? Closer to four point two. Same bean. Completely different habit."
        ),
        "cut": {
            "type": "comparison",
            "title": "Coffee kg per person / year",
            "leftLabel": "Finland",
            "leftValue": "12 kg",
            "rightLabel": "United States",
            "rightValue": "4.2 kg",
            "backgroundColor": "#0F172A",
            "accentColor": "#06B6D4",
        },
        "scene_type": "diagram",
        "narrative_role": "comparison",
        "hero_moment": True,
    },
    {
        "id": "sc3",
        "label": "Nordic leaders chart",
        "duration": 16.0,
        "narration": (
            "Norway, Iceland, Denmark, the Netherlands, Sweden — "
            "the top of the chart is Northern Europe. "
            "Not the country with the loudest coffee brand."
        ),
        "cut": {
            "type": "bar_chart",
            "title": "Per-capita coffee leaders (kg/person/year)",
            "chartData": [
                {"label": "Finland", "value": 12.0},
                {"label": "Norway", "value": 9.9},
                {"label": "Iceland", "value": 9.0},
                {"label": "Denmark", "value": 9.0},
                {"label": "Netherlands", "value": 8.4},
                {"label": "Sweden", "value": 8.2},
                {"label": "USA", "value": 4.2},
            ],
            "chartColors": [
                "#06B6D4",
                "#22D3EE",
                "#A78BFA",
                "#EC4899",
                "#34D399",
                "#F59E0B",
                "#64748B",
            ],
            "showGrid": True,
            "showValues": True,
            "chartAnimation": "grow",
            "backgroundColor": "#0F172A",
        },
        "scene_type": "diagram",
        "narrative_role": "evidence",
        "hero_moment": False,
    },
    {
        "id": "sc4",
        "label": "Two billion cups",
        "duration": 12.0,
        "narration": (
            "Zoom out further: humanity drinks more than two billion cups of coffee "
            "every day. The habit is planetary — the ranking is not what you expect."
        ),
        "cut": {
            "type": "stat_card",
            "stat": "2.2B+",
            "subtitle": "cups of coffee drunk worldwide every day",
            "accentColor": "#EC4899",
            "backgroundColor": "#0F172A",
        },
        "scene_type": "text_card",
        "narrative_role": "deliver_payload",
        "hero_moment": False,
    },
    {
        "id": "sc5",
        "label": "Growers ≠ drinkers",
        "duration": 16.0,
        "narration": (
            "Brazil grows about forty percent of the world's coffee. "
            "Yet Brazilians sit mid-pack as drinkers. "
            "Growers don't automatically wear the crown."
        ),
        "cut": {
            "type": "comparison",
            "title": "Produce vs drink",
            "leftLabel": "Brazil share of world production",
            "leftValue": "~40%",
            "rightLabel": "Brazil per-capita drinking",
            "rightValue": "mid-pack",
            "backgroundColor": "#0F172A",
            "accentColor": "#F59E0B",
        },
        "scene_type": "diagram",
        "narrative_role": "comparison",
        "hero_moment": False,
    },
    {
        "id": "sc6",
        "label": "Demand outruns supply",
        "duration": 12.0,
        "narration": (
            "And demand is winning. Roughly one hundred eighty million bags of coffee "
            "a year — while production forecasts keep lagging behind."
        ),
        "cut": {
            "type": "callout",
            "callout_type": "warning",
            "title": "Demand vs supply",
            "text": "~180M bags consumed yearly while production forecasts lag — the map is also a market signal.",
            "backgroundColor": "#0F172A",
        },
        "scene_type": "text_card",
        "narrative_role": "build_tension",
        "hero_moment": False,
    },
    {
        "id": "sc7",
        "label": "Landing CTA",
        "duration": 8.0,
        "narration": (
            "So next time someone says America runs on coffee — show them the map. "
            "The real caffeine capital speaks Finnish."
        ),
        "cut": {
            "type": "text_card",
            "text": "Show them the map.",
            "color": "#F8FAFC",
            "backgroundColor": "#0F172A",
            "fontSize": 64,
        },
        "scene_type": "text_card",
        "narrative_role": "call_to_action",
        "hero_moment": False,
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


def audio_duration(path: Path) -> float:
    """Prefer ffprobe — some TTS WAVs ship a broken RIFF frame count (0xFFFFFFFF)."""
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode == 0 and probe.stdout.strip():
        return float(probe.stdout.strip())
    # Fallback: size-based estimate for pcm_s16le mono 24kHz if wave header is broken
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        width = wf.getsampwidth()
        channels = max(wf.getnchannels(), 1)
        frames = wf.getnframes()
        if frames > 0 and frames < 2_000_000_000:
            return frames / float(rate)
    data_bytes = path.stat().st_size - 44
    return max(data_bytes / float(rate * width * channels), 1.0)


def schema_cuts_from_remotion(remotion_cuts: list[dict]) -> list[dict]:
    """edit_decisions.cuts schema forbids Remotion component fields — strip them."""
    allowed = {
        "id",
        "source",
        "in_seconds",
        "out_seconds",
        "speed",
        "layer",
        "transform",
        "transition_in",
        "transition_out",
        "transition_duration",
        "reason",
    }
    out = []
    for cut in remotion_cuts:
        slim = {k: v for k, v in cut.items() if k in allowed}
        slim.setdefault("source", "")
        slim.setdefault("layer", "primary")
        out.append(slim)
    return out


def main() -> int:
    ensure_vault_config_loaded()
    pdir = PROJECTS_DIR / PID
    if not pdir.exists():
        print(f"[fail] project missing at {pdir}", flush=True)
        return 1

    art_dir = pdir / "artifacts"
    research_path = art_dir / "research_brief.json"
    if not research_path.exists():
        print("[fail] research_brief.json missing — run research first", flush=True)
        return 1

    research = json.loads(research_path.read_text(encoding="utf-8"))
    spent = 0.0
    full_narration = " ".join(sc["narration"] for sc in SCENES)
    planned_duration = sum(sc["duration"] for sc in SCENES)

    # ── proposal (approved) ───────────────────────────────────────────────
    cp("proposal", "in_progress", {})
    concept_options = [
        {
            "id": "c1",
            "title": "The Map That Humiliates Starbucks",
            "hook": "America feels #1. Finland drinks three times more.",
            "narrative_structure": "myth_busting",
            "visual_approach": (
                "Remotion data graphics: hero title, comparison cards, animated "
                "bar chart of per-capita leaders, global stat, growers-vs-drinkers callout"
            ),
            "suggested_playbook": PLAYBOOK,
            "target_audience": "Curious YouTube viewers who think they know coffee culture",
            "target_platform": "youtube",
            "target_duration_seconds": TARGET_DURATION,
            "key_points": [
                "Finland ~12 kg/person/year vs US ~4.2 kg",
                "Nordic/Dutch countries dominate per-capita rankings",
                "2.2B+ cups drunk globally each day",
                "Brazil grows ~40% but is mid-pack as a drinker",
                "Demand (~180M bags) is outrunning supply forecasts",
            ],
            "core_message": "Brand ubiquity is not consumption leadership — the per-capita map tells the real story.",
            "cta": "Share the map the next time someone claims America runs on coffee.",
            "tone": "sharp, data-forward, lightly irreverent",
            "grounded_in": [
                "Finland 12 kg/person",
                "US 4.2 kg/person",
                "Nordic top tier",
                "2.2B cups/day",
                "Brazil production vs drinking",
                "180M bags demand",
            ],
            "why_this_works": (
                "Research DP1–DP3 create an instant myth-bust; DP4–DP6 widen to "
                "planetary scale and market stakes without losing the hook."
            ),
        },
        {
            "id": "c2",
            "title": "Growers Don't Drink the Crown",
            "hook": "Brazil grows the world's coffee. Someone else drinks it.",
            "narrative_structure": "comparison",
            "visual_approach": "Split-screen production vs consumption maps",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "Trade and sustainability-curious viewers",
            "target_platform": "youtube",
            "target_duration_seconds": TARGET_DURATION,
            "key_points": [
                "Brazil ~40% of world production",
                "Top drinkers are Northern Europe",
                "Value accrues downstream of the farm",
            ],
            "core_message": "Growing coffee and drinking coffee are different power maps.",
            "cta": "Follow the cup past the farm gate.",
            "tone": "investigative",
            "grounded_in": ["Brazil production share", "Nordic drinking leadership"],
            "why_this_works": "Counterintuitive producer/consumer split from research DP6.",
        },
        {
            "id": "c3",
            "title": "Two Billion Cups Before Lunch",
            "hook": "Humanity drinks more than two billion cups of coffee every day.",
            "narrative_structure": "data_narrative",
            "visual_approach": "Scale ladder from one cup to planetary demand",
            "suggested_playbook": PLAYBOOK,
            "target_audience": "General science/curiosity YouTube",
            "target_platform": "youtube",
            "target_duration_seconds": TARGET_DURATION,
            "key_points": [
                "2.2B+ cups daily",
                "180M bags yearly demand",
                "Supply lagging forecasts",
            ],
            "core_message": "Coffee is a planetary habit with a tightening supply story.",
            "cta": "Watch where the next bags have to come from.",
            "tone": "awe + urgency",
            "grounded_in": ["2.2B cups/day", "180M bags demand"],
            "why_this_works": "Scale hook from research DP4–DP5.",
        },
    ]

    proposal = must_valid(
        "proposal_packet",
        {
            "version": "1.0",
            "concept_options": concept_options,
            "selected_concept": {
                "concept_id": "c1",
                "rationale": "User approved Concept 1 with Remotion runtime and flat-motion-graphics.",
                "modifications": [
                    "Target ~90s YouTube",
                    "Voice: aditya via gpu_ai / tts_selector",
                    "Runtime: remotion",
                ],
            },
            "production_plan": {
                "pipeline": PIPELINE,
                "playbook": PLAYBOOK,
                "stages": [
                    {
                        "stage": "script",
                        "tools": [
                            {
                                "tool_name": "script_writer",
                                "role": "Write myth-bust narration from research",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                            }
                        ],
                        "approach": "Hook → US/Finland compare → Nordic chart → global scale → growers → demand → CTA",
                    },
                    {
                        "stage": "scene_plan",
                        "tools": [
                            {
                                "tool_name": "scene_planner",
                                "role": "Map script to Remotion component scenes",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                            }
                        ],
                        "approach": "hero_title, comparison, bar_chart, stat_card, callout, text_card",
                    },
                    {
                        "stage": "assets",
                        "tools": [
                            {
                                "tool_name": "tts_selector",
                                "role": "Narration",
                                "provider": "gpu_ai",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                                "why_this_provider": "User-approved aditya voice on cluster gpu-ai",
                            },
                            {
                                "tool_name": "gpu_ai_music",
                                "role": "Instrumental bed",
                                "provider": "gpu_ai",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                                "why_this_provider": "Cluster ACE-Step bed; pixabay fallback",
                            },
                        ],
                        "approach": "Component scenes need no still generation; TTS + music only",
                        "fallback_if_unavailable": "pixabay_music for bed; alternate TTS provider if gpu_ai down",
                    },
                    {
                        "stage": "edit",
                        "tools": [
                            {
                                "tool_name": "edit_director",
                                "role": "Build Remotion cut timeline synced to narration",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                            }
                        ],
                        "approach": "Scale scene holds to measured narration duration",
                    },
                    {
                        "stage": "compose",
                        "tools": [
                            {
                                "tool_name": "video_compose",
                                "role": "Remotion Explainer render",
                                "provider": "remotion",
                                "available": True,
                                "estimated_cost_usd": 0.0,
                                "why_this_provider": "User-locked remotion for chart/stat motion",
                            }
                        ],
                        "approach": "render_runtime=remotion, renderer_family=explainer-data, composition_mode=templated",
                    },
                ],
                "quality_tradeoffs": [
                    {
                        "tradeoff": "Remotion component scenes vs AI stills + Ken Burns",
                        "recommendation": "Prefer Remotion components for data clarity",
                        "quality_impact": "Stronger motion and chart readability; less photographic texture",
                    }
                ],
                "delivery_promise": {
                    "promise_type": "data_explainer",
                    "motion_required": True,
                    "tone_mode": "educational",
                    "quality_floor": "presentable",
                    "approved_fallback": None,
                },
                "renderer_family": "explainer-data",
                "render_runtime": "remotion",
                "composition_mode": "templated",
                "music_source": {
                    "source_type": "ai_generated",
                    "provider": "gpu_ai",
                    "mood_direction": "soft electronic documentary pulse, low key, instrumental",
                    "estimated_cost_usd": 0.0,
                },
                "taste_profile": {
                    "design_read": "Bold flat motion-graphics data explainer — charts and comparisons do the talking.",
                    "visual_variance": 5,
                    "motion_intensity": 7,
                    "information_density": 7,
                    "palette_discipline": "Playbook flat-motion-graphics slate + cyan/pink accents",
                    "anti_patterns": [
                        "Generic stock cafe b-roll slideshow",
                        "Wall of unlabeled numbers",
                    ],
                    "quality_gates": [
                        "Finland vs US comparison readable in one glance",
                        "Bar chart includes USA for contrast",
                        "Narration never invents unsourced stats",
                    ],
                },
            },
            "cost_estimate": {
                "total_estimated_usd": 0.15,
                "line_items": [
                    {
                        "tool": "tts_selector/gpu_ai_tts",
                        "operation": "Full narration (~90s)",
                        "quantity": 1,
                        "estimated_usd": 0.0,
                        "notes": "Cluster gpu-ai",
                    },
                    {
                        "tool": "gpu_ai_music",
                        "operation": "Instrumental bed ~95s",
                        "quantity": 1,
                        "estimated_usd": 0.0,
                        "notes": "ACE-Step via mcp-api; pixabay fallback",
                    },
                    {
                        "tool": "video_compose",
                        "operation": "Remotion 1080p render",
                        "quantity": 1,
                        "estimated_usd": 0.0,
                    },
                ],
                "budget_cap_usd": BUDGET,
                "budget_verdict": "within_budget",
            },
            "approval": {
                "status": "approved",
                "user_notes": "go — Concept 1, Remotion, ~90s YouTube, voice aditya/gpu_ai",
                "approved_budget_usd": BUDGET,
            },
            "metadata": {
                "title": TITLE,
                "approved_at": now_iso(),
            },
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
                    "subject": "Explainer concept",
                    "options_considered": [
                        {
                            "option_id": "c1",
                            "label": "The Map That Humiliates Starbucks",
                            "score": 1.0,
                            "reason": "Strongest myth-bust hook from research",
                        },
                        {
                            "option_id": "c2",
                            "label": "Growers Don't Drink the Crown",
                            "score": 0.7,
                            "reason": "Strong but narrower trade angle",
                            "rejected_because": "User selected Concept 1",
                        },
                        {
                            "option_id": "c3",
                            "label": "Two Billion Cups Before Lunch",
                            "score": 0.65,
                            "reason": "Scale awe, weaker brand-myth tension",
                            "rejected_because": "User selected Concept 1",
                        },
                    ],
                    "selected": "c1",
                    "reason": "User said go on Concept 1",
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
                        {
                            "option_id": "remotion",
                            "label": "Remotion (React scene components)",
                            "score": 1.0,
                            "reason": "Best for animated charts/stat cards",
                        },
                        {
                            "option_id": "hyperframes",
                            "label": "HyperFrames (HTML/CSS/GSAP)",
                            "score": 0.6,
                            "reason": "Capable motion but weaker chart grammar here",
                            "rejected_because": "User locked Remotion",
                        },
                        {
                            "option_id": "ffmpeg",
                            "label": "FFmpeg Ken Burns stills",
                            "score": 0.3,
                            "reason": "Would collapse data beats into still-led slideshow",
                            "rejected_because": "Fails motion_required data explainer",
                        },
                    ],
                    "selected": "remotion",
                    "reason": "User approved Remotion; charts need component motion",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-003",
                    "stage": "proposal",
                    "category": "composition_mode",
                    "subject": "How the Remotion composition is authored",
                    "options_considered": [
                        {
                            "option_id": "templated",
                            "label": "Templated Explainer stock scenes",
                            "score": 0.9,
                            "reason": "hero_title/stat_card/bar_chart/comparison cover the story",
                        },
                        {
                            "option_id": "atelier",
                            "label": "Atelier bespoke project-local composition",
                            "score": 0.55,
                            "reason": "Maximum uniqueness but slower for this data piece",
                            "rejected_because": "Templated components already match the brief",
                        },
                    ],
                    "selected": "templated",
                    "reason": "Data-explainer grammar maps cleanly to stock Explainer cuts",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.9,
                },
                {
                    "decision_id": "d-004",
                    "stage": "proposal",
                    "category": "renderer_family_selection",
                    "subject": "Creative grammar",
                    "options_considered": [
                        {
                            "option_id": "explainer-data",
                            "label": "explainer-data",
                            "score": 1.0,
                            "reason": "Charts and comparisons are the primary medium",
                        },
                        {
                            "option_id": "explainer-teacher",
                            "label": "explainer-teacher",
                            "score": 0.5,
                            "reason": "Better for conceptual metaphor than ranked data",
                            "rejected_because": "Wrong grammar for per-capita ranking story",
                        },
                    ],
                    "selected": "explainer-data",
                    "reason": "Locks Explainer composition to data-forward scenes",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-005",
                    "stage": "proposal",
                    "category": "voice_selection",
                    "subject": "Narration voice/provider",
                    "options_considered": [
                        {
                            "option_id": "gpu_ai_aditya",
                            "label": "gpu_ai voice aditya",
                            "score": 1.0,
                            "reason": "User-approved cluster voice",
                        },
                        {
                            "option_id": "other_tts",
                            "label": "Other TTS providers",
                            "score": 0.4,
                            "reason": "Available via selector but not requested",
                            "rejected_because": "User locked aditya/gpu_ai",
                        },
                    ],
                    "selected": "gpu_ai_aditya",
                    "reason": "Explicit user approval",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 1.0,
                },
                {
                    "decision_id": "d-006",
                    "stage": "proposal",
                    "category": "playbook_selection",
                    "subject": "Style playbook",
                    "options_considered": [
                        {
                            "option_id": "flat-motion-graphics",
                            "label": "Flat Motion Graphics",
                            "score": 1.0,
                            "reason": "Bold data graphics for social/YouTube explainers",
                        },
                        {
                            "option_id": "clean-professional",
                            "label": "Clean Professional",
                            "score": 0.5,
                            "reason": "Safer corporate tone, less punch",
                            "rejected_because": "Concept wants sharp myth-bust energy",
                        },
                    ],
                    "selected": "flat-motion-graphics",
                    "reason": "Matches approved concept visual approach",
                    "user_visible": True,
                    "user_approved": True,
                    "confidence": 0.95,
                },
            ],
        },
    )
    save_json(art_dir / "decision_log.json", decision_log)
    cp(
        "proposal",
        "completed",
        {"proposal_packet": proposal, "decision_log": decision_log},
        human_approved=True,
        cost_snapshot={
            "total_spent_usd": spent,
            "total_reserved_usd": 0.0,
            "budget_remaining_usd": BUDGET - spent,
        },
    )

    # ── script ────────────────────────────────────────────────────────────
    cp("script", "in_progress", {})
    t = 0.0
    sections = []
    for sc in SCENES:
        start = t
        end = t + sc["duration"]
        sections.append(
            {
                "id": sc["id"],
                "label": sc["label"],
                "text": sc["narration"],
                "start_seconds": start,
                "end_seconds": end,
                "speaker_directions": "Conversational, punchy, slight pause before key numbers",
                "delivery_cues": {
                    "pace": "conversational",
                    "energy": "engaged myth-bust",
                    "emphasis_words": ["Finland", "three times", "twelve", "two billion", "forty percent"],
                    "delivery_note": "Lean into the surprise on Finland vs America",
                    "provider_text": sc["narration"],
                },
                "enhancement_cues": [
                    {
                        "type": "stat_card" if sc["cut"]["type"] in {"stat_card", "comparison", "bar_chart"} else "animation",
                        "description": sc["label"],
                        "timestamp_seconds": start,
                    }
                ],
            }
        )
        t = end

    script = must_valid(
        "script",
        {
            "version": "1.0",
            "title": TITLE,
            "total_duration_seconds": planned_duration,
            "voice_performance": {
                "performance_intent": "Sharp data-myth-bust narrator who enjoys the plot twist",
                "pacing_profile": "conversational",
                "energy_curve": "hook high → evidence steady → landing wry",
                "pause_policy": "Brief beat before each key number",
                "sample_section_id": "sc1",
                "provider_notes": {
                    "gpu_ai": "voice=aditya, language=en, plain prose no SSML"
                },
            },
            "sections": sections,
            "metadata": {
                "word_count": len(full_narration.split()),
                "concept_id": "c1",
                "research_topic": research.get("topic"),
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
        start = t
        end = t + sc["duration"]
        scenes_out.append(
            {
                "id": sc["id"],
                "type": sc["scene_type"],
                "description": (
                    f"Remotion {sc['cut']['type']}: {sc['label']}. "
                    f"{sc['narration'][:80]}..."
                ),
                "start_seconds": start,
                "end_seconds": end,
                "script_section_id": sc["id"],
                "transition_in": "fade",
                "transition_out": "fade",
                "narrative_role": sc["narrative_role"],
                "information_role": sc["label"],
                "hero_moment": sc["hero_moment"],
                "shot_intent": f"Deliver {sc['cut']['type']} data beat",
                "required_assets": [
                    {
                        "type": "narration",
                        "description": f"Narration for {sc['id']}",
                        "source": "generate",
                    }
                ],
                "texture_keywords": ["flat", "bold", "data-graphics"],
            }
        )
        t = end

    scene_plan = must_valid(
        "scene_plan",
        {
            "version": "1.0",
            "style_playbook": PLAYBOOK,
            "scenes": scenes_out,
            "metadata": {
                "render_runtime": "remotion",
                "renderer_family": "explainer-data",
                "composition_mode": "templated",
            },
        },
    )
    save_json(art_dir / "scene_plan.json", scene_plan)
    cp("scene_plan", "completed", {"scene_plan": scene_plan}, human_approved=True)

    # ── assets ────────────────────────────────────────────────────────────
    cp("assets", "in_progress", {})
    (pdir / "assets/audio").mkdir(parents=True, exist_ok=True)
    narr_rel = "assets/audio/narration.wav"
    narr_path = pdir / narr_rel

    print(
        "[tool] tts_selector | preferred_provider=gpu_ai | voice=aditya | "
        f"chars={len(full_narration)}",
        flush=True,
    )
    from tools.audio.tts_selector import TTSSelector

    tts = TTSSelector().execute(
        {
            "text": full_narration,
            "voice_id": "aditya",
            "preferred_provider": "gpu_ai",
            "output_path": str(narr_path),
            "response_format": "wav",
        }
    )
    if not tts.success or not narr_path.exists():
        print(f"[fail] TTS: {tts.error}", flush=True)
        return 1
    spent += float(tts.cost_usd or 0)
    narr_dur = audio_duration(narr_path)
    tts_provider = (tts.data or {}).get("selected_provider", "gpu_ai")
    print(f"[ok] narration {narr_dur:.1f}s via {tts_provider} (${tts.cost_usd})", flush=True)

    manifest_assets = [
        {
            "id": "narration_main",
            "type": "narration",
            "path": narr_rel,
            "source_tool": "tts_selector",
            "scene_id": "sc1",
            "provider": tts_provider,
            "duration_seconds": round(narr_dur, 2),
            "cost_usd": float(tts.cost_usd or 0),
            "format": "wav",
            "voice_performance": {
                "source_section_id": "sc1",
                "delivery_cues_applied": True,
                "provider_text_used": True,
                "provider_settings": {"voice": "aditya", "preferred_provider": "gpu_ai"},
                "sample_approved": True,
                "review_notes": "User pre-approved voice aditya on gpu_ai",
            },
        }
    ]

    music_rel = "assets/music/bed.mp3"
    music_path = pdir / music_rel
    music_path.parent.mkdir(parents=True, exist_ok=True)
    music_tool = "gpu_ai_music"
    print(
        "[tool] gpu_ai_music | tags=ambient electronic, soft pulse, documentary, low key | "
        "seconds=95",
        flush=True,
    )
    from tools.gpu_ai.music import GpuAiMusic

    music = GpuAiMusic().execute(
        {
            "tags": "ambient electronic, soft documentary pulse, low key, instrumental bed",
            "seconds": 95,
            "loop": True,
            "lyrics": "[inst]",
            "response_format": "mp3",
            "output_path": str(music_path),
            "poll_timeout_s": 600,
        }
    )
    if not (music.success and music_path.exists()):
        print(f"[warn] gpu_ai_music failed: {music.error}; trying pixabay_music", flush=True)
        print("[tool] pixabay_music | query=ambient soft electronic calm", flush=True)
        from tools.audio.pixabay_music import PixabayMusic

        music = PixabayMusic().execute(
            {
                "query": "ambient soft electronic calm",
                "min_duration": 60,
                "max_duration": 180,
                "output_path": str(music_path),
            }
        )
        music_tool = "pixabay_music"

    if music.success and music_path.exists():
        music_cost = float(music.cost_usd or 0)
        spent += music_cost
        manifest_assets.append(
            {
                "id": "music_bed",
                "type": "music",
                "path": music_rel,
                "source_tool": music_tool,
                "scene_id": "sc1",
                "duration_seconds": 95,
                "cost_usd": music_cost,
                "format": "mp3",
            }
        )
        print(f"[ok] music via {music_tool}", flush=True)
    else:
        print(f"[warn] music skipped: {music.error}", flush=True)

    manifest = must_valid(
        "asset_manifest",
        {
            "version": "1.0",
            "assets": manifest_assets,
            "total_cost_usd": round(spent, 4),
            "metadata": {"tts_provider": tts_provider, "music_tool": music_tool},
        },
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
    scale = narr_dur / planned_duration if planned_duration else 1.0
    remotion_cuts = []
    t = 0.0
    for sc in SCENES:
        dur = sc["duration"] * scale
        cut = {
            "id": f"cut_{sc['id']}",
            "source": "",
            "in_seconds": round(t, 3),
            "out_seconds": round(t + dur, 3),
            "layer": "primary",
            "reason": sc["label"],
            "transition_in": "fade",
            "transition_out": "fade",
            "transition_duration": 0.3,
            **sc["cut"],
        }
        remotion_cuts.append(cut)
        t += dur

    overlays = [
        {
            "type": "section_title",
            "in_seconds": remotion_cuts[2]["in_seconds"] + 0.3,
            "out_seconds": remotion_cuts[2]["in_seconds"] + 3.5,
            "text": "Per capita",
            "subtitle": "Who actually drinks the most",
            "accentColor": "#06B6D4",
        },
        {
            "type": "stat_reveal",
            "in_seconds": remotion_cuts[1]["in_seconds"] + 1.0,
            "out_seconds": remotion_cuts[1]["out_seconds"] - 0.5,
            "text": "3×",
            "subtitle": "Finland vs USA",
            "accentColor": "#EC4899",
            "position": "bottom-right",
        },
    ]

    # Remotion <Audio> rejects file:// — stage into remotion-composer/public/
    import shutil

    composer_public = (
        Path(__file__).resolve().parent.parent / "remotion-composer" / "public" / PID
    )
    composer_public.mkdir(parents=True, exist_ok=True)
    shutil.copy2(narr_path, composer_public / "narration.wav")
    audio_block = {"narration": {"src": f"{PID}/narration.wav", "volume": 1.0}}
    if (pdir / music_rel).exists():
        shutil.copy2(pdir / music_rel, composer_public / "bed.mp3")
        audio_block["music"] = {
            "src": f"{PID}/bed.mp3",
            "volume": 0.12,
            "fadeInSeconds": 1.0,
            "fadeOutSeconds": 2.5,
            "loop": True,
        }

    remotion_props = {
        "version": "1.0",
        "theme": PLAYBOOK,
        "playbook": PLAYBOOK,
        "renderer_family": "explainer-data",
        "render_runtime": "remotion",
        "composition_mode": "templated",
        "cuts": remotion_cuts,
        "overlays": overlays,
        "captions": [],
        "audio": audio_block,
        "metadata": {
            "delivery_promise": proposal["production_plan"]["delivery_promise"],
            "proposal_render_runtime": "remotion",
            "playbook": PLAYBOOK,
            "compose_target": {"width": 1920, "height": 1080, "fit": "cover"},
        },
    }
    save_json(art_dir / "remotion_props.json", remotion_props)

    edit = must_valid(
        "edit_decisions",
        {
            "version": "1.0",
            "render_runtime": "remotion",
            "renderer_family": "explainer-data",
            "composition_mode": "templated",
            "cuts": schema_cuts_from_remotion(remotion_cuts),
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
                            "fade_out_seconds": 2.5,
                        }
                    }
                    if any(a["id"] == "music_bed" for a in manifest_assets)
                    else {}
                ),
            },
            "subtitles": {"enabled": False},
            "metadata": {
                "delivery_promise": proposal["production_plan"]["delivery_promise"],
                "proposal_render_runtime": "remotion",
                "remotion_props_path": "artifacts/remotion_props.json",
                "compose_target": {"width": 1920, "height": 1080, "fit": "cover"},
                "narration_duration_seconds": narr_dur,
            },
        },
    )
    save_json(art_dir / "edit_decisions.json", edit)
    cp("edit", "completed", {"edit_decisions": edit}, human_approved=True)

    # ── compose ───────────────────────────────────────────────────────────
    cp("compose", "in_progress", {})
    from tools.video.video_compose import VideoCompose

    out_mp4 = pdir / "renders" / "coffee_world_consumption.mp4"
    print(
        "[tool] video_compose | provider=remotion | render_runtime=remotion | "
        "renderer_family=explainer-data | reason=user-approved data explainer",
        flush=True,
    )
    compose = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": remotion_props,
            "asset_manifest": {
                "version": "1.0",
                "assets": [
                    {**a, "path": str(pdir / a["path"])} for a in manifest_assets
                ],
            },
            "scene_plan": scene_plan.get("scenes"),
            "proposal_packet": proposal,
            "output_path": str(out_mp4),
            "profile": "youtube_landscape",
            "options": {"subtitle_burn": False},
            "script_text": full_narration,
            "remotion_timeout_ms": 120000,
        }
    )
    if not compose.success:
        print(f"[fail] compose: {compose.error}", flush=True)
        cp(
            "compose",
            "failed",
            {"error": compose.error, "data": compose.data},
        )
        return 1

    # Probe duration
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(out_mp4),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    out_dur = float(probe.stdout.strip() or narr_dur)

    report = must_valid(
        "render_report",
        {
            "version": "1.0",
            "outputs": [
                {
                    "path": "renders/coffee_world_consumption.mp4",
                    "format": "mp4",
                    "resolution": "1920x1080",
                    "duration_seconds": round(out_dur, 2),
                    "codec": "h264",
                }
            ],
            "render_grammar": "explainer-data",
            "metadata": {
                "render_runtime": "remotion",
                "tts_tool": tts_provider,
                "music_tool": music_tool,
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
                    "platform": "board",
                    "status": "exported",
                    "url": f"https://om.baisoln.com/p/{PID}",
                    "export_path": "renders/coffee_world_consumption.mp4",
                    "timestamp": now_iso(),
                    "visibility": "unlisted",
                    "metadata_used": {
                        "title": TITLE,
                        "description": "Data explainer: Finland drinks ~3× more coffee per capita than the US.",
                        "hashtags": ["coffee", "data", "explainer"],
                    },
                }
            ],
            "metadata": {
                "title": TITLE,
                "output": "renders/coffee_world_consumption.mp4",
                "completed_at": now_iso(),
            },
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

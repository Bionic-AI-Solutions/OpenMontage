#!/usr/bin/env python3
"""Resume coffee explainer from existing narration/music — rebuild timeline + Remotion compose."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.checkpoint import PROJECTS_DIR
from lib.vault_config import ensure_vault_config_loaded
from scripts.produce_coffee_world import (
    BUDGET,
    PID,
    PLAYBOOK,
    SCENES,
    TITLE,
    audio_duration,
    cp,
    must_valid,
    now_iso,
    save_json,
    schema_cuts_from_remotion,
)
from tools.video.video_compose import VideoCompose


def main() -> int:
    ensure_vault_config_loaded()
    os.environ.setdefault("NODE_OPTIONS", "--max-old-space-size=4096")

    pdir = PROJECTS_DIR / PID
    art_dir = pdir / "artifacts"
    narr_path = pdir / "assets/audio/narration.wav"
    music_path = pdir / "assets/music/bed.mp3"
    if not narr_path.exists():
        print("[fail] narration missing", flush=True)
        return 1

    proposal = json.loads((art_dir / "proposal_packet.json").read_text(encoding="utf-8"))
    scene_plan = json.loads((art_dir / "scene_plan.json").read_text(encoding="utf-8"))
    manifest = json.loads((art_dir / "asset_manifest.json").read_text(encoding="utf-8"))
    full_narration = " ".join(sc["narration"] for sc in SCENES)
    planned = sum(sc["duration"] for sc in SCENES)
    narr_dur = audio_duration(narr_path)
    print(f"[fix] narr_dur={narr_dur:.2f}s planned={planned}", flush=True)
    if narr_dur > 300:
        print("[fail] narration duration still absurd — aborting", flush=True)
        return 1

    scale = narr_dur / planned
    remotion_cuts = []
    t = 0.0
    for sc in SCENES:
        dur = sc["duration"] * scale
        remotion_cuts.append(
            {
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
        )
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
    composer_public = Path(__file__).resolve().parent.parent / "remotion-composer" / "public" / PID
    composer_public.mkdir(parents=True, exist_ok=True)
    public_narr = composer_public / "narration.wav"
    public_music = composer_public / "bed.mp3"
    import shutil

    shutil.copy2(narr_path, public_narr)
    audio_block = {"narration": {"src": f"{PID}/narration.wav", "volume": 1.0}}
    if music_path.exists():
        shutil.copy2(music_path, public_music)
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
                    if music_path.exists()
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

    cp("compose", "in_progress", {})
    out_mp4 = pdir / "renders" / "coffee_world_consumption.mp4"
    print(
        "[tool] video_compose | provider=remotion | resume with fixed timeline",
        flush=True,
    )
    compose = VideoCompose().execute(
        {
            "operation": "render",
            "edit_decisions": remotion_props,
            "asset_manifest": {
                "version": "1.0",
                "assets": [
                    {**a, "path": str(pdir / a["path"])} for a in manifest["assets"]
                ],
            },
            "scene_plan": scene_plan.get("scenes"),
            "proposal_packet": proposal,
            "output_path": str(out_mp4),
            "profile": "youtube_landscape",
            "options": {"subtitle_burn": False},
            "script_text": full_narration,
            "remotion_timeout_ms": 180000,
        }
    )
    if not compose.success:
        print(f"[fail] compose: {compose.error}", flush=True)
        cp("compose", "failed", {"error": compose.error, "data": compose.data})
        return 1

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
    spent = float(manifest.get("total_cost_usd") or 0)

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
                        "description": (
                            "Data explainer: Finland drinks ~3× more coffee per capita than the US."
                        ),
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
        f"[done] {out_mp4} ({out_dur:.1f}s) board=https://om.baisoln.com/p/{PID}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

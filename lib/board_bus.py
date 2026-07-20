"""Board message bus — the disk contract between Backlot UI and the agent.

Server writes ONLY the inbox; the agent writes ONLY chat + heartbeat.
Both files are append-only JSONL inside the project directory, so the
existing watchfiles → SSE pipeline picks up changes with no new machinery.

Spec: docs/superpowers/specs/2026-07-20-backlot-interactive-board-design.md
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

INBOX_FILE = "inbox/messages.jsonl"
CHAT_DIR = "chat"
HEARTBEAT_FILE = ".agent_heartbeat"

# action name -> required fields beyond {stage, type, action}
ACTION_FIELDS: dict[str, list[str]] = {
    "approve": ["artifact_version"],
    "abort": [],
    "edit_script_line": ["line_id", "new_text"],
    "scene_note": ["scene_id", "note"],
    "reorder_scenes": ["order"],
    "drop_scene": ["scene_id"],
    "regenerate_asset": ["target"],
    "swap_provider": ["target"],
    "replace_asset": ["target", "path"],
    "override_decision": ["category", "subject", "chosen_option"],
}


def validate_message(payload: Any) -> Optional[str]:
    """Return an error string, or None if the message is well-formed."""
    if not isinstance(payload, dict):
        return "payload must be an object"
    if not isinstance(payload.get("stage"), str) or not payload["stage"]:
        return "missing 'stage'"
    mtype = payload.get("type")
    if mtype == "chat":
        if not isinstance(payload.get("text"), str) or not payload["text"].strip():
            return "chat message requires non-empty 'text'"
        return None
    if mtype == "action":
        action = payload.get("action")
        if action not in ACTION_FIELDS:
            return f"unknown action: {action!r}"
        for field in ACTION_FIELDS[action]:
            if payload.get(field) in (None, "", [], {}):
                return f"action {action!r} requires '{field}'"
        if action == "approve":
            version = payload.get("artifact_version")
            # bool is a subclass of int in Python — exclude it explicitly so
            # `artifact_version: true` doesn't sneak past an `isinstance(int)`
            # check.
            if isinstance(version, bool) or not isinstance(version, int):
                return "action 'approve' requires 'artifact_version' to be an integer"
        return None
    return f"unknown type: {mtype!r} (expected 'chat' or 'action')"


def append_inbox(project_dir: Path, payload: dict) -> dict:
    """Stamp id/ts and append one line. Caller must validate first."""
    stored = dict(payload)
    stored["id"] = f"m-{uuid.uuid4().hex[:8]}"
    stored["ts"] = time.time()
    path = Path(project_dir) / INBOX_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(stored, ensure_ascii=False) + "\n")
    return stored


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    out.append(obj)
    except OSError:
        return out
    return out


def read_inbox(project_dir: Path, cursor: Optional[dict] = None) -> list[dict]:
    """All messages, or those strictly after cursor {'id','ts'}.

    If the cursor id is not found (rotated/edited file), fall back to
    ts comparison so an approve is never double-applied.
    """
    messages = _read_jsonl(Path(project_dir) / INBOX_FILE)
    if not cursor:
        return messages
    ids = [m.get("id") for m in messages]
    if cursor.get("id") in ids:
        return messages[ids.index(cursor["id"]) + 1:]
    after_ts = cursor.get("ts") or 0
    return [m for m in messages if (m.get("ts") or 0) > after_ts]


def append_chat(
    project_dir: Path, stage: str, role: str, text: str,
    extra: Optional[dict] = None,
) -> dict:
    """Agent-side: append one message to the stage's chat thread."""
    msg: dict = {"id": f"c-{uuid.uuid4().hex[:8]}", "ts": time.time(),
                 "role": role, "text": text}
    if extra:
        msg.update(extra)
    path = Path(project_dir) / CHAT_DIR / f"{stage}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def read_chat(project_dir: Path, stage: str) -> list[dict]:
    return _read_jsonl(Path(project_dir) / CHAT_DIR / f"{stage}.jsonl")


def touch_heartbeat(project_dir: Path) -> None:
    path = Path(project_dir) / HEARTBEAT_FILE
    try:
        path.touch()
    except OSError:
        pass


def agent_live(project_dir: Path, window_seconds: float = 30.0) -> bool:
    path = Path(project_dir) / HEARTBEAT_FILE
    try:
        return (time.time() - path.stat().st_mtime) < window_seconds
    except OSError:
        return False

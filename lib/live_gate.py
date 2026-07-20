"""Live-gate helpers — how the agent holds a gate against the board inbox.

The agent calls ``wait_for_messages`` after writing an awaiting_human
checkpoint + gate presentation. The loop is a cheap file poll (no tokens
burned); the heartbeat file is what the board's "agent listening" dot reads.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from lib.board_bus import read_inbox, touch_heartbeat


def read_inbox_cursor(project_dir: Path, stage: str) -> Optional[dict]:
    """The last-processed inbox position recorded on the stage checkpoint."""
    path = Path(project_dir) / f"checkpoint_{stage}.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            return None
        cursor = metadata.get("inbox_cursor")
        return cursor if isinstance(cursor, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def cursor_for(message: dict) -> dict:
    """The cursor to persist (via write_checkpoint metadata) after processing."""
    return {"id": message.get("id"), "ts": message.get("ts")}


def wait_for_messages(
    project_dir: Path,
    cursor: Optional[dict] = None,
    timeout_seconds: float = 1800.0,
    poll_seconds: float = 2.0,
    heartbeat_seconds: float = 15.0,
) -> list[dict]:
    """Block until new inbox messages arrive or the hold times out.

    Returns every unprocessed message (ordered); [] on timeout. Touches the
    heartbeat on entry and every ``heartbeat_seconds`` so the board shows
    "agent listening" for the whole hold.
    """
    deadline = time.monotonic() + timeout_seconds
    last_beat = 0.0
    while True:
        now = time.monotonic()
        if now - last_beat >= heartbeat_seconds:
            touch_heartbeat(project_dir)
            last_beat = now
        messages = read_inbox(project_dir, cursor=cursor)
        if messages:
            return messages
        if now >= deadline:
            return []
        time.sleep(min(poll_seconds, max(0.01, deadline - now)))

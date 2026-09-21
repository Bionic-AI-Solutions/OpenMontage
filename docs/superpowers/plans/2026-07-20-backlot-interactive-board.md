# Backlot Interactive Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user drive gate decisions, stage chat, and inline tweaks from the Backlot board via a disk-mediated message bus, while the agent remains the sole writer of pipeline state.

**Architecture:** The Backlot server gains one general write path (`POST /inbox` → `projects/<id>/inbox/messages.jsonl`) plus an upload endpoint. The agent, holding a gate, polls the inbox with `lib/live_gate.py`, replies into `projects/<id>/chat/<stage>.jsonl`, and converts `approve` actions into `human_approved=True` checkpoints. The board renders chat threads and posts structured actions. Spec: `docs/superpowers/specs/2026-07-20-backlot-interactive-board-design.md`.

**Tech Stack:** Python 3.10 / FastAPI / pytest / vanilla-JS SPA (`backlot/ui/`). No new runtime dependencies except `python-multipart` (FastAPI upload support).

## Global Constraints

- Server writes ONLY `projects/<id>/inbox/` and `projects/<id>/uploads/` — never checkpoints, artifacts, or chat.
- Agent is sole writer of `chat/<stage>.jsonl`, checkpoints, artifacts.
- Money-spending verdicts (`approve`, `abort`) are always structured actions, never parsed from prose.
- An `approve` binds to an `artifact_version` (= stage's archived-checkpoint count + 1, i.e. the existing `versions` rail field).
- All new files append-only JSONL; one JSON object per line; `id`/`ts` stamped server-side (or agent-side for chat).
- Board must never block production: every new state read is defensive (malformed line → skip, missing file → empty).
- Follow existing test patterns in `tests/backlot/test_server.py` (fixtures `projects_root`, `client`, helper `_make_project`).
- Python style: match `backlot/state.py` (type hints, module docstrings, defensive reads).

---

### Task 1: Message bus module (`lib/board_bus.py`)

**Files:**
- Create: `lib/board_bus.py`
- Test: `tests/lib/test_board_bus.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces (used by Tasks 2–5, 9):
  - `validate_message(payload: dict) -> Optional[str]` — error string or None.
  - `append_inbox(project_dir: Path, payload: dict) -> dict` — stamps `id`/`ts`, appends, returns stored dict.
  - `read_inbox(project_dir: Path, cursor: Optional[dict] = None) -> list[dict]` — messages after cursor `{"id","ts"}`.
  - `append_chat(project_dir: Path, stage: str, role: str, text: str, extra: Optional[dict] = None) -> dict`
  - `read_chat(project_dir: Path, stage: str) -> list[dict]`
  - `touch_heartbeat(project_dir: Path) -> None` / `agent_live(project_dir: Path, window_seconds: float = 30.0) -> bool`
  - Constants: `INBOX_FILE = "inbox/messages.jsonl"`, `CHAT_DIR = "chat"`, `HEARTBEAT_FILE = ".agent_heartbeat"`, `ACTION_FIELDS`.

- [ ] **Step 1: Write the failing tests**

Create `tests/lib/test_board_bus.py`:

```python
"""Message-bus contract: inbox/chat JSONL, validation, cursor, heartbeat."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from lib import board_bus as bus


@pytest.fixture
def project_dir(tmp_path) -> Path:
    d = tmp_path / "proj"
    d.mkdir()
    return d


# ---- validation ----------------------------------------------------------

def test_chat_message_valid():
    assert bus.validate_message({"stage": "script", "type": "chat", "text": "hi"}) is None


def test_chat_message_requires_text():
    assert bus.validate_message({"stage": "script", "type": "chat"}) is not None


def test_unknown_type_rejected():
    assert bus.validate_message({"stage": "script", "type": "magic"}) is not None


def test_approve_requires_artifact_version():
    msg = {"stage": "script", "type": "action", "action": "approve"}
    assert bus.validate_message(msg) is not None
    msg["artifact_version"] = 2
    assert bus.validate_message(msg) is None


def test_unknown_action_rejected():
    msg = {"stage": "script", "type": "action", "action": "self_destruct"}
    assert bus.validate_message(msg) is not None


def test_edit_script_line_requires_fields():
    base = {"stage": "script", "type": "action", "action": "edit_script_line"}
    assert bus.validate_message(base) is not None
    ok = dict(base, line_id="s1", new_text="Better hook.")
    assert bus.validate_message(ok) is None


def test_regenerate_asset_requires_target():
    base = {"stage": "assets", "type": "action", "action": "regenerate_asset"}
    assert bus.validate_message(base) is not None
    ok = dict(base, target={"scene_id": "sc3", "asset": "visual"})
    assert bus.validate_message(ok) is None


def test_override_decision_requires_fields():
    base = {"stage": "proposal", "type": "action", "action": "override_decision"}
    assert bus.validate_message(base) is not None
    ok = dict(base, category="voice_selection", subject="Narration TTS provider",
              chosen_option="chirp3")
    assert bus.validate_message(ok) is None


def test_missing_stage_rejected():
    assert bus.validate_message({"type": "chat", "text": "hi"}) is not None


# ---- inbox append/read ---------------------------------------------------

def test_append_stamps_id_and_ts(project_dir):
    stored = bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "x"})
    assert stored["id"].startswith("m-") and stored["ts"] > 0
    lines = (project_dir / "inbox" / "messages.jsonl").read_text().strip().splitlines()
    assert json.loads(lines[0]) == stored


def test_read_inbox_all_and_after_cursor(project_dir):
    m1 = bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "one"})
    m2 = bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "two"})
    assert [m["text"] for m in bus.read_inbox(project_dir)] == ["one", "two"]
    after = bus.read_inbox(project_dir, cursor={"id": m1["id"], "ts": m1["ts"]})
    assert [m["id"] for m in after] == [m2["id"]]


def test_read_inbox_cursor_id_missing_falls_back_to_ts(project_dir):
    m1 = bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "one"})
    m2 = bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "two"})
    got = bus.read_inbox(project_dir, cursor={"id": "m-gone", "ts": m1["ts"]})
    assert [m["id"] for m in got] == [m2["id"]]


def test_read_inbox_skips_malformed_lines(project_dir):
    bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "ok"})
    with open(project_dir / "inbox" / "messages.jsonl", "a") as f:
        f.write("{not json\n")
    assert len(bus.read_inbox(project_dir)) == 1


def test_read_inbox_no_file(project_dir):
    assert bus.read_inbox(project_dir) == []


# ---- chat ---------------------------------------------------------------

def test_chat_roundtrip(project_dir):
    bus.append_chat(project_dir, "script", "agent", "Gate ready.", extra={"kind": "gate_presentation"})
    bus.append_chat(project_dir, "script", "user", "punchier hook")
    msgs = bus.read_chat(project_dir, "script")
    assert [m["role"] for m in msgs] == ["agent", "user"]
    assert msgs[0]["kind"] == "gate_presentation"
    assert bus.read_chat(project_dir, "assets") == []


# ---- heartbeat ----------------------------------------------------------

def test_heartbeat(project_dir):
    assert bus.agent_live(project_dir) is False
    bus.touch_heartbeat(project_dir)
    assert bus.agent_live(project_dir) is True
    assert bus.agent_live(project_dir, window_seconds=0.0) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/lib/test_board_bus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.board_bus'`

- [ ] **Step 3: Write the implementation**

Create `lib/board_bus.py`:

```python
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
            if payload.get(field) in (None, "", []):
                return f"action {action!r} requires '{field}'"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/lib/test_board_bus.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add lib/board_bus.py tests/lib/test_board_bus.py
git commit -m "feat(backlot): board message bus — inbox/chat JSONL contract"
```

---

### Task 2: `POST /api/project/{id}/inbox` endpoint

**Files:**
- Modify: `backlot/server.py` (add endpoint after the `library_events` route, before the thumbnails section)
- Test: `tests/backlot/test_server.py` (append)

**Interfaces:**
- Consumes: `board_bus.validate_message`, `board_bus.append_inbox` (Task 1); existing `_safe_project_dir`.
- Produces: `POST /api/project/{project_id}/inbox` — body = message dict; 200 → stored message (with `id`/`ts`); 400 invalid; 404 unknown project. Used by UI (Tasks 7–8) and integration test (Task 9).

- [ ] **Step 1: Write the failing tests**

Append to `tests/backlot/test_server.py`:

```python
# ---- inbox (interactive board) -------------------------------------------

def test_inbox_post_appends_message(client, projects_root):
    _make_project(projects_root)
    res = client.post("/api/project/film/inbox",
                      json={"stage": "script", "type": "chat", "text": "punchier hook"})
    assert res.status_code == 200
    body = res.json()
    assert body["id"].startswith("m-") and body["ts"] > 0
    stored = (projects_root / "film" / "inbox" / "messages.jsonl").read_text()
    assert "punchier hook" in stored


def test_inbox_post_rejects_invalid_message(client, projects_root):
    _make_project(projects_root)
    res = client.post("/api/project/film/inbox",
                      json={"stage": "script", "type": "action", "action": "self_destruct"})
    assert res.status_code == 400
    assert not (projects_root / "film" / "inbox").exists()


def test_inbox_post_unknown_project_404(client, projects_root):
    res = client.post("/api/project/nope/inbox",
                      json={"stage": "script", "type": "chat", "text": "x"})
    assert res.status_code == 404


def test_inbox_post_approve_requires_artifact_version(client, projects_root):
    _make_project(projects_root)
    res = client.post("/api/project/film/inbox",
                      json={"stage": "script", "type": "action", "action": "approve"})
    assert res.status_code == 400
    res = client.post("/api/project/film/inbox",
                      json={"stage": "script", "type": "action", "action": "approve",
                            "artifact_version": 1})
    assert res.status_code == 200


def test_server_never_writes_checkpoints(client, projects_root):
    """Governance: no server route may flip a checkpoint."""
    project = _make_project(projects_root)
    before = (project / "checkpoint_script.json").read_text()
    client.post("/api/project/film/inbox",
                json={"stage": "script", "type": "action", "action": "approve",
                      "artifact_version": 1})
    assert (project / "checkpoint_script.json").read_text() == before
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backlot/test_server.py -k inbox_post -v`
Expected: FAIL with 405 (route missing)

- [ ] **Step 3: Implement the endpoint**

In `backlot/server.py`, extend the module docstring's invariant sentence:

```python
"""...
The server never writes to project directories, with exactly two carve-outs:
``inbox/`` (board → agent messages) and ``uploads/`` (replacement media).
"""
```

Add the import at the top with the other `backlot`/`lib` imports:

```python
from lib.board_bus import append_inbox, validate_message
```

Add inside `create_app()` after the `library_events` route:

```python
    # ---- Inbox (the board's only general write path) -------------------

    @app.post("/api/project/{project_id}/inbox")
    async def post_inbox(project_id: str, request: Request) -> dict:
        project_dir = _safe_project_dir(project_id)
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="body must be JSON")
        error = validate_message(payload)
        if error:
            raise HTTPException(status_code=400, detail=error)
        return await asyncio.to_thread(append_inbox, project_dir, payload)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backlot/test_server.py -v`
Expected: all PASS (including pre-existing tests)

- [ ] **Step 5: Commit**

```bash
git add backlot/server.py tests/backlot/test_server.py
git commit -m "feat(backlot): POST /inbox endpoint — board writes intent, never state"
```

---

### Task 3: `POST /api/project/{id}/upload` endpoint

**Files:**
- Modify: `backlot/server.py`
- Modify: `requirements.txt` (add `python-multipart` if absent)
- Test: `tests/backlot/test_server.py` (append)

**Interfaces:**
- Consumes: `_safe_project_dir`.
- Produces: `POST /api/project/{project_id}/upload` (multipart field `file`) → `{"path": "uploads/<safe-name>"}`. The returned path is what the UI puts into a `replace_asset` action's `path` field.

- [ ] **Step 1: Write the failing tests**

Append to `tests/backlot/test_server.py`:

```python
# ---- upload (replacement media) ------------------------------------------

def test_upload_saves_media_file(client, projects_root):
    _make_project(projects_root)
    res = client.post("/api/project/film/upload",
                      files={"file": ("swap.png", b"\x89PNG fake", "image/png")})
    assert res.status_code == 200
    rel = res.json()["path"]
    assert rel.startswith("uploads/") and rel.endswith(".png")
    assert (projects_root / "film" / rel).read_bytes() == b"\x89PNG fake"


def test_upload_rejects_disallowed_extension(client, projects_root):
    _make_project(projects_root)
    res = client.post("/api/project/film/upload",
                      files={"file": ("evil.py", b"print(1)", "text/x-python")})
    assert res.status_code == 400


def test_upload_rejects_oversize(client, projects_root, monkeypatch):
    _make_project(projects_root)
    monkeypatch.setattr(server_mod, "MAX_UPLOAD_BYTES", 10)
    res = client.post("/api/project/film/upload",
                      files={"file": ("big.png", b"x" * 11, "image/png")})
    assert res.status_code == 413


def test_upload_sanitizes_traversal_names(client, projects_root):
    _make_project(projects_root)
    res = client.post("/api/project/film/upload",
                      files={"file": ("../../etc/passwd.png", b"x", "image/png")})
    assert res.status_code == 200
    saved = res.json()["path"]
    target = (projects_root / "film" / saved).resolve()
    assert (projects_root / "film" / "uploads").resolve() in target.parents
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backlot/test_server.py -k upload -v`
Expected: FAIL with 405

- [ ] **Step 3: Implement**

Ensure the dependency (skip if already present):

```bash
grep -q python-multipart requirements.txt || echo "python-multipart" >> requirements.txt
pip install python-multipart -q
```

In `backlot/server.py`, add to the imports: `from fastapi import UploadFile, File` and module constants near `THUMB_WIDTHS`:

```python
ALLOWED_UPLOAD_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif",
                      ".mp4", ".webm", ".mov", ".mp3", ".wav", ".m4a"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
```

Add inside `create_app()` after the inbox route:

```python
    @app.post("/api/project/{project_id}/upload")
    async def post_upload(project_id: str, file: UploadFile = File(...)) -> dict:
        project_dir = _safe_project_dir(project_id)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_UPLOAD_EXT:
            raise HTTPException(status_code=400, detail=f"extension not allowed: {suffix or '(none)'}")
        data = await file.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file too large")
        import re as _re, uuid as _uuid
        stem = _re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "upload").stem)[:60]
        name = f"{stem}-{_uuid.uuid4().hex[:6]}{suffix}"
        dest_dir = project_dir / "uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / name).write_bytes(data)
        return {"path": f"uploads/{name}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backlot/test_server.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backlot/server.py requirements.txt tests/backlot/test_server.py
git commit -m "feat(backlot): upload endpoint for replacement assets"
```

---

### Task 4: Board state — chat threads, liveness, artifact_version

**Files:**
- Modify: `backlot/state.py` (`load_board_state`, `_build_stage_rail`)
- Test: `tests/backlot/test_state.py` (append)

**Interfaces:**
- Consumes: `board_bus.read_chat`, `board_bus.agent_live` (Task 1).
- Produces (consumed by UI Tasks 7–8):
  - `state["chat"]: dict[stage_name, list[message]]` — only stages with existing chat files.
  - `state["agent_live"]: bool`.
  - Each stage rail entry gains `"artifact_version": int` (identical value to existing `"versions"` — explicit name the approve action stamps).

- [ ] **Step 1: Write the failing tests**

Append to `tests/backlot/test_state.py` (reuse that file's existing project-builder helpers; if it has none, use this self-contained pattern):

```python
def test_board_state_exposes_chat_and_liveness(tmp_path):
    from lib import board_bus as bus
    from backlot.state import load_board_state
    project = tmp_path / "chatty"
    (project / "artifacts").mkdir(parents=True)
    (project / "project.json").write_text(json.dumps(
        {"project_id": "chatty", "title": "Chatty", "pipeline_type": "cinematic"}))
    bus.append_chat(project, "script", "agent", "Gate ready.",
                    extra={"kind": "gate_presentation"})
    bus.touch_heartbeat(project)
    state = load_board_state(project)
    assert state["agent_live"] is True
    assert [m["text"] for m in state["chat"]["script"]] == ["Gate ready."]


def test_board_state_no_chat_dir(tmp_path):
    from backlot.state import load_board_state
    project = tmp_path / "quiet"
    project.mkdir()
    state = load_board_state(project)
    assert state["chat"] == {}
    assert state["agent_live"] is False


def test_stage_rail_has_artifact_version(tmp_path):
    from backlot.state import load_board_state
    project = tmp_path / "versioned"
    (project / "history").mkdir(parents=True)
    (project / "project.json").write_text(json.dumps(
        {"project_id": "versioned", "title": "V", "pipeline_type": "cinematic"}))
    (project / "checkpoint_script.json").write_text(json.dumps(
        {"stage": "script", "status": "awaiting_human", "timestamp": "2026-07-20T00:00:00Z"}))
    (project / "history" / "checkpoint_script_1.json").write_text(json.dumps(
        {"stage": "script", "status": "awaiting_human", "timestamp": "2026-07-19T00:00:00Z"}))
    state = load_board_state(project)
    script = next(s for s in state["stages"] if s["name"] == "script")
    assert script["artifact_version"] == 2 == script["versions"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/backlot/test_state.py -k "chat or artifact_version" -v`
Expected: FAIL with KeyError `'chat'` / `'artifact_version'`

- [ ] **Step 3: Implement**

In `backlot/state.py` add the import:

```python
from lib.board_bus import CHAT_DIR, agent_live, read_chat
```

In `_build_stage_rail`, in the first loop's `entry` dict, add directly under the `"versions"` line:

```python
            "artifact_version": len(versions) + (1 if cp else 0),
```

(and in the undeclared-stage entry dict add `"artifact_version": 1 + len(history.get(name, [])),` alongside its `"versions"` line).

In `load_board_state`, before building `state`, add:

```python
    chat: dict[str, list[dict]] = {}
    chat_dir = project_dir / CHAT_DIR
    if chat_dir.is_dir():
        for f in sorted(chat_dir.glob("*.jsonl")):
            msgs = read_chat(project_dir, f.stem)
            if msgs:
                chat[f.stem] = msgs
```

and in the `state` dict add:

```python
        "chat": chat,
        "agent_live": agent_live(project_dir),
```

Also add `"inbox"` and `"uploads"` to `SCAN_EXCLUDE` at the top of the file (media scanning must not surface bus internals), and `.agent_heartbeat` activity should NOT mark the project "live" by itself — `_last_activity` already only scans checkpoints/events/artifacts, so no change there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/backlot/ -v`
Expected: all PASS (existing suite still green)

- [ ] **Step 5: Commit**

```bash
git add backlot/state.py tests/backlot/test_state.py
git commit -m "feat(backlot): board state exposes chat threads, agent liveness, artifact_version"
```

---

### Task 5: Agent-side live-gate helpers (`lib/live_gate.py`)

**Files:**
- Create: `lib/live_gate.py`
- Test: `tests/lib/test_live_gate.py`

**Interfaces:**
- Consumes: `board_bus.read_inbox`, `board_bus.touch_heartbeat` (Task 1).
- Produces (used by the agent per Task 6's protocol, and Task 9's test):
  - `read_inbox_cursor(project_dir: Path, stage: str) -> Optional[dict]` — reads `metadata.inbox_cursor` from `checkpoint_<stage>.json`.
  - `wait_for_messages(project_dir, cursor=None, timeout_seconds=1800.0, poll_seconds=2.0, heartbeat_seconds=15.0) -> list[dict]` — blocking poll; touches heartbeat; returns new messages (may be several) or `[]` on timeout.
  - `cursor_for(message: dict) -> dict` — `{"id","ts"}` to store back via `write_checkpoint(metadata={"inbox_cursor": ...})`.

- [ ] **Step 1: Write the failing tests**

Create `tests/lib/test_live_gate.py`:

```python
"""Live-gate helpers: cursor read, blocking wait, heartbeat side-effect."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from lib import board_bus as bus
from lib import live_gate


@pytest.fixture
def project_dir(tmp_path) -> Path:
    d = tmp_path / "proj"
    d.mkdir()
    return d


def test_read_inbox_cursor(project_dir):
    (project_dir / "checkpoint_script.json").write_text(json.dumps(
        {"stage": "script", "status": "awaiting_human",
         "metadata": {"inbox_cursor": {"id": "m-abc", "ts": 5.0}}}))
    assert live_gate.read_inbox_cursor(project_dir, "script") == {"id": "m-abc", "ts": 5.0}
    assert live_gate.read_inbox_cursor(project_dir, "assets") is None


def test_cursor_for():
    assert live_gate.cursor_for({"id": "m-1", "ts": 9.0, "text": "x"}) == {"id": "m-1", "ts": 9.0}


def test_wait_returns_existing_messages_immediately(project_dir):
    bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "hello"})
    got = live_gate.wait_for_messages(project_dir, timeout_seconds=5.0, poll_seconds=0.05)
    assert [m["text"] for m in got] == ["hello"]


def test_wait_times_out_empty(project_dir):
    t0 = time.time()
    got = live_gate.wait_for_messages(project_dir, timeout_seconds=0.2, poll_seconds=0.05)
    assert got == [] and time.time() - t0 < 2.0


def test_wait_picks_up_message_written_during_wait(project_dir):
    def write_later():
        time.sleep(0.15)
        bus.append_inbox(project_dir, {"stage": "script", "type": "action",
                                       "action": "approve", "artifact_version": 1})
    threading.Thread(target=write_later).start()
    got = live_gate.wait_for_messages(project_dir, timeout_seconds=5.0, poll_seconds=0.05)
    assert got and got[0]["action"] == "approve"


def test_wait_touches_heartbeat(project_dir):
    live_gate.wait_for_messages(project_dir, timeout_seconds=0.2,
                                poll_seconds=0.05, heartbeat_seconds=0.01)
    assert (project_dir / bus.HEARTBEAT_FILE).is_file()


def test_wait_respects_cursor(project_dir):
    m1 = bus.append_inbox(project_dir, {"stage": "script", "type": "chat", "text": "old"})
    got = live_gate.wait_for_messages(project_dir, cursor=live_gate.cursor_for(m1),
                                      timeout_seconds=0.2, poll_seconds=0.05)
    assert got == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/lib/test_live_gate.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Implement**

Create `lib/live_gate.py`:

```python
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
        cursor = (data.get("metadata") or {}).get("inbox_cursor")
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/lib/test_live_gate.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add lib/live_gate.py tests/lib/test_live_gate.py
git commit -m "feat(backlot): live-gate helpers — inbox wait loop, cursor, heartbeat"
```

---

### Task 6: Protocol docs — checkpoint-protocol.md live-gate mode + AGENT_GUIDE pointer

**Files:**
- Modify: `skills/meta/checkpoint-protocol.md` (new section after "Step 5: Human Approval")
- Modify: `AGENT_GUIDE.md` (Human Checkpoint Protocol section — add two sentences)
- Modify: `backlot/README.md` (first paragraph: no longer purely read-only)

**Interfaces:**
- Consumes: `lib/live_gate.py` API (Task 5), `lib/board_bus.append_chat` (Task 1).
- Produces: the behavioral contract every future agent session follows.

- [ ] **Step 1: Add the live-gate section to `skills/meta/checkpoint-protocol.md`**

Insert after "Step 5: Human Approval (If Required)" (renumber nothing; it's a lettered sub-mode):

```markdown
### Step 5b: Live Gate — Board-Attached Holding (Preferred When Backlot Is Running)

When the Backlot server is reachable, do not end your turn at a gate.
Instead, HOLD the gate so the user can act from the board:

1. Write the `awaiting_human` checkpoint as usual.
2. Write your gate presentation to the stage chat:
   ```python
   from lib.board_bus import append_chat
   append_chat(project_dir, stage, "agent", presentation_text,
               extra={"kind": "gate_presentation",
                      "artifact_version": artifact_version})
   ```
   `artifact_version` = the stage's archived-checkpoint count in
   `projects/<id>/history/` + 1.
3. Hold with the blocking helper (cheap file poll — never a token loop):
   ```python
   from lib.live_gate import wait_for_messages, read_inbox_cursor, cursor_for
   cursor = read_inbox_cursor(project_dir, stage)
   messages = wait_for_messages(project_dir, cursor=cursor,
                                timeout_seconds=1800)
   ```
4. Dispatch each returned message IN ORDER; after each one, re-write the
   checkpoint with `metadata.inbox_cursor = cursor_for(message)`:
   - `action: approve` — consume ONLY if its `artifact_version` matches the
     currently presented version; then re-write the checkpoint
     `completed`/`human_approved=True` and advance. On mismatch, reply in
     chat asking to confirm against the new version, and keep holding.
   - `action: abort` — stop the pipeline; final chat message states where
     things stand.
   - Structured tweak (`edit_script_line`, `scene_note`, `reorder_scenes`,
     `drop_scene`, `regenerate_asset`, `swap_provider`, `replace_asset`,
     `override_decision`) — apply to the artifact, validate against
     `schemas/artifacts/`, append a `decision_log` entry when it changes a
     logged decision (same `(category, subject)` re-log rule), confirm in
     chat, RE-PRESENT the gate (version increments). A tweak never implies
     approval.
   - `chat` — treat exactly like a typed terminal reply: interpret with
     stage context, revise per the stage director skill if asked,
     re-review, re-present. Always answer in the stage chat.
   - A message for a DIFFERENT stage than the held one: acknowledge in
     that stage's chat; if it requires rewinding past completed stages,
     quantify the rework and cost and ask for confirmation first.
5. Messages echoed as quick-actions in the UI already appear in the chat
   thread; your replies always go through `append_chat` — never only to
   the terminal.
6. Terminal replies still win: if the user types in chat while you hold,
   process that input and stop polling. Both channels are equivalent and
   both are audited.
7. On timeout (default 30 min): post "still waiting — I'll apply your
   board actions next session" to the stage chat, END YOUR TURN cleanly.
   The resume protocol (Step 7) MUST drain unprocessed inbox messages
   (from `metadata.inbox_cursor`) BEFORE re-presenting the gate.

The Backlot server writes ONLY `inbox/` and `uploads/`. You remain the
sole writer of checkpoints, artifacts, and chat. A [Proceed] click never
flips a checkpoint by itself — you convert it.
```

- [ ] **Step 2: Update `AGENT_GUIDE.md`**

In the "Human Checkpoint Protocol" section, after the bullet ending "END YOUR TURN. Doing further pipeline work in the same response is a gate violation.", append:

```markdown
- **Live gate (board-attached):** when the Backlot server is running, prefer holding the gate instead of ending the turn — poll `projects/<id>/inbox/` with `lib/live_gate.wait_for_messages` and converse via `projects/<id>/chat/<stage>.jsonl`, per "Step 5b" of `skills/meta/checkpoint-protocol.md`. Board actions and terminal replies are equivalent inputs to the same gate.
```

- [ ] **Step 3: Update `backlot/README.md`**

Replace the first paragraph's "A read-only local board" sentence with:

```markdown
A local board that shows a production happening — and, at gates, takes your
input: each stage has a chat thread plus one-click [Proceed]/[Abort]. The
server's only writes are `inbox/` (your messages/actions) and `uploads/`;
the agent remains the sole writer of checkpoints, artifacts, and chat.
```

- [ ] **Step 4: Verify docs are consistent**

Run: `grep -n "inbox" AGENT_GUIDE.md skills/meta/checkpoint-protocol.md backlot/README.md | head -20`
Expected: all three files reference the inbox; no stale "never writes" claims remain (`grep -n "never writes" backlot/`).

- [ ] **Step 5: Commit**

```bash
git add skills/meta/checkpoint-protocol.md AGENT_GUIDE.md backlot/README.md
git commit -m "docs: live-gate protocol — board-attached gate holding"
```

---

### Task 7: UI — stage chat panel with Proceed/Abort

**Files:**
- Modify: `backlot/ui/board.js`
- Modify: `backlot/ui/board.css`
- Test: manual (Step 4) — the UI is vanilla JS with no test harness; server-side shape is covered by Task 4 tests.

**Interfaces:**
- Consumes: `state.chat[stage]`, `state.agent_live`, stage entry `artifact_version` (Task 4); `POST /inbox` (Task 2). Existing helpers in `board.js`/`lib.js`: `el(...)` element builder, `state` global, `selectedStage`, `renderDrawer(s)`, `toggleDrawer(name)`.
- Produces: `postInbox(payload) -> Promise<bool>` and `renderChatPanel(s, st)` used by Task 8's quick-actions.

- [ ] **Step 1: Add the transport + chat panel to `board.js`**

Add near the other top-level helpers (after `toggleDrawer`):

```javascript
async function postInbox(payload) {
  try {
    const res = await fetch(`/api/project/${encodedProjectId}/inbox`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))).detail || res.statusText;
      alert(`Board action failed: ${detail}`);
    }
    return res.ok;
  } catch (err) {
    alert(`Board action failed: ${err}`);
    return false;
  }
}

function chatMessageRow(m) {
  const who = m.role === "agent" ? "agent" : "you";
  return el("div", { class: `chat-msg chat-${who}` },
    el("span", { class: "chat-role" }, who),
    el("div", { class: "chat-text" }, m.text || ""));
}

function renderChatPanel(s, st) {
  const thread = (s.chat || {})[st.name] || [];
  const awaiting = st.status === "awaiting_human";
  const live = !!s.agent_live;

  const composer = el("form", {
    class: "chat-composer",
    onsubmit: async (e) => {
      e.preventDefault();
      const input = e.target.querySelector("input");
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      await postInbox({ stage: st.name, type: "chat", text });
    },
  },
    el("input", { type: "text", placeholder: live
      ? "Tell the agent what to change…"
      : "Agent offline — your message will queue…" }),
    el("button", { type: "submit" }, "SEND"));

  const gateButtons = awaiting ? el("div", { class: "chat-gate-actions" },
    el("button", {
      class: "gate-proceed", type: "button",
      onclick: () => postInbox({ stage: st.name, type: "action",
        action: "approve", artifact_version: st.artifact_version }),
    }, "✓ PROCEED AS RECOMMENDED"),
    el("button", {
      class: "gate-abort", type: "button",
      onclick: () => {
        if (confirm("Abort this production?")) {
          postInbox({ stage: st.name, type: "action", action: "abort" });
        }
      },
    }, "✕ ABORT")) : null;

  return el("section", { class: "chat-panel" },
    el("div", { class: "chat-head" },
      el("span", { class: `chat-live ${live ? "on" : "off"}` },
        live ? "● agent listening" : "○ agent offline — messages will queue"),
      awaiting ? el("span", { class: "chat-version" }, `v${st.artifact_version}`) : null),
    el("div", { class: "chat-thread" }, ...thread.map(chatMessageRow)),
    gateButtons,
    composer);
}
```

- [ ] **Step 2: Mount the panel in the stage drawer**

In `renderDrawer(s)`, immediately after the drawer header row (the element containing the `CLOSE ✕` span), insert:

```javascript
  children.push(renderChatPanel(s, st));
```

(adapting to how `renderDrawer` accumulates children — if it builds a single `el(...)` call, add `renderChatPanel(s, st)` as the first content argument after the header). Also, in `renderApprovalReview(s)`, next to the existing `OPEN FULL ARTIFACT` button, add:

```javascript
      el("button", { type: "button", class: "gate-proceed",
        onclick: () => postInbox({ stage: awaiting.name, type: "action",
          action: "approve",
          artifact_version: s.stages[stageIndex].artifact_version }),
      }, "✓ PROCEED AS RECOMMENDED"),
```

- [ ] **Step 3: Style it in `board.css`**

Append:

```css
/* ---- stage chat panel (interactive board) ---- */
.chat-panel { border-top: 1px solid var(--line, #333); margin-top: 12px; padding-top: 10px; }
.chat-head { display: flex; justify-content: space-between; font-size: 11px; opacity: .8; margin-bottom: 6px; }
.chat-live.on { color: #7dd87d; }
.chat-live.off { color: #999; }
.chat-thread { max-height: 260px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.chat-msg { padding: 6px 8px; border-radius: 6px; font-size: 12.5px; line-height: 1.4; }
.chat-agent { background: rgba(120, 140, 255, .12); align-self: flex-start; max-width: 92%; }
.chat-you { background: rgba(120, 255, 160, .10); align-self: flex-end; max-width: 92%; }
.chat-role { display: block; font-size: 9px; text-transform: uppercase; opacity: .5; margin-bottom: 2px; }
.chat-gate-actions { display: flex; gap: 8px; margin: 10px 0 6px; }
.gate-proceed { background: #2f7d46; color: #fff; border: 0; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-weight: 600; }
.gate-abort { background: transparent; color: #d66; border: 1px solid #d66; padding: 8px 12px; border-radius: 6px; cursor: pointer; }
.chat-composer { display: flex; gap: 6px; margin-top: 8px; }
.chat-composer input { flex: 1; background: rgba(255,255,255,.06); border: 1px solid var(--line, #333); border-radius: 6px; padding: 7px 9px; color: inherit; }
.chat-composer button { border: 1px solid var(--line, #333); background: transparent; color: inherit; border-radius: 6px; padding: 7px 10px; cursor: pointer; }
```

- [ ] **Step 4: Manual verification**

```bash
python -m backlot serve --port 4750 &
python scripts/backlot_simulate_run.py
```

Open `http://127.0.0.1:4750/p/backlot-demo-run`, click the `assets` stage:
- Chat panel renders (empty thread OK), liveness shows "○ agent offline".
- Type a message + SEND → `projects/backlot-demo-run/inbox/messages.jsonl` gains a line (`cat` it) and no JS console errors.
- On an `awaiting_human` stage the [✓ PROCEED] / [✕ ABORT] buttons render; clicking Proceed appends an `approve` action with `artifact_version`.

- [ ] **Step 5: Commit**

```bash
git add backlot/ui/board.js backlot/ui/board.css
git commit -m "feat(backlot-ui): stage chat panel with one-click proceed/abort"
```

---

### Task 8: UI — quick-actions (script edit, filmstrip, decision override)

**Files:**
- Modify: `backlot/ui/board.js`
- Modify: `backlot/ui/board.css`
- Test: manual (Step 3)

**Interfaces:**
- Consumes: `postInbox` (Task 7); action vocabulary (Task 1); `POST /upload` (Task 3).
- Produces: user-visible quick-action controls; each posts a structured action.

- [ ] **Step 1: Add the action helpers to `board.js`**

```javascript
function editScriptLine(stageName, section) {
  const next = prompt("Edit narration line:", section.text || "");
  if (next === null || next.trim() === "" || next === section.text) return;
  postInbox({ stage: stageName, type: "action", action: "edit_script_line",
    line_id: section.id, new_text: next.trim() });
}

function sceneQuickActions(card) {
  const stage = "assets";
  return el("div", { class: "scene-actions" },
    el("button", { title: "Note for this scene", onclick: () => {
      const note = prompt(`Note for scene ${card.id}:`);
      if (note) postInbox({ stage, type: "action", action: "scene_note",
        scene_id: card.id, note });
    }}, "🗒"),
    el("button", { title: "Regenerate visual", onclick: () => {
      const note = prompt("Optional guidance for the regeneration:") || undefined;
      postInbox({ stage, type: "action", action: "regenerate_asset",
        target: { scene_id: card.id, asset: "visual" }, note });
    }}, "↺"),
    el("button", { title: "Try a different provider", onclick: () => {
      postInbox({ stage, type: "action", action: "swap_provider",
        target: { scene_id: card.id, asset: "visual" } });
    }}, "⇄"),
    el("button", { title: "Drop this scene", onclick: () => {
      if (confirm(`Drop scene ${card.id}?`))
        postInbox({ stage: "scene_plan", type: "action", action: "drop_scene",
          scene_id: card.id });
    }}, "🗑"),
    el("button", { title: "Replace with your own file", onclick: async () => {
      const input = document.createElement("input");
      input.type = "file";
      input.onchange = async () => {
        const file = input.files[0];
        if (!file) return;
        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`/api/project/${encodedProjectId}/upload`,
          { method: "POST", body: form });
        if (!res.ok) { alert("Upload failed"); return; }
        const { path } = await res.json();
        postInbox({ stage, type: "action", action: "replace_asset",
          target: { scene_id: card.id, asset: "visual" }, path });
      };
      input.click();
    }}, "⤴"));
}

function decisionOverrideControl(entry) {
  const options = (entry.options_considered || [])
    .map((o) => (typeof o === "string" ? o : o.option || o.name))
    .filter(Boolean);
  if (!options.length) return null;
  return el("select", {
    class: "decision-override",
    onchange: (e) => {
      const chosen = e.target.value;
      if (!chosen || chosen === "__label") return;
      if (confirm(`Change "${entry.subject}" to ${chosen}?`)) {
        postInbox({ stage: entry.stage || "proposal", type: "action",
          action: "override_decision", category: entry.category,
          subject: entry.subject, chosen_option: chosen });
      }
      e.target.value = "__label";
    },
  }, el("option", { value: "__label" }, "change…"),
     ...options.map((o) => el("option", { value: o }, o)));
}
```

- [ ] **Step 2: Mount the controls**

- **Script lines:** in `scriptSections(script, limit)` (and the full-script modal `openScriptModal`), append to each section row:
  `el("button", { class: "line-edit", title: "Edit line", onclick: (e) => { e.stopPropagation(); editScriptLine("script", s); } }, "✎")`
- **Filmstrip:** locate the storyboard scene-card builder (search `board.js` for where `takes`/`generating` cards are rendered) and append `sceneQuickActions(card)` inside each card element.
- **Decisions rail:** locate where `decision_log` entries render (search for `options_considered` or `rejected_because`) and append `decisionOverrideControl(entry)` to each current decision row.

Append to `board.css`:

```css
.scene-actions { display: flex; gap: 4px; margin-top: 4px; }
.scene-actions button, .line-edit { background: transparent; border: 1px solid var(--line, #333); border-radius: 4px; color: inherit; cursor: pointer; font-size: 11px; padding: 2px 6px; opacity: .7; }
.scene-actions button:hover, .line-edit:hover { opacity: 1; }
.decision-override { margin-left: 6px; font-size: 11px; background: transparent; color: inherit; border: 1px solid var(--line, #333); border-radius: 4px; }
```

- [ ] **Step 3: Manual verification**

With the server + demo project from Task 7 Step 4: pencil on a script line, all five filmstrip buttons, and a decision "change…" dropdown each append a correctly-shaped line to `inbox/messages.jsonl` (verify with `tail -f projects/backlot-demo-run/inbox/messages.jsonl`); upload round-trips a small PNG into `uploads/`.

- [ ] **Step 4: Commit**

```bash
git add backlot/ui/board.js backlot/ui/board.css
git commit -m "feat(backlot-ui): quick-actions — script edit, filmstrip, decision override"
```

---

### Task 9: Integration — scripted human against a simulated run

**Files:**
- Create: `tests/backlot/test_interactive_flow.py`
- Modify: `scripts/backlot_simulate_run.py` (add a `--interactive` pause at the assets gate)

**Interfaces:**
- Consumes: everything above — `board_bus`, `live_gate`, `POST /inbox`, board state.
- Produces: end-to-end proof the loop closes: UI action → inbox → agent hold picks it up → checkpoint transition → chat visible in board state.

- [ ] **Step 1: Write the failing integration test**

Create `tests/backlot/test_interactive_flow.py`:

```python
"""End-to-end interactive-gate flow: board POST → agent hold → checkpoint.

The "agent" here is played by lib/live_gate + direct checkpoint writes in a
thread — the same calls the real agent makes per checkpoint-protocol Step 5b.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backlot import server as server_mod
from backlot import state as state_mod
from lib import board_bus as bus
from lib import live_gate


@pytest.fixture
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(state_mod, "PROJECTS_DIR", root)
    monkeypatch.setattr(server_mod, "PROJECTS_DIR", root)
    monkeypatch.setattr(server_mod, "_summary_cache", {})
    monkeypatch.setattr(server_mod, "_PROJECTS_ROOT_STR",
                        __import__("os").path.normcase(str(root.resolve())))
    return root


@pytest.fixture
def client(projects_root, monkeypatch):
    async def no_watch():
        return None
    monkeypatch.setattr(server_mod, "_watch_projects", no_watch)
    with TestClient(server_mod.create_app()) as c:
        yield c


def _gated_project(root: Path) -> Path:
    project = root / "interactive"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(
        {"project_id": "interactive", "title": "Interactive", "pipeline_type": "cinematic"}))
    (project / "checkpoint_script.json").write_text(json.dumps(
        {"stage": "script", "status": "awaiting_human",
         "timestamp": "2026-07-20T00:00:00Z", "artifacts": {}}))
    return project


def test_proceed_click_reaches_holding_agent(client, projects_root):
    project = _gated_project(projects_root)
    bus.append_chat(project, "script", "agent", "Script v1 ready — approve?",
                    extra={"kind": "gate_presentation", "artifact_version": 1})
    result: dict = {}

    def agent_hold():
        msgs = live_gate.wait_for_messages(project, timeout_seconds=10.0, poll_seconds=0.05)
        assert msgs, "hold timed out"
        msg = msgs[0]
        result["msg"] = msg
        if msg.get("action") == "approve" and msg.get("artifact_version") == 1:
            cp = json.loads((project / "checkpoint_script.json").read_text())
            cp.update(status="completed", human_approved=True,
                      metadata={"inbox_cursor": live_gate.cursor_for(msg)})
            (project / "checkpoint_script.json").write_text(json.dumps(cp))
            bus.append_chat(project, "script", "agent", "Approved — moving to scene_plan.")

    t = threading.Thread(target=agent_hold)
    t.start()
    time.sleep(0.1)  # agent is holding; board shows it live
    assert bus.agent_live(project) is True

    res = client.post("/api/project/interactive/inbox",
                      json={"stage": "script", "type": "action",
                            "action": "approve", "artifact_version": 1})
    assert res.status_code == 200
    t.join(timeout=10)
    assert not t.is_alive()

    cp = json.loads((project / "checkpoint_script.json").read_text())
    assert cp["status"] == "completed" and cp["human_approved"] is True
    assert cp["metadata"]["inbox_cursor"]["id"] == result["msg"]["id"]

    board = client.get("/api/project/interactive/state").json()
    texts = [m["text"] for m in board["chat"]["script"]]
    assert "Approved — moving to scene_plan." in texts


def test_resume_drains_queued_messages(client, projects_root):
    """Actions clicked while the agent was away are readable on next session."""
    project = _gated_project(projects_root)
    client.post("/api/project/interactive/inbox",
                json={"stage": "script", "type": "chat", "text": "queued while offline"})
    cursor = live_gate.read_inbox_cursor(project, "script")  # None — nothing processed
    queued = bus.read_inbox(project, cursor=cursor)
    assert [m["text"] for m in queued] == ["queued while offline"]
```

- [ ] **Step 2: Run to verify current behavior**

Run: `python -m pytest tests/backlot/test_interactive_flow.py -v`
Expected: PASS if Tasks 1–4 are complete (this task's test is the integration seal; if it fails, the failure names the broken seam — fix there, not here).

- [ ] **Step 3: Add `--interactive` to the simulator**

In `scripts/backlot_simulate_run.py`: add `import argparse` support at the top of `main()` (or module bottom), parse `--interactive`, and where the script currently writes the `assets` `awaiting_human` checkpoint and then immediately completes it, guard the completion:

```python
parser = argparse.ArgumentParser()
parser.add_argument("--interactive", action="store_true",
                    help="hold real gates: wait for board Proceed clicks instead of auto-approving")
args = parser.parse_args()
```

and at each `awaiting_human` → `completed` transition:

```python
if args.interactive:
    from lib.board_bus import append_chat
    from lib.live_gate import wait_for_messages, cursor_for, read_inbox_cursor
    append_chat(project_dir, stage, "agent",
                f"[sim] {stage} ready — click Proceed on the board.",
                extra={"kind": "gate_presentation", "artifact_version": 1})
    print(f"[sim] holding {stage} gate — click Proceed on the board…")
    msgs = wait_for_messages(project_dir, cursor=read_inbox_cursor(project_dir, stage),
                             timeout_seconds=600, poll_seconds=1.0)
    approved = any(m.get("action") == "approve" for m in msgs)
    if not approved:
        print(f"[sim] no approval — stopping at {stage}")
        return
```

(keep the existing non-interactive path unchanged so the demo and existing tests still run).

- [ ] **Step 4: Verify both simulator modes**

Run: `python scripts/backlot_simulate_run.py` — completes exactly as before.
Run: `python -m backlot serve --port 4750 &` then `python scripts/backlot_simulate_run.py --interactive` — holds at the first gate, board shows "● agent listening" + [✓ PROCEED]; clicking Proceed advances the sim. Full manual loop confirmed.

- [ ] **Step 5: Run the whole suite and commit**

Run: `python -m pytest tests/backlot/ tests/lib/test_board_bus.py tests/lib/test_live_gate.py -v`
Expected: all PASS

```bash
git add tests/backlot/test_interactive_flow.py scripts/backlot_simulate_run.py
git commit -m "test(backlot): end-to-end interactive gate flow + interactive simulator mode"
```

---

## Self-Review Notes

- **Spec coverage:** data contract → Task 1; inbox endpoint → Task 2; upload → Task 3; board state (chat/liveness/artifact_version) → Task 4; live-gate agent protocol → Tasks 5–6; chat panel + Proceed → Task 7; quick-actions → Task 8; integration/simulator → Task 9. Edge cases: version-mismatch approve (protocol doc + validation), queued-offline (Task 9 test 2), malformed lines (Task 1 test), server-can't-flip-checkpoints (Task 2 governance test), traversal-safe uploads (Task 3 test).
- **Deliberate scope cuts (per spec "out of scope"):** no embedded agent session, no countdown mode, no raw-JSON artifact editor, no auth.
- **UI caveat:** Tasks 7–8 mount points reference `board.js` by function name (`renderDrawer`, `scriptSections`, `renderApprovalReview`) verified to exist; the filmstrip/decision-rail mount points are located by searching for `takes` / `options_considered` at implementation time — adapt the insertion to the local element-builder style, keep the posted payloads exactly as written.

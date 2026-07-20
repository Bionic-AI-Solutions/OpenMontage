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


def test_regenerate_asset_rejects_empty_dict_target():
    msg = {"stage": "assets", "type": "action", "action": "regenerate_asset", "target": {}}
    assert bus.validate_message(msg) is not None


def test_approve_rejects_non_int_artifact_version():
    msg = {"stage": "script", "type": "action", "action": "approve", "artifact_version": "1"}
    assert bus.validate_message(msg) is not None


def test_approve_rejects_bool_artifact_version():
    msg = {"stage": "script", "type": "action", "action": "approve", "artifact_version": True}
    assert bus.validate_message(msg) is not None


def test_approve_accepts_int_artifact_version():
    msg = {"stage": "script", "type": "action", "action": "approve", "artifact_version": 1}
    assert bus.validate_message(msg) is None


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

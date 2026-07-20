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

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


def test_read_inbox_cursor_wrong_shape_metadata(project_dir):
    (project_dir / "checkpoint_script.json").write_text('{"stage": "script", "metadata": "oops"}')
    assert live_gate.read_inbox_cursor(project_dir, "script") is None


def test_read_inbox_cursor_non_dict_checkpoint(project_dir):
    (project_dir / "checkpoint_script.json").write_text("[1, 2, 3]")
    assert live_gate.read_inbox_cursor(project_dir, "script") is None

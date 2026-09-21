# Backlot Interactive Board — Design

**Date:** 2026-07-20
**Status:** Approved by user (brainstorming session)
**Owner:** Backlot (`backlot/`), checkpoint protocol (`skills/meta/checkpoint-protocol.md`)

## Problem

The Backlot board is a read-only observer. All decisions — gate approvals,
revisions, provider choices — flow through the agent chat (terminal). The user
wants to steer production **from the board**: a chat interface at each stage,
one-click acceptance of the agent's recommendation, and inline tweaks
(script lines, scene plan, assets, logged decisions) — without giving up the
audit trail or the agent's role as sole orchestrator.

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Interaction scope | Gate decisions + feedback **plus** inline tweaks (script line edits, scene plan actions, per-asset actions, decision overrides) |
| Control surface | **Per-stage chat panel** on the board; quick-actions echo into the chat thread |
| Agent pickup | **Agent waits & auto-continues**: holds the gate with a background watcher, continues the moment a board action arrives |
| Gate model | **Hard gates, one-click proceed**: nothing runs without user input, but accepting is a single [Proceed] click; chat handles overrides |
| Architecture | **Approach A — disk-mediated message bus** (rejected: embedded agent session in Backlot; chat-only relay without structured actions) |

## Core invariant (unchanged in spirit, narrowed in letter)

The agent is the **sole writer** of checkpoints, artifacts, and chat
transcripts. The Backlot server's invariant changes from "never writes to
project directories" to "writes **only** `inbox/` and `uploads/`". The server
never flips a checkpoint: a [Proceed] click becomes an `approve` inbox action
that the *agent* converts into `human_approved=True`. `lib/checkpoint.py`'s
gate enforcement is untouched.

## 1. Data contract

Two new per-project append-only JSONL files. Both live inside
`projects/<id>/`, so the existing watchfiles → SSE pipeline and ▶ REPLAY
inherit them for free.

### `projects/<id>/inbox/messages.jsonl` — written only by the server

One JSON object per line. `id` and `ts` are stamped server-side.

```json
{"id": "m-8f2a", "ts": 1752988800.1, "stage": "script", "type": "chat",
 "text": "make the hook punchier, and mention the price earlier"}

{"id": "m-9c11", "ts": 1752988912.4, "stage": "script", "type": "action",
 "action": "approve", "artifact_version": 2}

{"id": "m-a044", "ts": 1752989020.9, "stage": "assets", "type": "action",
 "action": "regenerate_asset", "target": {"scene_id": "sc3", "asset": "visual"},
 "note": "less stocky, more hand-drawn"}
```

`type` is one of:

- **`chat`** — free text; the agent interprets it with full stage context.
- **`action`** — structured and deterministic. Vocabulary:
  - `approve` (carries `artifact_version`), `abort`
  - `edit_script_line` (`line_id`, `new_text`)
  - `scene_note` (`scene_id`, `note`), `reorder_scenes` (`order`), `drop_scene` (`scene_id`)
  - `regenerate_asset` (`target`, optional `note`), `swap_provider` (`target`, optional `provider`), `replace_asset` (`target`, `path` under `uploads/`)
  - `override_decision` (`category`, `subject`, `chosen_option`)

Money-spending verdicts (approve/abort) are **always** `action`, never
inferred from prose.

**`artifact_version`** is defined as the number of archived checkpoints for
the stage in `projects/<id>/history/` plus one — i.e., it increments every
time the agent re-presents a revised artifact. `load_board_state` exposes it
per stage; the UI stamps the version it is currently displaying into every
`approve` action.

### `projects/<id>/chat/<stage>.jsonl` — written only by the agent

The stage's chat thread: gate presentation (artifact digest, review findings,
cost snapshot, recommendation), replies to user messages, confirmations of
applied tweaks. Quick-actions the user takes are echoed here by the agent so
the thread is the complete story of the stage.

### Consumption protocol

The agent records the last-processed inbox message id as
`metadata.inbox_cursor` on the current stage checkpoint. A crashed or resumed
session never re-applies or misses a message — same idempotent-resume
philosophy as `metadata.partial_progress`.

## 2. Backlot server

Three additions to `backlot/server.py`:

1. **`POST /api/project/{id}/inbox`** — validates against the action
   vocabulary (bad shape → 400), stamps `id`/`ts`, appends one line to
   `inbox/messages.jsonl`. Uses `_safe_project_dir` for path safety. The only
   general write endpoint.
2. **`POST /api/project/{id}/upload`** — saves a replacement media file under
   `projects/<id>/uploads/`, returns its path for use in a `replace_asset`
   action. Size-capped; extension allowlist (media types only).
3. **Board state additions** — `load_board_state` returns each stage's
   `chat/<stage>.jsonl` messages plus an `agent_liveness` flag derived from a
   heartbeat file (`projects/<id>/.agent_heartbeat`, mtime fresher than ~30s
   ⇒ live). No new SSE machinery needed.

## 3. Board UI

- **Stage chat panel** — clicking a stage on the rail opens its thread:
  agent's gate presentation at top, conversation below, composer at bottom.
  When the stage is `awaiting_human`, two persistent buttons sit above the
  composer: **[✓ Proceed as recommended]** (visual default) and **[✕ Abort]**.
- **Quick-actions in context** — pencil icon on a script line → inline edit
  (`edit_script_line`); filmstrip cards → note / regenerate / provider swap /
  drop; decision-rail entries → "change…" listing `options_considered`
  (`override_decision`). Each posts a structured action and appears in the
  stage chat.
- **Liveness indicator** — "● agent listening" vs "○ agent offline — messages
  will queue". Honest async: actions always land in the inbox; the indicator
  only tells the user whether pickup is immediate or on next resume.

## 4. Agent-side protocol — the "live gate"

New mode in `skills/meta/checkpoint-protocol.md`; the existing turn-based
flow remains as fallback. When a gated stage completes, the agent writes the
`awaiting_human` checkpoint as today, then instead of ending its turn:

1. Writes its gate presentation to `chat/<stage>.jsonl`.
2. Starts a cheap background watcher on `inbox/messages.jsonl` (file
   watch/poll — no token-burning busy-wait) and touches
   `.agent_heartbeat` every ~15s.
3. On a new inbox line, dispatches:
   - **`approve`** → consumed only if its `artifact_version` matches the
     currently presented artifact version; re-writes checkpoint `completed`
     with `human_approved=True`; advances. On version mismatch (an edit
     landed in between) the agent asks in chat to confirm against the new
     version.
   - **`abort`** → stops the pipeline; final chat message states where
     things stand.
   - **Structured tweak** → applies to the artifact; appends a
     `decision_log` entry when it changes a logged decision (existing
     re-log rule, same `(category, subject)` pair); confirms in chat;
     **re-presents the gate**. A tweak never implies approval.
   - **`chat`** → interprets with stage context; revises the artifact per
     the stage director skill if asked; re-reviews; re-presents. Identical
     semantics to a typed terminal reply.
4. Advances `metadata.inbox_cursor` after each processed message.

**Two channels, one gate.** A terminal reply during a hold is processed the
same as an inbox message — first input wins, both audited. Board approval and
chat approval are equivalent.

**Graceful degradation.** Max hold duration (default ~30 min, configurable).
On timeout: agent posts "still waiting — I'll apply your board actions next
session" to the stage chat, ends its turn, heartbeat goes stale, board shows
queued mode. On next session, the resume protocol drains queued inbox
messages **before** re-presenting the gate. Nothing clicked while the agent
was away is lost.

## 5. Edge cases

- **Message for a passed stage** (e.g. script comment while `assets` runs):
  agent acknowledges in chat, quantifies the rewind ("re-runs script →
  scene_plan → assets, ~$X — proceed?"), and only rolls back on
  confirmation. Checkpoint history archiving already supports rewinds.
- **Conflicting rapid actions** (tweak then approve): inbox is processed
  strictly in order; `artifact_version` stamping ensures an approve only
  binds to the artifact the user actually saw.
- **Multiple tabs**: appends are atomic single-line writes; safe.
- **Schema-breaking edits**: revised artifacts are validated against
  `schemas/artifacts/` like any agent-produced artifact; failures get a chat
  reply explaining why, artifact untouched.
- **Server down mid-run**: agent's watcher sees silence; terminal channel
  still works. The board remains an observer that can never block
  production.

## 6. Testing

- **Unit:** inbox message validation; action vocabulary round-trip;
  `inbox_cursor` resume semantics; assert server *cannot* flip checkpoints
  (gate violation still enforced).
- **Integration:** extend `scripts/backlot_simulate_run.py` with a scripted
  human that posts approve/tweak/chat actions against a simulated run;
  assert checkpoint transitions, chat transcripts, replay integrity.
- **Manual:** click through the demo run end-to-end.

## Out of scope

- Embedded agent session inside Backlot (Approach B) — the inbox makes this
  addable later without rework.
- Countdown auto-proceed and fully-autonomous steerable modes — the gate
  model here is strictly hard-gate + one-click.
- Full artifact editing in the UI (raw JSON editing).
- Auth/multi-user; Backlot remains a local single-user tool.

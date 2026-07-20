# Backlot — the living storyboard

A local board that shows a production happening — and, at gates, takes your
input: each stage has a chat thread plus one-click [Proceed]/[Abort]. The
server's only writes are `inbox/` (your messages/actions) and `uploads/`;
the agent remains the sole writer of checkpoints, artifacts, and chat.

```bash
python -m backlot open <project-id>   # start server if needed + open browser
python -m backlot open                # library view (all projects)
python -m backlot serve --port 4750   # run the server in the foreground
```

## How it stays live

No agent involvement in the transport. A `watchfiles` watcher on `projects/`
publishes change notifications over SSE; the browser refetches board state.
State sources:

| Board element | Disk source |
|---|---|
| identity / rail order | `project.json` + `pipeline_defs/<type>.yaml` |
| stage states, gates, versions | `checkpoint_<stage>.json` + `history/` |
| script card / modal | `artifacts/script.json` |
| filmstrip cards | `scene_plan × script × asset_manifest` join |
| generating shimmer, activity | `events.jsonl` (written by `BaseTool` instrumentation) |
| cost meter | checkpoint `cost_snapshot` |
| renders | `renders/*.mp4` (+ root-level mp4 heuristic) |
| stage chat threads | `chat/<stage>.jsonl` (written by the agent) |
| your messages/actions | `inbox/messages.jsonl` (written by the server) |

Projects without checkpoints degrade gracefully to a "what the watcher
found" view — media, snapshots, renders.

**Replay**: a completed run can be scrubbed end-to-end (▶ REPLAY RUN on the
board) — reconstructed from checkpoint history and event timestamps.

Try it without a real production:

```bash
python scripts/backlot_simulate_run.py          # live demo run (~1 min)
python -m backlot open backlot-demo-run
```

Design doc: `internal/design/LIVING_STORYBOARD.md`.

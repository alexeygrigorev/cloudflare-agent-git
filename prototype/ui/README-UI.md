# Agent Branches — change story review UI (A06)

Plain static screens for reviewing what concurrent coding agents did:
`index.html` (overview of all agent tasks) and `task.html?id=…` (one agent's
change story). No frameworks, no build step, no dependencies — HTML, CSS and
vanilla JS only. The Worker is expected to serve this folder as static assets
later; today it runs from any static file server.

## Open with fixtures (no server needed for data)

The UI can demo itself from `fixtures/` (`?fixture=1`):

```bash
cd prototype/ui
python3 -m http.server 8765
# then open:
#   http://localhost:8765/index.html?fixture=1
#   http://localhost:8765/task.html?id=task-0001&fixture=1
```

Any static file server works. Opening `index.html` directly from disk
(`file://`) does **not** work, because browsers block `fetch()` of local JSON
from `file://` pages — the folder must be served over HTTP.

The fixtures show all four pair states with three agents:

- `claude-0001` ↔ `codex-0002`: **conflict** (both changed
  `prototype/src/index.ts`; warning acknowledged by `claude-0001`)
- `claude-0001` ↔ `grok-0003`: **unknown — not safe** (compared, but
  `claude-0001`'s last passing test run was recorded for an older change,
  not its latest one)
- `codex-0002` ↔ `grok-0003`: **clean — tests ran** (compared at the current
  changes; both sides recorded passing test runs for exactly those changes)

Task pages: `task-0001` shows a test run that no longer matches the latest
change (stale evidence → unknown), `task-0002` a passing run at the latest
change, `task-0003` a passing docs-adjacent run.

The outline **not checked** badge appears whenever a pair has no comparison
at the current pair of changes — e.g. right after a fresh push, or when an
agent has not pushed anything yet.

## Open against `wrangler dev`

```bash
cd prototype
npx wrangler dev --local        # http://localhost:8787
```

Then serve `prototype/ui/` from any static server (as above) and open:

```
http://localhost:8765/index.html?api=http://localhost:8787
http://localhost:8765/task.html?id=task-0001&api=http://localhost:8787
```

Caveat: the Worker does not send CORS headers yet, so a browser may block
cross-origin calls from `:8765` to `:8787`. Same-origin use (no `?api=`)
works once the Worker serves this folder as static assets — that integration
is planned on the Worker side and will land with the expected branch merge.

## Data sources and honest fallbacks

| Screen | Endpoint | Notes |
| --- | --- | --- |
| `index.html` | `GET /status` | agents, heads, warnings, radar log |
| `task.html` | `GET /tasks/:id` (+ `GET /status`) | task detail, agent record; status supplies warnings for this agent |

The current L1 scaffold does not yet carry `intent`, `baseSha`, `pushLog`,
warning acknowledgement (`acknowledgedBy`/`acknowledgedAt`) or
`testEvidence`. All are optional: when missing, the UI shows plain
“not recorded / not stated” fallbacks and treats safety as **unknown**, never
as safe. Fixtures demonstrate the richer shapes the contract is expected to
grow into.

## Safety labels (the important rule)

Pair states are derived client-side from `/status`:

- **conflict** — an active warning covers the pair.
- **clean — tests ran** — only when the pair was compared at the current heads
  *and* both agents have a passing test run (`exit 0`) recorded for exactly
  those heads.
- **unknown — not safe** — compared without conflict, but test evidence is
  missing, failing, or recorded for an older change.
- **not checked** — no comparison at the current pair of heads yet.

Unknown is never rendered as green/safe; badges always carry their text
label, never color alone.

## Review decisions

`task.html` has a review decision area (approve / request changes / note).
Decisions are stored in `localStorage`, one key per task id, in this browser
only — nothing is sent to the server. Clearing is one click.

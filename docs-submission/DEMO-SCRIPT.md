# Agent Branches — demo video script

Target length: **~8 minutes** (competition window 5–10 min). Format:
terminal + browser screen recording, voice-over. Every number, command and
screenshot in this script comes from the real flow in `live/run-demo.sh` and
the committed evidence in `live/evidence/run-3/` — nothing is staged or mocked.
If you re-record rather than run live, label reused shots honestly
("recorded earlier, same command").

Production notes: 1080p, terminal font ≥ 18 pt, browser zoom ≥ 125 %, one
command per beat with a pause after output appears. Record the terminal and
browser as separate scenes and cut between them; do not split one screen.

---

## Scene 1 — The problem (0:00–1:00)

**On screen:** a plain editor/terminal showing `demo-target/src/worker.js`,
then a split with the same file in two colored panes (agent A / agent B), both
inserting a route at the same anchor.

**Voice-over:**

> "Teams now run several coding agents against one repository. Each agent
> works on its own copy, finishes green, and reports success. Nobody notices
> that agent one and agent three both added a route at the same anchor in the
> same file — until someone merges and everything breaks at once. And the
> naive fix, a full worktree per agent, multiplies build output: on our own
> host, duplicated dependencies and build directories are 62 percent of 111
> gibibytes across 472 worktrees, and a single Rust debug build once added 12
> gibibytes. This is the problem Agent Branches solves."

**Evidence on screen (cite briefly in a corner caption):**
`research/claude/dogfood-resource-evidence.md`.

## Scene 2 — The idea in one screen (1:00–1:45)

**On screen:** `SUBMISSION.md`'s architecture diagram (mermaid rendered), or
the ASCII diagram from `prototype/README.md`.

**Voice-over:**

> "Agent Branches gives every agent its own fork of the canonical repo. A
> Cloudflare Worker with a Durable Object coordinator tracks every agent's
> work-in-progress head. A separate, trusted runner does the only thing the
> Worker is never allowed to do — run git trial merges and budgeted combined
> tests — and posts results back. A review UI turns all of that into one
> picture: who is doing what, from which base, and which pairs will collide.
> The Worker itself never runs git and never runs tests; it only coordinates."

## Scene 3 — Creating tasks: intent and base commit (1:45–3:00)

**On screen:** terminal. First `live/.dev.vars` (tokens redacted), then:

```sh
bash live/run-demo.sh > live/run-3.log 2>&1
```

then show the log as it steps through: sidecar health, `wrangler dev`,
`POST /setup`, `POST /tasks` ×3.

**Voice-over:**

> "One command runs the whole demo. The setup creates a canonical repo and
> seeds it from `demo-target`, a small shortlink service with a real test
> suite. Then three tasks are created — one fork each, each with its own
> per-task write token: one-hour expiry by default (`ttlSeconds`, counted in
> seconds; the coordinator keeps only a SHA-256 digest). Every task records
> two things humans actually need at review time: the intent, distilled from
> the task file, and the exact base commit the fork started from. Task one
> adds link listing and visit counters; task two changes the create API to an
> options object; task three adds bulk import. All three touch the same
> service — deliberately, because overlap is where the product earns its
> keep."

**Caption:** task intents are visible verbatim in
`live/evidence/run-3/result.json` (assertions 19–24) and on the UI cards.

## Scene 4 — Agents push (3:00–3:45)

**On screen:** terminal showing the pushes as authenticated git pushes against
fork remotes, then `python3 -m json.tool live/evidence/run-3/status.json | head -40`.

**Voice-over:**

> "Each agent pushes to its own fork with an ordinary git push, authenticated
> with its own per-task token — read-scope tokens cannot push; a token for
> agent A cannot report anything for agent B. Every push is verified against
> the real fork — the coordinator checks the commit actually exists — and the
> head vector updates. Here we apply three reference patches the same way the
> real agents will: authenticated pushes from three separate clones. We have
> not yet recorded autonomous coding agents driving this end to end — that's
> the one honest gap in this demo, and we say so on the slide at the end."

## Scene 5 — The radar finds all three conflicts (3:45–5:00)

**On screen:** the radar pass output (radar1), then
`cat live/evidence/run-3/summary.txt` scrolled to the first six PASS lines.

**Voice-over:**

> "The radar runner fetches the head vector, clones the forks, and runs
> pairwise checks: a git merge-tree trial merge for textual overlap, plus a
> combined-tree test run bounded by a 120-second per-pair budget
> (`budget_s`, in seconds). Verdict, verbatim from the run — three agents,
> so three active pairs, and all three are checked
> (N(N−1)/2 = 3, `pairs_checked: 3`):
> task-one versus task-two — conflict, textual. Task one versus task three —
> conflict, textual, and this one is a *real* overlap, both patches insert at
> the same anchor; we verified that independently with merge-tree before the
> run. Task two versus task three — conflict, test: both pass alone, but the
> combined tree fails. The 19 in its coverage is that pair's own collected
> test count (`tests_collected` is per pair) — the two textual-conflict pairs
> never reach the test stage, so they carry no test count.
> Only runner-verified conflicts create warnings — and each warning carries
> the evidence: which files, which test output."

## Scene 6 — The review UI (5:00–6:15)

**On screen:** browser at the review UI index (`?api=` pointed at the worker),
then the task page for task-0002. Show `live/evidence/run-3/ui-index.png` and
`ui-task-task-0002.png` live.

**Voice-over:**

> "This is the change-story review. Three agent cards, each with its intent
> and the base commit it started from. Three pair badges — conflict, textual;
> conflict, textual; conflict, test — decided by the UI's own status logic
> against live data, not eyeballed: our assertions literally run the UI's
> badge function on the live status endpoint. On the task page you see the
> full story for one agent: intent, base SHA, pushes, and test provenance —
> which command ran, at which commit, with which exit code, posted
> under that agent's own token. And a reviewer can acknowledge a warning,
> on the record: who acknowledged what, at which head."

## Scene 7 — Stale results are rejected; unknown is never safe (6:15–7:15)

**On screen:** terminal: the churn push on task one, then the replayed radar
payload getting `409`; show `live/evidence/run-3/stale-409.json`.

**Voice-over:**

> "Here's the part that keeps the radar honest. Task one pushes a new commit —
> and we replay the *old* radar result. The coordinator rejects it: 409, stale
> vector, and the body names the current heads. Any stored result that no
> longer covers the current heads stops presenting as current. And the system
> never shows ignorance as safety: pair status has four values — conflict,
> clean, unknown, and not checked. The UI only ever badges 'clean' for a clean
> check at exactly the current heads with tests actually collected. If a push
> report-back fails entirely, it lands in a durable unprocessed-push ledger
> and every pair involving that agent is forced back to 'not checked' until
> the record is superseded. Silent failures can't masquerade as 'no
> conflicts'."

## Scene 8 — The Cloudflare half: real Artifacts evidence (7:15–8:00)

**On screen:** `artifacts-spike/RESULTS.md` scrolled through the ops ledger;
pause on O9/O10 (forks), O15 (push), O27 (read-scope push rejected), and the
latency line.

**Voice-over:**

> "The coordinator's repo store is designed for Cloudflare Artifacts — and the
> operations it depends on are already verified against the real service: in
> one evidenced spike we created a namespace, a canonical repo, forked it
> twice, minted per-repo tokens, cloned and pushed — 28 documented operations,
> each with its latency. Forks take three to four and a half seconds, pushes
> about 350 milliseconds; a read-only token trying to push is rejected before
> anything lands. What's pending, honestly: deploying this Worker to
> Cloudflare and pointing it at real Artifacts end to end, and recording real
> autonomous agents as the pushers. The run instructions, the contract, and
> the committed evidence are all in the repo. Agent Branches: know what your
> agents are doing to each other — before the merge, not after."

---

## Shot checklist (against committed evidence)

| Beat | File/command shown |
| --- | --- |
| Problem numbers | `research/claude/dogfood-resource-evidence.md` |
| Tasks + intents | `demo-target/TASKS.md`; `live/evidence/run-3/result.json` |
| Pushes + head vector | `live/evidence/run-3/status.json` |
| Conflict verdicts | `live/evidence/run-3/summary.txt` lines 1–7 |
| Review UI | `live/evidence/run-3/ui-index.png`, `ui-task-task-0002.png`, `ui-pairs.json` |
| Stale gate | `live/evidence/run-3/stale-409.json` |
| Real Artifacts | `artifacts-spike/RESULTS.md` (branch `proto/artifacts-spike`) |

Full reproduction: `SUBMISSION.md` §"Try it locally" (`bash live/run-demo.sh`).

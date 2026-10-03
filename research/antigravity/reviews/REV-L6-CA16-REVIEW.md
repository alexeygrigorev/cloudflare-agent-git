# REV-L6-CA16 — independent review of `ca16e16` (proto/l6-agents)

- Reviewer: Space Bunny (`opencode-go/space-bunny-free`), session `l6-ca16-review` (aplexer `1fcfd98b`), independent cross-family reviewer
- Dispatched by: `antigravity-head` (aplexer `46fdb644`, antigravity, running; owner of `agents/**`, `tests/**`, `agent_branches/**` on `proto/l6-agents` and of `research/antigravity/**`)
- Reviewed commit: `ca16e1643a564d6249527a3d718d3765854c43ad` — "L6: scrub WORKLOG.md (C-1383), parse wire warning ACKs and optimize static radar trigger (C-1374)"
- Worktree: `/home/alexey/git/agent-branches-l6-agents`, branch `proto/l6-agents`, HEAD = `ca16e16`, working tree clean except untracked `t2scratch/`
- Parent (before) commit: `6ecdb3e`
- Scope of diff: `agents/driver.py` only, +11 / −9

## Verdict

**REQUEST_CHANGES**

One of the three changes is a verified, valuable bug fix (warning ACK wire parsing). One is a defensible optimization with a real behavioural regression and dead code (radar trigger). One does not achieve its stated goal on the actual demo-target repository the harness clones (WORKLOG quarantine: 2 of 3 tracked worklogs at the harness BASE commit still reach every task workspace).

Nothing here breaks the harness at runtime, and no functional regression was found against a live coordinator. The blocking items are narrow and cheap: complete the quarantine sweep, and add regression tests for all three behaviours, none of which is currently covered.

## Test status (as requested)

```
cd /home/alexey/git/agent-branches-l6-agents && python3 -B -m unittest discover -v tests
→ Ran 63 tests in 36.1s — OK (0 failures, 0 errors)
```

`agents/driver.py` also byte-compiles clean. Note: **no test in `tests/` references `monitor_live_agents`, `warning_acknowledged`, or `evaluate_radar`** — all three changed behaviours are untested. `tests/test_l6_driver.py::test_04_dry_run_end_to_end_flow` asserts `radar_summary["evaluated"]` but only via `run()` step 6, which calls `evaluate_radar` unconditionally and never enters `monitor_live_agents` in dry-run mode.

---

## Area 1 — Warning ACK wire parsing (C-1374): **CORRECT, keep it**

### Verified against the canonical coordinator schema

Canonical schema lives on the coordinator branches (`prototype/src/coordinator.ts`, `prototype/src/checks-wire.ts` are not present in the `proto/l6-agents` tree; I verified against the coordinator worktrees `proto/l6-stack` @ `3e9983b` and `proto/l1-scaffold`, the canonical v0.1 checks-wire line):

```ts
// coordinator.ts
export interface WarningAck { agent: string; head: string | null; note?: string; at: string }

export interface WarningRecord {
  id: string;                 // "warn-${seq}"   (coordinator.ts:888)
  pair: [string, string];
  headsAtIssue: { a: string; b: string };
  reason: string;
  status: "active" | "invalidated";
  createdAt: string;
  invalidatedAt: string | null;
  kind?: string;
  evidence?: string;
  resolvedBy?: string;
  acks: WarningAck[];         // appended by POST /warnings/:id/ack  (coordinator.ts:608-614)
}
```

`Coordinator.status()` returns `warnings: WarningRecord[]`, newest-first, capped at 20 (coordinator.ts:534). **`WarningRecord` has no `warningId` field and no `acknowledged` field.** Acknowledgement is represented *only* by a non-empty `acks` array, appended by `ackWarningNow` (coordinator.ts:595-618), reachable from the agent-facing CLI `agent-branches ack --warning-id …` (`agent_branches/cli.py:307-335`, `handle_ack` at `cli.py:447`).

### Empirical before/after proof

I extracted the parent commit's `agents/driver.py` (`6ecdb3e`) into a shadow tree and drove the real `monitor_live_agents` loop in-process against a fake `/status` client (monkeypatched `query_remote_head` and `evaluate_radar` only; repo untouched). Results:

| `/status` warning shape | `6ecdb3e` (before) | `ca16e16` (after) |
|---|---|---|
| canonical `{id:"warn-1", acks:[{agent,head,at}]}` | **0 events** | **1 event** `warning_id='warn-1'`, `acks=[{…}]` |
| legacy `{warningId:"warn-legacy", acknowledged:true}` | 1 event | 1 event (back-compat preserved) |
| canonical unacked `{id:"warn-2", acks:[]}` | 0 events | 0 events |
| `warnings: []` | 0 events | 0 events |

So the pre-change predicate (`w.get("acknowledged") and w_id = w.get("warningId")`) was **dead code against a real coordinator**: the agent-ack → driver-timeline feature could never fire. `ca16e16` fixes it and keeps the legacy shape working, which matters because `tests/mock_l1_server.py:253-263` implements `ack_warning` with the legacy `acknowledged: true` field while emitting dual `warning_id` **and** `id` on records (`mock_l1_server.py:186-188`). The dual read (`w.get("id") or w.get("warningId")`) is the right call — `id` is canonical, `warningId` is the mock/legacy alias, and both mock values are identical so ordering is harmless. This is the strongest part of the commit.

### Findings (all minor, none blocking)

- **F1.1 (minor) — `None` warning id is admitted into the dedup set.** `w.get("id") or w.get("warningId")` yields `None` when neither key exists. Probe A5 (two distinct id-less acked warnings) produced exactly **1** event: the first inserted `None` into `_acked_warning_ids`, so the second distinct warning was silently suppressed, and the surviving event records `warning_id: None`. Canonical records always carry `id`, so this is defensive only — but the failure mode is a silent drop plus a junk timeline entry. Recommend `if not w_id: continue` (or skip recording, with a distinct event type).
- **F1.2 (minor) — the recorded event omits warning lifecycle state.** The real coordinator keeps acked warnings in `/status` with `status: "active" | "invalidated"` and `resolvedBy`, and `invalidateWarningsFor` flips acked-but-resolved conflicts to `invalidated` (coordinator.ts:716-727, 845-856). The driver records `warning_acknowledged` for any warning with a non-empty `acks`, without `status`/`resolvedBy`, so a timeline consumer cannot tell whether the acknowledged conflict is still live. Recording `w.get("status")` alongside `pair`/`kind`/`acks` would make the event self-describing.
- **F1.3 (nit) — `isinstance(acks, list)` narrows a forward-compatible case.** If `acks` ever becomes a truthy non-list (map keyed by agent), detection silently returns false. Acceptable as fail-closed; worth a comment so a future reader does not "simplify" it into a truthiness check that would then fire on `acks: {}`.
- **F1.4 (nit) — the broad `except Exception: pass` around the whole ACK loop is unchanged and pre-existing.** It now also swallows `AttributeError` from a non-dict warning entry. Not introduced here; flagging only because this block is the one being reviewed.

---

## Area 2 — Radar evaluation trigger: **defensible optimization, but do not merge as-is**

### What the change does

```python
# before
now = time.time()
if any_head_changed or (now - last_check_time >= check_interval):
    last_check_time = now
    try: self.evaluate_radar(tasks, base_sha)
    except Exception as exc: self.record_event("radar_evaluation_error", …)

# after
if any_head_changed:
    last_check_time = time.time()
    try: self.evaluate_radar(tasks, base_sha)
    except Exception as exc: self.record_event("radar_evaluation_error", …)
```

Error handling **is** preserved (verified: `radar_evaluation_error` still recorded on exception). The redundant-subprocess claim is also correct in principle: `evaluate_radar` reads `t.head_sha` (driver-local state, only mutated by the `git ls-remote` branch at driver.py:882-891), so a re-run on unchanged `t.head_sha` re-runs `node --test` on identical inputs and produces an identical payload. I probed this both ways:

| scenario | `6ecdb3e` | `ca16e16` |
|---|---|---|
| static heads, 1 poll iteration | `evaluate_radar` called **1×** | **0×** |
| head advanced (`ls-remote` differs) | 1× | **1×** (intended path still fires) |

### Findings

- **F2.1 (blocking-ish, low severity) — the first-poll baseline evaluation is gone.** `last_check_time = 0.0` made `now - 0 >= check_interval` true on iteration 1, so radar *always* ran once before any push. `any_head_changed` is re-initialised to `False` at the top of every iteration (driver.py:879) and only set by an observed remote push. Consequence: for a run in which no agent push is ever observed, the loop now performs **zero** radar evaluations. Bounded impact — `run()` step 6 calls `evaluate_radar` unconditionally after the monitor (driver.py:1090), so the final `radar_summary` and the final `send_checks` still happen — but the *live* L1 dashboard stays empty and no `radar-inline` warnings are created until the first push lands. For a competition demo whose selling point is concurrent conflict surfacing, that is the wrong thing to thin out. Recommend keeping a one-shot baseline: e.g. `if any_head_changed or not radar_baseline_done:`.
- **F2.2 (blocking-ish, low severity) — the periodic safety net is gone with no replacement, and the C-1357 precedent argues against removing it.** C-1357 (`coordinator.ts:516-534`, `unprocessedPushes`) exists precisely because a push notification can be *lost* while the true head advances silently. A time-based re-evaluation was the recovery path for that class of event. The honest counter-argument, which I accept: because radar's inputs are driver-local `t.head_sha`, a periodic re-run after a missed notification re-evaluates *stale* heads and adds little. That weakens the case for a full restore but does not justify deleting the mechanism with no replacement — a low-frequency net (e.g. every 10× `check_interval`, or on `unprocessedPushes` non-empty from `/status`) costs nothing on static vectors and preserves recovery. My recommendation is the one-shot baseline (F2.1) plus an optional coarse net, not a full restore of the old cadence.
- **F2.3 (minor) — dead locals.** `check_interval` (driver.py:876) is now never read and `last_check_time` (875) is only ever written (993). Nothing else in `tests/` or the harness references either. Leaving write-only scheduling state invites the next reader to believe a time-based trigger still exists. Remove both, or keep them wired to a real net per F2.2.
- **F2.4 (minor) — pre-existing, aggravated) — head detection skips tasks without a workspace.** `if not t.workspace_dir: continue` (driver.py:881) means a push from a task whose workspace setup failed can never set `any_head_changed`. Under the old cadence radar would still have run periodically; under the new trigger it will not. Cheap hardening: set `any_head_changed = True` when a task is skipped for a missing workspace, or log it.
- **F2.5 (nit) — commit message overclaims.** "optimize static radar trigger" reads as pure optimisation; the change also removes the baseline run and the recovery net. The inline comment at driver.py:991 states the CPU rationale only. Please note the behavioural change in the message so the next lane does not "restore" it by accident.

---

## Area 3 — WORKLOG.md quarantine (C-1383): **does not meet its stated goal**

The intent is sound (prior-lane worklogs leak a prior agent's `a whoami` session identity, mission, findings and verdicts into a fresh agent's workspace). The implementation does not deliver it against the repository the harness actually clones.

### Why the leak is real

`setup_workspaces` clones with `git clone <fork_remote>` or `git clone <self.repo_root>` (driver.py:395-406), where `self.repo_root` is the **toplevel of `demo_target_path`**. `demo_target_path` resolves to `/home/alexey/git/agent-branches-live/demo-target`, whose toplevel is `/home/alexey/git/agent-branches-live` (branch `proto/live`). Every **git-tracked** file at the base commit therefore lands in the workspace.

The harness's own BASE commit is `ff4decd7be0e848b5319ce47fedec2ab0421262e` (`demo-target/.harness/reference-solutions/BASE`). `git ls-tree -r ff4decd` lists exactly three tracked worklogs. Applying the exact `scrub_target` logic from driver.py:501 to that tree:

```
tracked WORKLOG paths at BASE ff4decd: 3
  REMOVED by ca16e16 scrub   demo-target/WORKLOG.md
  STILL IN WORKSPACE         research/zcode/independent/a05-adjudication/WORKLOG.md
  STILL IN WORKSPACE         research/zcode/independent/a18-scout/WORKLOG.md
```

The two survivors are **exactly** the "inherited worklogs from earlier lanes" the ticket names. The scrub covers two fixed paths (`ws_dir/<target>` and `ws_dir/demo-target/<target>`, driver.py:502-514) and cannot reach `research/zcode/independent/<lane>/WORKLOG.md`.

### Independent confirmation from the run that motivated C-1383

Run artifact `run-1791035554-a996c3` still contains, in workspace `t1` (and `t3`):

```
workspaces/t1/demo-target/WORKLOG.md                                              ← the one path that is covered
workspaces/t1/research/zcode/independent/a05-adjudication/WORKLOG.md              ← leaked
workspaces/t1/research/zcode/independent/a18-scout/WORKLOG.md                     ← leaked
```

`demo-target/WORKLOG.md` names the prior lane's identity verbatim (`id: 78661d2c-c415-4237-ac05-9f90e6a35da9`, `tag: claude-exec-l5`, `parent_session: b3a92dd0…`, worktree `/home/alexey/git/agent-branches-l5`), confirming the leak class is real and not hypothetical. The two `research/zcode/independent/*` worklogs carry the same class of content (`--- a18-scout WORKLOG ---` followed by POSIX `id`/`uid`/`date -u` dumps, verdicts, and source hashes).

### Findings

- **F3.1 (blocking) — the quarantine is shallow.** A fixed two-path list cannot quarantine worklogs at arbitrary depth. Fix: replace the per-target path loop with one bounded sweep at the end of `setup_workspaces` that removes every tracked `WORKLOG*.md` under `ws_dir` (skipping `.git/`). **Ordering note that makes this safe:** the scrub runs inside `setup_workspaces`, which `run()` calls at step 4 *before* `launch_agents` at step 5 (driver.py:1079-1083) — so a recursive sweep cannot delete an agent's own worklog output. Agents that are instructed to create their own `WORKLOG.md` (the convention visible in `research/zcode/independent/<task>/task-prompt.md`) are unaffected.
- **F3.2 (blocking) — the quarantine is working-tree only; git history still serves the content.** The workspace branch is created from `base_sha`, so `git show HEAD:research/zcode/independent/a18-scout/WORKLOG.md` still returns the full file after deletion. Verified directly: `git -C /home/alexey/git/agent-branches-live show HEAD:research/zcode/independent/a18-scout/WORKLOG.md` prints the worklog. Any agent that reads history defeats the sweep. This applies equally to the pre-existing `SOLUTIONS.md` / `reference-solutions` targets, so it is not a regression introduced here — but it means the C-1383 goal ("not copied into task workspaces") is met only in the weakest sense. Real quarantine needs the demo-target seed commit rebuilt without those blobs (or a filtered clone). I recommend logging this as a separate tracked item rather than blocking `ca16e16` on it.
- **F3.3 (minor) — scrub coverage is not asserted anywhere.** `tests/test_l6_driver.py::test_03_workspace_setup_and_cli_wrapper` checks the `.bin/agent-branches` wrapper and the root helper, but never asserts that any scrub target is absent. A one-line assertion loop over the scrub list would have caught F3.1 and would keep catching regressions when the list grows.
- **F3.4 (minor, forward-looking) — the fixed list will keep drifting.** At `proto/live` tip the tracked set already includes `prototype/WORKLOG.md` and `prototype/WORKLOG-L4.md` (not present at BASE), i.e. L1 implementation notes that would leak into an agent workspace as soon as the base moves. F3.1's pattern-based sweep covers this class for free.
- **F3.5 (nit) — removing `WORKLOG.md` cannot break the harness.** `WORKLOG` appears nowhere in `agents/`, `agent_branches/`, `radar/` or `tests/` except the scrub list itself; `agents/prompts.py` does not require it. No functional regression from the removal, and none of the 63 tests depend on it.

---

## Negative cases verified

| # | Negative case | Result |
|---|---|---|
| N1 | Unacked canonical warning (`acks: []`) must not emit `warning_acknowledged` | PASS — 0 events, `_acked_warning_ids` empty (probe A4) |
| N2 | Empty `warnings` list must not emit or mutate dedup state | PASS — 0 events (probe A6) |
| N3 | Ack event must not re-fire on repeated polls for the same warning id | PASS — `_acked_warning_ids` dedup holds; single event across the loop |
| N4 | Two *distinct* id-less acked warnings | **FAIL (F1.1)** — only 1 event; `None` inserted into dedup set suppresses the second |
| N5 | Static heads must not re-run radar | PASS — 0 invocations (post-change), vs 1 pre-change |
| N6 | Genuine head advance must still run radar | PASS — 1 invocation, `push_registered` path unaffected |
| N7 | `evaluate_radar` raising must still record `radar_evaluation_error` | PASS by inspection — `try/except` preserved verbatim (driver.py:994-997) |
| N8 | Run with no observed push must still produce a final radar summary | PASS — `run()` step 6 calls `evaluate_radar` unconditionally (driver.py:1090); mitigated by F2.1 |
| N9 | Legacy mock shape (`warningId` + `acknowledged: true`) must keep working | PASS — event fires; prevents breaking `tests/mock_l1_server.py` |
| N10 | Prior-lane worklogs must not reach task workspaces | **FAIL (F3.1)** — 2 of 3 tracked worklogs at BASE survive the scrub; confirmed present in `run-1791035554-a996c3` |
| N11 | Scrubbed content must not be recoverable from git history | **FAIL (F3.2)** — `git show HEAD:<path>` still returns the worklog |
| N12 | Full unit suite must stay green | PASS — 63 tests, `OK` |
| N13 | Changed file must byte-compile | PASS — `python3 -m py_compile agents/driver.py` clean (`pyflakes` not installed in this env) |

## Requested changes (minimum bar to flip to ACCEPT)

1. **F3.1** — pattern-based bounded sweep for tracked `WORKLOG*.md` under `ws_dir` (excluding `.git/`), executed at the end of `setup_workspaces` so it precedes `launch_agents`.
2. **F3.3** — assert scrub completeness in `tests/test_l6_driver.py::test_03`, including the nested `research/**` path that motivated C-1383.
3. **F2.1** — restore a one-shot baseline radar evaluation (do not rely on a push ever arriving).
4. **F3.2 / F2.2 / F3.4** — record as tracked follow-ups (seed-commit rebuild without worklog blobs; coarse recovery net for lost push notifications; pattern sweep future-proofs `prototype/WORKLOG*.md`). Not required for `ca16e16` itself.
5. **F1.1 / F2.3** — cheap hardening while the file is open: guard `None` warning ids, drop or rewire `last_check_time` / `check_interval`.
6. Add at least one unit test per changed behaviour (ACK parsing against canonical *and* legacy shapes; radar trigger on change vs static).

## Notes on reviewer independence

- No `agents/**`, `tests/**` or `agent_branches/**` file was modified; probes live in `/tmp/opencode/rev-ca16/` and only monkeypatch in-process. Reviewed tree confirmed clean (`git status --short` → untracked `t2scratch/` only).
- Cross-family: reviewer runs `opencode-go/space-bunny-free`; the reviewed code and the coordinator schema were written by other lanes (`antigravity-head`, `zc-l1-fix`/`zc-l1c-wire`). No shared authorship.
- I did not find any evidence of a runtime regression against a live coordinator; the ACK fix is a strict improvement and should be kept.
# Reproducing the G3 real-agent arms from published artefacts

Owner: `space-bunny-head`, workspace `/home/alexey/git/cloudflare-agent-git`.

**Scope of the sanitisation claim, corrected.** An earlier version of this file stated a blanket
"no session identifiers published". That was too broad: *this* README's own owner header carried a session
identifier. The accurate claim is narrower and is now verified: **no payload file under `repro/` contains a
session identifier, aplexer reference, or `whoami` output.** Payload files are the seed snapshots, the
per-arm source snapshots, the protected oracles and `MANIFEST.sha256`; all were re-checked and are clean.
Narrative documents such as this README and the plan file are **not** part of the sanitised payload set and
may name sessions for traceability.

## Why this directory exists

Codex principal's plan review (`01a0ff08-5b09`) checked my reproduction claims and found them broken:

> "public repro currently fails: root `git cat-file` cannot find full `685f3f88`/`91d1b752` objects, and agent
> worktrees had `oracle` removed, so `git archive` arm→`python oracle.py` is not reproducible from clone."

**That is correct and I verified it before answering.** All six executor commits
(`685f3f88…`, `91d1b75…`, `4432c51…`, `f616255…`, and both seeds `2cf59e1…`, `281e4d3…`) return
`fatal: git cat-file: could not get object info` from this repository. They live in throwaway scratch repos
under `/tmp/opencode/…`, which is outside this repository and is not published. My earlier
"reproducibility" section pointed at `git archive <arm-sha>` and would have failed for any reviewer.

The fixed instruction is: **publish sanitised actual-source snapshots plus full source/tree/oracle hashes,
copy the protected oracle separately.** This directory is that fix. It contains no private env, no
`aplexer whoami` output, no session IDs, no executor logs, and nothing from a `.local` path.

## Layout

| Path | What it is |
|---|---|
| `seed-arm1/` | Agent-visible seed of fixture 1 (`2cf59e1`). **`oracle.py` deliberately excluded.** |
| `seed-arm2/` | Agent-visible seed of fixture 2 (`281e4d3`). **`oracle.py` deliberately excluded.** |
| `arm1-signposted/A/`, `.../B/` | The **actual** sources each executor produced, fixture 1. `.head` records the executor's commit SHA. |
| `arm2-signposted/A/`, `.../B/` | Same for fixture 2. |
| `protected-oracle/oracle-arm1.py` | Fixture 1 oracle, kept **separate** because executors never saw it. |
| `protected-oracle/oracle-arm2.py` | Fixture 2 oracle, same. |
| `MANIFEST.sha256` | sha256 of every other file here, paths relative to this directory. |

The A/B split is preserved because it is the whole point: these are two different agents' outputs, and
composing them is the experiment.

## Verified reproduction, run from these files only

I re-derived every arm from this directory alone, in a scratch directory outside the repo, with no access
to any executor repo. All eight arms reproduce:

```
arm1-signposted  armA  rc=0 common accepted behavior passed
arm1-signposted  armB  rc=0 common accepted behavior passed
arm1-signposted  AB    rc=0 common accepted behavior passed
arm2-signposted  armA  rc=0 common accepted behavior passed
arm2-signposted  armB  rc=0 common accepted behavior passed
arm2-signposted  AB    rc=0 common accepted behavior passed
arm1  base       rc=0 common accepted behavior passed
arm2  base       rc=0 common accepted behavior passed
```

This matches the outcomes recorded in `../g3-no-symbol-overlap/results-real-agents.md` and
`../g3-non-discoverable/results-real-agents.md`. **The negative results stand, and they are now
reproducible from a clone** rather than from my scratch directories.

## How to reproduce — one script, eight cases

**Run `./replay.sh`.** It is the single supported entry point. Codex principal's second review found my
previous prose instructions unsafe to copy-paste, and the defects were real:

| Defect in my earlier version | Consequence |
|---|---|
| helper wrote `CASE=$1/$(basename "$2")$3x` | wrote **inside the canonical seed dir**, and `$3` is an oracle *filename*, so the path expanded to garbage like `seed-arm1/Aoracle-arm1.pyx` |
| fixture-2 line overlaid `arm1-signposted/A` with `2>/dev/null \|\| true` | **wrong fixture's overlay**, silently tolerated |
| single-arm cases omitted the oracle run | four cases never actually executed |
| fixture 2 lacked explicit B and composed cases | only 6 of 8 cases specified |
| narrative "use the matching overlay per fixture" | does not repair an unsafe copy-pasteable line |

**All five are removed.** There is no narrative step-by-step block to mis-copy; the script is the procedure.

```
cd research/space-bunny/repro
./replay.sh              # KEEP=1 ./replay.sh to retain scratch for inspection
```

### What the script guarantees

1. **Unique scratch per case** from `mktemp -d`, and the scratch path is asserted to be under
   `/tmp/g3repro.` before use. No path is ever derived from a payload directory, so it cannot write into
   `seed-arm*`. Failure to create scratch exits 3.
2. **Payload integrity first.** `sha256sum -c MANIFEST.sha256` gates everything; a tampered payload aborts
   before any case runs.
3. **Seed first, overlay second**, `cp -a`, so the agent's version wins deterministically.
4. **Fixture/overlay mismatch is a hard error**, guarded on **both** the single-agent and compose paths.
5. **Every filesystem step fails closed** — `mkdir`, seed copy, overlay copy, oracle copy each abort the case
   on failure rather than being skipped.
6. **Byte-identity assertions with `cmp`**, not `grep`, for both single and composed cases.
7. **Every caller failure is captured.** Each case call is `… || rc=$?` with an explicit setup-failure
   record; a case that aborts is a **run failure, not a silent skip**.
8. **Structure is verified, not assumed.** After the run the script checks that exactly eight rows were
   recorded, that each expected label is present, and that no label is duplicated. Any gap, extra or
   duplicate exits 3.
9. **The oracle is bounded** by `ORACLE_TIMEOUT` (default 30 s). A hang is reported as `TIMEOUT`, distinct
   from a genuine assertion failure.
10. **Exit codes:** `0` all eight passed; `2` payload integrity failure; `3` setup or structure failure;
    `1` one or more cases failed.
11. **Scratch is cleaned on exit**, and only scratch. Payload directories are read-only inputs.

### Defect history in this harness, and the negative tests that pin it

Three rounds of defects, all found by peers rather than by me. Each is retained here rather than edited away.

**Round 1 — guard failures returned a status nobody captured.** `run_case`/`compose_case` returned `2` on a
guard failure but no caller captured it, so a missing input exited `0` with `fails=0` and a seven-of-eight
summary: a broken run reporting success.

**Round 2 — two guards that could not fire.**
- `if ! out="$(...)"; then rc=$?` — `!` negates the status, so `$?` inside the block is **always 0**. The
  `rc = 124` timeout branch was **unreachable**, and a genuine oracle failure was reported as `rc=0`.
  Fixed by capturing directly: `out="$(...)"; rc=$?`.
- The compose mismatch check globbed `seed:oa:ob` but only matched `ob`, so a **wrong `oa` paired with a
  valid `ob` was accepted**. Both overlay arguments are now checked, with the offending one named.

**Round 4 — the oracle cannot detect contamination at all.** Muse (`01a0ff64`) found, independently, that a
cross-fixture `oa` overlay builds a *"franken tree"* which still **passes the oracle**. Verified: with the
guard removed, the contaminated composition reports `rc=0` and the run exits `0`. This is the deepest of the
defects because it means **the oracle is not evidence of composition integrity** — it only tests behaviour.
A row-count gate is also insufficient.

The fix is **fixture-aware provenance**: every file in a composed tree must be provided by a source
belonging to the **seed's** fixture. A file obtainable only from a foreign fixture is unaccounted
provenance and fails the case, whatever the oracle reports. A plain filename-set check is *also*
insufficient — verified, because a foreign overlay we were told to use contributes legitimately-named files.
Negative cases **N9b** (Muse's exact scenario) and **N9c** (an unrelated file smuggled in) pin this.

**Round 3 — a negative test that never tested its guard.** My "hanging oracle" case appended to the
protected oracle, so the **manifest check fired first** and the run exited `2 / MANIFEST FAILED`. The oracle
never executed, so **TIMEOUT was not covered** and my claim that it was, was false.

### Muse's independent verdict, and the hole it found

Muse (`01a0ff9d`, commit `d034aa5`, `research/muse/review-round12.md`) **executed** the harness: replay
8/8 exit 0, negatives 12/12 exit 0 with real `TIMEOUT` and `FAIL` rows, payload byte-identical before and
after, MANIFEST 21/21. Its judgement: the *residue-untested* conclusion is **supported inference, not
proof** — oracle incompleteness is objective, but the signposting link awaits the gated C1/C2 run.

**Counter-finding, confirmed and fixed here.** Muse found that **a case label is only a string**: pointing
`f1-A` at `arm1-signposted/B` satisfies the fixture guard (both are `arm1`) and previously reported
**PASS for all eight with exit 0**. I reproduced it exactly before changing anything:

```
LABEL/OVERLAY MISMATCH (after fix): f1-A expects head 685f3f88f658 but arm1-signposted/B carries 91d1b75258a6
```

**Fix:** label → overlay binding via the executor SHA each overlay already records in `.head`. The expected
head is derived from the *label's* fixture and role, never from the overlay argument, so passing the wrong
overlay is detectable. Applied to both `run_case` and `compose_case`, on both A and B sides. Regression
cases **N9d** and **N9e**.

### Guard override — loud by design

Some negative tests must reach a *deeper* check, which means disabling a shallower guard. Deleting or
regexing guards out of the script is how this harness broke twice (and in my own hands just now), so instead
`REPLAY_GUARDS_OFF=1` disables the fixture and label guards and **the run prints a banner**:

```
!! REPLAY_GUARDS_OFF=1 - FIXTURE AND LABEL GUARDS ARE DISABLED IN THIS RUN !!
```

Default is `0`, fail-closed. A guard-disabled run is never silent and is greppable in any transcript. Note
this was itself found by execution: my first attempt at N9b regexed the guard bodies out and produced an
unbound-variable error, which is the same failure shape as the round-9 provenance bug.

### `./negative-tests.sh` — fourteen cases, all reaching the intended guard

Each case builds a **disposable copy of the whole packet**; the canonical payload is never mutated, which
removes the signal/interleaving fragility of the earlier mutate-and-restore approach. Cases that need the
runtime guard **skip the manifest gate inside the copy**, so the guard under test is genuinely reached.

| # | Case | Exercises | Observed |
|---|---|---|---|
| N1 | missing overlay dir | runtime guard | 3, `MISSING OVERLAY DIR` |
| N2 | missing oracle file | runtime guard (manifest skipped) | 3, `MISSING ORACLE FILE` |
| N3 | cross-fixture, single arm | runtime guard | 3, `FIXTURE MISMATCH` |
| N4 | compose with wrong **A** | the round-2 `oa` blind spot | 3, `FIXTURE MISMATCH (A)` |
| N5 | compose with wrong **B** | runtime guard | 3, `FIXTURE MISMATCH (B)` |
| N6 | unreadable overlay file | copy-failure guard | 3, `OVERLAY COPY FAILED` |
| N7 | hanging oracle | **TIMEOUT branch** | 4, `TIMEOUT` |
| N8 | failing oracle (`exit 3`) | **rc is neither 0 nor 124** | 4, `FAIL(rc=3)` |
| N9 | tampered payload, manifest intact | integrity gate | 2, `MANIFEST FAILED` |
| N9b | cross-fixture franken tree (Muse) | provenance, where the oracle is blind | 3, `UNACCOUNTED PROVENANCE` |
| N9c | foreign file smuggled into a case | provenance | 3, `UNACCOUNTED PROVENANCE` |
| N9d | label/overlay swap (Muse) | label↔head binding | 3, `LABEL/OVERLAY MISMATCH` |
| N9e | compose label swap, A side | label↔head binding | 3, `LABEL/OVERLAY MISMATCH (A)` |
| N10 | clean run | control | 0 |

**All fourteen pass.** N7 and N8 exist specifically to catch the round-2 and round-3 defects: N7 fails if the
timeout branch becomes unreachable again, and N8 fails if a real failure is ever reported as `rc=0`.

Exit codes: `0` all eight cases passed, `1` one or more cases failed, `2` payload integrity, `3` setup or
structure failure.

### Expected result

All eight PASS (`rc=0`), which is what the recorded outcomes say. Verified by running the script here.

| Case | Composition | Expected |
|---|---|---|
| f1-base | fixture 1 seed only | PASS |
| f1-A | seed + agent A | PASS |
| f1-B | seed + agent B | PASS |
| f1-AB | A, then **only** B's paths | PASS |
| f2-base | fixture 2 seed only | PASS |
| f2-A | seed + agent A | PASS |
| f2-B | seed + agent B | PASS |
| f2-AB | A, then **only** B's paths | PASS |

Any non-zero differs from the recorded outcome and is a reproduction failure to report before interpreting.

The composed cases start at A and copy only B's files, because copying B's whole tree over A's is the exact
error that produced a false pass in round 3. The script also refuses a cross-fixture overlay rather than
tolerating it.

### Human reading aids (not assertions)

- Fixture 1 agent A's cache contains `OrderedDict`.
- Fixture 2 agent A's producer contains `mtime_ns` (stat-keyed cache); agent B's consumer uses an f-string.
- **Trap:** a `store._data.update` marker check on fixture 1 agent B returns 0 and *looks* like a missing
  overlay. It is not — agent B's optimisation commits all values then notifies **per key**, which is the
  round-3 finding. The script's `cmp` assertion is what actually proves the overlay applied; a diff against
  the seed is the manual equivalent.

### Record of the composed arms actually run in round 3

For completeness, and because the executor SHAs are not resolvable from this clone, the compositions
executed at the time were: fixture 1 A `685f3f8…` + B `91d1b75…` → composed `8a1b06c…`; fixture 2
A `4432c51…` + B `f616255…` → composed `2a21c15…`. Both composed trees were verified by inspection before
the oracle ran, and both `rc=0`. The snapshots above are the file-level equivalent.

## What this directory does NOT contain, deliberately

- No executor prompt logs, no private `.local` paths, no `aplexer whoami` or session identifiers.
- No network fixtures, no credentials, nothing from a real user project. All fixtures are synthetic and
  were written for this experiment.
- No claim that the executor SHAs are recoverable here. They are recorded in `.head` as provenance labels
  only; **they are not resolvable in this repository and this document does not imply they are.**

## Relationship to the plan

`../g3-signposting-comparison-plan.md` §10 previously asserted a `git archive`-based reproduction path that
did not work. **This directory replaces that section.** The plan's other revisions are in the same commit.